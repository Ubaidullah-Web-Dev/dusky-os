#!/usr/bin/env bash
# ==============================================================================
# Arch Linux: Zero-Touch Wayland SSO Master Configuration (Platinum Revision)
# Target: Hyprland 0.55.2+, UWSM, Greetd, Tuigreet, GNOME Keyring, Udiskie
# Kernel: 7.0.11+ | Systemd: 260+ | Bash: 5.3.9+
# ==============================================================================

set -euo pipefail

# --- 1. Privilege and Environment Validation ---
if [[ "${EUID}" -ne 0 ]]; then
    echo "CRITICAL: This script requires root privileges. Elevating..."
    exec sudo "$0" "$@"
fi

# Accurately identify the human user invoking the script
REAL_USER="${SUDO_USER:-}"
if [[ -z "$REAL_USER" ]] || [[ "$REAL_USER" == "root" ]]; then
    # Fallback: Find the first standard user (UID 1000-59999)
    REAL_USER=$(awk -F: '$3 >= 1000 && $3 < 60000 {print $1; exit}' /etc/passwd)
fi

if [[ -z "$REAL_USER" ]]; then
    echo "FATAL: Could not determine a valid non-root user. Aborting."
    exit 1
fi

USER_HOME=$(getent passwd "$REAL_USER" | cut -d: -f6)
echo "Targeting user configuration for: $REAL_USER"

# --- 2. Core Dependency Enforcement ---
echo "Verifying core Wayland and SSO dependencies..."
pacman -S --needed --noconfirm greetd greetd-tuigreet uwsm udiskie libsecret

# --- 3. Advanced Root Encryption Detection ---
# Correctly strips BTRFS subvolume strings (e.g., [/subvol]) from findmnt 
# output to prevent lsblk parsing fatalities in modern Arch topologies.
is_root_encrypted() {
    local root_dev raw_dev
    root_dev=$(findmnt -n -o SOURCE /) || return 1
    raw_dev=$(echo "$root_dev" | cut -d'[' -f1)
    lsblk -s -no TYPE "$raw_dev" 2>/dev/null | grep -q "^crypt$"
}

