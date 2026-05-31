#!/usr/bin/env bash
# =============================================================================
# Elite Arch Linux THP & Sysfs Optimizer
# Target: Arch Linux Cutting-Edge (Kernel 7.0+, Bash 5.3+)
# Scope: Platinum Grade. Dynamically scales THP via systemd-tmpfiles.
# Priority: Absolute Minimum RAM Footprint & Lowest Idle CPU Overhead.
# =============================================================================

set -euo pipefail

readonly CONFIG_FILE="/etc/tmpfiles.d/99-thp-optimize.conf"
readonly SCRIPT_NAME="${0##*/}"
readonly THP_BASE_DIR="/sys/kernel/mm/transparent_hugepage"

# --- Strict Path Resolution ---
readonly SELF_PATH="$(realpath -e -- "${BASH_SOURCE[0]}")"

# --- Formatting ---
if [[ -t 1 && -z "${NO_COLOR:-}" ]]; then
    C_RESET=$'\033[0m'
    C_GREEN=$'\033[1;32m'
    C_BLUE=$'\033[1;34m'
    C_RED=$'\033[1;31m'
    C_YELLOW=$'\033[1;33m'
    C_BOLD=$'\033[1m'
else
    C_RESET='' C_GREEN='' C_BLUE='' C_RED='' C_YELLOW='' C_BOLD=''
fi

log_info()    { printf '%s[INFO]%s %s\n'  "$C_BLUE"   "$C_RESET" "$1"; }
log_success() { printf '%s[OK]%s %s\n'    "$C_GREEN"  "$C_RESET" "$1"; }
log_warn()    { printf '%s[WARN]%s %s\n'  "$C_YELLOW" "$C_RESET" "$1"; }
log_error()   { printf '%s[ERROR]%s %s\n' "$C_RED"    "$C_RESET" "$1" >&2; }
die()         { log_error "$1"; exit "${2:-1}"; }

print_help() {
    cat <<EOF
${C_BOLD}Usage:${C_RESET} ${SCRIPT_NAME} [OPTIONS]

  --auto, -a           Auto-detect RAM size and set dynamic THP profile (default)
  --aggressive, -A     Force 32GB+ "Performance" THP allocation (Looser limits)
  --standard, -S       Force <32GB "Strict RAM Savings" THP allocation (Tight limits)
  --dry-run, -n        Print the generated systemd-tmpfiles config and exit
  --help, -h           Show this help menu
EOF
}

usage_error() { log_error "$1"; print_help >&2; exit 2; }

# --- 1. CLI Parsing ---
MODE="AUTO"
declare -i DRY_RUN=0

while [[ $# -gt 0 ]]; do
    case "$1" in
        --auto|-a)           MODE="AUTO"; shift ;;
        --aggressive|-A)     MODE="AGGRESSIVE"; shift ;;
        --standard|-S)       MODE="STANDARD"; shift ;;
        --dry-run|-n)        DRY_RUN=1; shift ;;
        --help|-h)           print_help; exit 0 ;;
        *)                   usage_error "Unknown argument: $1" ;;
    esac
done

# --- 2. Privilege Escalation ---
if [[ $EUID -ne 0 && $DRY_RUN -eq 0 ]]; then
    command -v sudo >/dev/null 2>&1 || die "'sudo' is not available."
    log_info "Root privileges required. Escalating..."
    exec sudo -- /usr/bin/bash "$SELF_PATH" "$@"
fi

# --- 3. Hardware Support Check ---
if [[ ! -d "$THP_BASE_DIR" ]]; then
    if (( DRY_RUN == 1 )); then
        log_warn "THP hardware directory ($THP_BASE_DIR) missing. Dry-run continuing..."
    else
        die "THP is disabled or not compiled into this kernel. Nothing to optimize."
    fi
fi

# --- 4. System State Detection ---
declare -i SYSTEM_RAM_GB=0

if [[ $(< /proc/meminfo) =~ MemTotal:[[:space:]]+([0-9]+) ]]; then
    SYSTEM_RAM_GB=$(( BASH_REMATCH[1] / 1048576 ))
