#!/usr/bin/env bash
# =============================================================================
# Elite Arch Linux ZRAM Configurator
# Target: Arch Linux Cutting-Edge (Kernel 7.0+, Bash 5.3+, systemd 260+)
# Scope: Platinum Grade. Maximum Memory Efficiency via pure ZRAM & Tmpfs.
# =============================================================================

set -euo pipefail

readonly SCRIPT_NAME="${0##*/}"
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

log_critical_action() {
    printf '\n'
    printf '%s======================================================================%s\n' "${C_RED}${C_BOLD}" "${C_RESET}"
    printf '%s [!] ACTION REQUIRED: BOOTLOADER MODIFIED [!]%s\n' "${C_RED}${C_BOLD}" "${C_RESET}"
    printf '%s======================================================================%s\n' "${C_RED}${C_BOLD}" "${C_RESET}"
    printf '%s You MUST regenerate your initramfs/UKI before your next reboot.%s\n' "${C_YELLOW}" "${C_RESET}"
    printf '%s Failure to do so will result in ZSWAP remaining active on boot.%s\n' "${C_YELLOW}" "${C_RESET}"
    printf '\n'
    printf '%s Run this command at the very end of your setup:%s\n' "${C_GREEN}" "${C_RESET}"
    printf '   %smkinitcpio -P%s\n' "${C_BOLD}" "${C_RESET}"
    printf '%s======================================================================%s\n' "${C_RED}${C_BOLD}" "${C_RESET}"
    printf '\n'
}

# --- Privilege Escalation ---
if [[ $EUID -ne 0 ]]; then
    log_info "Root privileges required. Escalating..."
    command -v sudo >/dev/null 2>&1 || die "sudo is required to run this script as root."
    exec sudo -- bash -- "$SELF_PATH" "$@"
fi

# --- Dependency Checks ---
for cmd in systemctl systemd-escape findmnt grep sed; do
    command -v "$cmd" >/dev/null 2>&1 || die "'$cmd' is required but missing."
done

readonly CMDLINE_FILE="/etc/kernel/cmdline"
readonly CONFIG_DIR="/etc/systemd/zram-generator.conf.d"
readonly CONFIG_FILE="${CONFIG_DIR}/99-elite-zram.conf"
readonly MOUNT_POINT="/mnt/zram1"

readonly ZRAM_SWAP_DEV="/dev/zram0"
readonly ZRAM_SIZE_EXPR="ram"
readonly COMPRESSION_ALGORITHM="zstd"

readonly GENERATOR_BIN="/usr/lib/systemd/system-generators/zram-generator"
readonly SWAP_SETUP_UNIT="systemd-zram-setup@zram0.service"
readonly SWAP_UNIT="dev-zram0.swap"
readonly MOUNT_UNIT_NAME="$(systemd-escape --path --suffix=mount "$MOUNT_POINT")"
readonly MOUNT_UNIT_PATH="/etc/systemd/system/${MOUNT_UNIT_NAME}"

tmp_config="$(umask 077 && mktemp)"
tmp_mount="$(umask 077 && mktemp)"
trap 'rm -f "$tmp_config" "$tmp_mount"' EXIT

mount_source_exact() {
    findmnt -rn -o SOURCE --mountpoint "$MOUNT_POINT" 2>/dev/null || true
}

unit_is_loaded() {
    [[ "$(systemctl show -p LoadState --value "$1" 2>/dev/null || true)" == "loaded" ]]
}

assert_unit_loaded() {
    local unit=$1
    unit_is_loaded "$unit" || die "Expected generated unit is not loaded after daemon-reload: $unit"
}

if systemd-detect-virt --quiet --container; then
    log_warn "Container detected. zram-generator does nothing inside containers; skipping."
    exit 0
fi

# =============================================================================
# --- 1. ZSWAP ANNIHILATION ---
# =============================================================================

log_info "Verifying ZSWAP status..."

readonly ZSWAP_PARAM="/sys/module/zswap/parameters/enabled"
if [[ -w "$ZSWAP_PARAM" ]]; then
    current_zswap=$(<"$ZSWAP_PARAM")
    if [[ "$current_zswap" == "Y" || "$current_zswap" == "1" ]]; then
        log_info "Live patching: Disabling zswap in the running kernel..."
        echo 0 > "$ZSWAP_PARAM" || log_warn "Failed to live-disable zswap."
    else
        log_success "Live memory: ZSWAP is cleanly disabled."
    fi
else
    log_warn "Zswap parameter not found. Kernel might not have zswap compiled in."
