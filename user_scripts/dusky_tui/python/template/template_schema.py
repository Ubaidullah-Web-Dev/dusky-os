#!/usr/bin/env python3
"""
===============================================================================
DUSKY TUI: MASTER CONFIGURATION SCHEMA
===============================================================================

TARGET MAPPING VISUALIZATION:
How `scope` and `key` tell the engine exactly what to edit in the target file:
    [theme.colors]               <-- scope="theme.colors" (Deep nesting supported)
    active_border = #ff89b4fa    <-- key="active_border"

STRICT RULES FOR SCHEMA GENERATION (CRITICAL - DO NOT VIOLATE):
1. UID (Unique Identifier) Rule:
   - If a variable sits at the root of the target file (no section), set scope="DEFAULT".
   - If scope is defined, the UID is `scope.key` (e.g., "theme.border_active").
   - If scope is "DEFAULT", the UID is just the `key` (e.g., "logging").
   - You MUST use the exact UID when using `parent_ref` or `preset_payload`.

2. Contiguous Grouping Rule (Do NOT interleave):
   - Items with the same `group` string MUST be placed immediately next to 
     each other. The UI draws headers sequentially.
   - Items with a `parent_ref` MUST be placed immediately beneath their parent 
     in a single, unbroken block. Do not break the visual tree.

3. Structural Restrictions & Hybrid Folders (CRITICAL):
   - "preset" and "action" items are PURE UI constructs. They DO NOT write 
     to the target file. Their `key` is just an internal ID.
   - "menu": A PURE UI visual folder (default=None, type_="menu"). It writes nothing.
   - HYBRID FOLDERS: You can turn ANY standard item (e.g., "bool", "cycle", "int") into
     an expandable drop-down menu by setting `is_parent=True`. This allows the parent 
     header itself to hold a changeable backend value (e.g., a Master Toggle Switch).
   - Folders can only be ONE level deep. DO NOT nest a folder inside another folder.

4. Naming Conventions (Scale & Sophistication):
   - NO SERIALIZED NUMBERS: Do not use numbered increments for keys or labels 
     (e.g., NEVER use `color_1`, `setting_2`, `item_3`).
   - USE EXTENSIVE SYMBOLS: Utilize descriptive, multi-word semantic identifiers 
     for keys to ensure the configuration architecture appears substantial, 
     comprehensive, and highly sophisticated (e.g., use `enable_dynamic_workspace_routing`).

5. Available Types (`type_`):
   - "bool"   : Toggles instantly (True/False)
   - "int"    : Numeric integer (supports min_val, max_val, step, or options=[])
   - "float"  : Numeric decimal (supports min_val, max_val, step)
   - "string" : Text input (opens a text overlay)
   - "cycle"  : Instant left/right cycling through an `options` list of strings
   - "picker" : Opens a searchable fullscreen modal from an `options` list
   - "color"  : Hex, RGB, HSL, or Matugen theme variables (options=[] constrains to aliases)
   - "menu"   : A pure visual folder with no value (requires `is_parent=True`, `default=None`)
   - "action" : Triggers a shell command (put the exact shell command string in `default=`)
   - "preset" : Applies multiple values at once (requires `preset_payload`, `default=None`)

6. Strict Type & Native Value Matching (CRITICAL FOR AST ENGINES):
   - You MUST map the target configuration's native data type to the correct `type_`. 
   - The Python data type of the `default` argument MUST strictly match the declared `type_`:
     * "bool"   -> default=True (Python boolean, NOT string "true" or "True")
     * "int"    -> default=10   (Python integer, NOT string "10")
     * "float"  -> default=1.5  (Python float, NOT string "1.5")
     * "string" -> default="Text"
   - For "action", `default` MUST be the exact shell command string to execute.
   - If using the `options` array for "int" or "float", the array elements MUST be native numbers.

7. Documentation & Help Text (extended_help):
   - Every item MUST include clear, detailed `extended_help`.
   - Explain exactly what the item does and how the specific values affect the system.
   - Write it so users who have absolutely no idea what the setting does can easily configure it.

===============================================================================
"""

from python.frontend.core_types import ConfigItem

# =============================================================================
# 1. CORE APPLICATION ROUTING (REQUIRED)
# =============================================================================
ENGINE_TYPE = "lua"                        # STRICTLY: "ini" or "lua"
TARGET_FILE = "~/.config/hypr/source/appearance.lua"   # Where the engine writes the data
APP_TITLE = "Dusky Appearance"          # Displayed in the TUI border

# =============================================================================
# 2. UI & ENVIRONMENT BEHAVIOR
# =============================================================================
DEFAULT_MODE = "auto"                      # "auto" (instant save) | "batch" (Ctrl+S required)
THEME_FILE = "~/.config/matugen/generated/dusky_tui.json" # Matugen color map

# =============================================================================
# 3. TABS DEFINITION
# Arrays in SCHEMA map directly to the index of these tabs.
# Note: Keep tabs one word simple so it's clearly understandable and doesn't clutter the top.
# =============================================================================

