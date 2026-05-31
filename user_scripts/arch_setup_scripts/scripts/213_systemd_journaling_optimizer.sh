#!/usr/bin/env bash
# =============================================================================
# Elite Arch Linux systemd-journald Optimizer
# Target: Arch Linux Cutting-Edge (systemd 260+, Bash 5.3+)
# Scope: Platinum Grade. Hard-caps logging memory to prevent silent RAM bloat.
# Priority: Caps tmpfs RAM waste at 50MB, eliminates legacy CPU overhead, 
#           and shields SSDs via IO batching and rate limiting.
# =============================================================================

set -euo pipefail

readonly SCRIPT_NAME="${0##*/}"
readonly SELF_PATH="$(realpath -e -- "${BASH_SOURCE[0]}")"

readonly CONFIG_DIR="/etc/systemd/journald.conf.d"
readonly CONFIG_FILE="${CONFIG_DIR}/99-ram-optimization.conf"

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

  --dry-run, -n        Print the generated systemd drop-ins and exit
  --help, -h           Show this help menu
EOF
}

usage_error() { log_error "$1"; print_help >&2; exit 2; }

# --- 1. CLI Parsing ---
declare -i DRY_RUN=0

while [[ $# -gt 0 ]]; do
    case "$1" in
        --dry-run|-n)        DRY_RUN=1; shift ;;
        --help|-h)           print_help; exit 0 ;;
        *)                   log_warn "Ignoring unknown argument: $1"; shift ;;
    esac
done

# --- 2. Privilege Escalation ---
if [[ $EUID -ne 0 && $DRY_RUN -eq 0 ]]; then
    log_info "Root privileges required. Escalating..."
    command -v sudo >/dev/null 2>&1 || die "'sudo' is not available."
    exec sudo -- /usr/bin/bash "$SELF_PATH" "$@"
fi

log_info "Initializing Platinum systemd-journald Optimizer..."

# --- 3. Temp File Generation ---
tmp_config="$(umask 077 && mktemp)"
trap 'rm -f "$tmp_config"' EXIT

# Generate strictly bounded Journal limits
cat > "$tmp_config" <<EOF
# Managed by ${SCRIPT_NAME}
# Scope: Prevent systemd-journald from consuming massive amounts of RAM, Disk, and CPU.

[Journal]
# --- STORAGE LIMITS ---
# Volatile Storage (RAM in /run/log/journal): Hard cap at 50MB.
# Prevents the default behavior of eating up to 10% of total system RAM.
RuntimeMaxUse=50M

# Persistent Storage (Disk in /var/log/journal): Hard cap at 250MB.
# Prevents logs from silently bloating your SSD over time.
SystemMaxUse=250M

# Rotate files frequently to keep read times instantaneous.
SystemMaxFileSize=50M

# Housekeeping: Automatically discard anything older than 1 month.
MaxRetentionSec=1month

# --- PERFORMANCE & CPU SHIELDS ---
# Compression: Force zstd compression on log payloads before writing.
Compress=yes

# SSD Wear & Latency Shield: Batch disk writes every 5 minutes instead of continuously.
SyncIntervalSec=5m

# CPU/IO Shield: Disable kernel audit logging. Bypasses rate limits and spikes CPU.
Audit=no

# Verbosity Cap: Drop debug-level spam before it consumes RAM.
MaxLevelStore=info

# Anti-Crash Loop Spam: Drop logs if a crashing app writes >100 lines in 10s.
RateLimitIntervalSec=10s
RateLimitBurst=100

# CPU Optimization: Disable legacy broadcast logging to save idle CPU cycles.
ForwardToSyslog=no
ForwardToWall=no
ForwardToKMsg=no
ForwardToConsole=no
EOF

# --- 4. Dry Run Check ---
if (( DRY_RUN == 1 )); then
    log_info "DRY RUN EXECUTED. Would generate the following configuration:"
    echo -e "\n${C_BOLD}[ ${CONFIG_FILE} ]${C_RESET}"
    cat "$tmp_config"
    exit 0
fi

# --- 5. Atomic Installation ---
install -d -m 0755 "$CONFIG_DIR"

if [[ -f "$CONFIG_FILE" ]] && cmp -s "$tmp_config" "$CONFIG_FILE"; then
    log_success "No changes required. systemd-journald is already strictly capped."
else
    install -Dm0644 "$tmp_config" "$CONFIG_FILE"
    log_success "Updated ${CONFIG_FILE}"
    
    log_info "Restarting systemd-journald to apply memory caps..."
    if systemctl restart systemd-journald.service; then
        log_success "systemd-journald successfully restarted. RAM limits active."
    else
        log_warn "Failed to seamlessly restart systemd-journald. Changes will apply on next reboot."
    fi
fi

# --- 6. Live Vacuuming ---
log_info "Vacuuming current journals to enforce new limits immediately..."
# This forces journald to instantly drop any logs exceeding our new rules, freeing RAM right now.
journalctl --vacuum-size=250M >/dev/null 2>&1 || true
journalctl --vacuum-time=1months >/dev/null 2>&1 || true

log_success "Logging topology is fully optimized for maximum RAM efficiency and SSD protection."

exit 0
