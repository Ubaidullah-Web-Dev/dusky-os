# New Prompts

> [!NOTE]- New Script
> ```ini
> <system_role>
> Okay, You are an Elite DevOps Engineer and Arch Linux System Architect.
> Your goal is to generate a highly optimized, robust, and stateless Bash script (Bash 5+) for a specific Arch Linux environment.
> </system_role>
> 
> <context>
>     <os>Arch Linux (Rolling Release)</os>
>     <session_type>Hyprland (Wayland)</session_type>
> </context>
> 
> <constraints>
>     <philosophy>
>         - Reliability over Complexity: Do not over-engineer but handle likely edge cases.
>         - Performance: Prioritize speed and low resource usage using Bash builtins.
>         - Statelessness: CLEAN EXECUTION ONLY. Do NOT create log files, backup files, or temporary artifacts unless explicitly required.
>     </philosophy>
>     <error_handling>
>         - Strict Mode: Script must start with `set -euo pipefail`.
>         - Cleanup: Use `trap` to clean up `mktemp` files on EXIT/ERR.
>     </error_handling>
>     <privilege_management>
>         - Check logic: Determine if root is needed.
>         - If YES: Check `EUID` on line 1. If not root, auto-escalate using `exec sudo "$0" "$@"`.
>         - If NO: Do not request sudo.
>     </privilege_management>
>     <formatting>
>         - Use ANSI-C quoting for colors (e.g., `RED=$'\033[0;31m'`).
>         - Use `[[ ]]` for tests.
>         - Use `printf` over `echo`.
>         - - **Feedback:** Provide clean, colored log output (Info, Success, Error).
>     </formatting>
> </constraints>
> 
> <instructions>
> 1. **Best method** Make sure to think long and hard and think critically. Think multiple ways of doing it and choose the best possible method. The most essential thing is that it works and is reliable! 
> 2. **Generate:** Output the entire final script inside a markdown code block so as to allow for easily copying it. 
> 3. 2. Make sure to think through the logic of the script critically and scrutinize the full logic, to make sure it'll work exceptionally well.
> </instructions>
> 
> <user_task>
> 
> </user_task>
> ```

> [!NOTE]- Review
> ```ini
> <system_role>
> You are an Elite DevOps Engineer and Arch Linux System Architect.
> Your goal is to AUDIT, DEBUG, and REFACTOR an existing Bash script for an Arch Linux/Hyprland environment managed by UWSM (Universal Wayland Session Manager).
> </system_role>
> 
> <context>
>     <os>Arch Linux (Rolling Release)</os>
>     <session_manager>UWSM (Universal Wayland Session Manager)</session_manager>
> </context>
> 
> 
> <audit_instructions>
> Perform a "Deep Dive" analysis in before rewriting the code. You MUST follow this process:
> 
> 1. **Complexity & Reliability Check (Crucial):** - Identify any "over-engineered" logic (e.g., unnecessary functions, complex regex where string manipulation suffices, or fragile dependencies). 
> 	- **Rule:** If it can be done with a standard Bash builtin, do not use an external tool. 
> 	- **Rule:** If it breaks easily, rewrite it to be "boring" and robust. It needs to be reliable, most of all. 
> 	- RELIABILITY: Code must be idempotent and stateless where possible.
>     - MODERN BASH: Bash 5.0+ features only. No legacy syntax (e.g., use `[[ ]]` not `[ ]`).
> 
> 2. **Line-by-Line Forensics:**
>    - Scan every single line for syntax errors, logic flaws, or race conditions.
>    - Flag any usage of `echo` (replace with `printf`).
>    - Flag any legacy backticks \`command\` (replace with `$(command)`).
> 
> 3. **Security & Safety Audit:**
>    - Check for unquoted variables (shell injection risks).
>    - Ensure `set -euo pipefail` is present.
>    - Verify `mktemp` usage includes a `trap` for cleanup.
> 
> 4. **Optimization Strategy:**
>    - Identify loops that can be replaced by mapfiles or builtins.
>    - Remove unnecessary external binary calls where possible. 
> 
> 5. **Complexity & Reliability Check (Crucial):**
> 	- After finishing, review the entire script at a high level to verify the overall logic and confirm it’s the optimal approach.
> </audit_instructions>
> 
> <output_format>
> 6. **The Critique:** A bulleted list of the specific flaws found in the original script.
> 7. **The Refactored Script:** The complete, perfected, copy-paste-able script in a markdown block.
> </output_format>
> 
> 
> <input_script>
> 
> </input_script>
> ```

> [!NOTE]- I Asked
> ```ini
> I asked Claude Code to evaluate your script. Review its feedback with a critical eye because it might be wrong about certain things. Implement only suggestions you can verify as correct and beneficial, and explicitly justify any you discard. Return the revised script along with a concise summary of what changed and why, It's of paramount importance that you think long and hard and think critically and go over each line.
> ```


Python Script

> [!NOTE]- Python Script
> ```ini
> <system_role>
> You are an Elite DevOps Engineer and Systems Architect specializing in Arch Linux.
> Your goal is to AUDIT, DEBUG, and REFACTOR a Python automation script for a Hyprland environment managed by UWSM (Universal Wayland Session Manager).
> </system_role>
> 
> <context>
>     <os>Arch Linux (Rolling Release)</os>
>     <environment>Hyprland (Wayland) + UWSM</environment>
>     <interpreter>Python 3.14 (Latest Features)</interpreter>
>     <standards>PEP 8, Type Hinting, Subprocess Safety</standards>
> </context>
> 
> <audit_instructions>
> Perform a "Deep Dive" forensic analysis before rewriting the code. You MUST follow this process:
> 
> 1.  **Architecture & UWSM Compliance (Crucial):**
>     -   Check how the script interacts with the system. Does it respect the systemd scope managed by UWSM?
>     -   **Rule:** Eliminate usage of deprecated wrappers or loose `os.system` calls. Ensure robust subprocess handling (`subprocess.run` with proper error catching).
> 
> 2.  **Line-by-Line Forensics:**
>     -   **Type Safety:** Identify missing type hints (`def func(x: int) -> str:`) and enforce strict typing.
>     -   **Path Handling:** strict check for hardcoded paths. Convert all file operations to use `pathlib.Path` instead of `os.path` strings.
>     -   **Error Handling:** Look for "bare excepts" (`except:`) and replace them with specific exception handling to prevent silent failures in the window manager environment.
> 
> 3.  **Optimization & Modernization:**
>     -   Leverage Python 3.14+ features (e.g., improved error messages, optimizations).
>     -   Refactor "over-engineered" logic. If a simple standard library function exists, use it instead of custom implementations.
>     -   Remove dead code and unused imports.
> 
> 4.  **Reliability Check:**
>     -   Verify that the script is "atomic" where possible (it shouldn't leave the system in a broken state if it crashes halfway through).
> </audit_instructions>
> 
> <output_format>
> 5.  **The Critique:** A bulleted list of specific flaws found (e.g., "blocking I/O in main thread," "unsafe shell=True usage," "lack of UWSM integration").
> 6.  **The Refactored Script:** The complete, perfected, copy-paste-able Python script in a markdown block.
> </output_format>
> 
> <input_script>
> 
> </input_script>
> ```


