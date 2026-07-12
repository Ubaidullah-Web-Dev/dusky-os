#!/usr/bin/env bash
# -----------------------------------------------------------------------------
# dusky-session - Graceful session teardown for Hyprland 0.55.4+
# Pure Hyprland native teardown
# Reference patterns from system_menu.sh and wlogout_scale.sh
# -----------------------------------------------------------------------------

set -euo pipefail

# 1. Dependency & Environment Validation (from wlogout_scale.sh pattern)
if [[ -z "${HYPRLAND_INSTANCE_SIGNATURE:-}" ]]; then
    echo "WARNING: HYPRLAND_INSTANCE_SIGNATURE not set, not inside Hyprland? Proceeding anyway." >&2
fi

for cmd in hyprctl jq systemctl; do
    if ! command -v "$cmd" >/dev/null 2>&1; then
        echo "ERROR: Required command '$cmd' not found in PATH." >&2
        exit 1
    fi
done

# 2. Action parsing & validation
ACTION="${1:-poweroff}"

case "$ACTION" in
    poweroff|reboot|soft-reboot|logout) ;;
    *)
        echo "Error: Invalid action '$ACTION'." >&2
        echo "Usage: ${0##*/} [poweroff|reboot|soft-reboot|logout]" >&2
        exit 1
        ;;
esac

# 3. State management clean-up (non-fatal)
STATE_DIR="${XDG_STATE_HOME:-$HOME/.local/state}/omarchy"
if [[ -d "$STATE_DIR" ]]; then
    shopt -s nullglob
    rm -f -- "$STATE_DIR"/re*-required 2>/dev/null || :
    shopt -u nullglob
fi

# 4. Reset workspace (visually cleaner for next boot, non-fatal)
# Best-effort, must not abort script if IPC fails
hyprctl dispatch workspace 1 >/dev/null 2>&1 || :

# 5. Smart teardown - Avoid killing our own ancestry
# If invoked via terminal/rofi, don't close that terminal immediately
declare -A skip_pids=()
curr_pid=$$

while [[ -r "/proc/$curr_pid/status" ]]; do
    skip_pids["$curr_pid"]=1
    ppid=""

    while IFS=$': \t' read -r key value _; do
        if [[ "$key" == "PPid" ]]; then
            ppid="$value"
            break
        fi
    done < "/proc/$curr_pid/status"

    [[ "$ppid" =~ ^[0-9]+$ ]] && (( ppid > 1 )) || break
    curr_pid="$ppid"
done

batch_cmds=""

# Safely capture JSON, avoiding process substitution error masking
if clients_json=$(hyprctl clients -j 2>/dev/null); then
    if client_rows=$(jq -r '.[] | "\(.pid)\t\(.address)"' <<<"$clients_json" 2>/dev/null); then
        if [[ -n "$client_rows" ]]; then
            while IFS=$'\t' read -r c_pid addr; do
                [[ -z "$c_pid" || -z "$addr" ]] && continue
                [[ -n "${skip_pids["$c_pid"]:-}" ]] && continue
                # Validate address format to prevent injection (hex address)
                [[ "$addr" =~ ^0x[0-9a-fA-F]+$ ]] || continue
                batch_cmds+="dispatch closewindow address:${addr}; "
            done <<<"$client_rows"
        fi
    fi
fi

# Best-effort window closure; script must proceed if IPC fails
if [[ -n "$batch_cmds" ]]; then
    hyprctl --batch "$batch_cmds" >/dev/null 2>&1 || :
    sleep 1
fi

# 6. Execute final action - Native Hyprland / systemd only
# We use native dispatch for logout or standard systemctl commands otherwise.
if [[ "$ACTION" == "logout" ]]; then
    exec hyprctl dispatch exit
else
    # --no-wall prevents broadcast to all users, cleaner for single-user desktop
    exec systemctl "$ACTION" --no-wall
fi
