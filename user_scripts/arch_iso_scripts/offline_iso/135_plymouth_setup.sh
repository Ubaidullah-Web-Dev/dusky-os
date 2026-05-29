#!/usr/bin/env bash
# Arch Linux (EFI + Btrfs root) | Dusky Minimalist Boot & LUKS Setup
# FORENSICALLY AUDITED (SYSTEMD-BOOT / PLYMOUTH API COMPLIANT)
# PALETTE: Pure Black (Background), Cornsilk (Logo), Olive Leaf (Logs)

set -Eeuo pipefail
export LC_ALL=C

# --- Configuration ---
readonly THEME_NAME="dusky"
readonly THEME_DIR="/usr/share/plymouth/themes/${THEME_NAME}"
readonly MKINITCPIO_CONF="/etc/mkinitcpio.conf.d/10-arch-btrfs-luks.conf"

# --- Helpers ---
fatal() { printf '\033[1;31m[FATAL]\033[0m %s\n' "$1" >&2; exit 1; }
info() { printf '\033[1;32m[INFO]\033[0m %s\n' "$1"; }
warn() { printf '\033[1;33m[WARN]\033[0m %s\n' "$1" >&2; }

require_cmd() {
    command -v "$1" >/dev/null 2>&1 || fatal "Required command not found: $1"
}

# --- Pre-flight Checks ---
if (( EUID != 0 )); then
    fatal "Deployment halted: Root privileges are strictly required."
fi

info "Validating base dependencies..."
require_cmd pacman
require_cmd sed
require_cmd grep
require_cmd base64

# --- Execution ---
info "Ensuring Plymouth is installed..."
if ! pacman -Q plymouth >/dev/null 2>&1; then
    if ! pacman -S --needed --noconfirm plymouth; then
        fatal "The installation of 'plymouth' failed. Ensure it is in your pacstrap payload."
    fi
fi

require_cmd plymouth-set-default-theme

info "Deploying custom minimal theme: $THEME_NAME..."
mkdir -p "$THEME_DIR"

# Generate a pure 1x1 white pixel dynamically (Bypasses missing initramfs font glyphs)
info "Generating mathematical pixel asset..."
echo "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/wcAAwAB/4O0lQAAAABJRU5ErkJggg==" | base64 -d > "${THEME_DIR}/pixel.png"

# Generate .plymouth configuration
cat << EOF > "${THEME_DIR}/${THEME_NAME}.plymouth"
[Plymouth Theme]
Name=Dusky Minimal
Description=Pure typographic LUKS prompt with geometric primitives.
ModuleName=script

[script]
ImageDir=${THEME_DIR}
ScriptFile=${THEME_DIR}/${THEME_NAME}.script
ConsoleLogBackgroundColor=0x000000
MonospaceFont=Cantarell 11
Font=Cantarell 11
EOF

# Generate .script file (The core visual logic)
cat << 'EOF' > "${THEME_DIR}/${THEME_NAME}.script"
# --- Pure Black Background (Maximum Contrast) ---
Window.SetBackgroundTopColor(0.0, 0.0, 0.0);
Window.SetBackgroundBottomColor(0.0, 0.0, 0.0);

global.pixel_image = Image("pixel.png");

# --- Logo & Animation Engine (Cornsilk text: #fefae0) ---
global.logo_image = Image.Text("dusky", 0.9961, 0.9804, 0.8784, 1.0, "Cantarell 36");
global.logo_sprite = Sprite(global.logo_image);
global.logo_sprite.SetPosition(
    Window.GetWidth() / 2 - global.logo_image.GetWidth() / 2,
    Window.GetHeight() / 2 - global.logo_image.GetHeight() / 2,
    10 # Z-Index
);

global.animation_time = 0.0;
global.password_dialog_active = 0;

fun refresh_callback () {
    if (global.password_dialog_active == 0) {
        global.animation_time += 0.025;
        # Subtle breathing effect mapped to opacity (0.7 to 1.0)
        opacity = 0.85 + (0.15 * Math.Sin(global.animation_time * 2.0));
        global.logo_sprite.SetOpacity(opacity);
    } else {
        global.logo_sprite.SetOpacity(1.0);
    }
}
Plymouth.SetRefreshFunction(refresh_callback);

# --- Minimal Progress Line (3 pixels tall) ---
global.progress_sprite = Sprite();
global.dialog_y = global.logo_sprite.GetY() + global.logo_image.GetHeight() + 45;
global.progress_sprite.SetPosition(0, global.dialog_y, 10);
global.progress_sprite.SetOpacity(0);

