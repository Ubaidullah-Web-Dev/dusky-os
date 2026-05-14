#!/usr/bin/env python3
"""
===============================================================================
DUSKY TUI: MASTER CONFIGURATION SCHEMA
===============================================================================
Target: ~/.config/hypr/edit_here/source/appearance.lua
"""

from python.frontend.core_types import ConfigItem

# =============================================================================
# 1. CORE APPLICATION ROUTING
# =============================================================================
ENGINE_TYPE = "lua"
TARGET_FILE = "~/.config/hypr/edit_here/source/appearance.lua"
APP_TITLE = "Appearance Settings"

# =============================================================================
# 2. UI & ENVIRONMENT BEHAVIOR
# =============================================================================
DEFAULT_MODE = "auto"
THEME_FILE = "~/.config/matugen/generated/dusky_tui.json"

# =============================================================================
# 3. TABS DEFINITION
# =============================================================================
TABS = [
    "1. General & Borders",
    "2. Decorations & Blur",
    "3. Misc & Grouping",
    "4. Profiles & Actions"
]

# =============================================================================
# 4. SCHEMA DEFINITION
# =============================================================================
SCHEMA = {
    # -------------------------------------------------------------------------
    # TAB 0: GENERAL & BORDERS
    # -------------------------------------------------------------------------
    0: [
        ConfigItem(
            label="Border Size",
            key="border_size",
            scope="general",
            type_="int",
            default=1,
            min_val=0,
            max_val=15,
            step=1,
            group="Layout & Gaps",
            extended_help="Size of the border around windows (in layout pixels)."
        ),
        ConfigItem(
            label="Inner Gaps",
            key="gaps_in",
            scope="general",
            type_="int",
            default=4,
            min_val=0,
            max_val=50,
            step=1,
            group="Layout & Gaps",
            extended_help="Gaps between windows."
        ),
        ConfigItem(
            label="Outer Gaps",
            key="gaps_out",
            scope="general",
            type_="int",
            default=8,
            min_val=0,
            max_val=50,
            step=1,
            group="Layout & Gaps",
            extended_help="Gaps between windows and monitor edges."
        ),
        ConfigItem(
            label="Floating Window Gaps",
            key="float_gaps",
            scope="general",
            type_="int",
            default=0,
            min_val=-1,
            max_val=50,
            step=1,
            group="Layout & Gaps",
            extended_help="Gaps specifically for floating windows. (-1 means default)."
        ),
        
        ConfigItem(
            label="Active Border Color",
            key="col.active_border",
            scope="general",
            type_="color",
            default="primary",
            group="Border Colors"
        ),
        ConfigItem(
            label="Inactive Border Color",
            key="col.inactive_border",
            scope="general",
            type_="color",
            default="inverse_on_surface",
            group="Border Colors"
        ),
        
        ConfigItem(
            label="Resize on Border",
            key="resize_on_border",
            scope="general",
            type_="bool",
            default=True,
            group="Window Interactions",
            extended_help="Enables resizing windows by clicking and dragging on borders and gaps."
        ),
        ConfigItem(
            label="Hover Icon on Border",
            key="hover_icon_on_border",
            scope="general",
            type_="bool",
            default=True,
            group="Window Interactions"
        ),
        ConfigItem(
            label="Allow Tearing",
            key="allow_tearing",
            scope="general",
            type_="bool",
            default=True,
            group="Window Interactions"
        ),
    ],

    # -------------------------------------------------------------------------
    # TAB 1: DECORATIONS & BLUR
    # -------------------------------------------------------------------------
    1: [
        ConfigItem(
            label="Corner Rounding",
            key="rounding",
            scope="decoration",
            type_="int",
            default=10,
            min_val=0,
            max_val=30,
            step=1,
            group="Window Styling"
        ),
        ConfigItem(
            label="Active Window Opacity",
            key="active_opacity",
            scope="decoration",
            type_="float",
            default=0.85,
            min_val=0.0,
            max_val=1.0,
            step=0.05,
            group="Window Styling"
        ),
        ConfigItem(
            label="Inactive Window Opacity",
            key="inactive_opacity",
            scope="decoration",
            type_="float",
            default=0.85,
            min_val=0.0,
            max_val=1.0,
            step=0.05,
            group="Window Styling"
        ),
        ConfigItem(
            label="Dim Inactive Windows",
            key="dim_inactive",
            scope="decoration",
            type_="bool",
            default=True,
            group="Dimming Effects"
        ),
        ConfigItem(
            label="Inactive Dim Strength",
            key="dim_strength",
            scope="decoration",
            type_="float",
            default=0.3,
            min_val=0.0,
            max_val=1.0,
            step=0.1,
            group="Dimming Effects"
        ),
        ConfigItem(
            label="Special Workspace Dim",
            key="dim_special",
            scope="decoration",
            type_="float",
            default=0.8,
            min_val=0.0,
            max_val=1.0,
            step=0.1,
            group="Dimming Effects"
        ),

        # --- BLUR MENU FOLDER ---
        ConfigItem(
            label="Blur Settings",
            key="blur_menu_id",
            scope="DEFAULT",
            type_="menu",
            default=None,
            is_parent=True,
            expanded=False,
            group="Render Layers"
        ),
        ConfigItem(
            label="Enable Blur",
            key="enabled",
            scope="decoration/blur",
            type_="bool",
            default=True,
            parent_ref="blur_menu_id"
        ),
        ConfigItem(
            label="Blur Size",
            key="size",
            scope="decoration/blur",
            type_="int",
            default=10,
            min_val=1,
            max_val=20,
            step=1,
            parent_ref="blur_menu_id"
        ),
        ConfigItem(
            label="Blur Passes",
            key="passes",
            scope="decoration/blur",
            type_="int",
            default=2,
            min_val=1,
            max_val=10,
            step=1,
            parent_ref="blur_menu_id"
        ),
        ConfigItem(
            label="Blur Popups",
            key="popups",
            scope="decoration/blur",
            type_="bool",
            default=False,
            parent_ref="blur_menu_id"
        ),
        ConfigItem(
            label="Vibrancy",
            key="vibrancy",
            scope="decoration/blur",
            type_="float",
            default=0.1696,
            min_val=0.0,
            max_val=1.0,
            step=0.05,
            parent_ref="blur_menu_id"
        ),

        # --- SHADOW MENU FOLDER ---
        ConfigItem(
            label="Shadow Settings",
            key="shadow_menu_id",
            scope="DEFAULT",
            type_="menu",
            default=None,
            is_parent=True,
            expanded=False,
            group="Render Layers"
        ),
        ConfigItem(
            label="Enable Shadows",
            key="enabled",
            scope="decoration/shadow",
            type_="bool",
            default=True,
            parent_ref="shadow_menu_id"
        ),
        ConfigItem(
            label="Shadow Range",
            key="range",
            scope="decoration/shadow",
            type_="int",
            default=10,
            min_val=1,
            max_val=50,
            step=1,
            parent_ref="shadow_menu_id"
        ),
        ConfigItem(
            label="Shadow Color",
            key="color",
            scope="decoration/shadow",
            type_="string",
            default="rgba(1a1a1aee)",
            parent_ref="shadow_menu_id"
        ),
    ],

    # -------------------------------------------------------------------------
    # TAB 2: MISC & GROUPING
    # -------------------------------------------------------------------------
    2: [
        ConfigItem(
            label="Background Color",
            key="background_color",
            scope="misc",
            type_="color",
            default="background",
            group="Visual Overrides"
        ),
        ConfigItem(
            label="Default Font Family",
            key="font_family",
            scope="misc",
            type_="string",
            default="Sans",
            group="Visual Overrides"
        ),
        ConfigItem(
            label="Disable Hyprland Logo",
            key="disable_hyprland_logo",
            scope="misc",
            type_="bool",
            default=True,
            group="Visual Overrides"
        ),
        ConfigItem(
            label="Animate Manual Resizes",
            key="animate_manual_resizes",
            scope="misc",
            type_="bool",
            default=False,
            group="UI Animations"
        ),
        ConfigItem(
            label="Workspace Wraparound",
            key="workspace_wraparound",
            scope="animations",
            type_="bool",
            default=False,
            group="UI Animations"
        ),

        # --- GROUPBAR MENU FOLDER ---
        ConfigItem(
            label="Groupbar Settings",
            key="groupbar_menu_id",
            scope="DEFAULT",
            type_="menu",
            default=None,
            is_parent=True,
            expanded=False,
            group="Window Groups"
        ),
        ConfigItem(
            label="Enable Groupbars",
            key="enabled",
            scope="group/groupbar",
            type_="bool",
            default=True,
            parent_ref="groupbar_menu_id"
        ),
        ConfigItem(
            label="Groupbar Height",
            key="height",
            scope="group/groupbar",
            type_="int",
            default=14,
            min_val=5,
            max_val=30,
            step=1,
            parent_ref="groupbar_menu_id"
        ),
        ConfigItem(
            label="Render Titles",
            key="render_titles",
            scope="group/groupbar",
            type_="bool",
            default=True,
            parent_ref="groupbar_menu_id"
        ),
        ConfigItem(
            label="Font Size",
            key="font_size",
            scope="group/groupbar",
            type_="int",
            default=8,
            min_val=6,
            max_val=16,
            step=1,
            parent_ref="groupbar_menu_id"
        ),
    ],

    # -------------------------------------------------------------------------
    # TAB 3: PROFILES & ACTIONS
    # -------------------------------------------------------------------------
    3: [
        ConfigItem(
            label="Apply 'Performance' Profile",
            key="preset_perf_id",
            scope="DEFAULT",
            type_="preset",
            default=None,
            group="Profiles",
            extended_help="Disables blur, shadows, and animations to maximize system performance.",
            preset_payload={
                "decoration/blur.enabled": False,
                "decoration/shadow.enabled": False,
                "misc.animate_manual_resizes": False,
                "decoration.rounding": 0,
            }
        ),
        ConfigItem(
            label="Apply 'Eye Candy' Profile",
            key="preset_visual_id",
            scope="DEFAULT",
            type_="preset",
            default=None,
            group="Profiles",
            extended_help="Enables heavy blur, deep shadows, and high rounding.",
            preset_payload={
                "decoration/blur.enabled": True,
                "decoration/blur.passes": 3,
                "decoration/shadow.enabled": True,
                "decoration/shadow.range": 25,
                "decoration.rounding": 15,
            }
        ),
        ConfigItem(
            label="Factory Reset Everything",
            key="preset_factory_reset",
            scope="DEFAULT",
            type_="preset",
            default=None,
            group="Maintenance",
            preset_payload={
                "__ALL_DEFAULTS__": True
            }
        ),
    ]
}