# --- 4. Safely Compile AUR PAM Module (LUKS-encrypted root only) ---
if is_root_encrypted; then
    echo "LUKS root detected. Resolving 'pam-fde-boot-pw-git'..."
    
    if ! pacman -Qq pam-fde-boot-pw-git &>/dev/null; then
        echo "Installing build dependencies (base-devel, meson, ninja, git)..."
        pacman -S --needed --noconfirm base-devel git meson ninja

        BUILD_DIR="${USER_HOME}/.cache/aur-build-pam"
        rm -rf "$BUILD_DIR" # Guarantee idempotency on subsequent runs
        mkdir -p "$BUILD_DIR"
        chown "$REAL_USER:$REAL_USER" "$BUILD_DIR"
        
        # Demote privileges purely to compile the source code in an isolated directory
        echo "Compiling pam-fde-boot-pw-git as unprivileged user: $REAL_USER..."
        sudo -u "$REAL_USER" bash -c "
            cd '$BUILD_DIR' && \
            git clone https://aur.archlinux.org/pam-fde-boot-pw-git.git . && \
            makepkg -sc --noconfirm
        "
            
        # Retain root elevation to force the installation of the resulting artifact
        echo "Installing compiled artifact..."
        pacman -U --noconfirm "$BUILD_DIR"/*.pkg.tar.zst
        rm -rf "$BUILD_DIR"
    else
        echo "pam-fde-boot-pw-git is already installed."
    fi
else
    echo "Root partition is unencrypted; skipping pam-fde-boot-pw deployment."
fi

# --- 5. Architecting UWSM & Tuigreet ---
echo "Deploying Greetd, Tuigreet, and UWSM Wrappers..."

# Abstraction wrapper to bypass Tuigreet's double-dash delimiter logic 
# and lack of shell expansion for complex arguments.
mkdir -p /usr/local/bin
cat > /usr/local/bin/wayland-session << 'EOF'
#!/usr/bin/env bash
exec uwsm start -- hyprland.desktop
EOF
chmod 0755 /usr/local/bin/wayland-session

# Create Tuigreet cache directory explicitly to prevent graphical looping
mkdir -p /var/cache/tuigreet
# Only chown if the greeter user actually exists (standard if greetd is installed)
if getent passwd greeter >/dev/null; then
    chown greeter:greeter /var/cache/tuigreet
fi
chmod 0755 /var/cache/tuigreet

mkdir -p /etc/greetd
cat > /etc/greetd/config.toml << EOF
[terminal]
vt = 1

[default_session]
# Launch Tuigreet using the abstracted UWSM executable
command = "tuigreet --time --remember --remember-session --cmd /usr/local/bin/wayland-session"
user = "greeter"

[initial_session]
# This directive enables the autologin bypass, skipping the PAM Auth phase
command = "/usr/local/bin/wayland-session"
user = "$REAL_USER"
EOF

if getent passwd greeter >/dev/null; then
    chown -R greeter:greeter /etc/greetd
fi

# --- 6. The Platinum PAM Stack ---
echo "Configuring PAM stack for automated Keyring decryption..."
# Silence the backup in case greetd was freshly installed and the PAM file is missing
cp /etc/pam.d/greetd "/etc/pam.d/greetd.bak.$(date +%s)" 2>/dev/null || true

if is_root_encrypted; then
    # Full SSO stack: Extracts kernel cache and sequentially injects it into the GNOME Keyring
    cat > /etc/pam.d/greetd << 'EOF'
#%PAM-1.0
auth       required     pam_securetty.so
auth       requisite    pam_nologin.so
auth       include      system-local-login
auth       optional     pam_gnome_keyring.so
account    include      system-local-login
password   include      system-local-login

# --- SESSION PHASE ---
session    include      system-local-login
session    optional     pam_fde_boot_pw.so inject_for=gkr
session    optional     pam_gnome_keyring.so auto_start
EOF
else
    # Fallback stack without LUKS injection capabilities
    cat > /etc/pam.d/greetd << 'EOF'
#%PAM-1.0
auth       required     pam_securetty.so
auth       requisite    pam_nologin.so
auth       include      system-local-login
auth       optional     pam_gnome_keyring.so
account    include      system-local-login
password   include      system-local-login

# --- SESSION PHASE ---
session    include      system-local-login
session    optional     pam_gnome_keyring.so auto_start
EOF
fi

# --- 7. Systemd Service Overrides ---
echo "Applying Systemd overrides for Kernel Keyring inheritance..."
mkdir -p /etc/systemd/system/greetd.service.d
# Forcing 'inherit' ensures Greetd can access the root session keyring
# before the 60-second systemd cache destruction timer fires.
cat > /etc/systemd/system/greetd.service.d/keyringmode.conf << 'EOF'
[Service]
KeyringMode=inherit
EOF

# --- 8. Automating Udiskie for External Drives ---
echo "Writing udiskie YAML configuration..."
mkdir -p "${USER_HOME}/.config/udiskie"
cat > "${USER_HOME}/.config/udiskie/config.yml" << 'EOF'
program_options:
  # Query the active GNOME Keyring via secret-tool for silent unlocks,
  # bypassing the hardcoded graphical popup mechanism.
  password_prompt: ["secret-tool", "lookup", "uuid", "{id_uuid}"]
  automount: true
  notify: true
  tray: auto
EOF
chown -R "$REAL_USER":"$REAL_USER" "${USER_HOME}/.config/udiskie"

# --- 9. Service Enablement ---
echo "Enabling boot services..."
# Safely enable the display manager using native systemd headless detection
if systemd-detect-virt -q --chroot; then
    echo "Chroot environment detected. Forcing service enablement..."
    systemctl enable greetd.service --force
else
    systemctl daemon-reload
    systemctl enable greetd.service
fi

echo "====================================================================="
echo " Deployment Complete! You are fully configured for Wayland SSO.      "
echo "====================================================================="
