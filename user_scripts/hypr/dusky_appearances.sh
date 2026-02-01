#!/usr/bin/env bash
# -----------------------------------------------------------------------------
# Dusky Appearances (v5.3 - Centered & Fast)
# -----------------------------------------------------------------------------
# Target: Arch Linux / Hyprland / UWSM
# Description: Tabbed TUI to modify hyprland appearance.conf.
#              Fixes: Input lag, all alignment issues, branding.
# -----------------------------------------------------------------------------

set -uo pipefail

# --- Configuration ---
readonly CONFIG_FILE="${HOME}/.config/hypr/source/appearance.conf"
declare -ri MAX_DISPLAY_ROWS=12

# --- ANSI Constants ---
readonly C_RESET=$'\033[0m'
readonly C_CYAN=$'\033[1;36m'
readonly C_GREEN=$'\033[1;32m'
readonly C_MAGENTA=$'\033[1;35m'
readonly C_RED=$'\033[1;31m'
readonly C_WHITE=$'\033[1;37m'
readonly C_GREY=$'\033[1;30m'
readonly C_INVERSE=$'\033[7m'
readonly CLR_EOL=$'\033[K'
readonly CLR_EOS=$'\033[J'
readonly CURSOR_HOME=$'\033[H'
readonly CURSOR_HIDE=$'\033[?25l'
readonly CURSOR_SHOW=$'\033[?25h'
# SGR Mouse Mode (1006) + Button Event (1002)
readonly MOUSE_ON=$'\033[?1000h\033[?1002h\033[?1006h'
readonly MOUSE_OFF=$'\033[?1000l\033[?1002l\033[?1006l'