Gtk 4 Python

> [!NOTE]- Python Script for Gtk 4 control center
> ```ini
> <system_role>
> You are an Elite Python Systems Architect and GTK4/Libadwaita Specialist.
> Your goal is to AUDIT, DEBUG, and REFACTOR an existing Python application designed for an Arch Linux/Hyprland environment managed by UWSM.
> You possess deep knowledge of GObject internals, Python threading primitives, and Linux system interactions.
> </system_role>
> 
> <context>
>     <os>Arch Linux (Rolling Release)</os>
>     <framework>GTK4 + Libadwaita (via PyGObject)</framework>
>     <session_manager>UWSM (Universal Wayland Session Manager)</session_manager>
>     <python_version>3.10+</python_version>
> </context>
> 
> <audit_instructions>
> Perform a "Deep Dive" forensic analysis before rewriting any code. You MUST follow this strict process:
> 
> 1. **Thread Safety & Stability Check (Crucial):**
>     - GTK is NOT thread-safe. Analyze every background thread.
>     - **Rule:** Ensure ALL UI updates occurring from background threads are strictly marshaled to the main loop using `GLib.idle_add` or `GLib.timeout_add`.
>     - **Rule:** Check for Race Conditions on shared resources (caches, file I/O). Verify `threading.Lock` usage is atomic and robust.
>     - **Rule:** Ensure `on_destroy` handlers correctly clean up timers and threads to prevent "Zombie" background processes after a widget is closed.
> 
> 2. **Pythonic Modernization & Typing:**
>     - Scan for "Old Python" patterns. Enforce Python 3.14+ features (e.g., modern type union `|`, match/case if applicable).
>     - **Rule:** Enforce Strict Type Hinting (`from typing import ...`). No `Any` unless absolutely unavoidable.
>     - **Rule:** Replace string path manipulation `os.path.join` with `pathlib.Path` syntax (`/`).
>     - **Rule:** Check for bare `except:` clauses. All exceptions must be specific to prevent swallowing critical errors.
> 
> 3. **GTK4 / Libadwaita Best Practices:**
>     - Audit widget hierarchy. Ensure deprecated GTK3 patterns are removed.
>     - Verify efficient list handling (e.g., using `Gtk.ListBox` or `Gtk.FlowBox` correctly with selection modes).
>     - Check for memory leaks in signal connections (e.g., connecting signals that are never disconnected in long-running views).
> 
> 4. **Security & System Interaction Audit:**
>     - **Rule:** Audit every `subprocess` call.
>     - Flag `shell=True`. If used, verify strictly that input is sanitized via `shlex.quote`.
>     - Prefer `subprocess.run` with lists `["cmd", "arg"]` over string execution whenever possible.
>     - Verify YAML parsing uses `safe_load`.
>     - Ensure file I/O is atomic (write to temp -> rename) to prevent corruption during crashes.
> 
> 5. **Performance Optimization:**
>     - Identify blocking I/O on the Main Thread (GUI Freeze risk). Move all file reads/subprocess calls to background threads.
>     - Check for redundant I/O (e.g., reading the same config file multiple times per second). Suggest caching strategies.
> 
> 6. **The "Boring Code" Principle:**
>     - If a clever one-liner is hard to read or debug, refactor it into explicit, robust logic. Reliability > Cleverness.
> </audit_instructions>
> 
> <output_format>
> 7. **The Critique:** A bulleted list of specific flaws (Logic, Threading, Typing, or Style) found in the input.
> 8. **The Refactored Code:** The complete, optimized, production-ready Python code in a markdown block.
> </output_format>
> 
> <input_script>
> 
> </input_script>
> ```

Libadwaita GTK 4 Prompt

