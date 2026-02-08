#!/usr/bin/env bash
# -----------------------------------------------------------------------------
# Script: Hyprlock Theme Manager (htm)
# Engine: Dusky TUI v3.0.2 (Syntax Hotfix)
# -----------------------------------------------------------------------------

set -euo pipefail

# Ensure consistent numeric formatting to prevent locale bugs
export LC_NUMERIC=C

# =============================================================================
# ▼ CONFIGURATION & CONSTANTS ▼
# =============================================================================

readonly _CONFIG_HOME="${XDG_CONFIG_HOME:-${HOME}/.config}"
readonly CONFIG_ROOT="${_CONFIG_HOME}/hypr"
readonly THEMES_ROOT="${CONFIG_ROOT}/hyprlock_themes"
readonly TARGET_CONFIG="${CONFIG_ROOT}/hyprlock.conf"

readonly APP_TITLE="Hyprlock Theme Manager"
readonly APP_VERSION="v2.0.0"

# TUI Dimensions
declare -ri MAX_DISPLAY_ROWS=14
declare -ri BOX_INNER_WIDTH=76
declare -ri ITEM_START_ROW=5  # Row index where items begin (Header=3 + Spacer=1 + Start=1)
declare -ri ITEM_PADDING=32

# --- ANSI Constants ---
declare _h_line_buf
printf -v _h_line_buf '%*s' "$BOX_INNER_WIDTH" ''
readonly H_LINE="${_h_line_buf// /─}"
unset _h_line_buf

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
readonly CLR_SCREEN=$'\033[2J'
readonly CURSOR_HOME=$'\033[H'
readonly CURSOR_HIDE=$'\033[?25l'
readonly CURSOR_SHOW=$'\033[?25h'
readonly MOUSE_ON=$'\033[?1000h\033[?1002h\033[?1006h'
readonly MOUSE_OFF=$'\033[?1000l\033[?1002l\033[?1006l'

# Timeout for reading escape sequences.
# 0.05s is standard for capturing full SGR sequences over SSH/Terminals.
readonly ESC_READ_TIMEOUT=0.05

# --- State Variables ---
declare -i SELECTED_ROW=0
declare -i SCROLL_OFFSET=0
declare -i PREVIEW_MODE=0
declare -i TOGGLE_MODE=0
declare ORIGINAL_STTY=""

declare -a TAB_ITEMS_0=()
declare -a THEME_PATHS=()

# =============================================================================
# ▼ CORE FUNCTIONS ▼
# =============================================================================

cleanup() {
    # Silence errors during cleanup to prevent visual garbage on exit
    printf '%s%s%s' "${MOUSE_OFF}" "${CURSOR_SHOW}" "${C_RESET}" 2>/dev/null || :
    if [[ -n "${ORIGINAL_STTY:-}" ]]; then
        stty "${ORIGINAL_STTY}" 2>/dev/null || :
    fi
    printf '\n' 2>/dev/null || :
}
trap cleanup EXIT
trap 'exit 130' INT
trap 'exit 143' TERM

log_info()    { printf '%s[INFO]%s %s\n' "${C_CYAN}" "${C_RESET}" "$*"; }
log_success() { printf '%s[SUCCESS]%s %s\n' "${C_GREEN}" "${C_RESET}" "$*"; }
log_err()     { printf '%s[ERROR]%s %s\n' "${C_RED}" "${C_RESET}" "$*" >&2; }