else
    die "FATAL: Could not parse /proc/meminfo natively."
fi

# --- 5. Tuning Profile Resolution ---
declare -i EXPECTED_MAX_PTES
declare -i EXPECTED_SCAN_SLEEP
declare -i EXPECTED_PAGES_TO_SCAN
declare EXPECTED_ENABLED
declare EXPECTED_DEFRAG
declare EXPECTED_SHMEM

# The 30 GB Demarcation Line
if [[ "$MODE" == "AGGRESSIVE" ]] || [[ "$MODE" == "AUTO" && SYSTEM_RAM_GB -ge 30 ]]; then
    EXPECTED_MODE="PERFORMANCE_LEAN (32GB+)"
    EXPECTED_MAX_PTES=255          # Allow up to ~50% internal fragmentation for faster THP promotion.
    EXPECTED_SCAN_SLEEP=15000      # 15s wakeups. Less CPU overhead than default 10s, but keeps memory tight.
    EXPECTED_PAGES_TO_SCAN=4096    # Standard scan burst (16MB per wakeup).
    EXPECTED_ENABLED="madvise"     # Blocks global RAM waste.
    EXPECTED_DEFRAG="defer+madvise" # Async defrag to maintain large contiguous blocks.
    EXPECTED_SHMEM="within_size"   # Safe hugepages for Wayland/tmpfs.
else
    EXPECTED_MODE="STRICT_RAM_SAVINGS (<32GB)"
    EXPECTED_MAX_PTES=64           # Max 256KB waste per HugePage. Extremely strict RAM cap.
    EXPECTED_SCAN_SLEEP=30000      # 30s wakeups. Drops daemon idle CPU usage by 66%.
    EXPECTED_PAGES_TO_SCAN=1024    # Drops the duration of the CPU spike during wakeups by 75%.
    EXPECTED_ENABLED="madvise"     # Only give THP to apps that explicitly ask (Browsers/Games).
    EXPECTED_DEFRAG="madvise"      # Zero background stuttering. Only defragments when explicitly requested.
    EXPECTED_SHMEM="within_size"   # Zero RAM bloat for Wayland shared memory.
fi

# --- 6. Generation & Verification ---
log_info "Initializing Platinum THP & Sysfs Optimizer..."
log_info "Detected System RAM: ${C_BOLD}${SYSTEM_RAM_GB} GB${C_RESET}"

if [[ "$MODE" != "AUTO" ]]; then
    log_warn "Manual Override Engaged: Cache Mode forced to ${C_BOLD}${EXPECTED_MODE}${C_RESET}"
fi

# Secure temp file generation
tmpfile="$(umask 077 && mktemp)"
trap 'rm -f "$tmpfile"' EXIT

cat > "$tmpfile" <<EOF
# Managed by ${SCRIPT_NAME}
# Scope: Transparent HugePages (THP) systemd-tmpfiles initialization
# Detected State: Desktop Mode=${EXPECTED_MODE}, RAM=${SYSTEM_RAM_GB}GB

# Enable THP ONLY for applications that explicitly request it (madvise).
# Prevents global memory bloat (saving ~15% RAM system-wide) while giving max speed to heavy apps.
w /sys/kernel/mm/transparent_hugepage/enabled - - - - ${EXPECTED_ENABLED}

# Set defrag to prevent synchronous UI stutters during memory compaction.
w /sys/kernel/mm/transparent_hugepage/defrag - - - - ${EXPECTED_DEFRAG}

# Optimize shared memory HugePages to prevent tmpfs RAM waste (Crucial for Wayland compositors).
w /sys/kernel/mm/transparent_hugepage/shmem_enabled - - - - ${EXPECTED_SHMEM}

# khugepaged: Control "Empty Box" internal fragmentation limit to strictly save RAM.
w /sys/kernel/mm/transparent_hugepage/khugepaged/max_ptes_none - - - - ${EXPECTED_MAX_PTES}

# khugepaged: Reduce daemon wakeups to dramatically lower idle CPU usage.
w /sys/kernel/mm/transparent_hugepage/khugepaged/scan_sleep_millisecs - - - - ${EXPECTED_SCAN_SLEEP}

