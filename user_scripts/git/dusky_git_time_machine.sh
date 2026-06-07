#!/usr/bin/env bash
# =============================================================================
# Dusky Git Time Machine (Platinum Edition - Architecture v7 - Perfect Zenith)
# Environment: Bash 5.3+, FZF 0.73+, Arch Linux
# Mechanisms: Unit Separator (\x1f) indexing, Subshell Function Exporting,
#             Calculated Byte-Parity Column Alignment, Dynamic ANSI Stripping,
#             Automated Stash-and-Pop Safety Protocols, No-Ellipsis Truncation.
# =============================================================================

# 1. Global Git Bare Repository Overrides
export GIT_DIR="$HOME/dusky/"
export GIT_WORK_TREE="$HOME"

# CRITICAL FIX: Lock the session PID. FZF subshells have different PIDs,
# so relying on '$$' inside the exported functions breaks stash recovery!
export DUSKY_SESSION_ID="$$"

# Guarantee UTF-8 character width mapping for Awk length() calculations
export LC_ALL=en_US.UTF-8

# Purge any global FZF options that might disable mouse support natively
unset FZF_DEFAULT_OPTS

# Clean up the session stash flag when the script completely exits
trap 'rm -f "/tmp/dusky_time_machine_stash_${DUSKY_SESSION_ID}"' EXIT


# 2. Native Bash Functions for FZF Execution Payloads
_dusky_git_help() {
    clear
    printf "\n\n  \033[1;38;5;81m󰏖 Dusky Time Machine - Keyboard Shortcuts\033[0m\n"
    printf "  \033[38;5;238m──────────────────────────────────────────────\033[0m\n"
    printf "  \033[1;33m[ENTER]\033[0m          Time Travel (Force Checkout selected commit)\n"
    printf "  \033[1;33m[DOUBLE-CLICK]\033[0m   Time Travel via Mouse\n"
    printf "  \033[1;33m[CTRL-R]\033[0m         Return to Present (Force Checkout default branch)\n"
    printf "  \033[1;33m[CTRL-W]\033[0m         Wipe Changes (Hard Reset to current HEAD)\n"
    printf "  \033[1;33m[ALT-C]\033[0m          Copy current Commit Hash to Clipboard\n"
    printf "  \033[1;33m[F1 / CTRL-O]\033[0m    Show this Help Menu\n"
    printf "  \033[1;33m[ESC]\033[0m            Exit Time Machine\n\n"
    printf "  \033[38;5;242mPress any key to return...\033[0m"
    
    # Read the first keypress to exit the menu
    read -rsn1 < /dev/tty
    # CRITICAL FIX: Drain the terminal input buffer of any remaining bytes.
    # (Prevents multi-byte escape sequences like F1/^[OP from bleeding into the search prompt)
    while read -rsn1 -t 0.01 < /dev/tty; do :; done
}
export -f _dusky_git_help

