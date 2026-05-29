#!/usr/bin/env bash
# Platinum Grade RAM Forensics for Arch Linux & Hyprland
# Auto-elevates, uses paru/yay for AUR dependencies safely, and maps exact memory allocations.

set -euo pipefail

# --- 1. PRIVILEGE ESCALATION ---
if [[ "$EUID" -ne 0 ]]; then
    echo -e "\e[1;33m[!] Elevated privileges required. Auto-elevating to root...\e[0m"
    exec sudo bash "$0" "$@"
fi

# --- 2. DEPENDENCY MANAGEMENT (AUR SAFE) ---
REQUIRED_PKGS=()
command -v smem >/dev/null 2>&1 || REQUIRED_PKGS+=("smem")
command -v zramctl >/dev/null 2>&1 || REQUIRED_PKGS+=("util-linux")
command -v slabtop >/dev/null 2>&1 || REQUIRED_PKGS+=("procps-ng")

if [[ ${#REQUIRED_PKGS[@]} -gt 0 ]]; then
    echo -e "\e[1;34m[*] Missing dependencies detected: ${REQUIRED_PKGS[*]}\e[0m"
    
    # AUR helpers strictly refuse to run as root. We must drop privileges to $SUDO_USER.
    if [[ -n "${SUDO_USER:-}" ]]; then
        if command -v paru >/dev/null 2>&1; then
            echo -e "\e[1;34m[*] Installing via paru as user '$SUDO_USER'...\e[0m"
            sudo -u "$SUDO_USER" paru -S --noconfirm --needed "${REQUIRED_PKGS[@]}"
        elif command -v yay >/dev/null 2>&1; then
            echo -e "\e[1;34m[*] Installing via yay as user '$SUDO_USER'...\e[0m"
            sudo -u "$SUDO_USER" yay -S --noconfirm --needed "${REQUIRED_PKGS[@]}"
        else
            echo -e "\e[1;31m[!] No AUR helper (paru/yay) found. Attempting pacman...\e[0m"
            pacman -S --noconfirm --needed "${REQUIRED_PKGS[@]}" || true
        fi
    else
        echo -e "\e[1;31m[!] Script run directly as root. Cannot safely use AUR helpers.\e[0m"
        echo -e "\e[1;33m[*] Attempting pacman fallback...\e[0m"
        pacman -S --noconfirm --needed "${REQUIRED_PKGS[@]}" || true
    fi

    # Safety check before proceeding
    if ! command -v smem >/dev/null 2>&1; then
        echo -e "\e[1;31m[!] CRITICAL: 'smem' failed to install. Please install it manually (paru -S smem).\e[0m"
        exit 1
    fi
fi

# --- 3. FORENSICS EXECUTION ---
REPORT="ram_forensics_report.txt"
echo -e "\e[1;32m[*] Commencing Deep Kernel RAM Analysis...\e[0m"
echo -e "========================================================================="

# Function to safely extract memory values in kB (defaults to 0 if missing)
get_mem() {
    local val
    val=$(awk -v key="$1" '$1 == key ":" {print $2}' /proc/meminfo)
    echo "${val:-0}"
}

# Run diagnostics and use 'tee' to simultaneously print to terminal and save to file
{
    echo "========================================================================="
    echo "                  PLATINUM SYSTEM RAM FORENSICS REPORT                   "
    echo " Date: $(date)"
    echo " Kernel: $(uname -r)"
    echo "========================================================================="

    echo -e "\n[1] THE TRUE MEMORY MATH (Kernel 7.x Breakdown)"
    echo "-------------------------------------------------------------------------"
    MEM_TOTAL=$(get_mem MemTotal)
    MEM_FREE=$(get_mem MemFree)
    MEM_AVAIL=$(get_mem MemAvailable)
    BUFFERS=$(get_mem Buffers)
    CACHED=$(get_mem Cached)
    SHMEM=$(get_mem Shmem)
    SLAB=$(get_mem Slab)
    PAGE_TABLES=$(get_mem PageTables)
    ANON_PAGES=$(get_mem AnonPages)

    # Convert to MB
    USED_ROUGH=$(( (MEM_TOTAL - MEM_FREE - BUFFERS - CACHED - SHMEM) / 1024 ))
    USERSPACE_MB=$(( ANON_PAGES / 1024 ))
    KERNEL_MB=$(( (SLAB + PAGE_TABLES) / 1024 ))
    SHMEM_MB=$(( SHMEM / 1024 ))
    
    # Calculate Unaccounted / Hardware memory
    UNACCOUNTED_MB=$(( USED_ROUGH - USERSPACE_MB - KERNEL_MB ))

    echo "Total Usable RAM: $((MEM_TOTAL / 1024)) MB"
    echo "Truly Available RAM (Free + Reclaimable): $((MEM_AVAIL / 1024)) MB"
    echo ""
    echo "--- EXACT ALLOCATION SPREAD ---"
    printf "%-40s %6s MB\n" "1. Userspace Apps (AnonPages):" "$USERSPACE_MB"
    printf "%-40s %6s MB\n" "2. Shared Memory / IPC (Shmem/Tmpfs):" "$SHMEM_MB"
    printf "%-40s %6s MB\n" "3. Kernel Structures (Slab+PageTbls):" "$KERNEL_MB"
    printf "%-40s %6s MB\n" "4. Unaccounted / Hardware / DMA:" "$UNACCOUNTED_MB"
    echo ""
    echo "DIAGNOSTIC RULE: If 'Unaccounted' > 150MB, GPU drivers / Aquamarine buffers are holding RAM."

    echo -e "\n[2] COMPRESSED RAM (ZRAM / ZSWAP) ANALYSIS"
    echo "-------------------------------------------------------------------------"
    if zramctl --raw >/dev/null 2>&1; then
        zramctl --output NAME,ALGORITHM,DISKSIZE,DATA,COMPR,TOTAL || true
        echo "-> 'TOTAL' is the physical RAM actively consumed by your compressed swap."
    else
        echo "ZRAM is not active or configured."
    fi

    echo -e "\n[3] TRUE PROCESS ISOLATION (Top 15 PSS Processes)"
    echo "-------------------------------------------------------------------------"
    # -k (KB/MB), -r (reverse sort), -p (percentages), -c (columns). || true prevents pipefail crashes.
    smem -t -k -r -p -c "pid user command uss pss rss" | head -n 16 || true
    echo "-> PSS is the mathematically fair share of RAM a process consumes (ignoring shared double-counts)."

    echo -e "\n[4] SHARED MEMORY / TMPFS (Wayland/IPC Vectors)"
    echo "-------------------------------------------------------------------------"
    df -h -t tmpfs | awk 'NR==1 || ($3 != "0" && $3 != "0K") {print $0}' || true
    echo "-> This memory sits physically in RAM. Unclosed Wayland surfaces/sockets accumulate here."

    echo -e "\n[5] KERNEL SLAB LEAK DETECTION (Top 10 Caches)"
    echo "-------------------------------------------------------------------------"
    slabtop -o -s c | head -n 17 || true
    echo "-> If ext4_inode_cache or a specific driver is massive, the kernel cache allocator is holding your RAM."

    echo -e "\n[6] WAYLAND / AQUAMARINE GRAPHICS BUFFERS (DMA-BUF)"
    echo "-------------------------------------------------------------------------"
    MOUNTED_DEBUGFS=false
    if ! mountpoint -q /sys/kernel/debug; then
        mount -t debugfs none /sys/kernel/debug
        MOUNTED_DEBUGFS=true
    fi

    if [[ -f /sys/kernel/debug/dma_buf/bufinfo ]]; then
        # Extract and display the most relevant lines to save space
        grep -E "^size|^attached|^Total" /sys/kernel/debug/dma_buf/bufinfo | head -n 25 || true
    else
        echo "DMA-BUF trace unavailable (Kernel lockdown=integrity or debugfs missing)."
    fi

    if [[ "$MOUNTED_DEBUGFS" == true ]]; then
        umount /sys/kernel/debug
    fi
    echo "-> These are raw GPU buffers backed by system RAM (completely invisible to standard task managers)."

} | tee "$REPORT"

echo -e "\n\e[1;32m[✓] Forensic pass complete. Full report mapped and saved to: $REPORT\e[0m"
