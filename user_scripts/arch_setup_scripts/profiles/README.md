# Dusky Arch Linux Master Orchestrator — Profile Configuration & Reference

Complete reference for writing and editing orchestrator profile `.toml` files.
Covers every section, flag, condition, CLI argument, and environment variable
so you can configure profiles from scratch without reading the source code.

**Orchestrator version:** 19.0.0 &emsp; **Runtime:** Python 3.14+ &emsp; **TUI:** Textual 8.2.8+

---

## 1. Included Profiles

| File | Name | Purpose |
| :--- | :--- | :--- |
| `01_main.toml` | Main Setup | Full Arch Linux desktop: dotfiles, Hyprland, themes, services, AUR. |
| `02_iso.toml` | ISO Setup | Post-ISO install: skips AUR builds, sleep timeouts, heavy package installs. |
| `03_dusk_personal.toml` | Dusk Personal Setup | Personal workstation: ASUS tweaks, TTS/STT, Firefox symlinks, backup managers. |

---

## 2. Profile TOML Structure

A profile has six top-level tables. All are optional except `[sequence]`.

```toml
# ─── IDENTITY ────────────────────────────────────────────────────────────────
[profile]
name = "Main Setup"                 # Display name (defaults to filename stem)
description = "Full Arch install"   # One-line summary shown in profile selector
post_script_delay = 0               # Seconds to pause between tasks (default: 0)

# ─── EXECUTION POLICY ────────────────────────────────────────────────────────
[policy]
audio = true                # Play audio cues on completion/failure (default: true)
notify = true               # Send desktop notifications via notify-send (default: true)
inhibit_sleep = true        # Inhibit system sleep/idle during the run (default: true)
task_timeout = 0            # Global per-task timeout in seconds; 0 = disabled (default: 0)
stop_on_fail = false        # Abort entire pipeline on first failure (default: false)
manual = false              # Prompt via modal before every task (default: false)
force = false               # Export DUSKY_FORCE=1 and append --force to all tasks (default: false)

# ─── GIT SELF-UPDATE ─────────────────────────────────────────────────────────
[git]
enabled = true              # Pull latest dotfiles before running tasks (default: false)
git_dir = "~/dusky"         # Bare repo path (--git-dir)
work_tree = "~/"            # Working tree path (--work-tree)
remote = "origin"           # Remote name (default: "origin")

# ─── SCRIPT SEARCH DIRECTORIES ───────────────────────────────────────────────
# The orchestrator searches these directories IN ORDER to find each script name.
# First match wins. If a script name is found in more than one directory, the
# orchestrator raises a [CONFLICT] error unless you resolve it below.
# Paths support ~ (home) and environment variables.
[search_dirs]
dirs = [
    "~/user_scripts/arch_setup_scripts/scripts",
    "~/user_scripts/arch_setup_scripts",
    "~/user_scripts/rofi",
    "~/user_scripts/images",
    "~/user_scripts/theme_matugen",
]

# ─── CONFLICT RESOLUTIONS ────────────────────────────────────────────────────
# When the same script filename exists in multiple search directories, map the
# script name to the exact path you want to use.
[conflict_resolutions]
# "wallpaper_selector.py" = "~/user_scripts/images/wallpaper_selector.py"

# ─── TASK SEQUENCE ────────────────────────────────────────────────────────────
[sequence]
scripts = [ ... ]           # Compact string entries (recommended, see §3)
tasks = [ ... ]             # Detailed TOML table entries (optional, see §7)
```

---

## 3. Compact Task Entry Format

Each string in `scripts = [...]` follows this format:

```
"MODE | FLAGS | COMMAND ARGS"
"MODE | COMMAND ARGS"
"COMMAND ARGS"
```

### Execution Modes

| Mode | Meaning |
| :--- | :--- |
| `U` | Run as the regular user |
| `S` | Run with `sudo` (administrative privileges) |

If omitted, defaults to `U`.

### Examples

```toml
scripts = [
    # Simple: user mode, no flags
    "U | 002_pre_generated_colors.sh",

    # Sudo mode with arguments
    "S | 050_pacman_config.sh --auto",

    # Condition + once flag (only runs if battery exists, only runs once)
    "U | if:battery,once | 135_battery_notify_service.sh --auto",

    # Multiple conditions (AND): only runs if nvidia GPU AND not a VM
    "U | if:gpu:nvidia,if:not:vm | 380_nvidia_open_source.sh --auto",

    # Ignore failures, retry 3 times with 5s delay
    "S | ignore,retry:3,retry_delay:5 | 055_pacman_reflector.sh",

    # Interactive script (suspends TUI, opens full PTY)
    "U | interactive | dusky_matugen_config_tui.sh",

    # Relative path script (resolved relative to search_dirs or script directory)
    "U | user_scripts/git/dusky_backup_manager.py --new",
]
```