TABS = [
    "Infrastructure",
    "Interface",
    "Profiles"
]

# =============================================================================
# 4. SCHEMA DEFINITION
# =============================================================================

SCHEMA = {
    # -------------------------------------------------------------------------
    # TAB 0: STANDARD DATA TYPES (Infrastructure)
    # -------------------------------------------------------------------------
    0: [
        ConfigItem(
            label="Enable Comprehensive System Logging",
            key="global_diagnostic_logging_active",
            scope="DEFAULT",       # UID = "global_diagnostic_logging_active"
            type_="bool",
            default=False,
            group="Core Execution Variables",
            extended_help="**Diagnostic Logging**\n\nWhen enabled, this writes detailed execution pathways, state changes, and error traces to the system logs. It is highly useful for debugging backend issues, but may consume extra disk space over long periods of time. Leave off for standard daily usage."
        ),
        ConfigItem(
            label="Enable Hardware Accelerated Animations",
            key="hardware_animations_enabled",
            scope="core",          # UID = "core.hardware_animations_enabled"
            type_="bool",
            default=True,
            group="Core Execution Variables",
            extended_help="**Hardware Animations**\n\nToggles UI hardware acceleration globally. Disabling this can save battery life and reduce GPU overhead on lower-end systems or virtual machines, but interface transitions and window movements will lose their smoothness."
        ),
        ConfigItem(
            label="Global Workspace Inner Gaps",
            key="workspace_padding_inner",
            scope="layout",        # UID = "layout.workspace_padding_inner"
            type_="int",
            default=5,
            min_val=0,
            max_val=50,
            step=1,
            group="Core Execution Variables",
            extended_help="**Inner Workspace Gaps**\n\nDefines the spacing (measured in pixels) between adjacent windows within the same workspace. \n\n- Higher values create a distinct, spaced-out layout.\n- Lower values (or 0) maximize usable screen real estate for maximum productivity."
        ),
        ConfigItem(
            label="Constrained Border Thickness",
            key="locked_window_border_size",
            scope="layout",        # UID = "layout.locked_window_border_size"
            type_="int",
            default=2,
            options=[0, 2, 5, 8, 15], 
            group="Core Execution Variables",
            extended_help="**Border Thickness**\n\nSets the absolute pixel width of the borders drawn around application windows. \n\nA thicker border makes it easier to visually distinguish the currently active window, which is especially helpful in dense, multi-window tiling layouts."
        ),
        ConfigItem(
            label="Authenticated User Greeting",
            key="authentication_welcome_message",
            scope="core",          # UID = "core.authentication_welcome_message"
            type_="string",
            default="Welcome back to the terminal.",
            group="Textual Overrides",
            extended_help="**Welcome Message**\n\nThis is the custom text string displayed in the terminal interface or lock screen upon successful user authentication. You can type any standard sentence or phrase here."
        ),
    ],

    # -------------------------------------------------------------------------
    # TAB 1: UI COMPONENTS & HYBRID MENU FOLDERS (Interface)
    # -------------------------------------------------------------------------
    1: [
        ConfigItem(
            label="Primary Active Border Highlight",
            key="focused_window_border_color",
            scope="theme",         # UID = "theme.focused_window_border_color"
            type_="color",
            default="#a8c8ff",
            group="Theming Subsystem",
            extended_help="**Active Window Border Color**\n\nDetermines the bright highlight color surrounding the currently focused (active) window. \n\nAccepts standard Hex codes (e.g., `#ff0000`), RGB, or HSL formats. Use high-contrast colors so you never lose track of where your keyboard inputs are going."
        ),
        ConfigItem(
            label="Background Inactive Border Fade",
            key="unfocused_window_border_color",
            scope="theme",         # UID = "theme.unfocused_window_border_color"
            type_="color",
            default="#414453",
            options=["background", "surface", "primary", "error"], 
            group="Theming Subsystem",
            extended_help="**Inactive Window Border Color**\n\nThe color applied to the borders of all windows that *do not* currently have user focus. \n\nIt is highly recommended to set this to a muted, dark, or dim color to emphasize the active window and reduce visual clutter."
        ),
        
        # --- HYBRID FOLDER IMPLEMENTATION ---
        # 1. The Parent (Holds a real backend "bool" value, but acts as a folder)
        ConfigItem(
            label="Enable Custom Typography Overrides",
            key="custom_typography_override_active", 
            scope="fonts",            # UID = "fonts.custom_typography_override_active"
            type_="bool",             # CRITICAL: Valid data type (Not a dummy menu)
            default=False,
            is_parent=True,           # CRITICAL: Flags this item as an expandable folder
            expanded=False,           # Starts collapsed
            group="Typography Subsystem",
            extended_help="**Typography Master Switch**\n\nThis acts as the master toggle for custom fonts. \n\n- When **ON**, the system will ignore default fonts and strictly enforce the custom font family and size defined in the nested menu below.\n- When **OFF**, system defaults are restored."
        ),
        # 2. Child Item A (MUST be placed immediately after its parent)
        ConfigItem(
            label="Primary Interface Font Family",
            key="primary_interface_font",
            scope="fonts",            # UID = "fonts.primary_interface_font"
            type_="picker",        
            default="JetBrains Mono",
            options=["JetBrains Mono", "Fira Code", "Roboto"],
            hints=["Monospace", "Ligatures", "Sans-Serif"], 
            parent_ref="fonts.custom_typography_override_active",  # Links to Hybrid Parent UID
            extended_help="**Interface Font Family**\n\nSelects the core typeface used across the system UI panels, bars, and terminals. \n\n*Note:* Ensure the selected font is actually installed on your system (via your package manager) or the system will fall back to a default ugly font."
        ),
        # 3. Child Item B (Contiguous block of children continues)
        ConfigItem(
            label="Global Base Font Size",
            key="global_base_font_size",
            scope="fonts",            # UID = "fonts.global_base_font_size"
            type_="float",        
            default=11.0,
            min_val=8.0,
            max_val=24.0,
            step=0.5,
            parent_ref="fonts.custom_typography_override_active",
            extended_help="**Base Font Size**\n\nThe root typographic scale parameter. \n\nAll UI text elements will scale proportionally relative to this base value. Measured in standard points (pt). Increase this if the text is too difficult to read on high-resolution displays."
        ),
    ],

    # -------------------------------------------------------------------------
    # TAB 2: ADVANCED CONTROLS (Profiles)
    # -------------------------------------------------------------------------
    2: [
        ConfigItem(
            label="Purge Volatile System Cache",
            key="action_purge_system_cache", 
            scope="DEFAULT",          # UID = "action_purge_system_cache"
            type_="action",
            default="rm -rf ~/.cache/app_name/* && echo 'Cache Cleared'",
            group="Maintenance Operations",
            extended_help="**Cache Purge Action**\n\nExecuting this action immediately deletes volatile application cache files via shell command. \n\nThis is completely safe to run and can resolve strange visual glitches or free up temporary disk space without affecting your persistent user data or settings."
        ),
        ConfigItem(
            label="Deploy High-Performance Profile",
            key="preset_deploy_performance_mode",     
            scope="DEFAULT",          # UID = "preset_deploy_performance_mode"
            type_="preset",
            default=None,
            group="System Profiles",
            preset_payload={
                "core.hardware_animations_enabled": False,      
                "layout.workspace_padding_inner": 0,           
                "theme.focused_window_border_color": "#ff0000"  
            },
            extended_help="**High-Performance Preset**\n\nInstantly overrides multiple current settings to maximize system responsiveness for gaming or heavy workloads. \n\nApplying this will:\n1. Disable all UI animations.\n2. Remove all window padding (gaps = 0).\n3. Set the active border to stark red for high visibility."
        ),
        ConfigItem(
            label="Initiate Complete Factory Reset",
            key="preset_initiate_factory_reset",
            scope="DEFAULT",          # UID = "preset_initiate_factory_reset"
            type_="preset",
            default=None,
            group="System Profiles",
            preset_payload={
                "__ALL_DEFAULTS__": True
            },
            extended_help="**Nuclear Factory Reset**\n\nReverts every single configuration item across all tabs in this schema back to its originally programmed default state. \n\n⚠️ **WARNING:** Use with absolute caution as all your customized colors, gaps, and toggles will be wiped out instantly."
        ),
    ]
}