fun progress_callback (duration, progress) {
    if (global.password_dialog_active == 1) {
        global.progress_sprite.SetOpacity(0);
        return;
    }
    
    max_width = Window.GetWidth() * 0.3;
    bar_width = Math.Int(max_width * progress);
    if (bar_width < 1) bar_width = 1;
    
    # Scale base64 pixel to a 3px tall line, opacity 0.8
    scaled_bar = global.pixel_image.Scale(bar_width, 3);
    global.progress_sprite.SetImage(scaled_bar);
    global.progress_sprite.SetX(Window.GetWidth() / 2 - bar_width / 2);
    global.progress_sprite.SetOpacity(0.8);
}
Plymouth.SetBootProgressFunction(progress_callback);

# --- LUKS Password Prompt ---
global.prompt_sprite = Sprite();
global.prompt_sprite.SetPosition(Window.GetWidth() / 2, global.dialog_y, 20);
global.prompt_sprite.SetOpacity(0);

global.bullets = [];

fun display_normal_callback () {
    global.password_dialog_active = 0;
    global.prompt_sprite.SetOpacity(0);
    for (index = 0; global.bullets[index]; index++) {
        global.bullets[index].SetOpacity(0);
    }
}

fun display_password_callback (prompt_text, bullet_count) {
    global.password_dialog_active = 1;
    global.progress_sprite.SetOpacity(0);
    
    # Render prompt text (Cornsilk slightly muted via alpha channel)
    prompt_image = Image.Text(prompt_text, 0.9961, 0.9804, 0.8784, 0.8, "Cantarell 12");
    global.prompt_sprite.SetImage(prompt_image);
    global.prompt_sprite.SetX(Window.GetWidth() / 2 - prompt_image.GetWidth() / 2);
    global.prompt_sprite.SetOpacity(1);
    
    # Render Geometric Bullets (6x6 squares to avoid font glyph issues)
    bullet_size = 6;
    bullet_spacing = 10;
    total_width = bullet_count * bullet_size + (bullet_count - 1) * bullet_spacing;
    start_x = Window.GetWidth() / 2 - total_width / 2;
    bullet_y = global.prompt_sprite.GetY() + prompt_image.GetHeight() + 20;
    
    # Clear old bullets
    for (index = 0; global.bullets[index]; index++) {
        global.bullets[index].SetOpacity(0);
    }
    
    # Draw new bullets
    for (index = 0; index < bullet_count; index++) {
        if (!global.bullets[index]) {
            global.bullets[index] = Sprite(global.pixel_image.Scale(bullet_size, bullet_size));
        }
        global.bullets[index].SetPosition(start_x + index * (bullet_size + bullet_spacing), bullet_y, 20);
        global.bullets[index].SetOpacity(0.9);
    }
}
Plymouth.SetDisplayNormalFunction(display_normal_callback);
Plymouth.SetDisplayPasswordFunction(display_password_callback);

# --- Systemd Message Broadcasting (Olive Leaf: #606c38) ---
global.message_sprite = Sprite();
global.message_sprite.SetPosition(Window.GetWidth() / 2, Window.GetHeight() * 0.85, 5);

fun display_message_callback (text) {
    my_image = Image.Text(text, 0.3765, 0.4235, 0.2196, 1.0, "Cantarell 10");
    global.message_sprite.SetImage(my_image);
    global.message_sprite.SetX(Window.GetWidth() / 2 - my_image.GetWidth() / 2);
    global.message_sprite.SetOpacity(1);
}

fun hide_message_callback (text) {
    global.message_sprite.SetOpacity(0);
}

Plymouth.SetMessageFunction(display_message_callback);
Plymouth.SetHideMessageFunction(hide_message_callback);
Plymouth.SetUpdateStatusFunction(display_message_callback);

fun quit_callback () { global.logo_sprite.SetOpacity(1); }
Plymouth.SetQuitFunction(quit_callback);
EOF

chmod 0644 "${THEME_DIR}"/*

info "Patching mkinitcpio drop-in config to inject plymouth hook..."
if [[ -f "$MKINITCPIO_CONF" ]]; then
    if ! grep -q "^[^#]*HOOKS=.*plymouth" "$MKINITCPIO_CONF"; then
        sed -i --follow-symlinks -E 's/^([^#]*HOOKS=\([^)]*systemd)([[:space:]]*)/\1 plymouth /' "$MKINITCPIO_CONF"
        info "Injected modern plymouth hook into $MKINITCPIO_CONF"
    else
        info "plymouth hook already present."
    fi
else
    if grep -q "^[^#]*HOOKS=.*systemd" /etc/mkinitcpio.conf && ! grep -q "^[^#]*HOOKS=.*plymouth" /etc/mkinitcpio.conf; then
         sed -i -E 's/^([^#]*HOOKS=\([^)]*systemd)([[:space:]]*)/\1 plymouth /' /etc/mkinitcpio.conf
         info "Injected modern plymouth hook into /etc/mkinitcpio.conf"
    fi
fi

info "Setting default theme to ${THEME_NAME}..."
# Removed the -R flag to prevent premature initramfs generation
plymouth-set-default-theme "$THEME_NAME"

info "Dusky Plymouth deployment complete. (Initramfs rebuild intentionally deferred)."