---

## 4. Condition Reference (`if:<condition>`)

Conditions control whether a task runs based on live system state.
If a condition evaluates to **false**, the task is **silently skipped** (not marked as failed).

### Hardware & Environment

| Condition | True when… |
| :--- | :--- |
| `if:wayland` | `WAYLAND_DISPLAY` is set |
| `if:x11` | `DISPLAY` is set |
| `if:graphical` | Either Wayland or X11 session is active |
| `if:desktop` | Active desktop session (Wayland/X11/Mir) and not pure SSH |
| `if:ssh` | Running inside an SSH connection (`SSH_CONNECTION` / `SSH_TTY`) |
| `if:vm` | Virtual machine (QEMU/KVM, VMware, VirtualBox, Bochs) |
| `if:baremetal` | Physical hardware (opposite of `if:vm`) |
| `if:battery` | `/sys/class/power_supply/*/type` contains `Battery` |
| `if:btrfs` | Root filesystem (`/`) is Btrfs (checked via `/proc/mounts`) |

### GPU Detection

| Condition | Detection method |
| :--- | :--- |
| `if:gpu:nvidia` | `/sys/module/nvidia` exists OR `lspci` contains "nvidia" |
| `if:gpu:intel` | `/sys/module/i915` or `/sys/module/xe` exists OR `lspci` contains "intel" |
| `if:gpu:amd` | `/sys/module/amdgpu` exists OR `lspci` contains "amd"/"ati"/"radeon" |

### File, Binary & Package Checks

| Condition | True when… |
| :--- | :--- |
| `if:command:<cmd>` | Binary `<cmd>` is found in `$PATH` |
| `if:package:<pkg>` | Pacman package is installed (`pacman -Qq <pkg>`) |
| `if:path:<path>` | File or directory exists |
| `if:file:<path>` | Regular file exists |
| `if:dir:<path>` | Directory exists (supports `~`, e.g. `if:dir:~/user_scripts/images`) |
| `if:missing:<path>` | File or directory does **NOT** exist |
| `if:group:<group>` | Current user belongs to the specified group |
| `if:env:<VAR>` | Environment variable `<VAR>` is set and non-empty |

### Systemd Service Checks

| Condition | True when… |
| :--- | :--- |
| `if:service_active:<unit>` | System service is active (`systemctl is-active --quiet`) |
| `if:user_service_active:<unit>` | User service is active (`systemctl --user is-active --quiet`) |

### Logic Operators

| Syntax | Behavior |
| :--- | :--- |
| `if:not:<condition>` | Inverts any condition (e.g. `if:not:vm`, `if:not:command:sddm`) |
| `if:always` / `if:true` / `if:yes` | Always true (force-run) |
| `if:never` / `if:false` / `if:no` | Always false (force-skip) |

### Compound Conditions (AND logic)

Multiple conditions are combined with **AND** logic. Two ways to write them:

```toml
# Comma-separated inside a single if: flag
"U | if:gpu:nvidia,if:not:vm | 380_nvidia_open_source.sh"

# Multiple if: flags in the flags column (also AND'd)
"U | if:wayland,if:battery | 455_hyprctl_reload.sh"
```

All sub-conditions must be true for the task to execute.

---

## 5. Task Flags Reference

Flags go in the middle column, comma-separated: `"MODE | flag1,flag2,flag3 | script.sh"`.

### Failure Handling

| Flag(s) | Effect |
| :--- | :--- |
| `ignore`, `ignore-fail`, `true` | Mark task as "ignored" on failure; continue pipeline |
| `on_failure:ask` | Show interactive modal on failure (default) |
| `on_failure:abort` | Abort entire pipeline immediately on failure |
| `on_failure:continue` | Mark task as "failed" and continue to next task |
| `on_failure:skip` | Mark task as "skipped" and continue to next task |
| `on_failure:manual` | Open manual terminal resolution prompt on failure |

> **Note:** Placing `true` as the **first word of the command field** (not the flags column)
> also enables `ignore_fail`. Example: `"S | true 050_pacman_config.sh --auto"`.

### Interactive / PTY Control

| Flag(s) | Effect |
| :--- | :--- |
| `interactive`, `tui`, `prompt`, `fullscreen`, `tty`, `suspend` | Force interactive PTY session; suspends TUI and gives the script full terminal control |
| `no-interactive`, `noninteractive`, `inline`, `embedded` | Force non-interactive inline execution; suppresses PTY allocation |