check_deps() {
    # Removed unused 'tput', 'awk', 'sed'
    local -a deps=(realpath find sort)
    local -a missing=()
    local cmd
    for cmd in "${deps[@]}"; do
        command -v "${cmd}" &>/dev/null || missing+=("${cmd}")
    done
    if (( ${#missing[@]} )); then
        log_err "Missing core dependencies: ${missing[*]}"
        exit 1
    fi
}

init() {
    if (( EUID == 0 )); then
        log_err "Do not run as root."
        exit 1
    fi
    if [[ ! -d "${THEMES_ROOT}" ]]; then
        log_err "Themes directory not found: ${THEMES_ROOT}"
        exit 1
    fi
    check_deps
}

discover_themes() {
    local config_file dir name
    while IFS= read -r -d '' config_file; do
        dir="${config_file%/*}"
        THEME_PATHS+=("${dir}")

        name=""
        # Soft dependency check for jq
        if [[ -f "${dir}/theme.json" ]] && command -v jq &>/dev/null; then
            name=$(jq -r '.name // empty' "${dir}/theme.json" 2>/dev/null) || true
        fi
        if [[ -z "${name}" ]]; then
             name="${dir##*/}"
        fi
        TAB_ITEMS_0+=("${name}")
    done < <(find "${THEMES_ROOT}" -mindepth 2 -maxdepth 2 \
                  -name "hyprlock.conf" -print0 2>/dev/null | sort -z)

    if (( ${#TAB_ITEMS_0[@]} == 0 )); then
        log_err "No themes found in ${THEMES_ROOT}"
        exit 1
    fi
}

detect_current_theme() {
    local target="${TARGET_CONFIG}"
    local real_target=""
    local real_theme_dir candidate_resolved
    local -i i

    [[ -e "${target}" ]] || return 0

    if [[ -L "${target}" ]]; then
        real_target=$(realpath -- "${target}" 2>/dev/null) || return 0
    elif [[ -f "${target}" ]]; then
        local key value path
        # Pure bash parser for "source = ..."
        while IFS='=' read -r key value || [[ -n "${key}" ]]; do
            # Trim whitespace
            key="${key#"${key%%[![:space:]]*}"}"
            key="${key%"${key##*[![:space:]]}"}"
            
            if [[ "${key}" == "source" ]]; then
                path="${value}"
                path="${path#"${path%%[![:space:]]*}"}"
                path="${path%"${path##*[![:space:]]}"}"
                
                # Expand tilde
                if [[ "${path}" == "~"* ]]; then
                    path="${HOME}${path:1}"
                fi
                real_target=$(realpath -- "${path}" 2>/dev/null) || true
                break
            fi
        done < "${target}"
    fi

    [[ -n "${real_target}" ]] || return 0
    real_theme_dir="${real_target%/*}"

    for (( i = 0; i < ${#THEME_PATHS[@]}; i++ )); do
        if [[ "${THEME_PATHS[i]}" == "${real_theme_dir}" ]]; then
            SELECTED_ROW=${i}
            return 0
        fi
        candidate_resolved=$(realpath -- "${THEME_PATHS[i]}" 2>/dev/null) || continue
        if [[ "${candidate_resolved}" == "${real_theme_dir}" ]]; then
            SELECTED_ROW=${i}
            return 0
        fi
    done

    return 0
}

apply_theme() {
    local -i idx=$1
    local theme_dir="${THEME_PATHS[idx]}"
    local theme_name="${TAB_ITEMS_0[idx]}"
    local source="${theme_dir}/hyprlock.conf"

    if [[ ! -r "${source}" ]]; then
        log_err "Cannot read: ${source}"
        return 0 # Do not return 1, or set -e will kill the TUI
    fi

    local source_entry="${source/#"${HOME}"/\~}"
    if ! printf 'source = %s\n' "${source_entry}" > "${TARGET_CONFIG}"; then
        log_err "Failed to write: ${TARGET_CONFIG}"
        return 0
    fi

    if (( TOGGLE_MODE )); then
        printf '%s\n' "${theme_name}"
    else
        APPLIED_THEME_NAME="${theme_name}"
    fi
}

# =============================================================================
# ▼ UI ENGINE ▼
# =============================================================================

draw_ui() {
    local buf="" pad_buf="" padded_item="" item
    local -i i count visible_start visible_end rows_rendered
    local -i visible_len left_pad right_pad

    # --- Header Box (Matches "Master Template" Header Only style) ---
    buf+="${CURSOR_HOME}"
    buf+="${C_MAGENTA}┌${H_LINE}┐${C_RESET}"$'\n'

    visible_len=$(( ${#APP_TITLE} + ${#APP_VERSION} + 1 ))
    left_pad=$(( (BOX_INNER_WIDTH - visible_len) / 2 ))
    right_pad=$(( BOX_INNER_WIDTH - visible_len - left_pad ))

    printf -v pad_buf '%*s' "${left_pad}" ''
    buf+="${C_MAGENTA}│${pad_buf}${C_WHITE}${APP_TITLE} ${C_CYAN}${APP_VERSION}${C_MAGENTA}"
    printf -v pad_buf '%*s' "${right_pad}" ''
    buf+="${pad_buf}│${C_RESET}"$'\n'

    buf+="${C_MAGENTA}└${H_LINE}┘${C_RESET}"$'\n'

    # --- List Rendering ---
    count=${#TAB_ITEMS_0[@]}

    # Clamp selection
    (( SELECTED_ROW < 0 )) && SELECTED_ROW=0
    (( SELECTED_ROW >= count )) && SELECTED_ROW=$(( count - 1 ))

    # Adjust scroll window
    if (( SELECTED_ROW < SCROLL_OFFSET )); then
        SCROLL_OFFSET=${SELECTED_ROW}
    elif (( SELECTED_ROW >= SCROLL_OFFSET + MAX_DISPLAY_ROWS )); then
        SCROLL_OFFSET=$(( SELECTED_ROW - MAX_DISPLAY_ROWS + 1 ))
    fi

    local -i max_scroll=$(( count - MAX_DISPLAY_ROWS ))
    (( max_scroll < 0 )) && max_scroll=0
    (( SCROLL_OFFSET > max_scroll )) && SCROLL_OFFSET=${max_scroll}
    (( SCROLL_OFFSET < 0 )) && SCROLL_OFFSET=0

    visible_start=${SCROLL_OFFSET}
    visible_end=$(( SCROLL_OFFSET + MAX_DISPLAY_ROWS ))
    (( visible_end > count )) && visible_end=${count}

    if (( SCROLL_OFFSET > 0 )); then
        buf+="${C_GREY}    ▲ (more above)${CLR_EOL}${C_RESET}"$'\n'
    else
        buf+="${CLR_EOL}"$'\n'
    fi

    for (( i = visible_start; i < visible_end; i++ )); do
        item="${TAB_ITEMS_0[i]}"
        printf -v padded_item "%-${ITEM_PADDING}s" "${item:0:${ITEM_PADDING}}"

        if (( i == SELECTED_ROW )); then
            buf+="${C_CYAN} ➤ ${C_INVERSE}${padded_item}${C_RESET}${CLR_EOL}"$'\n'
        else
            buf+="    ${padded_item}${CLR_EOL}"$'\n'
        fi
    done

    # Fill remaining rows
    rows_rendered=$(( visible_end - visible_start ))
    for (( i = rows_rendered; i < MAX_DISPLAY_ROWS; i++ )); do
        buf+="${CLR_EOL}"$'\n'
    done

    # --- Footer ---
    if (( count > MAX_DISPLAY_ROWS )); then
        local position_info="[$(( SELECTED_ROW + 1 ))/${count}]"
        if (( visible_end < count )); then
            buf+="${C_GREY}    ▼ (more below) ${position_info}${CLR_EOL}${C_RESET}"$'\n'
        else
            buf+="${C_GREY}                   ${position_info}${CLR_EOL}${C_RESET}"$'\n'
        fi
    else
        buf+="${CLR_EOL}"$'\n'
    fi

    buf+=$'\n'"${C_CYAN} [Enter] Apply  [p] Preview  [↑/↓ j/k] Nav  [q] Quit${C_RESET}"$'\n'

    # --- Preview Pane ---
    if (( PREVIEW_MODE )); then
        local conf="${THEME_PATHS[SELECTED_ROW]}/hyprlock.conf"
        buf+=$'\n'"${C_MAGENTA}── Preview: ${C_WHITE}${TAB_ITEMS_0[SELECTED_ROW]}${C_MAGENTA} ──${C_RESET}"$'\n'
        if [[ -r "${conf}" ]]; then
            local line
            local -i pcount=0
            # Guard against read failure exiting script
            while (( pcount < 8 )) && IFS= read -r line; do
                buf+="  ${C_GREY}${line}${C_RESET}${CLR_EOL}"$'\n'
                (( pcount++ )) || true 
            done < "${conf}"
        else
            buf+="  ${C_RED}(Unable to read config)${C_RESET}${CLR_EOL}"$'\n'
        fi
    fi

    buf+="${CLR_EOS}"
    printf '%s' "${buf}"
}

# --- Navigation ---
navigate() {
    local -i dir=$1
    local -i count=${#TAB_ITEMS_0[@]}
    (( count == 0 )) && return 0
    # Safe negative modulo arithmetic
    SELECTED_ROW=$(( (SELECTED_ROW + dir + count) % count ))
    return 0
}

navigate_page() {
    local -i dir=$1
    local -i count=${#TAB_ITEMS_0[@]}
    (( count == 0 )) && return 0
    SELECTED_ROW=$(( SELECTED_ROW + dir * MAX_DISPLAY_ROWS ))
    (( SELECTED_ROW < 0 )) && SELECTED_ROW=0
    (( SELECTED_ROW >= count )) && SELECTED_ROW=$(( count - 1 ))
    return 0
}

navigate_end() {
    local -i target=$1
    local -i count=${#TAB_ITEMS_0[@]}
    (( count == 0 )) && return 0
    if (( target == 0 )); then
        SELECTED_ROW=0
    else
        SELECTED_ROW=$(( count - 1 ))
    fi
    return 0
}

# --- Mouse Handling (SGR 1006 protocol) ---
handle_mouse() {
    local input="$1"
    local -i button x y

    # Robust regex: matches full SGR sequence.
    # We MUST verify match before accessing BASH_REMATCH to avoid "unbound variable" error.
    local regex='^\[<([0-9]+);([0-9]+);([0-9]+)([Mm])$'

    if ! [[ "${input}" =~ ${regex} ]]; then
        return 0
    fi

    button=${BASH_REMATCH[1]}
    x=${BASH_REMATCH[2]}
    y=${BASH_REMATCH[3]}
    local type="${BASH_REMATCH[4]}"

    # Scroll wheel
    if (( button == 64 )); then
        navigate -1
        return 0
    fi
    if (( button == 65 )); then
        navigate 1
        return 0
    fi

    # Only process press events (M), ignore release (m)
    [[ "${type}" != "M" ]] && return 0

    local -i count=${#TAB_ITEMS_0[@]}
    local -i item_row_start=${ITEM_START_ROW}

    if (( y >= item_row_start && y < item_row_start + MAX_DISPLAY_ROWS )); then
        local -i clicked_idx=$(( y - item_row_start + SCROLL_OFFSET ))
        if (( clicked_idx >= 0 && clicked_idx < count )); then
            SELECTED_ROW=${clicked_idx}
        fi
    fi

    return 0
}

# --- Smart Escape Sequence Reader ---
# Reads until a valid terminator is found, preventing sequence fragmentation.
read_escape_seq() {
    local char
    _ESCAPE_SEQ=""

    while IFS= read -rsn1 -t "${ESC_READ_TIMEOUT}" char; do
        _ESCAPE_SEQ+="${char}"
        case "${_ESCAPE_SEQ}" in
            O[A-Z])          return 0 ;; # SS3 (e.g. F1-F4)
            '['*[A-Za-z~])   return 0 ;; # CSI (Arrows, Mouse, Etc)
        esac
    done
    return 0
}

# --- Interactive Mode ---
run_interactive() {
    local key
    declare APPLIED_THEME_NAME=""

    [[ ! -t 0 ]] && { log_err "Interactive mode requires a terminal"; exit 1; }

    ORIGINAL_STTY=$(stty -g 2>/dev/null) || ORIGINAL_STTY=""
    # Force blocking read to prevent CPU spin
    stty -icanon -echo min 1 time 0 2>/dev/null || :

    printf '%s%s%s%s' "${MOUSE_ON}" "${CURSOR_HIDE}" "${CLR_SCREEN}" "${CURSOR_HOME}"

    while true; do
        draw_ui

        IFS= read -rsn1 key || break

        if [[ "${key}" == $'\x1b' ]]; then
            read_escape_seq
            case "${_ESCAPE_SEQ}" in
                '[A'|'OA')      navigate -1 ;;
                '[B'|'OB')      navigate 1 ;;
                '[5~')          navigate_page -1 ;;
                '[6~')          navigate_page 1 ;;
                '[H'|'[1~')     navigate_end 0 ;;
                '[F'|'[4~')     navigate_end 1 ;;
                '['*'<'*[Mm])   handle_mouse "${_ESCAPE_SEQ}" ;;
                *)              ;; 
            esac
        else
            case "${key}" in
                k|K)            navigate -1 ;;
                j|J)            navigate 1 ;;
                g)              navigate_end 0 ;;
                G)              navigate_end 1 ;;
                # Prevent exit on 0 result under set -e
                p|P)            PREVIEW_MODE=$(( PREVIEW_MODE ? 0 : 1 )) ;;
                '')             apply_theme "${SELECTED_ROW}"
                                cleanup
                                log_success "Applied theme: ${APPLIED_THEME_NAME:-Unknown}"
                                exit 0 ;;
                q|Q|$'\x03')    break ;;
                *)              ;;
            esac
        fi
    done
}

# --- Main Entry Point ---
main() {
    while (( $# )); do
        case "$1" in
            --toggle)  TOGGLE_MODE=1 ;;
            --preview) PREVIEW_MODE=1 ;;
            -h|--help) printf 'Usage: %s [--toggle] [--preview]\n' "${0##*/}"; exit 0 ;;
            --)        shift; break ;;
            -*)        log_err "Unknown option: $1"; exit 1 ;;
            *)         break ;;
        esac
        shift
    done

    init
    discover_themes
    detect_current_theme

    if (( TOGGLE_MODE )); then
        local -i total=${#TAB_ITEMS_0[@]}
        SELECTED_ROW=$(( (SELECTED_ROW + 1) % total ))
        apply_theme "${SELECTED_ROW}"
    else
        run_interactive
    fi
}

main "$@"