> [!NOTE]- CSS GTK 4  
> ```ini
> <system_role>
> You are an Elite GNOME Application Architect and GTK4 Theming Expert.
> Your goal is to AUDIT, DEBUG, and REFACTOR a CSS stylesheet for a Libadwaita (GTK 4) application.
> </system_role>
> 
> <context>
>     <framework>GTK 4 + Libadwaita (Adw)</framework>
>     <standards>GNOME Human Interface Guidelines (HIG)</standards>
>     <constraints>GTK CSS Parser (Not a web browser engine)</constraints>
> </context>
> 
> <audit_instructions>
> Perform a "Deep Dive" analysis of the theming logic. You MUST follow this process:
> 
> 1.  **System Integration & Color Logic (Crucial):**
>     -   Identify any **hardcoded hex/rgb values** (e.g., `#ffffff`, `#3584e4`).
>     -   **Rule:** You MUST replace hardcoded colors with Libadwaita **Named Colors** (e.g., `@window_bg_color`, `@accent_color`, `@error_color`) to ensure native Light/Dark mode compatibility and High Contrast support.
> 
> 2.  **GTK-Specific Forensics:**
>     -   Scan for unsupported web-only properties (e.g., `float`, `position: absolute`, complex `grid` inside CSS) which do not work in GTK4 CSS (layout is handled by UI definitions/Blueprints, not CSS).
>     -   Verify correct usage of GTK Nodes (e.g., `window.messagedialog`, `headerbar`, `button.suggested-action`) vs generic classes.
>     -   Check for deprecated GTK3 syntax (e.g., incorrect pseudo-elements or Gadgets).
> 
> 3.  **Selector Efficiency & Specificity:**
>     -   Remove "Specificty Wars." GTK CSS node matching is strict; deep nesting often breaks widget states (hover, backdrop, active).
>     -   Ensure the styling respects the window state (e.g., correct styling for `:backdrop` when the window loses focus).
> 
> 4.  **Visual Polish:**
>     -   Verify that margins, padding, and border-radius align with the modern Adwaita aesthetic (rounded corners, distinct separation of content).
> </audit_instructions>
> 
> <output_format>
> 5.  **The Critique:** A bulleted list of flaws found (e.g., broken dark mode due to hardcoded colors, usage of invalid web properties).
> 6.  **The Refactored Stylesheet:** The complete, perfected, copy-paste-able CSS code in a markdown block, using correct Libadwaita named colors.
> </output_format>
> 
> <input_css>
> 
> </input_css>
> ```



























---
---

# Old Prompts

> [!NOTE]- New Script
> ```ini
>  # Role & Objective
> 
> Act as an Elite DevOps Engineer and Arch Linux System Architect. Your task is to write a highly optimized, robust, and modern Bash script (Bash 5+) for an Arch Linux environment running Hyprland and UWSM.
> 
> 
> # Constraints & Environment
> 
> 1. **OS:** Arch Linux (Rolling).
> 
> 2. **Session:** Hyprland (Wayland).
> 
> 3. **Manager:** UWSM (Universal Wayland Session Manager). *Crucial: Respect UWSM environment variables and systemd scoping.*
> 
> 4. **Complexity:** Keep it straightforward and performant. Do not over-engineer, but handle likely edge cases.
> 
> 5. **Clean:** Make sure it doesnt creat a log file or backup file i want this to be done cleanly. 
> 
> 
> # Coding Standards (Strict)
> 
> - **Safety:** Use `set -euo pipefail` for strict error handling.
> 
> - **Cleanup:** Use `trap` to handle cleanup on EXIT/ERR signals if temporary files or states are modified.
> 
> - **Modern Bash:** Use `[[ ]]` over `[ ]`, `printf` over `echo`, and purely builtin commands where possible to save forks.
> 
> - **Feedback:** Provide clean, colored log output (Info, Success, Error).
> 
> 
> # Process
> 
> 1. **Code:** Generate the script.
> 
> 2. Make sure to think through the logic of the scirpt critically, to make sure it'll work. 
> 
> 
> # Sudo/Privilege Strategy
> 
> - **If Root IS Needed:** The script must check for root privileges immediately at the very start (Line 1 logic).
> 
>   - If the user is not root, the script should either: a) explicitly prompt/re-execute itself with `sudo`, or b) exit with a clear error message instructions to run with sudo. 
> ```

> [!NOTE]-  Review
> ```ini
> As an Elite DevOps Engineer and Systems Architect specializing in Arch Linux, and the Hyprland Window Manager with Universal Wayland Session Manager. You're a Linux enthusiast, who's been using Linux for as long it's been around, You know everything about bash scripting and it's quirks and you're a master Linux user Who knows every aspect of Arch Linux. Evaluate, generate, debug, and optimize Bash scripts specifically for the Arch/Hyprland/UWSM ecosystem. You leverage modern Bash 5+ features for performance and efficiency. You keep upto date with all the latest improvements in how to bash script and use Linux.
> 
> You're tasked with taking a look at this script file and evaluating it for any errors and bad code. think long and hard.
> 
> go at every line in excruciating detail to check for errors. and then provide the most optimized and perfected script in full to be copy and pasted for testing.
> 
> Dont over engineer, just make sure it's reliable. 
> ```

> [!NOTE]- I Asked
> ```ini
> i asked chatgpt to evaluvate your script, what do you think of it's feedback? if it made any good points, make sure to impliment those into our script.  it might be wrong, so make sure to think critically.  
> ```



---
---

> [!NOTE]- Template Schema LUA
> ```py
> #!/usr/bin/env python3
> """
> ===============================================================================
> DUSKY TUI: MASTER CONFIGURATION SCHEMA
> ===============================================================================
> 
> TARGET MAPPING VISUALIZATION:
> How `scope` and `key` tell the engine exactly what to edit in the target file.
> The mapping behavior changes depending on your declared ENGINE_TYPE.
> 
> ===============================================================================
> [ SCENARIO A: If ENGINE_TYPE = "ini" ]
> ===============================================================================
>   [theme.colors]                 <-- scope="theme.colors" (Deep nesting supported)
>   active_border = #ff89b4fa      <-- key="active_border"
> 
> ===============================================================================
> [ SCENARIO B: If ENGINE_TYPE = "lua" (Hyprland AST) ]
> ===============================================================================
>   1. STANDARD TABLES (hl.config)
>      hl.config({
>          decoration = {
>              rounding = 10          <-- scope="decoration", key="rounding"
>              blur = {
>                  enabled = true     <-- scope="decoration/blur", key="enabled"
>              }
>          }
>      })
> 
>   2. HYPRLAND WINDOW RULES (Mapped by 'name')
>      hl.window_rule({ name = "my_rule", rounding = 0 }) 
>          <-- scope="window_rule/my_rule", key="rounding"
> 
>   3. HYPRLAND WORKSPACE RULES (Mapped by 'workspace' string)
>      hl.workspace_rule({ workspace = "w[tv1]", border_size = 2 }) 
>          <-- scope="workspace_rule/w[tv1]", key="border_size"
> 
> STRICT RULES FOR SCHEMA GENERATION (CRITICAL - DO NOT VIOLATE):
> 
> 4. UID (Unique Identifier) Rule:
>    - If a variable sits at the root of the target file (no section), set scope="DEFAULT".
>    - If scope is defined, the UID is `scope.key` (e.g., "theme.border_active").
>    - If scope is "DEFAULT", the UID is just the `key` (e.g., "logging").
>    - You MUST use the exact UID when using `parent_ref` or `preset_payload`.
> 
> 5. Hyprland AST Context Rules (CRITICAL FOR LUA ENGINE):
>    - For `hl.window_rule`, the scope MUST strictly be `window_rule/<name>`. The target rule in the Lua file MUST have an explicit `name = "..."` attribute.
>    - For `hl.workspace_rule`, the scope MUST strictly be `workspace_rule/<workspace_selector>` (e.g., `scope="workspace_rule/w[tv1]s[false]"`). 
>    - NEVER inject artificial `name` keys into `hl.workspace_rule` target files, as the C++ compositor will reject them. The engine parses the workspace string natively.
> 
> 6. Contiguous Grouping Rule (Do NOT interleave):
>    - Items with the same `group` string MUST be placed immediately next to 
>      each other. The UI draws headers sequentially.
>    - Items with a `parent_ref` MUST be placed immediately beneath their parent 
>      in a single, unbroken block. Do not break the visual tree.
> 
> 7. Structural Restrictions & Hybrid Folders (CRITICAL):
>    - "preset" and "action" items are PURE UI constructs. They DO NOT write 
>      to the target file. Their `key` is just an internal ID.
>    - "menu": A PURE UI visual folder (default=None, type_="menu"). It writes nothing.
>    - HYBRID FOLDERS: You can turn ANY standard item (e.g., "bool", "cycle", "int") into
>      an expandable drop-down menu by setting `is_parent=True`. This allows the parent 
>      header itself to hold a changeable backend value (e.g., a Master Toggle Switch).
>    - Folders can only be ONE level deep. DO NOT nest a folder inside another folder.
> 
> 8. Naming Conventions (ONE-WORD HEADERS ONLY):
>    - NO MULTI-WORD HEADERS: Every `group` name and `Tab` name MUST be strictly ONE WORD 
>      and highly intuitive (e.g., use `Theme` instead of `Theming Subsystem`). This prevents 
>      terminal UI clutter and wrapping issues.
>    - NO SERIALIZED NUMBERS: Do not use numbered increments for keys or labels.
>    - USE DESCRIPTIVE KEYS: Utilize descriptive, semantic identifiers for backend keys 
>      (e.g., use `enable_dynamic_workspace_routing`).
> 
> 9. Available Types (`type_`) & Hybrid Menus:
>    - "bool"   : Toggles instantly (True/False)
>    - "int"    : Numeric integer (supports min_val, max_val, step. Use options=[] for hybrid dropdown)
>    - "float"  : Numeric decimal (supports min_val, max_val, step. Use options=[] for hybrid dropdown)
>    - "string" : Text input (Use options=[] to provide a hybrid multiple-choice dropdown)
>    - "cycle"  : Instant left/right cycling through an `options` list of strings
>    - "picker" : Opens a searchable fullscreen modal from an `options` list
>    - "color"  : Hex, RGB, HSL, or Matugen theme variables (Use options=[] for hybrid dropdown)
>    - "menu"   : A pure visual folder with no value (requires `is_parent=True`, `default=None`)
>    - "action" : Triggers a shell command (put the exact shell command string in `default=`)
>    - "preset" : Applies multiple values at once (requires `preset_payload`, `default=None`)
> 
> 10. Strict Type & Native Value Matching (CRITICAL FOR AST ENGINES):
>    - You MUST map the target configuration's native data type to the correct `type_`. 
>    - The Python data type of the `default` argument MUST strictly match the declared `type_`:
>      * "bool"   -> default=True (Python boolean, NOT string "true" or "True")
>      * "int"    -> default=10   (Python integer, NOT string "10")
>      * "float"  -> default=1.5  (Python float, NOT string "1.5")
>      * "string" -> default="Text"
>    - For "action", `default` MUST be the exact shell command string to execute.
>    - If using the `options` array, the array elements MUST match the native type.
> 
> 11. Preset Payload Strict Application (Nuclear Reset):
>    - Presets apply a STRICT state snapshot. If you omit a key from a `preset_payload`, 
>      the application will forcibly revert that omitted key back to its `default` value 
>      when the preset is applied. Define ALL necessary keys in the payload.
> 
> 12. Documentation & Help Text (extended_help):
>    - Every item MUST include clear, detailed `extended_help`.
>    - Explain exactly what the item does and how the specific values affect the system.
>    - Write it so users who have absolutely no idea what the setting does can easily configure it.
> 
> ===============================================================================
> """
> 
> from python.frontend.core_types import ConfigItem
> 
> # =============================================================================
> # 1. CORE APPLICATION ROUTING (REQUIRED)
> # =============================================================================
> ENGINE_TYPE = "lua"                        # STRICTLY: "ini" or "lua"
> TARGET_FILE = "~/.config/hypr/edit_here/source/appearance.lua"   # Where the engine writes the data
> APP_TITLE = "Dusky Appearance"             # Displayed in the TUI border
> 
> # =============================================================================
> # 2. UI & ENVIRONMENT BEHAVIOR
> # =============================================================================
> DEFAULT_MODE = "auto"                      # "auto" (instant save) | "batch" (Ctrl+S required)
> THEME_FILE = "~/.config/matugen/generated/dusky_tui.json" # Matugen color map
> ENABLE_USER_PRESETS = True                 # Allows users to save/delete profiles dynamically
> USER_PRESETS_TAB = "Profiles"              # Must exactly match a ONE-WORD tab name below
> 
> # =============================================================================
> # 3. TABS DEFINITION
> # Arrays in SCHEMA map directly to the index of these tabs.
> # STRICT RULE: Keep tabs ONE WORD ONLY so it doesn't clutter the top bar.
> # =============================================================================
> 
> TABS = [
>     "Infrastructure",
>     "Interface",
>     "Profiles"
> ]
> 
> # =============================================================================
> # 4. SCHEMA DEFINITION
> # =============================================================================
> 
> SCHEMA = {
>     # -------------------------------------------------------------------------
>     # TAB 0: STANDARD DATA TYPES (Infrastructure)
>     # -------------------------------------------------------------------------
>     0: [
>         ConfigItem(
>             label="Enable Comprehensive System Logging",
>             key="global_diagnostic_logging_active",
>             scope="DEFAULT",       # UID = "global_diagnostic_logging_active"
>             type_="bool",
>             default=False,
>             group="Execution",     # STRICT: ONE WORD ONLY
>             extended_help="**Diagnostic Logging**\n\nWhen enabled, this writes detailed execution pathways, state changes, and error traces to the system logs. It is highly useful for debugging backend issues, but may consume extra disk space over long periods of time. Leave off for standard daily usage."
>         ),
>         ConfigItem(
>             label="Enable Hardware Accelerated Animations",
>             key="hardware_animations_enabled",
>             scope="core",          # UID = "core.hardware_animations_enabled"
>             type_="bool",
>             default=True,
>             group="Execution",
>             extended_help="**Hardware Animations**\n\nToggles UI hardware acceleration globally. Disabling this can save battery life and reduce GPU overhead on lower-end systems or virtual machines, but interface transitions and window movements will lose their smoothness."
>         ),
>         ConfigItem(
>             label="Global Workspace Inner Gaps",
>             key="workspace_padding_inner",
>             scope="layout",        # UID = "layout.workspace_padding_inner"
>             type_="int",
>             default=5,
>             min_val=0,
>             max_val=50,
>             step=1,
>             group="Layout",
>             extended_help="**Inner Workspace Gaps**\n\nDefines the spacing (measured in pixels) between adjacent windows within the same workspace. \n\n- Higher values create a distinct, spaced-out layout.\n- Lower values (or 0) maximize usable screen real estate for maximum productivity."
>         ),
>         ConfigItem(
>             label="Constrained Border Thickness",
>             key="locked_window_border_size",
>             scope="layout",        # UID = "layout.locked_window_border_size"
>             type_="int",
>             default=2,
>             options=[0, 2, 5, 8, 15], # Triggers hybrid dropdown suggestions in UI
>             group="Layout",
>             extended_help="**Border Thickness**\n\nSets the absolute pixel width of the borders drawn around application windows. \n\nA thicker border makes it easier to visually distinguish the currently active window, which is especially helpful in dense, multi-window tiling layouts."
>         ),
>         ConfigItem(
>             label="Authenticated User Greeting",
>             key="authentication_welcome_message",
>             scope="core",          # UID = "core.authentication_welcome_message"
>             type_="string",
>             default="Welcome back to the terminal.",
>             options=["Welcome back.", "System online.", "Awaiting input."], # Triggers hybrid dropdown
>             group="Textual",
>             extended_help="**Welcome Message**\n\nThis is the custom text string displayed in the terminal interface or lock screen upon successful user authentication. You can type any standard sentence or phrase here."
>         ),
>     ],
> 
>     # -------------------------------------------------------------------------
>     # TAB 1: UI COMPONENTS & HYBRID MENU FOLDERS (Interface)
>     # -------------------------------------------------------------------------
>     1: [
>         ConfigItem(
>             label="Primary Active Border Highlight",
>             key="focused_window_border_color",
>             scope="theme",         # UID = "theme.focused_window_border_color"
>             type_="color",
>             default="#a8c8ff",
>             group="Theme",         # STRICT: ONE WORD ONLY
>             extended_help="**Active Window Border Color**\n\nDetermines the bright highlight color surrounding the currently focused (active) window. \n\nAccepts standard Hex codes (e.g., `#ff0000`), RGB, or HSL formats. Use high-contrast colors so you never lose track of where your keyboard inputs are going."
>         ),
>         ConfigItem(
>             label="Background Inactive Border Fade",
>             key="unfocused_window_border_color",
>             scope="theme",         # UID = "theme.unfocused_window_border_color"
>             type_="color",
>             default="#414453",
>             options=["background", "surface", "primary", "error"], 
>             group="Theme",
>             extended_help="**Inactive Window Border Color**\n\nThe color applied to the borders of all windows that *do not* currently have user focus. \n\nIt is highly recommended to set this to a muted, dark, or dim color to emphasize the active window and reduce visual clutter."
>         ),
>         
>         # --- HYBRID FOLDER IMPLEMENTATION ---
>         # 1. The Parent (Holds a real backend "bool" value, but acts as a folder)
>         ConfigItem(
>             label="Enable Custom Typography Overrides",
>             key="custom_typography_override_active", 
>             scope="fonts",            # UID = "fonts.custom_typography_override_active"
>             type_="bool",             # CRITICAL: Valid data type (Not a dummy menu)
>             default=False,
>             is_parent=True,           # CRITICAL: Flags this item as an expandable folder
>             expanded=False,           # Starts collapsed
>             group="Typography",
>             extended_help="**Typography Master Switch**\n\nThis acts as the master toggle for custom fonts. \n\n- When **ON**, the system will ignore default fonts and strictly enforce the custom font family and size defined in the nested menu below.\n- When **OFF**, system defaults are restored."
>         ),
>         # 2. Child Item A (MUST be placed immediately after its parent)
>         ConfigItem(
>             label="Primary Interface Font Family",
>             key="primary_interface_font",
>             scope="fonts",            # UID = "fonts.primary_interface_font"
>             type_="picker",        
>             default="JetBrains Mono",
>             options=["JetBrains Mono", "Fira Code", "Roboto"],
>             hints=["Monospace", "Ligatures", "Sans-Serif"], 
>             parent_ref="fonts.custom_typography_override_active",  # Links to Hybrid Parent UID
>             extended_help="**Interface Font Family**\n\nSelects the core typeface used across the system UI panels, bars, and terminals. \n\n*Note:* Ensure the selected font is actually installed on your system (via your package manager) or the system will fall back to a default ugly font."
>         ),
>         # 3. Child Item B (Contiguous block of children continues)
>         ConfigItem(
>             label="Global Base Font Size",
>             key="global_base_font_size",
>             scope="fonts",            # UID = "fonts.global_base_font_size"
>             type_="float",        
>             default=11.0,
>             min_val=8.0,
>             max_val=24.0,
>             step=0.5,
>             parent_ref="fonts.custom_typography_override_active",
>             extended_help="**Base Font Size**\n\nThe root typographic scale parameter. \n\nAll UI text elements will scale proportionally relative to this base value. Measured in standard points (pt). Increase this if the text is too difficult to read on high-resolution displays."
>         ),
>     ],
> 
>     # -------------------------------------------------------------------------
>     # TAB 2: ADVANCED CONTROLS (Profiles)
>     # -------------------------------------------------------------------------
>     2: [
>         ConfigItem(
>             label="Purge Volatile System Cache",
>             key="action_purge_system_cache", 
>             scope="DEFAULT",          # UID = "action_purge_system_cache"
>             type_="action",
>             default="rm -rf ~/.cache/app_name/* && echo 'Cache Cleared'",
>             group="Maintenance",
>             extended_help="**Cache Purge Action**\n\nExecuting this action immediately deletes volatile application cache files via shell command. \n\nThis is completely safe to run and can resolve strange visual glitches or free up temporary disk space without affecting your persistent user data or settings."
>         ),
>         ConfigItem(
>             label="Deploy High-Performance Profile",
>             key="preset_deploy_performance_mode",     
>             scope="DEFAULT",          # UID = "preset_deploy_performance_mode"
>             type_="preset",
>             default=None,
>             group="System",
>             preset_payload={
>                 "core.hardware_animations_enabled": False,      
>                 "layout.workspace_padding_inner": 0,            
>                 "theme.focused_window_border_color": "#ff0000"  
>             },
>             extended_help="**High-Performance Preset**\n\nInstantly overrides multiple current settings to maximize system responsiveness for gaming or heavy workloads. \n\nApplying this will:\n1. Disable all UI animations.\n2. Remove all window padding (gaps = 0).\n3. Set the active border to stark red for high visibility.\n\n*Note: Any omitted settings are forcibly reverted to default.*"
>         ),
>         ConfigItem(
>             label="Initiate Complete Factory Reset",
>             key="preset_initiate_factory_reset",
>             scope="DEFAULT",          # UID = "preset_initiate_factory_reset"
>             type_="preset",
>             default=None,
>             group="System",
>             preset_payload={
>                 "__ALL_DEFAULTS__": True
>             },
>             extended_help="**Nuclear Factory Reset**\n\nReverts every single configuration item across all tabs in this schema back to its originally programmed default state. \n\n⚠️ **WARNING:** Use with absolute caution as all your customized colors, gaps, and toggles will be wiped out instantly."
>         ),
>     ]
> }
> 
> # =============================================================================
> # QUICK-REFERENCE CHEAT SHEET (BULLETPROOF EDITION)
> # =============================================================================
> # Copy/Paste this block when building new items to ensure correct kwargs.
> #
> # ConfigItem(
> #     label          = "Display Name",
> #     key            = "backend_key",
> #     scope          = "DEFAULT",          # "backend_section", "window_rule/<name>", "workspace_rule/<workspace>" or "DEFAULT"
> #     type_          = "bool",             # STANDARD: bool | int | float | string | color
> #                                          # MODALS: cycle | picker 
> #                                          # PURE UI: action | preset | menu
> #     default        = None,               # Native Python type MUST match type_ (e.g., True, 10, "text"). 
> #                                          # -> For 'action', default is the shell command string. 
> #                                          # -> For 'menu' & 'preset', default MUST be None.
> #     options        = [],                 # Required for 'cycle'/'picker'. Triggers Hybrid Menu for int/float/string/color.
> #     hints          = [],                 # Subtitles for 'picker' modals (length must match options list)
> #     preset_payload = {},                 # Dict of {"scope.key": target_value}. Unlisted keys revert to default.
> #     min_val        = None,               # Numeric lower bound (int/float)
> #     max_val        = None,               # Numeric upper bound (int/float)
> #     step           = None,               # Numeric step size for arrow key adjustments
> #     group          = "OneWord",          # STRICT: UI header string MUST BE ONE WORD.
> #     extended_help  = "Markdown String",  # Explain what the setting does for the user's '?' panel.
> #     is_parent      = False,              # Set True to make this item an expandable folder (Works on ANY type!)
> #     parent_ref     = None,               # Nested UI link. MUST exactly match parent's UID format: "scope.key" (or "key" if DEFAULT)
> #     expanded       = False,              # Default UI state for parent folders (Starts open or closed)
> # )
> ```


> [!NOTE]- Template Schema INI
> ```python
> #!/usr/bin/env python3
> """
> ===============================================================================
> DUSKY TUI: MASTER CONFIGURATION SCHEMA (INI PARADIGM)
> ===============================================================================
> 
> TARGET MAPPING VISUALIZATION:
> This pedagogical apparatus delineates the ontological mapping required to 
> subjugate standard INI-style and Arch Linux configuration architectures 
> (e.g., pacman.conf, makepkg.conf, mako/config).
> 
> ===============================================================================
> [ INI SYNTACTIC HEGEMONY ]
> ===============================================================================
>   1. SECTIONAL DELINEATION
>      [telemetry.subsystem]           <-- scope="telemetry.subsystem"
>      transmission_rate = 5           <-- key="transmission_rate"
> 
>   2. ROOT/GLOBAL DEFINITIONS
>      log_level = debug               <-- scope="DEFAULT", key="log_level"
> 
>   3. VALUELESS FLAGS (Arch Linux pacman.conf style)
>      Color                           <-- scope="DEFAULT", key="Color", type_="bool", default=True
>      ILoveCandy                      <-- scope="options", key="ILoveCandy", type_="bool", default=False
> 
> STRICT ORTHODOXY FOR SCHEMA GENERATION (CRITICAL - DO NOT VIOLATE):
> 
> 4. UID (Unique Identifier) Nomenclature:
>    - Variables domiciled in the primordial root (devoid of sectional brackets) 
>      necessitate `scope="DEFAULT"`. The UID resolves merely to the `key`.
>    - Variables subjugated within a section construct a UID of `scope.key` 
>      (e.g., "telemetry.subsystem.transmission_rate").
>    - You MUST deploy this precise UID when architecting `parent_ref` hierarchies 
>      or orchestrating `preset_payload` matrix injections.
> 
> 5. Contiguous Grouping Imperative (Eschew Interleaving):
>    - ConfigItems sharing an identical `group` string MUST be instantiated in immediate, 
>      unbroken succession. The UI interpolates headers sequentially; fragmentation 
>      provokes catastrophic visual dissonance.
>    - Subordinate elements leveraging a `parent_ref` MUST reside instantaneously 
>      beneath their sovereign parent. Do not rupture the visual taxonomy.
> 
> 6. Structural Restrictions & Hybrid Folders (CRITICAL):
>    - "preset" and "action" paradigms exist as PURE UI ephemera. They exert zero 
>      direct mutation upon the target file. Their `key` is an internal lexical anchor.
>    - "menu": A phantom categorical folder (default=None, type_="menu"). It writes nothing.
>    - HYBRID FOLDERS: You may transmute ANY functional integer, boolean, or string into 
>      an expandable drop-down menu by asserting `is_parent=True`. This orchestrates a 
>      scenario wherein the parent header retains substantive backend agency whilst 
>      concealing subordinate parameters.
>    - Folders tolerate singular depth exclusively. Labyrinthine nesting is strictly forbidden.
> 
> 7. Lexical Parsimony (ONE-WORD HEADERS ONLY):
>    - NO MULTI-WORD HEADERS: Every `group` moniker and `Tab` designation MUST comprise 
>      a solitary, highly descriptive lexeme (e.g., prioritize `Cryptography` over 
>      `Encryption Security Subsystem`). This mitigates terminal interface asphyxiation.
>    - USE DESCRIPTIVE KEYS: Employ rigorous, semantically unassailable identifiers 
>      for backend keys.
> 
> 8. The Ontological Categories (`type_`):
>    - "bool"   : Binary toggle (True/False). Translates to `key=true/false` or uncommented valueless flags.
>    - "int"    : Integer mathematics (min_val, max_val, step).
>    - "float"  : Decimal mathematics (min_val, max_val, step).
>    - "string" : Alphanumeric character strings.
>    - "cycle"  : Instantaneous horizontal iteration via predefined `options` array.
>    - "picker" : Fullscreen modal search query derived from `options`.
>    - "color"  : Hexadecimal, RGB, or Matugen integration variable.
>    - "menu"   : Pure structural abstraction (requires `is_parent=True`, `default=None`).
>    - "action" : Triggers asynchronous POSIX shell execution (command string resides in `default`).
>    - "preset" : Orchestrates multi-variable state synchronization (requires `preset_payload`).
> 
> 9. Strict Type & Native Value Congruence:
>    - The Python literal assigned to `default` MUST mirror the epistemological reality 
>      of the `type_` declaration:
>      * "bool"   -> default=True (Native Python boolean)
>      * "int"    -> default=10   (Native Python integer)
>      * "string" -> default="Text" (Native Python string)
> 
> 10. Preset Payload Rigidity (The Nuclear Override):
>    - Presets constitute an uncompromising totalitarian state replacement. If a schema 
>      variable is omitted from the `preset_payload`, the engine will coercively 
>      revert that abandoned variable to its programmed `default`. Enumerate all 
>      mandatory states within the payload dictation.
> 
> 11. Pedagogy & Hermeneutics (`extended_help`):
>    - Every entity MUST incorporate exhaustively detailed `extended_help`.
>    - Elucidate the precise systemic ramifications of mutating the variable. 
>    - Construct the prose such that an uninitiated interlocutor may effortlessly 
>      decipher the operational consequences.
> 
> ===============================================================================
> """
> 
> from python.frontend.core_types import ConfigItem
> 
> # =============================================================================
> # 1. MACROSCOPIC SYSTEM ROUTING (REQUIRED)
> # =============================================================================
> ENGINE_TYPE = "ini"                        # STRICTLY ENFORCED: "ini"
> TARGET_FILE = "~/.config/hegemony/daemon.conf" # The physical locus of state modification
> APP_TITLE = "Dusky Subsystem Control"      # The authoritative nomenclature atop the UI
> 
> # =============================================================================
> # 2. ENVIRONMENTAL PARAMETRIZATION
> # =============================================================================
> DEFAULT_MODE = "auto"                      # "auto" (instantaneous IO) | "batch" (deferred transactional commit via Ctrl+S)
> THEME_FILE = "~/.config/matugen/generated/dusky_tui.json" # Chromatic variable mapping
> ENABLE_USER_PRESETS = True                 # Authorize localized profile synthesization
> USER_PRESETS_TAB = "Configurations"        # Must identically reflect a ONE-WORD tab designation below
> 
> # =============================================================================
> # 3. MACRO-TAXONOMY (TABS DEFINITION)
> # =============================================================================
> 
> TABS = [
>     "Infrastructure",
>     "Cryptography",
>     "Configurations"
> ]
> 
> # =============================================================================
> # 4. THE SCHEMATIC ARCHITECTURE
> # =============================================================================
> 
> SCHEMA = {
>     # -------------------------------------------------------------------------
>     # TAB 0: SYSTEMIC INFRASTRUCTURE
>     # -------------------------------------------------------------------------
>     0: [
>         ConfigItem(
>             label="Enforce Sovereign Telemetry",
>             key="telemetry_active",
>             scope="DEFAULT",       # UID = "telemetry_active" (Resides in the root of the INI)
>             type_="bool",
>             default=False,
>             group="Surveillance",  # STRICT: ONE WORD ONLY
>             extended_help="**Sovereign Telemetry Override**\n\nWhen instantiated, this parameter authorizes the daemon to perpetually exfiltrate operational diagnostics to the centralized hegemony. While ostensibly utilized for systemic optimization, the interlocutor should recognize the inherent privacy degradation precipitated by enabling this conduit."
>         ),
>         ConfigItem(
>             label="Maximum Concurrent Vectors",
>             key="max_connections",
>             scope="network",       # UID = "network.max_connections" (Resides under [network])
>             type_="int",
>             default=1024,
>             min_val=1,
>             max_val=65535,
>             step=64,
>             group="Network",
>             extended_help="**Socket Allocation Maximum**\n\nDelineates the absolute upper boundary of concurrent asynchronous socket connections permitted by the internal hypervisor. Elevating this threshold augments systemic throughput at the proportional expense of volatile memory allocation."
>         ),
>         ConfigItem(
>             label="Primary Routing Protocol",
>             key="routing_heuristic",
>             scope="network",       # UID = "network.routing_heuristic"
>             type_="cycle",
>             default="bbr",
>             options=["bbr", "cubic", "reno", "illinois"], 
>             group="Network",
>             extended_help="**Congestion Control Algorithm**\n\nDictates the algorithmic paradigm employed to govern packet transmission rates across the digital ether. `bbr` maximizes bandwidth utilization, whilst legacy protocols like `reno` provide predictable, albeit antiquated, bottleneck arbitration."
>         ),
>     ],
> 
>     # -------------------------------------------------------------------------
>     # TAB 1: CRYPTOGRAPHIC SUBSYSTEMS & HYBRID ABSTRACTIONS
>     # -------------------------------------------------------------------------
>     1: [
>         # --- HYBRID FOLDER IMPLEMENTATION ---
>         # 1. The Sovereign Parent (Possesses authentic backend agency whilst masquerading as a structural folder)
>         ConfigItem(
>             label="Enable Quantum Resistance",
>             key="quantum_hardening_enabled", 
>             scope="security",         # UID = "security.quantum_hardening_enabled"
>             type_="bool",             # Valid data type, subjected to backend I/O
>             default=False,
>             is_parent=True,           # Manifests the expandable menu morphology
>             expanded=False,           # Defaults to obfuscation
>             group="Encryption",
>             extended_help="**Quantum Hardening Master Switch**\n\nThis Boolean orchestrates a macroscopic pivot toward post-quantum cryptographic primitives. \n\n- **ON**: Enforces draconian lattice-based cryptography, neutralizing Shor's algorithm threat vectors.\n- **OFF**: Retains reliance on standard elliptic curve vulnerabilities."
>         ),
>         # 2. Subordinate Entity A (Must sequentially succeed its Sovereign)
>         ConfigItem(
>             label="Lattice Generation Algorithm",
>             key="lattice_primitive",
>             scope="security",         # UID = "security.lattice_primitive"
>             type_="picker",        
>             default="Kyber768",
>             options=["Kyber512", "Kyber768", "Kyber1024", "Dilithium"],
>             hints=["Low Security", "Standard Hegemony", "Paranoid", "Signature Scheme"], 
>             parent_ref="security.quantum_hardening_enabled",  # Syntactic linkage to the Sovereign's UID
>             extended_help="**Post-Quantum Primitive Selection**\n\nSelects the specific mathematical architecture utilized to obfuscate symmetrical key exchanges. Elevating the matrix dimensions (e.g., Kyber1024) increases decryption resistance exponentially but severely degrades handshake velocity."
>         ),
>         # 3. Subordinate Entity B
>         ConfigItem(
>             label="Entropy Pool Rotation Interval",
>             key="entropy_rotation_seconds",
>             scope="security",         # UID = "security.entropy_rotation_seconds"
>             type_="int",        
>             default=3600,
>             min_val=60,
>             max_val=86400,
>             step=60,
>             parent_ref="security.quantum_hardening_enabled",
>             extended_help="**Entropy Regeneration Matrix**\n\nQuantifies the chronological span (in seconds) preceding the forceful invalidation and reconstitution of the cryptographic entropy pool. Hyper-frequent rotations safeguard against prolonged state compromises."
>         ),
>     ],
> 
>     # -------------------------------------------------------------------------
>     # TAB 2: ORCHESTRATION & STATE SYNCHRONIZATION
>     # -------------------------------------------------------------------------
>     2: [
>         ConfigItem(
>             label="Purge Cryptographic Ephemera",
>             key="action_purge_keys", 
>             scope="DEFAULT",          # UID = "action_purge_keys"
>             type_="action",
>             default="rm -rf ~/.config/hegemony/keys/* && echo 'Keyring Obliterated'",
>             group="Maintenance",
>             extended_help="**Destructive State Purge**\n\nExecuting this command line stratagem immediately decimates all volatile session keys via the POSIX subsystem. Utilize this mechanism exclusively during confirmed digital incursions to sever adversarial persistence."
>         ),
>         ConfigItem(
>             label="Instantiate Lockdown Paradigm",
>             key="preset_lockdown_mode",     
>             scope="DEFAULT",          # UID = "preset_lockdown_mode"
>             type_="preset",
>             default=None,
>             group="Orchestration",
>             preset_payload={
>                 "telemetry_active": False,      
>                 "network.max_connections": 1,            
>                 "security.quantum_hardening_enabled": True,
>                 "security.lattice_primitive": "Kyber1024"
>             },
>             extended_help="**Totalitarian Security Preset**\n\nInstantly overwrites the operational matrix to enforce maximal defensive posturing. \n\nImplementation guarantees:\n1. Severance of all non-essential telemetry.\n2. Strangulation of concurrent connections to absolute singularity.\n3. Mandatory implementation of paramount post-quantum cryptography.\n\n*Note: Any configuration unaddressed within this payload shall be ruthlessly regressed to its primordial default.*"
>         ),
>     ]
> }
> 
> # =============================================================================
> # QUICK-REFERENCE CODEX (THE INI HEGEMONY)
> # =============================================================================
> #
> # ConfigItem(
> #     label          = "Display Nomenclature",
> #     key            = "backend_identifier",
> #     scope          = "section_name",     # "section_name" (e.g., [core]) or "DEFAULT" for root keys
> #     type_          = "bool",             # STANDARD: bool | int | float | string | color
> #                                          # MODALS: cycle | picker 
> #                                          # ABSTRACTIONS: action | preset | menu
> #     default        = None,               # Native Python type MUST reflect type_ (e.g., True, 10, "text"). 
> #                                          # -> For 'action', default is the POSIX execution string. 
> #                                          # -> For 'menu' & 'preset', default MUST resolve to None.
> #     options        = [],                 # Imperative for 'cycle'/'picker'. Triggers Hybrid Dropdowns for standard scalars.
> #     hints          = [],                 # Explanatory subtitles for 'picker' modals.
> #     preset_payload = {},                 # Dict mapping "scope.key" to target_value. Omissions trigger factory reset.
> #     min_val        = None,               # Mathematical nadir (int/float)
> #     max_val        = None,               # Mathematical zenith (int/float)
> #     step           = None,               # Iterative adjustment coefficient
> #     group          = "OneWord",          # STRICT: Visual header MUST be a solitary lexeme.
> #     extended_help  = "Markdown Prose",   # Rigorous documentation for the interlocutor's perusal.
> #     is_parent      = False,              # Dictates whether this entity encapsulates subordinate logic.
> #     parent_ref     = None,               # Syntactic linkage to a Sovereign parent. Must mirror parent's UID ("scope.key").
> #     expanded       = False,              # Default UI expansion state.
> # )
> ```