> **Auto-detection:** If neither flag is set, the orchestrator scans the first 20 lines of the
> script for the comment `# dusky_interactive=true`. If found, the script is automatically
> run in interactive mode. You can override this with `no-interactive`.

### Execution Control

| Flag(s) | Effect |
| :--- | :--- |
| `force`, `--force` | Export `DUSKY_FORCE=1` and append `--force` to the command arguments |
| `always`, `always_run` | Re-run this task every time, even if previously completed |
| `timeout:<seconds>` | Per-task execution timeout (overrides `[policy] task_timeout`) |
| `retry:<count>` | Number of automatic retries on failure (default: 0) |
| `retry_delay:<seconds>` | Delay between retries in seconds (default: 1.0) |

---

## 6. `once` Persistence Markers

Tasks marked with `once` record successful execution in a **separate persistent database**
(`~/Documents/state/once.db`). Unlike normal profile state, `once` markers survive `--reset`.

### Mode (when does it re-run?)

| Flag(s) | Behavior |
| :--- | :--- |
| `once`, `run_once`, `sticky`, `once:content`, `once:hash` | Runs once. Re-runs only if the script **file content changes** (blake2b hash mismatch). |
| `once:forever`, `once:exact`, `once:permanent` | Runs **strictly once, permanently**. Never re-runs, even if the script file changes. |

### Scope (shared across profiles?)

| Flag(s) | Behavior |
| :--- | :--- |
| `once:profile`, `once:local` | Marker is scoped to the **current profile** only (default). |
| `once:global`, `once:machine` | Marker is shared across **all profiles** on the machine. |

### Combining Mode + Scope

Combine by listing multiple flags:

```toml
# Run once per profile, re-run if file changes
"U | once | 300_git_config.sh"

# Run once globally across all profiles, never re-run
"S | once:forever,once:global | 050_pacman_config.sh --auto"
```

### Managing Once Markers via CLI

```bash
# List all persistent once markers
./orchestrator.sh --list-once

# Forget (delete) a specific once marker so a script can re-run
./orchestrator.sh --forget-once 300_git_config.sh

# Forget multiple at once (--forget-once can be repeated)
./orchestrator.sh --forget-once 050_pacman_config.sh --forget-once 300_git_config.sh
```

---

## 7. Detailed TOML Task Table Format (`sequence.tasks`)

For complex tasks, use TOML tables instead of compact strings:

```toml
[[sequence.tasks]]
cmd = "050_pacman_config.sh"        # Script name (also accepts: script, path)
args = ["--auto"]                   # Arguments (string or array)
mode = "S"                          # "U" or "S" (default: "U")
flags = "ignore"                    # Comma-separated string flags (same as §5)
condition = "command:pacman"        # Condition string WITHOUT "if:" prefix
timeout = 60.0                      # Per-task timeout in seconds
retry = 2                           # Retry count on failure
retry_delay = 3.0                   # Delay between retries in seconds
on_failure = "continue"             # "ask", "abort", "continue", "skip", "manual"
once = true                         # Enable once-marker tracking
once_mode = "forever"               # "content" or "forever"
once_scope = "profile"              # "profile" or "global"
always = false                      # Always re-run regardless of state
force = false                       # Export DUSKY_FORCE=1, append --force
interactive = false                 # Force interactive PTY mode
ignore_fail = false                 # Ignore failures
```

> **Note:** `scripts = [...]` and `tasks = [...]` can coexist in the same profile.
> All `scripts` entries are loaded first, followed by all `tasks` entries.

---

## 8. Environment Variables Exported to Child Scripts

Every script executed by the orchestrator receives these environment variables:

| Variable | Value |
| :--- | :--- |
| `DUSKY_VERSION` | Orchestrator version (e.g. `19.0.0`) |
| `DUSKY_RUN_ID` | Unique run session ID |
| `DUSKY_PROFILE_NAME` | Active profile name |
| `DUSKY_PROFILE_FILE` | Absolute path to the active `.toml` profile |
| `DUSKY_TASK_SCRIPT` | Script filename being executed |
| `DUSKY_TASK_PATH` | Resolved absolute path to the script |
| `DUSKY_TASK_MODE` | `U` or `S` |
| `DUSKY_TASK_INDEX` | Task position in the sequence (1-based) |
| `DUSKY_TASK_STATE_KEY` | Internal state key for this task |
| `DUSKY_TASK_LOG_FILE` | Path to this task's individual log file |
| `DUSKY_USER` | Target username |
| `DUSKY_TARGET_USER` | Same as `DUSKY_USER` |
| `DUSKY_USER_HOME` | Target user's home directory |
| `DUSKY_LOG_DIR` | Directory containing run logs |
| `DUSKY_STATE_DIR` | Directory containing state databases |
| `DUSKY_BACKUP_DIR` | Directory for orchestrator backups |
| `DUSKY_FORCE` | `1` if force mode is active, `0` otherwise |
| `DUSKY_INTERACTIVE` | `1` if running in interactive PTY mode, `0` otherwise |
| `DUSKY_ALWAYS` | `1` if task has `always` flag, `0` otherwise |