# --- State ---
declare -i SELECTED_ROW=0
declare -i CURRENT_TAB=0
readonly -a TABS=("Layout" "Decoration" "Blur" "Shadow" "Snap")
declare -ri TAB_COUNT=${#TABS[@]}

# Mouse Click Zones (Calculated during draw)
declare -a TAB_ZONES=()

# --- Data Structures ---
declare -A ITEM_MAP      # label -> "key|type|block|min|max|step"
declare -A VALUE_CACHE   # label -> cached value
declare -a TAB_ITEMS_0=() TAB_ITEMS_1=() TAB_ITEMS_2=() TAB_ITEMS_3=() TAB_ITEMS_4=()

# --- Registration ---
register() {
    local tab_idx=$1 label=$2 config=$3
    ITEM_MAP["$label"]=$config
    local -n tab_ref="TAB_ITEMS_${tab_idx}"
    tab_ref+=("$label")
}

# --- DEFINITIONS ---

# Tab 0: Layout & General
register 0 "Gaps In"            "gaps_in|int||0|100|1"
register 0 "Gaps Out"           "gaps_out|int||0|100|1"
register 0 "Gaps Workspaces"    "gaps_workspaces|int|general|0|100|1"
register 0 "Border Size"        "border_size|int||0|10|1"
register 0 "Resize on Border"   "resize_on_border|bool|general|||"
register 0 "Allow Tearing"      "allow_tearing|bool|general|||"

# Tab 1: Decoration
register 1 "Rounding"           "rounding|int||0|30|1"
register 1 "Rounding Power"     "rounding_power|float||0.0|10.0|0.1"
register 1 "Active Opacity"     "active_opacity|float||0.1|1.0|0.05"
register 1 "Inactive Opacity"   "inactive_opacity|float||0.1|1.0|0.05"
register 1 "Fullscreen Opacity" "fullscreen_opacity|float||0.1|1.0|0.05"
register 1 "Dim Inactive"       "dim_inactive|bool||||"
register 1 "Dim Strength"       "dim_strength|float||0.0|1.0|0.05"
register 1 "Dim Special"        "dim_special|float||0.0|1.0|0.05"

# Tab 2: Blur
register 2 "Blur Enabled"       "enabled|bool|blur|||"
register 2 "Blur Size"          "size|int|blur|1|20|1"
register 2 "Blur Passes"        "passes|int|blur|1|10|1"
register 2 "Blur Xray"          "xray|bool|blur|||"
register 2 "Blur Noise"         "noise|float|blur|0.0|1.0|0.01"
register 2 "Blur Contrast"      "contrast|float|blur|0.0|2.0|0.05"
register 2 "Blur Brightness"    "brightness|float|blur|0.0|2.0|0.05"
register 2 "Blur Popups"        "popups|bool|blur|||"
register 2 "Blur Vibrancy"      "vibrancy|float|blur|0.0|1.0|0.05"

# Tab 3: Shadow
register 3 "Shadow Enabled"     "enabled|bool|shadow|||"
register 3 "Shadow Range"       "range|int|shadow|0|100|1"
register 3 "Shadow Power"       "render_power|int|shadow|1|4|1"
register 3 "Shadow Sharp"       "sharp|bool|shadow|||"
register 3 "Shadow Scale"       "scale|float|shadow|0.0|1.1|0.05"
register 3 "Shadow Ignore Win"  "ignore_window|bool|shadow|||"
register 3 "Shadow Color"       "color_toggle|action|shadow|||"

# Tab 4: Snap
register 4 "Snap Enabled"       "enabled|bool|snap|||"
register 4 "Snap Window Gap"    "window_gap|int|snap|0|50|1"
register 4 "Snap Monitor Gap"   "monitor_gap|int|snap|0|50|1"
register 4 "Snap Border Overlap" "border_overlap|bool|snap|||"

# --- DEFAULTS ---
declare -A DEFAULTS=(
    # General
    ["Gaps In"]=6
    ["Gaps Out"]=12
    ["Gaps Workspaces"]=0
    ["Border Size"]=2
    ["Resize on Border"]=false
    ["Allow Tearing"]=true
    # Decoration
    ["Rounding"]=6
    ["Rounding Power"]=6.0
    ["Active Opacity"]=1.0
    ["Inactive Opacity"]=1.0
    ["Fullscreen Opacity"]=1.0
    ["Dim Inactive"]=true
    ["Dim Strength"]=0.2
    ["Dim Special"]=0.8
    # Blur
    ["Blur Enabled"]=false
    ["Blur Size"]=4
    ["Blur Passes"]=2
    ["Blur Xray"]=false
    ["Blur Noise"]=0.0117
    ["Blur Contrast"]=0.8916
    ["Blur Brightness"]=0.8172
    ["Blur Popups"]=false
    ["Blur Vibrancy"]=0.1696
    # Shadow
    ["Shadow Enabled"]=false
    ["Shadow Range"]=35
    ["Shadow Power"]=2
    ["Shadow Sharp"]=false
    ["Shadow Scale"]=1.0
    ["Shadow Ignore Win"]=true
    ["Shadow Color"]='rgba(1a1a1aee)'
    # Snap
    ["Snap Enabled"]=false
    ["Snap Window Gap"]=10
    ["Snap Monitor Gap"]=10
    ["Snap Border Overlap"]=false
)

# --- Helpers ---
log_err() { printf '%s[ERROR]%s %s\n' "$C_RED" "$C_RESET" "$1" >&2; }

cleanup() {
    printf '%s%s%s' "$MOUSE_OFF" "$CURSOR_SHOW" "$C_RESET"
    clear
}

escape_sed_replacement() {
    local s=$1
    s=${s//\\/\\\\}
    s=${s//&/\\&}
    s=${s//\//\\/}
    printf '%s' "$s"
}

trap cleanup EXIT
trap 'exit 130' INT
trap 'exit 143' TERM

# --- Core Logic ---

get_value_from_file() {
    local key=$1 block=${2:-}

    awk -v key="$key" -v target_block="$block" '
        BEGIN { depth = 0; in_target = 0; found = 0 }
        /^[[:space:]]*#/ { next }
        /{/ {
            depth++
            if (target_block != "" && match($0, "^[[:space:]]*" target_block "[[:space:]]*\\{")) {
                in_target = 1
                target_depth = depth
            }
        }
        /}/ {
            if (in_target && depth == target_depth) in_target = 0
            depth--
        }
        /=/ && !found {
            if ((target_block == "") || in_target) {
                if (match($0, "^[[:space:]]*" key "[[:space:]]*=")) {
                    val = substr($0, index($0, "=") + 1)
                    gsub(/[[:space:]]*#.*/, "", val)
                    gsub(/^[[:space:]]+|[[:space:]]+$/, "", val)
                    print val
                    found = 1
                    exit
                }
            }
        }
    ' "$CONFIG_FILE"
}

write_value_to_file() {
    local key=$1 new_val=$2 block=${3:-}
    local safe_val
    safe_val=$(escape_sed_replacement "$new_val")

    if [[ -n $block ]]; then
        sed --follow-symlinks -i \
            "/^[[:space:]]*${block}[[:space:]]*{/,/^[[:space:]]*}/ {
                s|^\([[:space:]]*${key}[[:space:]]*=[[:space:]]*\)[^#[:space:]]*|\1${safe_val}|
            }" "$CONFIG_FILE"
    else
        sed --follow-symlinks -i \
            "s|^\([[:space:]]*${key}[[:space:]]*=[[:space:]]*\)[^#[:space:]]*|\1${safe_val}|" \
            "$CONFIG_FILE"
    fi
}

load_tab_values() {
    local -n items_ref="TAB_ITEMS_${CURRENT_TAB}"
    local item key type block min max step val

    for item in "${items_ref[@]}"; do
        IFS='|' read -r key type block min max step <<< "${ITEM_MAP[$item]}"

        if [[ $key == "color_toggle" ]]; then
            val=$(get_value_from_file "color" "shadow")
        else
            val=$(get_value_from_file "$key" "$block")
        fi
        
        VALUE_CACHE["$item"]=${val:-unset}
    done
}

modify_value() {
    local label=$1
    local -i direction=$2
    local key type block min max step current new_val

    IFS='|' read -r key type block min max step <<< "${ITEM_MAP[$label]}"
    current=${VALUE_CACHE[$label]:-}
    [[ $current == "unset" ]] && current=""

    case $type in
        int)
            [[ ! $current =~ ^-?[0-9]+$ ]] && current=${min:-0}
            local -i int_step=${step:-1} int_val=$current
            (( int_val += direction * int_step )) || :
            [[ -n $min && int_val -lt min ]] && int_val=$min
            [[ -n $max && int_val -gt max ]] && int_val=$max
            new_val=$int_val
            ;;
        float)
            [[ ! $current =~ ^-?[0-9]*\.?[0-9]+$ ]] && current=${min:-0.0}
            new_val=$(awk -v c="$current" -v dir="$direction" -v s="${step:-0.1}" \
                          -v mn="$min" -v mx="$max" '
                BEGIN {
                    val = c + (dir * s)
                    if (mn != "" && val < mn) val = mn
                    if (mx != "" && val > mx) val = mx
                    printf "%.4g", val
                }
            ')
            ;;
        bool)
            [[ $current == "true" ]] && new_val="false" || new_val="true"
            ;;
        action)
            if [[ $key == "color_toggle" ]]; then
                key="color"
                [[ $current == *'$primary'* ]] && new_val='rgba(1a1a1aee)' || new_val='$primary'
            else
                return 0
            fi
            ;;
        *) return 0 ;;
    esac

    write_value_to_file "$key" "$new_val" "$block"
    VALUE_CACHE["$label"]=$new_val
}

set_absolute_value() {
    local label=$1 new_val=$2
    local key type block min max step
    IFS='|' read -r key type block min max step <<< "${ITEM_MAP[$label]}"
    
    [[ $key == "color_toggle" ]] && key="color"
    
    write_value_to_file "$key" "$new_val" "$block"
    VALUE_CACHE["$label"]=$new_val
}

reset_defaults() {
    local -n items_ref="TAB_ITEMS_${CURRENT_TAB}"
    local item def_val
    
    for item in "${items_ref[@]}"; do
        def_val=${DEFAULTS[$item]:-}
        [[ -n $def_val ]] && set_absolute_value "$item" "$def_val"
    done
}

# --- UI Rendering ---

draw_ui() {
    local buf=""
    local -i i current_col=3
    
    buf+="${CURSOR_HOME}"
    
    # 66-char wide box (including borders)
    buf+="${C_MAGENTA}┌────────────────────────────────────────────────────────────────┐${C_RESET}"$'\n'
    
    # ALIGNMENT FIX: Center Alignment
    # Inner width 64. "Dusky Appearances v5.3" is 22 chars. 
    # (64-22)/2 = 21 padding on each side.
    buf+="${C_MAGENTA}│$(printf '%*s' 21 '')${C_WHITE}Dusky Appearances ${C_CYAN}v5.3${C_MAGENTA}$(printf '%*s' 21 '')│${C_RESET}"$'\n'
    
    local tab_line="${C_MAGENTA}│ "
    TAB_ZONES=()
    
    for (( i = 0; i < TAB_COUNT; i++ )); do
        local name=${TABS[i]}
        local -i len=${#name}
        local -i zone_start=$current_col
        
        if (( i == CURRENT_TAB )); then
            tab_line+="${C_CYAN}${C_INVERSE} ${name} ${C_RESET}${C_MAGENTA}│ "
        else
            tab_line+="${C_GREY} ${name} ${C_MAGENTA}│ "
        fi
        
        TAB_ZONES+=("${zone_start}:$(( zone_start + len + 1 ))")
        (( current_col += len + 4 ))
    done
    
    # ALIGNMENT FIX: Box right border fix (65 - len)
    local -i tab_line_len=$(( current_col - 1 ))
    local -i pad_needed=$(( 65 - tab_line_len ))
    
    (( pad_needed > 0 )) && tab_line+=$(printf '%*s' "$pad_needed" '')
    tab_line+="${C_MAGENTA}│${C_RESET}"
    
    buf+="${tab_line}"$'\n'
    buf+="${C_MAGENTA}└────────────────────────────────────────────────────────────────┘${C_RESET}"$'\n'

    local -n items_ref="TAB_ITEMS_${CURRENT_TAB}"
    local -i count=${#items_ref[@]}
    local item val display

    (( SELECTED_ROW >= count )) && SELECTED_ROW=$(( count - 1 ))
    (( SELECTED_ROW < 0 )) && SELECTED_ROW=0

    for (( i = 0; i < count; i++ )); do
        item=${items_ref[i]}
        val=${VALUE_CACHE[$item]:-unset}

        case $val in
            true)         display="${C_GREEN}ON${C_RESET}" ;;
            false)        display="${C_RED}OFF${C_RESET}" ;;
            unset)        display="${C_RED}unset${C_RESET}" ;;
            *'$primary'*) display="${C_MAGENTA}Dynamic${C_RESET}" ;;
            *)            display="${C_WHITE}${val}${C_RESET}" ;;
        esac

        if (( i == SELECTED_ROW )); then
            buf+="${C_CYAN} ➤ ${C_INVERSE}"
            buf+=$(printf '%-22s' "$item")
            buf+="${C_RESET} : ${display}${CLR_EOL}"$'\n'
        else
            buf+="   "
            buf+=$(printf ' %-22s' "$item")
            buf+=" : ${display}${CLR_EOL}"$'\n'
        fi
    done

    for (( i = count; i < MAX_DISPLAY_ROWS; i++ )); do
        buf+="${CLR_EOL}"$'\n'
    done

    buf+=$'\n'"${C_CYAN} [Tab] Category  [r] Reset  [←/→ h/l] Adjust  [↑/↓ j/k] Nav  [q] Quit${C_RESET}"$'\n'
    buf+="${C_CYAN} File: ${C_WHITE}${CONFIG_FILE}${C_RESET}${CLR_EOL}${CLR_EOS}"
    
    printf '%s' "$buf"
}

