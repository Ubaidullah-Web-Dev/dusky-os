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
    "General",
    "Decorations",
    "Misc",
    "Presets"
]

# =============================================================================
# COLOR ALIASES
# =============================================================================
COLOR_ALIASES = [
    "primary", "secondary", "tertiary", "error", "background", 
    "surface", "surface_variant", "outline", "inverse_on_surface", 
    "on_surface", "primary_container", "secondary_container", "tertiary_container",
    "rgba(1a1a1aee)", "rgba(000000ff)", "rgba(ffffff11)", "rgba(00000000)"
]

# =============================================================================
# 4. SCHEMA DEFINITION
# =============================================================================
SCHEMA = {
    # -------------------------------------------------------------------------
    # TAB 0: GENERAL
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
            group="Layout & Gaps"
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
            group="Layout & Gaps"
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
            group="Layout & Gaps"
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
            group="Layout & Gaps"
        ),
        ConfigItem(
            label="Workspace Gaps",
            key="gaps_workspaces",
            scope="general",
            type_="int",
            default=0,
            min_val=0,
            max_val=50,
            step=1,
            group="Layout & Gaps"
        ),

        ConfigItem(
            label="Active Border Color",
            key="col.active_border",
            scope="general",
            type_="color",
            default="primary",
            options=COLOR_ALIASES,
            group="Border Colors"
        ),
        ConfigItem(
            label="Inactive Border Color",
            key="col.inactive_border",
            scope="general",
            type_="color",
            default="inverse_on_surface",
            options=COLOR_ALIASES,
            group="Border Colors"
        ),
        ConfigItem(
            label="No-Group Active Border",
            key="col.nogroup_border_active",
            scope="general",
            type_="color",
            default="secondary",
            options=COLOR_ALIASES,
            group="Border Colors"
        ),
        ConfigItem(
            label="No-Group Inactive Border",
            key="col.nogroup_border",
            scope="general",
            type_="color",
            default="inverse_on_surface",
            options=COLOR_ALIASES,
            group="Border Colors"
        ),

        ConfigItem(
            label="Resize on Border",
            key="resize_on_border",
            scope="general",
            type_="bool",
            default=True,
            group="Window Interactions"
        ),
        ConfigItem(
            label="Border Grab Area",
            key="extend_border_grab_area",
            scope="general",
            type_="int",
            default=15,
            min_val=0,
            max_val=50,
            step=1,
            group="Window Interactions"
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
            label="Resize Corner",
            key="resize_corner",
            scope="general",
            type_="int",
            default=0,
            min_val=0,
            max_val=4,
            step=1,
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
    # TAB 1: DECORATIONS
    # -------------------------------------------------------------------------
    1: [
        ConfigItem(
            label="Corner Rounding",
            key="rounding",
            scope="decoration",
            type_="int",
            default=10,
            min_val=0,
            max_val=50,
            step=1,
            group="Window Styling"
        ),
        ConfigItem(
            label="Rounding Power",
            key="rounding_power",
            scope="decoration",
            type_="float",
            default=2.5,
            min_val=1.0,
            max_val=4.0,
            step=0.1,
            group="Window Styling"
        ),
        ConfigItem(
            label="Border Part of Window",
            key="border_part_of_window",
            scope="decoration",
            type_="bool",
            default=True,
            group="Window Styling"
        ),
        ConfigItem(
            label="Active Opacity",
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
            label="Inactive Opacity",
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
            label="Fullscreen Opacity",
            key="fullscreen_opacity",
            scope="decoration",
            type_="float",
            default=1.0,
            min_val=0.0,
            max_val=1.0,
            step=0.05,
            group="Window Styling"
        ),
        ConfigItem(
            label="Screen Shader Path",
            key="screen_shader",
            scope="decoration",
            type_="string",
            default="",
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
        ConfigItem(
            label="Dim Around Rules",
            key="dim_around",
            scope="decoration",
            type_="float",
            default=0.4,
            min_val=0.0,
            max_val=1.0,
            step=0.1,
            group="Dimming Effects"
        ),
        ConfigItem(
            label="Dim Modals",
            key="dim_modal",
            scope="decoration",
            type_="bool",
            default=True,
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
            max_val=30,
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
            label="Ignore Opacity",
            key="ignore_opacity",
            scope="decoration/blur",
            type_="bool",
            default=True,
            parent_ref="blur_menu_id"
        ),
        ConfigItem(
            label="New Optimizations",
            key="new_optimizations",
            scope="decoration/blur",
            type_="bool",
            default=True,
            parent_ref="blur_menu_id"
        ),
        ConfigItem(
            label="X-Ray Mode",
            key="xray",
            scope="decoration/blur",
            type_="bool",
            default=False,
            parent_ref="blur_menu_id"
        ),
        ConfigItem(
            label="Noise",
            key="noise",
            scope="decoration/blur",
            type_="float",
            default=0.0117,
            min_val=0.0,
            max_val=1.0,
            step=0.01,
            parent_ref="blur_menu_id"
        ),
        ConfigItem(
            label="Contrast",
            key="contrast",
            scope="decoration/blur",
            type_="float",
            default=0.8916,
            min_val=0.0,
            max_val=2.0,
            step=0.1,
            parent_ref="blur_menu_id"
        ),
        ConfigItem(
            label="Brightness",
            key="brightness",
            scope="decoration/blur",
            type_="float",
            default=0.8172,
            min_val=0.0,
            max_val=2.0,
            step=0.1,
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
        ConfigItem(
            label="Vibrancy Darkness",
            key="vibrancy_darkness",
            scope="decoration/blur",
            type_="float",
            default=0.0,
            min_val=0.0,
            max_val=1.0,
            step=0.05,
            parent_ref="blur_menu_id"
        ),
        ConfigItem(
            label="Special Workspace Blur",
            key="special",
            scope="decoration/blur",
            type_="bool",
            default=False,
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
            label="Popups Ignore Alpha",
            key="popups_ignorealpha",
            scope="decoration/blur",
            type_="float",
            default=0.2,
            min_val=0.0,
            max_val=1.0,
            step=0.1,
            parent_ref="blur_menu_id"
        ),
        ConfigItem(
            label="Blur Input Methods",
            key="input_methods",
            scope="decoration/blur",
            type_="bool",
            default=False,
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
            label="Render Power",
            key="render_power",
            scope="decoration/shadow",
            type_="int",
            default=1,
            min_val=1,
            max_val=4,
            step=1,
            parent_ref="shadow_menu_id"
        ),
        ConfigItem(
            label="Sharp Shadows",
            key="sharp",
            scope="decoration/shadow",
            type_="bool",
            default=False,
            parent_ref="shadow_menu_id"
        ),
        ConfigItem(
            label="Shadow Color",
            key="color",
            scope="decoration/shadow",
            type_="color",
            default="rgba(1a1a1aee)",
            options=COLOR_ALIASES,
            parent_ref="shadow_menu_id"
        ),
        ConfigItem(
            label="Shadow Scale",
            key="scale",
            scope="decoration/shadow",
            type_="float",
            default=1.0,
            min_val=0.0,
            max_val=1.0,
            step=0.1,
            parent_ref="shadow_menu_id"
        ),

        # --- GLOW MENU FOLDER ---
        ConfigItem(
            label="Glow Settings",
            key="glow_menu_id",
            scope="DEFAULT",
            type_="menu",
            default=None,
            is_parent=True,
            expanded=False,
            group="Render Layers"
        ),
        ConfigItem(
            label="Enable Glow",
            key="enabled",
            scope="decoration/glow",
            type_="bool",
            default=False,
            parent_ref="glow_menu_id"
        ),
        ConfigItem(
            label="Glow Range",
            key="range",
            scope="decoration/glow",
            type_="int",
            default=10,
            min_val=1,
            max_val=50,
            step=1,
            parent_ref="glow_menu_id"
        ),
        ConfigItem(
            label="Render Power",
            key="render_power",
            scope="decoration/glow",
            type_="int",
            default=3,
            min_val=1,
            max_val=4,
            step=1,
            parent_ref="glow_menu_id"
        ),
        ConfigItem(
            label="Glow Color",
            key="color",
            scope="decoration/glow",
            type_="color",
            default="primary_container",
            options=COLOR_ALIASES,
            parent_ref="glow_menu_id"
        ),
    ],

    # -------------------------------------------------------------------------
    # TAB 2: MISC
    # -------------------------------------------------------------------------
    2: [
        ConfigItem(
            label="Background Color",
            key="background_color",
            scope="misc",
            type_="color",
            default="background",
            options=COLOR_ALIASES,
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
            label="Splash Font Family",
            key="splash_font_family",
            scope="misc",
            type_="string",
            default="",
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
            label="Disable Splash Rendering",
            key="disable_splash_rendering",
            scope="misc",
            type_="bool",
            default=True,
            group="Visual Overrides"
        ),
        ConfigItem(
            label="Force Default Wallpaper",
            key="force_default_wallpaper",
            scope="misc",
            type_="int",
            default=1,
            min_val=-1,
            max_val=2,
            step=1,
            group="Visual Overrides"
        ),

        ConfigItem(
            label="Animate Manual Resizes",
            key="animate_manual_resizes",
            scope="misc",
            type_="bool",
            default=False,
            group="System Behavior"
        ),
        ConfigItem(
            label="Animate Mouse Dragging",
            key="animate_mouse_windowdragging",
            scope="misc",
            type_="bool",
            default=False,
            group="System Behavior"
        ),
        ConfigItem(
            label="Unfocused Render FPS",
            key="render_unfocused_fps",
            scope="misc",
            type_="int",
            default=5,
            min_val=1,
            max_val=60,
            step=1,
            group="System Behavior"
        ),
        ConfigItem(
            label="Enable ANR Dialog",
            key="enable_anr_dialog",
            scope="misc",
            type_="bool",
            default=True,
            group="System Behavior"
        ),

        # --- GROUP MENU ---
        ConfigItem(
            label="Window Group Colors",
            key="group_menu_id",
            scope="DEFAULT",
            type_="menu",
            default=None,
            is_parent=True,
            expanded=False,
            group="Window Groups"
        ),
        ConfigItem(
            label="Active Group Border",
            key="col.border_active",
            scope="group",
            type_="color",
            default="primary",
            options=COLOR_ALIASES,
            parent_ref="group_menu_id"
        ),
        ConfigItem(
            label="Inactive Group Border",
            key="col.border_inactive",
            scope="group",
            type_="color",
            default="inverse_on_surface",
            options=COLOR_ALIASES,
            parent_ref="group_menu_id"
        ),
        ConfigItem(
            label="Active Locked Border",
            key="col.border_locked_active",
            scope="group",
            type_="color",
            default="tertiary",
            options=COLOR_ALIASES,
            parent_ref="group_menu_id"
        ),
        ConfigItem(
            label="Inactive Locked Border",
            key="col.border_locked_inactive",
            scope="group",
            type_="color",
            default="tertiary_container",
            options=COLOR_ALIASES,
            parent_ref="group_menu_id"
        ),

        # --- GROUPBAR MENU ---
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
            label="Stacked Rendering",
            key="stacked",
            scope="group/groupbar",
            type_="bool",
            default=False,
            parent_ref="groupbar_menu_id"
        ),
        ConfigItem(
            label="Enable Gradients",
            key="gradients",
            scope="group/groupbar",
            type_="bool",
            default=False,
            parent_ref="groupbar_menu_id"
        ),
        ConfigItem(
            label="Text Color",
            key="text_color",
            scope="group/groupbar",
            type_="color",
            default="on_surface",
            options=COLOR_ALIASES,
            parent_ref="groupbar_menu_id"
        ),
        ConfigItem(
            label="Active Color",
            key="col.active",
            scope="group/groupbar",
            type_="color",
            default="primary",
            options=COLOR_ALIASES,
            parent_ref="groupbar_menu_id"
        ),

        # --- HARDWARE MENU ---
        ConfigItem(
            label="Hardware & Pipeline",
            key="hw_menu_id",
            scope="DEFAULT",
            type_="menu",
            default=None,
            is_parent=True,
            expanded=False,
            group="Advanced Hardware"
        ),
        ConfigItem(
            label="XWayland Nearest Neighbor",
            key="use_nearest_neighbor",
            scope="xwayland",
            type_="bool",
            default=True,
            parent_ref="hw_menu_id"
        ),
        ConfigItem(
            label="XWayland Zero Scaling",
            key="force_zero_scaling",
            scope="xwayland",
            type_="bool",
            default=False,
            parent_ref="hw_menu_id"
        ),
        ConfigItem(
            label="Nvidia Anti-Flicker",
            key="nvidia_anti_flicker",
            scope="opengl",
            type_="bool",
            default=True,
            parent_ref="hw_menu_id"
        ),
        ConfigItem(
            label="Direct Scanout Mode",
            key="direct_scanout",
            scope="render",
            type_="int",
            default=0,
            options=[0, 1, 2],
            parent_ref="hw_menu_id"
        ),
        ConfigItem(
            label="XP Rendering Mode",
            key="xp_mode",
            scope="render",
            type_="bool",
            default=False,
            parent_ref="hw_menu_id"
        ),
    ],

    # -------------------------------------------------------------------------
    # TAB 3: PRESETS
    # -------------------------------------------------------------------------
    3: [
        ConfigItem(
            label="Factory Reset Everything",
            key="preset_factory_reset",
            scope="DEFAULT",
            type_="preset",
            default=None,
            group="Utility",
            preset_payload={"__ALL_DEFAULTS__": True}
        ),
        ConfigItem(
            label="Profile: Performance (Max FPS)",
            key="preset_perf_id",
            scope="DEFAULT",
            type_="preset",
            default=None,
            group="Utility",
            preset_payload={
                "decoration/blur.enabled": False,
                "decoration/shadow.enabled": False,
                "decoration/glow.enabled": False,
                "misc.animate_manual_resizes": False,
                "decoration.rounding": 0,
            }
        ),
        ConfigItem(
            label="Profile: Eye Candy (Max Visuals)",
            key="preset_visual_id",
            scope="DEFAULT",
            type_="preset",
            default=None,
            group="Utility",
            preset_payload={
                "decoration/blur.enabled": True,
                "decoration/blur.passes": 3,
                "decoration/blur.size": 12,
                "decoration/shadow.enabled": True,
                "decoration/shadow.range": 25,
                "decoration/glow.enabled": True,
                "decoration.rounding": 15,
                "misc.animate_manual_resizes": True,
                "misc.animate_mouse_windowdragging": True,
            }
        ),
        
        # --- THE WILD PRESETS ---
        ConfigItem(
            label="Cyberpunk Neon",
            key="pre_cyber",
            scope="DEFAULT",
            type_="preset",
            default=None,
            group="Wild Styles",
            preset_payload={
                "decoration.rounding": 0,
                "general.border_size": 2,
                "general.col.active_border": "error",
                "general.col.inactive_border": "rgba(000000ff)",
                "decoration/glow.enabled": True,
                "decoration/glow.color": "error",
                "decoration/glow.range": 15,
                "misc.background_color": "rgba(000000ff)"
            }
        ),
        ConfigItem(
            label="Ghosted Glass",
            key="pre_ghost",
            scope="DEFAULT",
            type_="preset",
            default=None,
            group="Wild Styles",
            preset_payload={
                "decoration.active_opacity": 0.6,
                "decoration.inactive_opacity": 0.4,
                "general.border_size": 1,
                "general.col.active_border": "rgba(ffffff11)",
                "decoration/blur.enabled": True,
                "decoration/blur.passes": 4,
                "decoration/blur.size": 8,
                "decoration/shadow.enabled": False
            }
        ),
        ConfigItem(
            label="Chunky Blocks",
            key="pre_chunk",
            scope="DEFAULT",
            type_="preset",
            default=None,
            group="Wild Styles",
            preset_payload={
                "general.border_size": 6,
                "general.gaps_in": 15,
                "general.gaps_out": 25,
                "decoration.rounding": 20,
                "decoration/shadow.enabled": False,
                "decoration/blur.enabled": False,
                "decoration.active_opacity": 1.0,
                "decoration.inactive_opacity": 1.0
            }
        ),
        ConfigItem(
            label="Origami Paper",
            key="pre_paper",
            scope="DEFAULT",
            type_="preset",
            default=None,
            group="Wild Styles",
            preset_payload={
                "decoration/blur.enabled": False,
                "decoration/shadow.enabled": True,
                "decoration/shadow.sharp": True,
                "decoration/shadow.range": 8,
                "decoration.rounding": 2,
                "general.col.active_border": "outline",
                "misc.background_color": "surface"
            }
        ),
        ConfigItem(
            label="Neon Lights",
            key="pre_neon",
            scope="DEFAULT",
            type_="preset",
            default=None,
            group="Wild Styles",
            preset_payload={
                "decoration/glow.enabled": True,
                "decoration/glow.range": 25,
                "decoration/glow.color": "tertiary",
                "general.border_size": 3,
                "general.col.active_border": "tertiary",
                "decoration/shadow.enabled": False,
                "decoration.rounding": 10
            }
        ),
        ConfigItem(
            label="Glassmorphism",
            key="pre_glass",
            scope="DEFAULT",
            type_="preset",
            default=None,
            group="Wild Styles",
            preset_payload={
                "decoration.active_opacity": 0.75,
                "decoration.inactive_opacity": 0.65,
                "decoration/blur.passes": 3,
                "decoration/blur.size": 15,
                "general.border_size": 0,
                "decoration.rounding": 12,
                "decoration/shadow.enabled": True,
                "decoration/shadow.range": 30
            }
        ),
        ConfigItem(
            label="Harsh Minimalist",
            key="pre_min",
            scope="DEFAULT",
            type_="preset",
            default=None,
            group="Wild Styles",
            preset_payload={
                "general.gaps_in": 0,
                "general.gaps_out": 0,
                "decoration.rounding": 0,
                "general.border_size": 1,
                "general.col.active_border": "outline",
                "decoration/shadow.enabled": False,
                "decoration/blur.enabled": False
            }
        ),
        ConfigItem(
            label="Retro 8-Bit",
            key="pre_8bit",
            scope="DEFAULT",
            type_="preset",
            default=None,
            group="Wild Styles",
            preset_payload={
                "xwayland.use_nearest_neighbor": True,
                "decoration.rounding": 0,
                "general.border_size": 4,
                "general.col.active_border": "primary",
                "decoration/shadow.sharp": True,
                "decoration/shadow.range": 10,
                "decoration/shadow.color": "primary"
            }
        ),
        ConfigItem(
            label="The Void",
            key="pre_void",
            scope="DEFAULT",
            type_="preset",
            default=None,
            group="Wild Styles",
            preset_payload={
                "misc.background_color": "rgba(000000ff)",
                "decoration.active_opacity": 1.0,
                "decoration.inactive_opacity": 0.3,
                "general.border_size": 1,
                "general.col.active_border": "surface_variant",
                "decoration/glow.enabled": False,
                "decoration/shadow.enabled": False
            }
        ),
        ConfigItem(
            label="Round & Bouncy",
            key="pre_round",
            scope="DEFAULT",
            type_="preset",
            default=None,
            group="Wild Styles",
            preset_payload={
                "decoration.rounding": 30,
                "decoration.rounding_power": 2.0,
                "general.gaps_in": 10,
                "general.gaps_out": 20,
                "general.border_size": 3,
                "decoration/shadow.enabled": True
            }
        ),
        ConfigItem(
            label="Corporate Professional",
            key="pre_corp",
            scope="DEFAULT",
            type_="preset",
            default=None,
            group="Wild Styles",
            preset_payload={
                "decoration.rounding": 8,
                "general.border_size": 1,
                "general.col.active_border": "primary_container",
                "decoration/shadow.enabled": True,
                "decoration/shadow.range": 12,
                "decoration/blur.size": 5
            }
        ),
        ConfigItem(
            label="Vaporwave Sunset",
            key="pre_sunset",
            scope="DEFAULT",
            type_="preset",
            default=None,
            group="Wild Styles",
            preset_payload={
                "decoration/glow.enabled": True,
                "decoration/glow.color": "tertiary",
                "decoration/shadow.enabled": True,
                "decoration/shadow.color": "error",
                "general.col.active_border": "secondary",
                "decoration.rounding": 0
            }
        ),
        ConfigItem(
            label="Hacker Terminal",
            key="pre_hack",
            scope="DEFAULT",
            type_="preset",
            default=None,
            group="Wild Styles",
            preset_payload={
                "misc.background_color": "rgba(000000ff)",
                "general.col.active_border": "primary",
                "general.col.inactive_border": "rgba(000000ff)",
                "decoration.rounding": 0,
                "decoration/glow.enabled": True,
                "decoration/glow.color": "primary",
                "decoration/shadow.enabled": False
            }
        ),
        ConfigItem(
            label="Cotton Candy",
            key="pre_candy",
            scope="DEFAULT",
            type_="preset",
            default=None,
            group="Wild Styles",
            preset_payload={
                "general.col.active_border": "tertiary",
                "general.col.inactive_border": "tertiary_container",
                "decoration.rounding": 25,
                "decoration/glow.enabled": True,
                "decoration/glow.color": "tertiary",
                "decoration/blur.enabled": True,
                "decoration/blur.vibrancy": 0.8
            }
        ),
        ConfigItem(
            label="Opaque Solid",
            key="pre_opaque",
            scope="DEFAULT",
            type_="preset",
            default=None,
            group="Wild Styles",
            preset_payload={
                "decoration.active_opacity": 1.0,
                "decoration.inactive_opacity": 1.0,
                "decoration/blur.enabled": False,
                "general.border_size": 2,
                "decoration.rounding": 5
            }
        ),
        ConfigItem(
            label="Outlined Box",
            key="pre_outlined",
            scope="DEFAULT",
            type_="preset",
            default=None,
            group="Wild Styles",
            preset_payload={
                "general.border_size": 5,
                "general.gaps_in": 0,
                "general.gaps_out": 0,
                "decoration.rounding": 0,
                "general.col.active_border": "secondary",
                "decoration/shadow.enabled": False
            }
        ),
        ConfigItem(
            label="Deep Space",
            key="pre_space",
            scope="DEFAULT",
            type_="preset",
            default=None,
            group="Wild Styles",
            preset_payload={
                "misc.background_color": "surface_container_lowest",
                "decoration/blur.enabled": True,
                "decoration/blur.size": 20,
                "decoration/glow.enabled": True,
                "decoration/glow.color": "primary",
                "general.col.active_border": "surface_variant"
            }
        ),
    ]
}