fi

if [[ -f "$CMDLINE_FILE" ]]; then
    declare -i needs_cmdline_update=0
    
    if grep -q -E '(^|[[:space:]])zswap\.enabled=0([[:space:]]|$)' "$CMDLINE_FILE"; then
        log_success "Bootloader: zswap.enabled=0 is perfectly configured."
    else
        log_info "Bootloader: Patching $CMDLINE_FILE to enforce zswap.enabled=0..."
        sed -i -E 's/[[:space:]]*zswap\.enabled=[^[:space:]]*//g' "$CMDLINE_FILE"
        sed -i -E 's/[[:space:]]+$//' "$CMDLINE_FILE"
        sed -i -E 's/$/ zswap.enabled=0/' "$CMDLINE_FILE"
        needs_cmdline_update=1
    fi

    if (( needs_cmdline_update == 1 )); then
        log_success "Bootloader cmdline successfully patched."
        log_critical_action
    fi
else
    log_warn "$CMDLINE_FILE not found. If using GRUB, manually add 'zswap.enabled=0'."
fi

# =============================================================================
# --- 2. ZRAM & TMPFS CONFIGURATION ---
# =============================================================================

if [[ ! -x "$GENERATOR_BIN" ]]; then
    log_warn "zram-generator is missing. Auto-healing..."
    while [[ -f /var/lib/pacman/db.lck ]]; do
        log_warn "Pacman is currently locked. Waiting 3 seconds..."
        sleep 3
    done
    pacman -Sy --needed --noconfirm zram-generator || die "Auto-healing failed."
    log_success "zram-generator successfully bootstrapped."
fi

if grep -Eq '(^|[[:space:]])systemd\.zram=0([[:space:]]|$)' /proc/cmdline; then
    die "FATAL: Kernel cmdline explicitly disables zram device creation."
fi

install -d -m 0755 -- "$CONFIG_DIR"
install -d -m 0755 -- "$MOUNT_POINT"
log_info "Directories prepared."

cat > "$tmp_config" <<EOF
# Managed by Elite Arch Linux ZRAM Configurator.
[zram0]
zram-size = ${ZRAM_SIZE_EXPR}
compression-algorithm = ${COMPRESSION_ALGORITHM}
swap-priority = 100
options = discard
EOF

cat > "$tmp_mount" <<EOF
# Managed by Elite Arch Linux ZRAM Configurator
# Scope: High-Performance Tmpfs back-end for Wayland/Scripts.
[Unit]
Description=High-Performance tmpfs (ZRAM-backed) for ${MOUNT_POINT}
Before=local-fs.target
ConditionPathExists=${MOUNT_POINT}

[Mount]
What=tmpfs
Where=${MOUNT_POINT}
Type=tmpfs
Options=rw,nosuid,nodev,relatime,size=100%,mode=1777

[Install]
WantedBy=local-fs.target
EOF

install -Dm0644 "$tmp_config" "$CONFIG_FILE"
log_success "ZRAM pool configuration written to ${CONFIG_FILE}"

install -Dm0644 "$tmp_mount" "$MOUNT_UNIT_PATH"
log_success "Tmpfs mount unit written to ${MOUNT_UNIT_PATH}"

log_info "Reloading systemd daemon to ingest new architecture..."
systemctl daemon-reload

assert_unit_loaded "$SWAP_SETUP_UNIT"
assert_unit_loaded "$SWAP_UNIT"
assert_unit_loaded "$MOUNT_UNIT_NAME"

systemctl enable "$MOUNT_UNIT_NAME" >/dev/null 2>&1 || true

current_source="$(mount_source_exact)"
if [[ $current_source == "/dev/zram1" || $current_source == "zram1" ]]; then
    log_warn "$MOUNT_POINT is currently mounted via legacy ext2 ZRAM block."
    log_warn "The new tmpfs architecture will seamlessly take over upon reboot."
else
    # Attempt live mount if it's purely unmounted right now
    systemctl start "$MOUNT_UNIT_NAME" >/dev/null 2>&1 || true
    if [[ "$(mount_source_exact)" == "tmpfs" ]]; then
        log_success "Live memory: tmpfs successfully attached to ${MOUNT_POINT}."
    fi
fi

if systemctl is-active --quiet "$SWAP_UNIT"; then
    log_info "$SWAP_UNIT is currently active."
fi

log_success "Platinum ZRAM & Tmpfs architecture installed safely."
log_info "Reboot the system to apply the new memory topology natively."

exit 0