_dusky_git_list() {
    # Using %x1f (Unit Separator byte) to cleanly divide data fields.
    git log --all --graph --color=always \
        --format="%x1f%h%x1f%cd%x1f%an%x1f%C(auto)%d%x1f%s" \
        --date=format:"%m/%d" | \
    awk -v FS=$'\x1f' '
        # Helper function to strip ANSI codes and calculate true visual length
        function vlen(s) {
            c = s
            gsub(/\033\[[0-9;]*[a-zA-Z]/, "", c)
            return length(c)
        }
        
        {
            if (NF == 1) {
                # Pure graph line (No commit attached)
                graph = $1
                pad_len = 60 - vlen(graph)
                if (pad_len < 0) pad_len = 0
                pad = sprintf("%*s", pad_len, "")
                
                # Formats precisely to match the standard layout borders
                printf "\x1f \033[38;5;242m      \033[0m \033[38;5;238m│\033[0m %s%s \033[38;5;238m│\033[0m\n", graph, pad
            } else {
                graph = $1
                hash = $2
                date = $3
                author = $4
                refs = $5
                msg = $6
                
                # Strict truncation for column integrity
                if (length(author) > 15) author = substr(author, 1, 15)
                gsub(/\|/, "│", msg)
                if (length(refs) > 0) refs = refs " "
                
                # Math: Calculate available space inside the strict 60-character boundary
                base_vlen = vlen(graph) + vlen(refs)
                max_msg = 60 - base_vlen
                if (max_msg < 1) max_msg = 1 
                
                # Safely truncate the message BEFORE applying any color codes (no dots added)
                if (length(msg) > max_msg) {
                    msg = substr(msg, 1, max_msg)
                }
                
                # Assemble the colored middle block
                mid = graph refs "\033[38;5;253m" msg "\033[0m"
                mid_vlen = base_vlen + length(msg)
                
                # Pad out the remainder to hit exactly 60 characters
                pad_len = 60 - mid_vlen
                if (pad_len < 0) pad_len = 0
                pad = sprintf("%*s", pad_len, "")
                
                # Mathematical Alignment:
                # Field 1 (Hidden index): hash
                # Field 2 (Visible grid): Space(1) + Date(6) + Space(1) + Pipe(1) + Space(1) + Gr/Msg(60) + Space(1) + Pipe(1) + Space(1) + Author(15)
                printf "%s\x1f \033[1;38;5;114m%-6s\033[0m \033[38;5;238m│\033[0m %s%s \033[38;5;238m│\033[0m \033[1;38;5;203m%-15s\033[0m\n", hash, date, mid, pad, author
            }
        }
    '
}
export -f _dusky_git_list

_dusky_git_preview() {
    local -r hash="$1"
    
    # Intercept pure graph lines and show a stylized, perfectly measured ghost pane
    if [[ -z "$hash" || "$hash" == " " ]]; then
        # 40 Dashes to perfectly match the 38 inner text characters + 2 padding spaces
        printf "\n\n  \033[1;38;5;242m╭────────────────────────────────────────╮\033[0m"
        printf "\n  \033[1;38;5;242m│\033[0m \033[3;38;5;238mGraph connection line. No commit here.\033[0m \033[1;38;5;242m│\033[0m"
        printf "\n  \033[1;38;5;242m╰────────────────────────────────────────╯\033[0m\n"
        exit 0
    fi

    if command -v delta >/dev/null 2>&1; then
        git show "$hash" | delta --side-by-side --width="${FZF_PREVIEW_COLUMNS:-120}" --paging=never
    else
        git show --color=always "$hash"
    fi
}
export -f _dusky_git_preview

_dusky_git_checkout() {
    local -r hash="$1"
    [[ -z "$hash" ]] && exit 0
    
    # SAFETY SHIELD: If leaving a working branch, auto-stash uncommitted changes
    # (Maintains --include-untracked as per user requirement, fixed $$ identifier)
    if git symbolic-ref -q HEAD >/dev/null; then
        if ! git diff-index --quiet HEAD -- || [[ -n "$(git ls-files --exclude-standard --others)" ]]; then
            git stash push --include-untracked -m "DUSKY_AUTO_STASH" >/dev/null 2>&1
            touch "/tmp/dusky_time_machine_stash_${DUSKY_SESSION_ID}"
        fi
    fi
    
    git checkout -f "$hash" >/dev/null 2>&1
}
export -f _dusky_git_checkout

_dusky_git_return() {
    local main_branch
    main_branch=$(git symbolic-ref refs/remotes/origin/HEAD 2>/dev/null | sed 's@^refs/remotes/origin/@@')
    
    # Advanced detached HEAD fallback detection
    if [[ -z "$main_branch" ]]; then
        for b in main master; do
            if git show-ref --verify --quiet "refs/heads/$b"; then
                main_branch="$b"
                break
            fi
        done
    fi
    
    if [[ -n "$main_branch" ]]; then
        git checkout -f "$main_branch" >/dev/null 2>&1
        
        # RESTORE SHIELD: Auto-pop the exact stash we created when leaving the present
        if [[ -f "/tmp/dusky_time_machine_stash_${DUSKY_SESSION_ID}" ]]; then
            git stash pop >/dev/null 2>&1
            rm -f "/tmp/dusky_time_machine_stash_${DUSKY_SESSION_ID}"
        fi
    fi
}
export -f _dusky_git_return

_dusky_git_restore() {
    git reset --hard HEAD >/dev/null 2>&1
}
export -f _dusky_git_restore

_dusky_git_copy() {
    local -r hash="$1"
    [[ -z "$hash" ]] && exit 0
    if command -v wl-copy >/dev/null 2>&1; then
        printf "%s" "$hash" | wl-copy
    fi
}
export -f _dusky_git_copy


# 3. Main Engine Execution
main() {
    if ! command -v fzf >/dev/null 2>&1; then
        printf "\n\e[31m✖ Error:\e[0m 'fzf' is not installed.\n\n" >&2
        exit 1
    fi

    # Mathematically aligned visual header.
    # The 3 leading spaces account EXACTLY for: FZF Pointer (2 spaces) + List Start Buffer (1 space).
    # Widths map 1:1 to the Row Generator: %-6s | %-60s | %-15s
    local -r visual_header=$(printf "   \033[1;37m%-6s\033[0m \033[38;5;238m│\033[0m \033[1;37m%-60s\033[0m \033[38;5;238m│\033[0m \033[1;37m%-15s\033[0m" "DATE" "GRAPH / REFS / MESSAGE" "AUTHOR")

    # Launch FZF, bypassing Zsh interpolation by hard-binding to bash subprocesses
    _dusky_git_list | fzf --ansi \
        --with-shell="bash -c" \
        --delimiter=$'\x1f' \
        --with-nth=2 \
        --tiebreak=index \
        --no-sort \
        --no-hscroll \
        --ellipsis='' \
        --prompt=" :: Time Machine ❯ " \
        --pointer=">" \
        --marker="✓" \
        --layout=reverse \
        --border=rounded \
        --border-label=" 󰏖 Dusky Time Machine [F1 / Ctrl-O: Help] " \
        --border-label-pos=3 \
        --info=hidden \
        --header="$visual_header" \
        --header-first \
        --bind="enter:execute-silent(_dusky_git_checkout {1})+transform-prompt( [ -n \"{1}\" ] && echo \" :: Traveled to {1} ❯ \" || echo \" :: Time Machine ❯ \" )+reload-sync(_dusky_git_list)" \
        --bind="double-click:execute-silent(_dusky_git_checkout {1})+transform-prompt( [ -n \"{1}\" ] && echo \" :: Traveled to {1} ❯ \" || echo \" :: Time Machine ❯ \" )+reload-sync(_dusky_git_list)" \
        --bind="ctrl-r:execute-silent(_dusky_git_return)+change-prompt( :: Returned to Present ❯ )+reload-sync(_dusky_git_list)" \
        --bind="ctrl-w:execute-silent(_dusky_git_restore)+change-prompt( :: Restored (Hard Reset) ❯ )+reload-sync(_dusky_git_list)" \
        --bind="alt-c:execute-silent(_dusky_git_copy {1})+transform-prompt( [ -n \"{1}\" ] && echo \" :: Copied {1} ❯ \" || echo \" :: Time Machine ❯ \" )" \
        --bind="f1:execute(_dusky_git_help)" \
        --bind="ctrl-o:execute(_dusky_git_help)" \
        --color="bg+:#1e1e2e,bg:#11111b,spinner:#f5e0dc" \
        --color="fg:#cdd6f4,fg+:#cdd6f4,header:#89b4fa,info:#cba6f7" \
        --color="pointer:#a6e3a1,marker:#f5e0dc,prompt:#cba6f7" \
        --color="hl:#f38ba8,hl+:#f38ba8,border:#585b70,label:#a6e3a1" \
        --preview="_dusky_git_preview {1}" \
        --preview-window="right,65%,border-left,wrap"

    # Clean exit payload
    clear
    printf "\e[1;32m✔ Disengaged Time Machine.\e[0m (Current HEAD: \e[33m%s\e[0m)\n" "$(git rev-parse --short HEAD 2>/dev/null)"
}

main "$@"
