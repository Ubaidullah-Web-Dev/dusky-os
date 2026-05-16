#!/usr/bin/env python3
"""
===============================================================================
DUSKY TUI: TRACKPAD GESTURES CONFIGURATION SCHEMA
===============================================================================
"""

from python.frontend.core_types import ConfigItem

# =============================================================================
# 1. CORE APPLICATION ROUTING (REQUIRED)
# =============================================================================
ENGINE_TYPE = "lua"
TARGET_FILE = "~/.config/hypr/edit_here/source/trackpad.lua"
APP_TITLE = "Trackpad Gestures"

# =============================================================================
# 2. UI & ENVIRONMENT BEHAVIOR
# =============================================================================
DEFAULT_MODE = "auto"
THEME_FILE = "~/.config/matugen/generated/dusky_tui.json"

# =============================================================================
# 3. TABS DEFINITION
# =============================================================================
TABS = [
    "1. Gesture Physics",
    "2. Advanced Navigation",
    "3. Profiles & Reset"
]

# =============================================================================
# 4. SCHEMA DEFINITION
# =============================================================================
SCHEMA = {
    # -------------------------------------------------------------------------
    # TAB 0: GESTURE PHYSICS
    # -------------------------------------------------------------------------
    0: [
        ConfigItem(
            label="Swipe Distance",
            key="workspace_swipe_distance",
            scope="gestures",
            type_="int",
            default=300,
            min_val=50,
            max_val=1500,
            step=50,
            group="Distance & Speed",
            extended_help="**Swipe Distance**\n\nMaximum swipe travel distance in pixels required to trigger a full workspace transition."
        ),
        ConfigItem(
            label="Commit Cancel Ratio",
            key="workspace_swipe_cancel_ratio",
            scope="gestures",
            type_="float",
            default=0.5,
            min_val=0.0,
            max_val=1.0,
            step=0.1,
            group="Distance & Speed",
            extended_help="**Cancel Ratio**\n\nThe fraction of the total swipe distance needed to commit to a workspace switch (0.0 to 1.0). If you lift your fingers before this threshold, the workspace snaps back."
        ),
        ConfigItem(
            label="Min Speed to Force Switch",
            key="workspace_swipe_min_speed_to_force",
            scope="gestures",
            type_="int",
            default=30,
            min_val=0,
            max_val=200,
            step=5,
            group="Distance & Speed",
            extended_help="**Force Speed**\n\nMinimum speed (in pixels per timepoint) required to force a workspace change regardless of the cancel ratio. Set to 0 to disable."
        ),
        ConfigItem(
            label="1:1 Gesture Close Timeout",
            key="close_max_timeout",
            scope="gestures",
            type_="int",
            default=1000,
            min_val=0,
            max_val=5000,
            step=100,
            group="Timing",
            extended_help="**Close Max Timeout**\n\nMaximum time in milliseconds a 1:1 gesture window has to close."
        ),
    ],

    # -------------------------------------------------------------------------
    # TAB 1: ADVANCED NAVIGATION
    # -------------------------------------------------------------------------
    1: [
        ConfigItem(
            label="Invert Swipe Direction",
            key="workspace_swipe_invert",
            scope="gestures",
            type_="bool",
            default=True,
            group="Navigation Behavior",
            extended_help="**Invert Direction**\n\nInverts the swipe direction. When enabled, this mimics 'natural scrolling' on macOS and modern trackpad drivers."
        ),
        ConfigItem(
            label="Create New Workspace on Swipe",
            key="workspace_swipe_create_new",
            scope="gestures",
            type_="bool",
            default=True,
            group="Navigation Behavior",
            extended_help="**Create New Workspace**\n\nAutomatically creates a new, empty workspace when swiping past the last active workspace."
        ),
        ConfigItem(
            label="Allow Swiping Forever",
            key="workspace_swipe_forever",
            scope="gestures",
            type_="bool",
            default=False,
            group="Navigation Behavior",
            extended_help="**Swipe Forever**\n\nAllows you to continuously swipe past neighbouring workspaces without stopping at the edge."
        ),
        ConfigItem(
            label="Use Relative Workspaces ('r' prefix)",
            key="workspace_swipe_use_r",
            scope="gestures",
            type_="bool",
            default=False,
            group="Navigation Behavior",
            extended_help="**Relative Workspaces**\n\nUses the 'r' prefix (relative) instead of the 'm' prefix when switching workspaces. Useful for specific multi-monitor behaviors."
        ),
        ConfigItem(
            label="Lock Swipe Direction",
            key="workspace_swipe_direction_lock",
            scope="gestures",
            type_="bool",
            default=True,
            group="Axis Locking",
            extended_help="**Direction Lock**\n\nLocks the swipe axis (horizontal or vertical) once the initial direction is established, preventing diagonal drifting."
        ),
        ConfigItem(
            label="Direction Lock Threshold",
            key="workspace_swipe_direction_lock_threshold",
            scope="gestures",
            type_="int",
            default=10,
            min_val=0,
            max_val=100,
            step=2,
            group="Axis Locking",
            extended_help="**Lock Threshold**\n\nDistance in pixels the swipe must travel before the direction lock fully engages."
        ),
    ],

    # -------------------------------------------------------------------------
    # TAB 2: PROFILES & RESET
    # -------------------------------------------------------------------------
    2: [
        ConfigItem(
            label="Apply 'Fast & Fluid' Profile",
            key="preset_fluid",
            scope="DEFAULT",
            type_="preset",
            default=None,
            group="Profiles",
            preset_payload={
                "gestures.workspace_swipe_distance": 200,
                "gestures.workspace_swipe_cancel_ratio": 0.3,
                "gestures.workspace_swipe_min_speed_to_force": 20,
                "gestures.workspace_swipe_direction_lock": False
            },
            extended_help="**Fast & Fluid**\n\nRequires very little finger travel to switch workspaces. Disables axis locking for a looser, more sensitive feel."
        ),
        ConfigItem(
            label="Apply 'Firm & Intentional' Profile",
            key="preset_firm",
            scope="DEFAULT",
            type_="preset",
            default=None,
            group="Profiles",
            preset_payload={
                "gestures.workspace_swipe_distance": 500,
                "gestures.workspace_swipe_cancel_ratio": 0.7,
                "gestures.workspace_swipe_min_speed_to_force": 60,
                "gestures.workspace_swipe_direction_lock": True,
                "gestures.workspace_swipe_direction_lock_threshold": 25
            },
            extended_help="**Firm & Intentional**\n\nRequires long, deliberate swipes to trigger a workspace change. Highly resistant to accidental triggers."
        ),
        ConfigItem(
            label="Factory Reset Everything",
            key="preset_factory_reset",
            scope="DEFAULT",
            type_="preset",
            default=None,
            group="Reset",
            preset_payload={
                "__ALL_DEFAULTS__": True
            },
            extended_help="**Factory Reset**\n\nReverts all settings across all tabs back to their default values."
        ),
    ]
}
