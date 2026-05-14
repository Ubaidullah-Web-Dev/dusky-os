#!/usr/bin/env python3
"""
DUSKY TUI: MASTER CONFIGURATION SCHEMA
Auto-generated Schema for Hyprland Input & Cursor configuration.
"""

from python.frontend.core_types import ConfigItem

# =============================================================================
# 1. CORE APPLICATION ROUTING (REQUIRED)
# =============================================================================
ENGINE_TYPE = "lua"
TARGET_FILE = "~/.config/hypr/edit_here/source/input.lua"
APP_TITLE = "Input & Cursor Settings"

# =============================================================================
# 2. UI & ENVIRONMENT BEHAVIOR
# =============================================================================
DEFAULT_MODE = "auto"
THEME_FILE = "~/.config/matugen/generated/dusky_tui.json"

# =============================================================================
# 3. TABS DEFINITION
# =============================================================================
TABS = [
    "1. Keyboard & Typing",
    "2. Mouse & Touchpad",
    "3. Focus & Interaction",
    "4. Cursor & Hardware",
    "5. Profiles & Actions"
]

# =============================================================================
# 4. SCHEMA DEFINITION
# =============================================================================
SCHEMA = {
    # -------------------------------------------------------------------------
    # TAB 0: KEYBOARD & TYPING
    # -------------------------------------------------------------------------
    0: [
        ConfigItem(
            label="Keyboard Layout",
            key="kb_layout",
            scope="input",
            type_="string",
            default="us",
            group="Layout Settings",
            extended_help="**XKB Keymap Layout**\n\nSets the primary keyboard layout (e.g., 'us', 'gb', 'de')."
        ),
        ConfigItem(
            label="Keyboard Variant",
            key="kb_variant",
            scope="input",
            type_="string",
            default="",
            group="Layout Settings"
        ),
        ConfigItem(
            label="Keyboard Options",
            key="kb_options",
            scope="input",
            type_="string",
            default="",
            group="Layout Settings"
        ),
        ConfigItem(
            label="Enable Numlock on Startup",
            key="numlock_by_default",
            scope="input",
            type_="bool",
            default=False,
            group="Behavior"
        ),
        ConfigItem(
            label="Resolve Binds by Sym",
            key="resolve_binds_by_sym",
            scope="input",
            type_="bool",
            default=False,
            group="Behavior",
            extended_help="Determines how keybinds behave when multiple keyboard layouts are active."
        ),
        ConfigItem(
            label="Key Repeat Rate (repeats/sec)",
            key="repeat_rate",
            scope="input",
            type_="int",
            default=35,
            min_val=1,
            max_val=100,
            step=1,
            group="Repeat Settings"
        ),
        ConfigItem(
            label="Key Repeat Delay (ms)",
            key="repeat_delay",
            scope="input",
            type_="int",
            default=250,
            min_val=100,
            max_val=1000,
            step=10,
            group="Repeat Settings",
            extended_help="**Delay**\n\nDelay in milliseconds before key repeating starts when a key is held down."
        ),
        # Virtual Keyboard Nested Menu
        ConfigItem(
            label="Virtual Keyboard Options",
            key="menu_vkb",
            scope="DEFAULT",
            type_="menu",
            default=None,
            is_parent=True,
            group="Virtual Inputs"
        ),
        ConfigItem(
            label="Share Key States",
            key="share_states",
            scope="input/virtualkeyboard",
            type_="int",
            default=2,
            options=[0, 1, 2],
            parent_ref="menu_vkb",
            extended_help="Unify key states with other hardware keyboards."
        ),
        ConfigItem(
            label="Release Pressed on Close",
            key="release_pressed_on_close",
            scope="input/virtualkeyboard",
            type_="bool",
            default=False,
            parent_ref="menu_vkb",
            extended_help="Release all active keys when the virtual keyboard overlay is closed."
        ),
    ],

    # -------------------------------------------------------------------------
    # TAB 1: MOUSE & TOUCHPAD
    # -------------------------------------------------------------------------
    1: [
        ConfigItem(
            label="Pointer Sensitivity",
            key="sensitivity",
            scope="input",
            type_="float",
            default=0.0,
            min_val=-1.0,
            max_val=1.0,
            step=0.1,
            group="Mouse Core",
            extended_help="**Sensitivity**\n\nlibinput sensitivity, clamped from -1.0 to 1.0."
        ),
        ConfigItem(
            label="Acceleration Profile",
            key="accel_profile",
            scope="input",
            type_="cycle",
            default="adaptive",
            options=["adaptive", "flat", "custom"],
            group="Mouse Core"
        ),
        ConfigItem(
            label="Force No Acceleration (Raw Input)",
            key="force_no_accel",
            scope="input",
            type_="bool",
            default=False,
            group="Mouse Core",
            extended_help="Bypass all OS acceleration and read raw signal only (Ideal for gaming)."
        ),
        ConfigItem(
            label="Left Handed Mode",
            key="left_handed",
            scope="input",
            type_="bool",
            default=False,
            group="Mouse Core",
            extended_help="Swaps the Left Mouse Button (LMB) and Right Mouse Button (RMB)."
        ),
        ConfigItem(
            label="Scroll Method",
            key="scroll_method",
            scope="input",
            type_="cycle",
            default="2fg",
            options=["2fg", "edge", "on_button_down", "no_scroll"],
            group="Global Scrolling"
        ),
        ConfigItem(
            label="Natural Scroll",
            key="natural_scroll",
            scope="input",
            type_="bool",
            default=False,
            group="Global Scrolling",
            extended_help="Invert scroll direction so that content follows the finger (macOS style)."
        ),
        ConfigItem(
            label="Scroll Speed Multiplier",
            key="scroll_factor",
            scope="input",
            type_="float",
            default=1.0,
            min_val=0.1,
            max_val=5.0,
            step=0.1,
            group="Global Scrolling"
        ),
        ConfigItem(
            label="Emulate Discrete Scroll",
            key="emulate_discrete_scroll",
            scope="input",
            type_="int",
            default=1,
            options=[0, 1, 2],
            group="Global Scrolling",
            extended_help="Discretise high-resolution scroll events.\n\n0 = Off\n1 = Non-standard\n2 = All"
        ),
        
        # Touchpad Nested Menu
        ConfigItem(
            label="Touchpad Settings",
            key="menu_touchpad",
            scope="DEFAULT",
            type_="menu",
            default=None,
            is_parent=True,
            group="Touchpad Specific"
        ),
        ConfigItem(
            label="Disable While Typing",
            key="disable_while_typing",
            scope="input/touchpad",
            type_="bool",
            default=True,
            parent_ref="menu_touchpad"
        ),
        ConfigItem(
            label="Natural Scroll (Touchpad)",
            key="natural_scroll",
            scope="input/touchpad",
            type_="bool",
            default=True,
            parent_ref="menu_touchpad"
        ),
        ConfigItem(
            label="Tap to Click",
            key="tap_to_click",
            scope="input/touchpad",
            type_="bool",
            default=True,
            parent_ref="menu_touchpad"
        ),
        ConfigItem(
            label="Tap and Drag",
            key="tap_and_drag",
            scope="input/touchpad",
            type_="bool",
            default=True,
            parent_ref="menu_touchpad",
            extended_help="Enable tap-and-drag mode for trackpads."
        ),
        ConfigItem(
            label="Drag Lock Behavior",
            key="drag_lock",
            scope="input/touchpad",
            type_="int",
            default=0,
            options=[0, 1, 2],
            parent_ref="menu_touchpad",
            extended_help="Lift-and-continue drag:\n0 = Off\n1 = Timeout\n2 = Sticky"
        ),
        ConfigItem(
            label="Middle Button Emulation",
            key="middle_button_emulation",
            scope="input/touchpad",
            type_="bool",
            default=False,
            parent_ref="menu_touchpad",
            extended_help="Clicking LMB + RMB simultaneously equates to a middle click."
        ),
        ConfigItem(
            label="Three-Finger Drag",
            key="drag_3fg",
            scope="input/touchpad",
            type_="int",
            default=0,
            options=[0, 1, 2],
            parent_ref="menu_touchpad",
            extended_help="0 = Off\n1 = 3 Fingers\n2 = 4 Fingers"
        ),
    ],

    # -------------------------------------------------------------------------
    # TAB 2: FOCUS & INTERACTION
    # -------------------------------------------------------------------------
    2: [
        ConfigItem(
            label="Follow Mouse Focus",
            key="follow_mouse",
            scope="input",
            type_="int",
            default=1,
            options=[0, 1, 2, 3],
            group="Window Focus",
            extended_help="**Mouse Focus Model**\n\n0 = Disabled (Click to focus)\n1 = Full follow\n2 = Loose follow\n3 = Fully decoupled"
        ),
        ConfigItem(
            label="Refocus on Mouse Move",
            key="mouse_refocus",
            scope="input",
            type_="bool",
            default=True,
            group="Window Focus",
            extended_help="Forces the active window to change when the mouse moves over a new window (Requires follow_mouse=1)."
        ),
        ConfigItem(
            label="Focus on Close",
            key="focus_on_close",
            scope="input",
            type_="int",
            default=0,
            options=[0, 1, 2],
            group="Window Focus",
            extended_help="Behavior when the active window is closed:\n0 = Next in tree\n1 = Window under cursor\n2 = Most recently focused"
        ),
        ConfigItem(
            label="Tiled/Float Focus Override",
            key="float_switch_override_focus",
            scope="input",
            type_="int",
            default=1,
            options=[0, 1],
            group="Window Focus",
            extended_help="Focus the window under the cursor when transitioning between tiled and floating states."
        ),
        ConfigItem(
            label="Inactive Hit-box Shrink (px)",
            key="follow_mouse_shrink",
            scope="input",
            type_="int",
            default=0,
            min_val=0,
            max_val=50,
            step=1,
            group="Advanced Interaction"
        ),
        ConfigItem(
            label="Focus Change Threshold (px)",
            key="follow_mouse_threshold",
            scope="input",
            type_="float",
            default=0.0,
            min_val=0.0,
            max_val=100.0,
            step=1.0,
            group="Advanced Interaction",
            extended_help="Minimum distance the cursor must travel before changing window focus."
        ),
        ConfigItem(
            label="Off-Window Axis Events",
            key="off_window_axis_events",
            scope="input",
            type_="int",
            default=1,
            options=[0, 1, 2, 3],
            group="Advanced Interaction",
            extended_help="Axis events outside focused window:\n0 = Ignore\n1 = Out-of-bounds\n2 = Fake\n3 = Warp"
        ),
    ],

    # -------------------------------------------------------------------------
    # TAB 3: CURSOR & HARDWARE
    # -------------------------------------------------------------------------
    3: [
        ConfigItem(
            label="Cursor Visibility",
            key="invisible",
            scope="cursor",
            type_="bool",
            default=False,
            group="Appearance",
            extended_help="Hide the cursor entirely from the screen."
        ),
        ConfigItem(
            label="Inactive Hide Timeout (s)",
            key="inactive_timeout",
            scope="cursor",
            type_="float",
            default=0.0,
            min_val=0.0,
            max_val=120.0,
            step=1.0,
            group="Appearance",
            extended_help="Hide the cursor after this many seconds of being idle. Set to 0.0 to disable."
        ),
        ConfigItem(
            label="Hide on Key Press",
            key="hide_on_key_press",
            scope="cursor",
            type_="bool",
            default=False,
            group="Appearance"
        ),
        ConfigItem(
            label="Enable Hyprcursor Theme Support",
            key="enable_hyprcursor",
            scope="cursor",
            type_="bool",
            default=True,
            group="Appearance"
        ),
        ConfigItem(
            label="Cursor Zoom Factor",
            key="zoom_factor",
            scope="cursor",
            type_="float",
            default=1.0,
            min_val=1.0,
            max_val=10.0,
            step=0.1,
            group="Zoom Mechanics"
        ),
        ConfigItem(
            label="Rigid Zoom Tracking",
            key="zoom_rigid",
            scope="cursor",
            type_="bool",
            default=False,
            group="Zoom Mechanics",
            extended_help="Rigidly lock the viewport zoom to the exact center of the cursor, overriding loose camera follow."
        ),
        ConfigItem(
            label="Hardware Cursors Mode",
            key="no_hardware_cursors",
            scope="cursor",
            type_="int",
            default=2,
            options=[0, 1, 2],
            group="Hardware Integration",
            extended_help="**HW Cursor Mode**\n\n0 = Force Hardware Cursors\n1 = Force Software Cursors\n2 = Auto detection"
        ),
        ConfigItem(
            label="Sync XCursor with GSettings",
            key="sync_gsettings_theme",
            scope="cursor",
            type_="bool",
            default=True,
            group="Hardware Integration"
        ),
        ConfigItem(
            label="Use CPU Buffer for HW Cursors",
            key="use_cpu_buffer",
            scope="cursor",
            type_="int",
            default=2,
            options=[0, 1, 2],
            group="Hardware Integration",
            extended_help="Required for some Nvidia setups.\n\n0 = No\n1 = Yes\n2 = Auto"
        ),
        ConfigItem(
            label="Disable Cursor Warps",
            key="no_warps",
            scope="cursor",
            type_="bool",
            default=False,
            group="Warping Behavior",
            extended_help="Suppress automatic cursor warps on window focus or keybind triggers."
        ),
        ConfigItem(
            label="Persistent Internal Warps",
            key="persistent_warps",
            scope="cursor",
            type_="bool",
            default=False,
            group="Warping Behavior",
            extended_help="Cursor remembers and returns to its last position inside a window upon refocus."
        ),
    ],

    # -------------------------------------------------------------------------
    # TAB 4: PROFILES & ACTIONS
    # -------------------------------------------------------------------------
    4: [
        ConfigItem(
            label="Reload Hyprland Configuration",
            key="action_reload_wm",
            scope="DEFAULT",
            type_="action",
            default="hyprctl reload",
            group="System Actions"
        ),
        ConfigItem(
            label="Apply 'Gaming' Profile (Raw Input)",
            key="preset_gaming",
            scope="DEFAULT",
            type_="preset",
            default=None,
            group="Quick Profiles",
            preset_payload={
                "input.force_no_accel": True,
                "input.accel_profile": "flat",
                "input.follow_mouse": 1
            }
        ),
        ConfigItem(
            label="Apply 'Laptop' Profile",
            key="preset_laptop",
            scope="DEFAULT",
            type_="preset",
            default=None,
            group="Quick Profiles",
            preset_payload={
                "input/touchpad.tap_to_click": True,
                "input/touchpad.natural_scroll": True,
                "input/touchpad.disable_while_typing": True,
                "input.scroll_method": "2fg"
            }
        ),
        ConfigItem(
            label="Factory Reset Input & Cursor",
            key="preset_factory_reset",
            scope="DEFAULT",
            type_="preset",
            default=None,
            group="Danger Zone",
            preset_payload={
                "__ALL_DEFAULTS__": True
            }
        ),
    ]
}
