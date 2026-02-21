#!/usr/bin/env bash
# ==============================================================================
#  ARCH DOTFILES LOG SUBMITTER (ELITE ARCHITECT EDITION)
#  - Zero-fork Timestamping (Bash Native)
#  - Optimized Pacman Dependency Checking
#  - GitDelta Bare Repo Integration
#  - Bulletproof TTY Color Handling
#  - Multi-Service Upload Fallback (0x0.st → litterbox → local)
#  - ZERO-CLICK AUTO-UPLOAD ENABLED
# ==============================================================================

# 1. Strict Safety Settings
set -Eeuo pipefail
shopt -s inherit_errexit 2>/dev/null || true

# --- CONFIGURATION ---
readonly LOG_SOURCE="${HOME:?HOME is not set}/Documents/logs"
readonly UPLOAD_PRIMARY="https://0x0.st"
readonly UPLOAD_SECONDARY="https://litterbox.catbox.moe/resources/internals/api.php"
readonly GIT_DIR="$HOME/dusky"
readonly WORK_TREE="$HOME"
readonly MAX_UPLOAD_BYTES=536870912  # 512 MiB

# Runtime variables
TEMP_DIR=""
ARCHIVE_FILE=""

# --- COLORS (Smart TTY / Terminfo Check) ---
RED="" GREEN="" YELLOW="" BLUE="" BOLD="" RESET=""

if [[ -t 1 && -t 2 && -v TERM && -n "$TERM" && "$TERM" != "dumb" ]] \
    && command -v tput &>/dev/null; then
    RED=$(tput setaf 1 2>/dev/null) || true
    GREEN=$(tput setaf 2 2>/dev/null) || true
    YELLOW=$(tput setaf 3 2>/dev/null) || true
    BLUE=$(tput setaf 4 2>/dev/null) || true
    BOLD=$(tput bold 2>/dev/null) || true
    RESET=$(tput sgr0 2>/dev/null) || true
fi

# --- UTILITIES ---
log() {
    printf '%s[%s]%s %s\n' "$BLUE" "${1:-INFO}" "$RESET" "${2:-}" >&2
}

die() {
    printf '%sERROR: %s%s\n' "$RED" "${1:-Unknown error}" "$RESET" >&2
    exit 1
}

cleanup() {
    if [[ -v TEMP_DIR && -d "$TEMP_DIR" ]]; then
        rm -rf -- "$TEMP_DIR"
    fi
}
trap cleanup EXIT

# --- DEPENDENCY MANAGEMENT ---
check_and_install_deps() {
    local -a deps=("curl" "wl-clipboard" "pciutils" "git")

    local missing_deps
    missing_deps=$(pacman -T "${deps[@]}" 2>/dev/null) || true

    if [[ -n "$missing_deps" ]]; then
        local -a to_install
        mapfile -t to_install <<< "$missing_deps"
        printf '%sInstalling missing dependencies: %s%s\n' \
            "$YELLOW" "${to_install[*]}" "$RESET" >&2
        sudo pacman -S --needed --noconfirm "${to_install[@]}" \
            || die "Failed to install dependencies."
    fi
}

# --- GITDELTA EXTRACTION ---
capture_gitdelta() {
    log "INFO" "Capturing GitDelta diff from bare repo..."

    mkdir -p -- "$LOG_SOURCE" || die "Cannot create log directory"

    local timestamp
    printf -v timestamp '%(%Y-%m-%d_%H-%M-%S)T' -1
    local delta_file="${LOG_SOURCE}/gitdelta_${timestamp}.log"

    local -a git_cmd=("/usr/bin/git" "--git-dir=$GIT_DIR" "--work-tree=$WORK_TREE")

    if [[ ! -d "$GIT_DIR" ]]; then
        log "WARNING" "Bare repo not found at $GIT_DIR. Skipping gitdelta."
        return 0
    fi

    # Check for pathspec file before attempting git add
    local pathspec_file="${WORK_TREE}/.git_dusky_list"
    if [[ -f "$pathspec_file" ]]; then
        (cd "$WORK_TREE" && "${git_cmd[@]}" add \
            --pathspec-from-file=.git_dusky_list 2>/dev/null) || true
    else
        log "WARNING" "Pathspec file not found: $pathspec_file — skipping git add"
    fi

    # Verify HEAD exists (repo has at least one commit)
    if "${git_cmd[@]}" rev-parse HEAD &>/dev/null; then
        "${git_cmd[@]}" diff --color=never HEAD > "$delta_file" || true
        log "INFO" "GitDelta saved to: $delta_file"
    else
        log "WARNING" "No commits in bare repo at $GIT_DIR. Skipping diff."
    fi
}