Scripts can use these to adapt behavior. For example:

```bash
if [[ "$DUSKY_FORCE" == "1" ]]; then
    echo "Force mode: overwriting existing config"
fi
```

---

## 9. Script Auto-Detection Behavior

### Interpreter Resolution

The orchestrator determines how to run each script automatically:

1. **ELF binary** → executed directly (no interpreter)
2. **Shebang line** (`#!/usr/bin/env python3`) → uses the specified interpreter
3. **File extension** (`.py` → Python, `.sh` → Bash, `.fish` → Fish)
4. **Fallback** → Bash

### Interactive Auto-Detection

If no `interactive` / `no-interactive` flag is set in the profile, the orchestrator
reads the first 20 lines of the script file. If any line matches:

```
# dusky_interactive=true
```

…the script is automatically run in interactive PTY mode (TUI suspends, script
gets full terminal control). You can override this per-task with `no-interactive`.

---

## 10. Complete CLI Reference

### Profile Selection & Inspection

```bash
./orchestrator.sh                                # Interactive TUI profile selector
./orchestrator.sh --profile 01_main              # Select by filename stem
./orchestrator.sh --profile "Main Setup"          # Select by profile name
./orchestrator.sh --profile 3                     # Select by index number
./orchestrator.sh --list                          # List all profiles and exit
./orchestrator.sh --list-scripts                  # Show task sequence for selected profile
```

### State Management

```bash
./orchestrator.sh --profile 01_main --reset       # Delete state database for profile
./orchestrator.sh --profile 01_main --reset-and-run  # Reset state, then run immediately
./orchestrator.sh --list-once                     # List all persistent once markers
./orchestrator.sh --forget-once 300_git_config.sh # Delete once marker(s) for a script
```

### Execution Controls

| Flag | Effect |
| :--- | :--- |
| `--dry-run` | Validate manifest and print task sequence without executing anything |
| `--explain` | Print detailed condition evaluation breakdown for each task |
| `--force` | Export `DUSKY_FORCE=1` globally, append `--force` to all scripts |
| `--manual`, `-m` | Prompt via modal before every task |
| `--stop-on-fail` | Abort pipeline on first task failure |
| `--task-timeout SEC` | Set global per-task timeout in seconds (0 = disabled) |
| `--allow-root` | Allow running the orchestrator directly as root |
| `--sudo-password PASS` | Provide sudo password non-interactively |
| `--sudo-password-file FILE` | Read sudo password from a file |

### Git Self-Update Controls

| Flag | Effect |
| :--- | :--- |
| `--no-git-update` | Skip git self-update step |
| `--git-update-only` | Run git self-update and exit |
| `--offline` | Skip all network-dependent steps (git update) |
| `--yes`, `-y` | Auto-confirm destructive git update prompts |

### UI & Notification Controls

| Flag | Effect |
| :--- | :--- |
| `--ascii` | Render TUI with ASCII characters instead of Unicode |
| `--no-audio` | Disable audio notifications |
| `--no-notify` | Disable desktop notifications |
| `--no-inhibit` | Do not inhibit system sleep/idle during execution |

### Diagnostics

| Flag | Effect |
| :--- | :--- |
| `--doctor` | Run full environment diagnostics (versions, paths, dependencies) |
| `--version` | Print version number and exit |
| `-h`, `--help` | Display help menu |

---

## 11. State & Log File Locations

All state is stored under `~/Documents/`:

| What | Path |
| :--- | :--- |
| Profile state databases | `~/Documents/state/<Profile_Name>.db` |
| Persistent once markers | `~/Documents/state/once.db` |
| Execution log files | `~/Documents/logs/dusky_<profile>_<timestamp>.log` |
| Per-task log files | `~/Documents/logs/<run_id>/<script_name>.log` |
| Git backup directory | `~/Documents/dusky_backups/` |
| Cache directory | `~/.cache/dusky/` |
| Runtime lock file | `/run/user/<UID>/dusky/orchestrator.lock` |

> **Tip:** Use `./orchestrator.sh --doctor` to see the exact resolved paths for your system.