# --- Input Handling ---

navigate() {
    local -i dir=$1
    local -n items_ref="TAB_ITEMS_${CURRENT_TAB}"
    local -i count=${#items_ref[@]}
    (( SELECTED_ROW += dir )) || :
    (( SELECTED_ROW < 0 )) && SELECTED_ROW=$(( count - 1 ))
    (( SELECTED_ROW >= count )) && SELECTED_ROW=0
}

adjust() {
    local -i dir=$1
    local -n items_ref="TAB_ITEMS_${CURRENT_TAB}"
    [[ ${#items_ref[@]} -eq 0 ]] && return 0
    modify_value "${items_ref[SELECTED_ROW]}" "$dir"
}

switch_tab() {
    local -i dir=${1:-1}
    (( CURRENT_TAB += dir )) || :
    (( CURRENT_TAB >= TAB_COUNT )) && CURRENT_TAB=0
    (( CURRENT_TAB < 0 )) && CURRENT_TAB=$(( TAB_COUNT - 1 ))
    SELECTED_ROW=0
    load_tab_values
    clear
}

set_tab() {
    local -i idx=$1
    if (( idx != CURRENT_TAB && idx >= 0 && idx < TAB_COUNT )); then
        CURRENT_TAB=$idx
        SELECTED_ROW=0
        load_tab_values
        clear
    fi
}

handle_mouse() {
    local input=$1
    local -i button x y i
    local type zone start end
    
    # Matches SGR sequence: "[<0;10;5M"
    if [[ $input =~ ^\[\<([0-9]+)\;([0-9]+)\;([0-9]+)([Mm])$ ]]; then
        button=${BASH_REMATCH[1]}
        x=${BASH_REMATCH[2]}
        y=${BASH_REMATCH[3]}
        type=${BASH_REMATCH[4]}
        
        [[ $type != "M" ]] && return 0

        # Tab Row = 3
        if (( y == 3 )); then
            for (( i = 0; i < TAB_COUNT; i++ )); do
                zone=${TAB_ZONES[i]}
                start=${zone%%:*}
                end=${zone##*:}
                if (( x >= start && x <= end )); then
                    set_tab "$i"
                    return 0
                fi
            done
        fi
        
        # Item rows start at 5
        local -i item_start_y=5
        local -n items_ref="TAB_ITEMS_${CURRENT_TAB}"
        local -i count=${#items_ref[@]}
        
        if (( y >= item_start_y && y < item_start_y + count )); then
            SELECTED_ROW=$(( y - item_start_y ))
            if (( x > 30 )); then
                (( button == 0 )) && adjust 1 || adjust -1
            fi
        fi
    fi
}

# --- Main ---

main() {
    [[ ! -f $CONFIG_FILE ]] && { log_err "Config not found: $CONFIG_FILE"; exit 1; }
    command -v awk &>/dev/null || { log_err "Required: awk"; exit 1; }
    command -v sed &>/dev/null || { log_err "Required: sed"; exit 1; }

    printf '%s%s' "$MOUSE_ON" "$CURSOR_HIDE"
    load_tab_values
    clear

    local key seq char
    while true; do
        draw_ui
        
        IFS= read -rsn1 key || :
        
        if [[ $key == $'\x1b' ]]; then
            # LAG FIX: Instant buffer drain for zero-latency arrow keys
            seq=""
            while IFS= read -rsn1 -t 0.001 char; do
                seq+="$char"
            done
            
            case $seq in
                '[Z')               switch_tab -1 ;;        # Shift+Tab
                '[A'|'OA')          navigate -1 ;;          # Up
                '[B'|'OB')          navigate 1 ;;           # Down
                '[C'|'OC')          adjust 1 ;;             # Right
                '[D'|'OD')          adjust -1 ;;            # Left
                '['*'<'*)           handle_mouse "$seq" ;;  # SGR Mouse
            esac
        else
            case $key in
                k|K)            navigate -1 ;;
                j|J)            navigate 1 ;;
                l|L)            adjust 1 ;;
                h|H)            adjust -1 ;;
                $'\t')          switch_tab 1 ;;
                r|R)            reset_defaults ;;
                q|Q|$'\x03')    break ;;
            esac
        fi
    done
}

main