# --- REPORT GENERATOR ---
generate_system_report() {
    log "INFO" "Generating hardware and environment report..."

    mkdir -p -- "$LOG_SOURCE" || die "Cannot create log directory"
    local report_file="${LOG_SOURCE}/000_system_hardware_report.txt"
    local current_time
    printf -v current_time '%(%Y-%m-%d %H:%M:%S %Z)T' -1

    {
        printf '========================================================\n'
        printf '  DEBUG REPORT: %s\n' "$current_time"
        printf '========================================================\n\n'

        printf '[KERNEL]\n'
        uname -sr 2>/dev/null || printf 'N/A\n'

        printf '\n[DISTRO]\n'
        grep -E '^(PRETTY_NAME|ID|BUILD_ID)=' /etc/os-release 2>/dev/null \
            || printf 'N/A\n'

        printf '\n[CPU]\n'
        lscpu 2>/dev/null \
            | grep -E 'Model name|Architecture|Socket|Core|Thread' \
            || printf 'N/A\n'

        printf '\n[GPU]\n'
        lspci -k 2>/dev/null | grep -A2 -E '(VGA|3D)' || printf 'N/A\n'

        printf '\n[RAM]\n'
        free -h 2>/dev/null || printf 'N/A\n'

        printf '\n[STORAGE]\n'
        lsblk -f -e 7 2>/dev/null || printf 'N/A\n'
        printf -- '---\n'
        df -h / /home 2>/dev/null || df -h / 2>/dev/null || printf 'N/A\n'

        if command -v hyprctl &>/dev/null; then
            printf '\n[HYPRLAND]\n'
            hyprctl version 2>/dev/null | head -n1 || printf 'N/A\n'
        fi

        printf '\n[WAYLAND ENVIRONMENT]\n'
        env | grep -E '^(WAYLAND_DISPLAY|DISPLAY|XDG_CURRENT_DESKTOP|XDG_SESSION_TYPE|QT_QPA_PLATFORM|GBM_BACKEND|LIBVA_DRIVER_NAME|__GLX_VENDOR_LIBRARY_NAME)=' \
            || printf 'N/A\n'

    } > "$report_file" || die "Cannot write report to disk"
}