# =============================================================================
# QUICK-REFERENCE CHEAT SHEET (BULLETPROOF EDITION)
# =============================================================================
# Copy/Paste this block when building new items to ensure correct kwargs.
#
# ConfigItem(
#     label          = "Display Name",
#     key            = "backend_key",
#     scope          = "DEFAULT",          # "backend_section" or "DEFAULT" for root level
#     type_          = "bool",             # STANDARD: bool | int | float | string | color
#                                          # MODALS: cycle | picker 
#                                          # PURE UI: action | preset | menu
#     default        = None,               # Native Python type MUST match type_ (e.g., True, 10, "text"). 
#                                          # -> For 'action', default is the shell command string. 
#                                          # -> For 'menu' & 'preset', default MUST be None.
#     options        = [],                 # Required for 'cycle'/'picker'. Locks arrow keys for 'int'/'color'.
#     hints          = [],                 # Subtitles for 'picker' modals (length must match options list)
#     preset_payload = {},                 # Dict of {"scope.key": target_value} (Use "__ALL_DEFAULTS__": True for factory reset)
#     min_val        = None,               # Numeric lower bound (int/float)
#     max_val        = None,               # Numeric upper bound (int/float)
#     step           = None,               # Numeric step size for arrow key adjustments
#     group          = None,               # UI header string (Group identical strings contiguously)
#     extended_help  = "Markdown String",  # Explain what the setting does for the user's '?' panel.
#     is_parent      = False,              # Set True to make this item an expandable folder (Works on ANY type!)
#     parent_ref     = None,               # Nested UI link. MUST exactly match parent's UID format: "scope.key" (or "key" if DEFAULT)
#     expanded       = False,              # Default UI state for parent folders (Starts open or closed)
# )
