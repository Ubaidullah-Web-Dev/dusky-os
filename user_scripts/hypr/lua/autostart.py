#!/usr/bin/env python3
"""
===============================================================================
DUSKY TUI: AUTOSTART CONFIGURATION SCHEMA
===============================================================================
"""

from python.frontend.core_types import ConfigItem

# =============================================================================
# 1. CORE APPLICATION ROUTING
# =============================================================================
ENGINE_TYPE = "lua"                        
TARGET_FILE = "~/.config/hypr/edit_here/source/autostart.lua"   
APP_TITLE = "Dusky Autostart & Actions"          

# =============================================================================
# 2. UI & ENVIRONMENT BEHAVIOR
# =============================================================================
DEFAULT_MODE = "auto"                      
THEME_FILE = "~/.config/matugen/generated/dusky_tui.json" 

# =============================================================================
# 3. TABS DEFINITION
# =============================================================================
TABS = [
    "1. Display Server & Essentials",
    "2. Background Services & UI",
    "3. Diagnostics & Hacks"
]

# =============================================================================
# 4. SCHEMA DEFINITION
# =============================================================================
SCHEMA = {
    # -------------------------------------------------------------------------
    # TAB 0: DISPLAY SERVER & ESSENTIALS
    # -------------------------------------------------------------------------
    0: [
        ConfigItem(
            label="Enable XWayland",
            key="enabled",
            scope="xwayland",       # UID = "xwayland.enabled"
            type_="bool",
            default=False,
            group="Display Server",
            extended_help="**XWayland Configuration**\n\nDisabling XWayland saves 20-30 MBs of RAM, but it will prevent legacy X11 applications from working."
        ),
        ConfigItem(
            label="Start Gnome Keyring (Secrets)",
            key="action_gnome_keyring",
            scope="DEFAULT",        # UID = "action_gnome_keyring"
            type_="action",
            default="uwsm-app -- /usr/bin/gnome-keyring-daemon --start --components=secrets",
            group="System Essentials",
            extended_help="**Gnome Keyring**\n\nStores passwords for apps like VSCode, Chrome, etc.\n\n*Note: It is recommended to enable the systemd service instead of auto-starting with exec-once.*"
        ),
        ConfigItem(
            label="Grant Display Root Access (XHost)",
            key="action_xhost",
            scope="DEFAULT",        # UID = "action_xhost"
            type_="action",
            default="uwsm-app -- xhost +si:localuser:root",
            group="System Essentials",
            extended_help="**XHost Access**\n\nGrants root access to the display, which is required for GUI applications like GParted or Synaptic to run.\n\n*Requires `xorg-xhost` to be installed.*"
        ),
    ],

    # -------------------------------------------------------------------------
    # TAB 1: BACKGROUND SERVICES & UI
    # -------------------------------------------------------------------------
    1: [
        ConfigItem(
            label="Launch Wallpaper Engine",
            key="action_awww_daemon",
            scope="DEFAULT",
            type_="action",
            default="uwsm-app -- awww-daemon",
            group="Background Services"
        ),
        ConfigItem(
            label="Launch Idle Manager",
            key="action_hypridle",
            scope="DEFAULT",
            type_="action",
            default="uwsm-app -- hypridle",
            group="Background Services",
            extended_help="**Hypridle**\n\nManages screen dimming, lock screen initialization, and DPMS behavior on idle."
        ),
        ConfigItem(
            label="Launch Waybar",
            key="action_waybar_autostart",
            scope="DEFAULT",
            type_="action",
            default="uwsm-app -- $HOME/user_scripts/waybar/waybar_autostart.sh",
            group="User Interface"
        ),
        ConfigItem(
            label="Launch Network Applet",
            key="action_nmapplet",
            scope="DEFAULT",
            type_="action",
            default="uwsm-app -- nm-applet",
            group="User Interface"
        ),
        
        # --- CLIPBOARD MANAGER NESTED MENU ---
        ConfigItem(
            label="Clipboard Manager Services",
            key="menu_clipboard_id", 
            scope="DEFAULT",         # UID = "menu_clipboard_id"
            type_="menu",          
            default=None,
            is_parent=True,           
            expanded=False,           
            group="Clipboard"
        ),
        ConfigItem(
            label="Start Text Clipboard",
            key="action_cliphist_text",
            scope="DEFAULT",
            type_="action",
            default="uwsm-app -- wl-paste --type text --watch cliphist store",
            parent_ref="menu_clipboard_id"
        ),
        ConfigItem(
            label="Start Image Clipboard",
            key="action_cliphist_image",
            scope="DEFAULT",
            type_="action",
            default="uwsm-app -- wl-paste --type image --watch cliphist store",
            parent_ref="menu_clipboard_id"
        ),
        ConfigItem(
            label="Start Clipboard Persist",
            key="action_clip_persist",
            scope="DEFAULT",
            type_="action",
            default="uwsm-app -- wl-clip-persist --clipboard regular",
            parent_ref="menu_clipboard_id"
        ),
    ],

    # -------------------------------------------------------------------------
    # TAB 2: DIAGNOSTICS & HACKS
    # -------------------------------------------------------------------------
    2: [
        ConfigItem(
            label="Fix Slow App Launch (Env Import)",
            key="action_systemd_env", 
            scope="DEFAULT",          
            type_="action",
            default="systemctl --user import-environment $(env | cut -d'=' -f 1)",
            group="System Hacks",
            extended_help="**Systemd Variables Fix**\n\nImports current environment variables to systemd to prevent exceptionally slow GUI application launch times."
        ),
        ConfigItem(
            label="Update DBUS Activation Environment",
            key="action_dbus_update", 
            scope="DEFAULT",          
            type_="action",
            default="dbus-update-activation-environment --systemd --all",
            group="System Hacks"
        ),
        
        # --- DUSKY GLANCE NESTED MENU ---
        ConfigItem(
            label="Dusky Glance Tools",
            key="menu_dusky_glance_id",
            scope="DEFAULT",          # UID = "menu_dusky_glance_id"
            type_="menu",
            default=None,
            is_parent=True,
            expanded=True,
            group="Diagnostics"
        ),
        ConfigItem(
            label="Check CPU Usage",
            key="action_glance_cpu",
            scope="DEFAULT",
            type_="action",
            default="~/user_scripts/rofi/dusky_glance.sh --cpu",
            parent_ref="menu_dusky_glance_id"
        ),
        ConfigItem(
            label="Check RAM Usage",
            key="action_glance_ram",
            scope="DEFAULT",
            type_="action",
            default="~/user_scripts/rofi/dusky_glance.sh --ram",
            parent_ref="menu_dusky_glance_id"
        ),
        ConfigItem(
            label="Check System Temp",
            key="action_glance_temp",
            scope="DEFAULT",
            type_="action",
            default="~/user_scripts/rofi/dusky_glance.sh --temp",
            parent_ref="menu_dusky_glance_id"
        ),
        ConfigItem(
            label="Check Battery Status",
            key="action_glance_battery",
            scope="DEFAULT",
            type_="action",
            default="~/user_scripts/rofi/dusky_glance.sh --battery",
            parent_ref="menu_dusky_glance_id"
        ),
        ConfigItem(
            label="Check Network",
            key="action_glance_network",
            scope="DEFAULT",
            type_="action",
            default="~/user_scripts/rofi/dusky_glance.sh --network",
            parent_ref="menu_dusky_glance_id"
        ),
        ConfigItem(
            label="Check System Uptime",
            key="action_glance_uptime",
            scope="DEFAULT",
            type_="action",
            default="~/user_scripts/rofi/dusky_glance.sh --uptime",
            parent_ref="menu_dusky_glance_id"
        ),
        ConfigItem(
            label="Check Workspace Details",
            key="action_glance_workspace",
            scope="DEFAULT",
            type_="action",
            default="~/user_scripts/rofi/dusky_glance.sh --workspace",
            parent_ref="menu_dusky_glance_id"
        ),
        ConfigItem(
            label="Check System Clock",
            key="action_glance_clock",
            scope="DEFAULT",
            type_="action",
            default="~/user_scripts/rofi/dusky_glance.sh --clock",
            parent_ref="menu_dusky_glance_id"
        ),
    ]
}