# --- PAYLOAD ENGINE ---
prepare_payload() {
    log "PROCESS" "Staging logs from $LOG_SOURCE..."

    TEMP_DIR=$(mktemp -d "${TMPDIR:-/tmp}/dotfiles_debug.XXXXXX") \
        || die "Cannot create temporary directory"
    ARCHIVE_FILE="${TEMP_DIR}/debug_logs.tar.gz"

    [[ -d "$LOG_SOURCE" ]] || die "Log directory missing: $LOG_SOURCE"

    local -a files
    shopt -s nullglob dotglob
    files=("$LOG_SOURCE"/*)
    shopt -u nullglob dotglob

    (( ${#files[@]} > 0 )) || die "No logs found in $LOG_SOURCE"

    # Stage logs (includes hidden files — intentional for dotfile configs)
    local staging="${TEMP_DIR}/logs"
    mkdir -p -- "$staging"
    cp -r -- "$LOG_SOURCE"/. "$staging/" || die "Failed to stage logs"

    log "PACK" "Compressing archive..."
    tar -czf "$ARCHIVE_FILE" -C "$TEMP_DIR" logs || die "Compression failed"

    # Sanity-check archive size
    local file_bytes
    file_bytes=$(stat -c '%s' "$ARCHIVE_FILE") || die "Cannot stat archive"
    if (( file_bytes > MAX_UPLOAD_BYTES )); then
        log "WARNING" "Archive is $(( file_bytes / 1048576 )) MiB — exceeds 512 MiB upload limit"
        log "WARNING" "Remote upload will be skipped; archive preserved locally"
    fi
}

# --- UPLOAD ENGINE (Multi-Service Fallback with Retry) ---
upload_file() {
    local file="$1"
    local file_bytes
    file_bytes=$(stat -c '%s' "$file") || die "Cannot stat archive"

    if (( file_bytes > MAX_UPLOAD_BYTES )); then
        log "WARNING" "Archive too large for remote upload. Falling back to local."
        save_local_fallback "$file"
        return 1
    fi

    local response="" url="" attempt

    # --- PRIMARY: 0x0.st ---
    log "UPLOAD" "Trying 0x0.st..."
    for attempt in 1 2; do
        if response=$(curl -sS --fail --connect-timeout 30 --max-time 120 \
                -F "file=@${file}" -- "$UPLOAD_PRIMARY" 2>&1); then
            read -r url <<< "$response"
            if [[ "$url" == http* ]]; then
                log "INFO" "Upload succeeded via 0x0.st (attempt $attempt)"
                printf '%s' "$url"
                return 0
            fi
        fi
        log "WARNING" "0x0.st attempt $attempt failed: ${response:-no response}"
        (( attempt < 2 )) && sleep 2
    done

    # --- SECONDARY: litterbox.catbox.moe ---
    log "UPLOAD" "Trying litterbox.catbox.moe..."
    for attempt in 1 2; do
        if response=$(curl -sS --fail --connect-timeout 30 --max-time 120 \
                -F "reqtype=fileupload" \
                -F "time=72h" \
                -F "fileToUpload=@${file}" \
                -- "$UPLOAD_SECONDARY" 2>&1); then
            read -r url <<< "$response"
            if [[ "$url" == http* ]]; then
                log "INFO" "Upload succeeded via litterbox (attempt $attempt)"
                printf '%s' "$url"
                return 0
            fi
        fi
        log "WARNING" "litterbox attempt $attempt failed: ${response:-no response}"
        (( attempt < 2 )) && sleep 2
    done

    # --- TERTIARY: Local fallback ---
    log "WARNING" "All upload services failed."
    save_local_fallback "$file"
    return 1
}

save_local_fallback() {
    local file="$1"
    local timestamp
    printf -v timestamp '%(%Y-%m-%d_%H-%M-%S)T' -1
    local fallback_path="${LOG_SOURCE}/debug_logs_${timestamp}.tar.gz"

    cp -- "$file" "$fallback_path" || die "Failed to save local fallback copy"

    printf '\n%s======================================================%s\n' "$YELLOW" "$RESET" >&2
    printf ' %sUPLOAD FAILED — Archive saved locally%s\n' "$BOLD" "$RESET" >&2
    printf ' Path: %s%s%s\n' "$BLUE" "$fallback_path" "$RESET" >&2
    printf '\n Upload manually to https://0x0.st :\n' >&2
    printf '   curl -F "file=@%s" https://0x0.st\n' "$fallback_path" >&2
    printf '%s======================================================%s\n' "$YELLOW" "$RESET" >&2
}

# --- HELP ---
show_help() {
    cat << EOF
Usage: $(basename "$0") [OPTIONS]

Options:
    -h, --help    Show this help message

Collects logs and git diffs from ~/Documents/logs, generates a hardware/env report,
and automatically uploads for sharing in GitHub issues.

Upload services (tried in order):
    1. 0x0.st
    2. litterbox.catbox.moe (72h expiry)
    3. Local fallback (archive saved to ~/Documents/logs/)
EOF
}

# --- MAIN ---
main() {
    while (( $# > 0 )); do
        case "$1" in
            -a|--auto)   shift; continue ;; # Ignored for backwards compatibility
            -h|--help)   show_help; exit 0 ;;
            --)          shift; break ;;
            -*)          die "Unknown option: $1" ;;
            *)           die "Unexpected argument: $1" ;;
        esac
        shift
    done

    check_and_install_deps
    capture_gitdelta
    generate_system_report
    prepare_payload

    local file_size
    file_size=$(du -h "$ARCHIVE_FILE" | cut -f1)

    printf '\n%s--- PAYLOAD READY & UPLOADING ---%s\n' "$YELLOW" "$RESET"
    printf 'File:    %s\n' "$ARCHIVE_FILE"
    printf 'Size:    %s\n' "$file_size"
    printf 'Content: Logs + Hardware/Env Report + GitDelta\n'
    printf '%s---------------------%s\n' "$YELLOW" "$RESET"

    local url
    if url=$(upload_file "$ARCHIVE_FILE"); then
        local clip_msg=""
        if [[ -v WAYLAND_DISPLAY ]] && command -v wl-copy &>/dev/null; then
            printf '%s' "$url" | wl-copy 2>/dev/null && clip_msg=" (Copied to clipboard)"
        fi

        printf '\n%s======================================================%s\n' "$GREEN" "$RESET"
        printf ' %sSUCCESS!%s%s\n' "$BOLD" "$RESET" "$clip_msg"
        printf ' URL: %s%s%s%s\n' "$BLUE" "$BOLD" "$url" "$RESET"
        printf '\n Paste the link into your GitHub issue or Discord.\n'
        printf '%s======================================================%s\n' "$GREEN" "$RESET"
    fi
    # If upload_file returned 1, save_local_fallback already printed instructions
}

main "$@"