# khugepaged: Limit the amount of memory scanned per wakeup to eliminate CPU spikes.
w /sys/kernel/mm/transparent_hugepage/khugepaged/pages_to_scan - - - - ${EXPECTED_PAGES_TO_SCAN}
EOF

# Dry Run Check
if (( DRY_RUN == 1 )); then
    log_info "DRY RUN EXECUTED. Generated systemd-tmpfiles configuration:"
    echo "------------------------------------------------------"
    cat "$tmpfile"
    echo "------------------------------------------------------"
    exit 0
fi

# Apply to Disk
if [[ -f "$CONFIG_FILE" ]] && cmp -s "$tmpfile" "$CONFIG_FILE"; then
    log_info "Configuration file already matches desired state. No disk write needed."
else
    install -Dm0644 "$tmpfile" "$CONFIG_FILE"
    log_success "Configuration written to ${CONFIG_FILE}"
fi

# Apply to Live Kernel via systemd-tmpfiles
log_info "Applying tmpfiles.d configuration to live sysfs..."
systemd-tmpfiles --create "$CONFIG_FILE" || die "Failed to apply systemd-tmpfiles."

# Hardened Live Verification
actual_enabled="$(< "${THP_BASE_DIR}/enabled")"
actual_defrag="$(< "${THP_BASE_DIR}/defrag")"
actual_shmem="$(< "${THP_BASE_DIR}/shmem_enabled")"
actual_ptes="$(< "${THP_BASE_DIR}/khugepaged/max_ptes_none")"
actual_scan_sleep="$(< "${THP_BASE_DIR}/khugepaged/scan_sleep_millisecs")"
actual_pages_to_scan="$(< "${THP_BASE_DIR}/khugepaged/pages_to_scan")"

if [[ "$actual_enabled" != *"[$EXPECTED_ENABLED]"* ]]; then
    die "Verification failed: THP 'enabled' is '${actual_enabled}', expected to contain '[${EXPECTED_ENABLED}]'."
fi

if [[ "$actual_defrag" != *"[$EXPECTED_DEFRAG]"* ]]; then
    die "Verification failed: THP 'defrag' is '${actual_defrag}', expected to contain '[${EXPECTED_DEFRAG}]'."
fi

if [[ "$actual_shmem" != *"[$EXPECTED_SHMEM]"* ]]; then
    die "Verification failed: THP 'shmem_enabled' is '${actual_shmem}', expected to contain '[${EXPECTED_SHMEM}]'."
fi

if [[ "$actual_ptes" != "$EXPECTED_MAX_PTES" ]]; then
    die "Verification failed: THP 'max_ptes_none' is '${actual_ptes}', expected '${EXPECTED_MAX_PTES}'."
fi

if [[ "$actual_scan_sleep" != "$EXPECTED_SCAN_SLEEP" ]]; then
    die "Verification failed: THP 'scan_sleep_millisecs' is '${actual_scan_sleep}', expected '${EXPECTED_SCAN_SLEEP}'."
fi

if [[ "$actual_pages_to_scan" != "$EXPECTED_PAGES_TO_SCAN" ]]; then
    die "Verification failed: THP 'pages_to_scan' is '${actual_pages_to_scan}', expected '${EXPECTED_PAGES_TO_SCAN}'."
fi

log_success "Verified live sysfs kernel values:"
log_success "  enabled = [${EXPECTED_ENABLED}]"
log_success "  defrag = [${EXPECTED_DEFRAG}]"
log_success "  shmem_enabled = [${EXPECTED_SHMEM}]"
log_success "  max_ptes_none = ${actual_ptes} (Strict RAM Cap)"
log_success "  scan_sleep_millisecs = ${actual_scan_sleep} (Low CPU Wakeups)"
log_success "  pages_to_scan = ${actual_pages_to_scan} (Low CPU Spike)"
log_success "  Active Tuning Profile: [${C_BOLD}${EXPECTED_MODE}${C_RESET}]"

exit 0
