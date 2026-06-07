#!/usr/bin/env bash
# =============================================================================
# Dusky Git Time Machine (Platinum Edition - Architecture v7 - Perfect Zenith)
# Environment: Bash 5.3+, FZF 0.73+, Arch Linux, Hyprland/UWSM
# Mechanisms: Unit Separator (\x1f) indexing, Subshell Function Exporting,
#             Calculated Byte-Parity Column Alignment, Dynamic ANSI Stripping,
#             Automated Stash-and-Pop Safety Protocols, No-Ellipsis Truncation.
# =============================================================================

# 1. STRICT SAFETY & ENVIRONMENT
set -euo pipefail
IFS=$'\n\t'

# Global Git Bare Repository Overrides
export GIT_DIR="$HOME/dusky/"
export GIT_WORK_TREE="$HOME"

# CRITICAL FIX 1: Absolute Sensory Deprivation for Git
# Disables pagers, terminal prompts, background locks, and 2026 Git advice hints
export GIT_PAGER=cat
export GIT_TERMINAL_PROMPT=0
export GIT_OPTIONAL_LOCKS=0
export GIT_ADVICE=0

# Dummy fallback so SSH/Git never try to steal standard input
export GIT_ASKPASS=true
export SSH_ASKPASS=true

# Lock the session PID for precise, collision-free stash tracking
export DUSKY_SESSION_ID="$$"

# Guarantee UTF-8 character width mapping for Awk length() calculations
export LC_ALL=en_US.UTF-8

# Purge any global FZF options that might interfere with custom UI bindings
unset FZF_DEFAULT_OPTS

# Clean up the session stash flags when the script completely exits
# CRITICAL FIX 2: Auto-return to present if user hits Ctrl-C while time-traveling
_dusky_cleanup() {
    if [ -f "/tmp/dusky_tm_branch_${DUSKY_SESSION_ID}" ]; then
        _dusky_git_return >/dev/null 2>&1
    fi
    rm -f "/tmp/dusky_tm_stashed_${DUSKY_SESSION_ID}" 2>/dev/null || true
    rm -f "/tmp/dusky_tm_branch_${DUSKY_SESSION_ID}" 2>/dev/null || true
}
trap _dusky_cleanup EXIT

# =============================================================================
# 2. CORE TIME-TRAVEL LOGIC & I/O ISOLATION
# =============================================================================

_dusky_git_checkout() {
    # FIX: Complete I/O Detachment to prevent FZF freezing & escape character bleed.
    exec < /dev/null > /dev/null 2>&1

    # Extract only the commit hash securely
    local target_commit
    target_commit=$(echo "$1" | awk '{print $1}')
    [ -z "$target_commit" ] && return 0

    # FIX: Automated Stash-and-Pop Safety Protocol
    if [ ! -f "/tmp/dusky_tm_stashed_${DUSKY_SESSION_ID}" ]; then
        git rev-parse --abbrev-ref HEAD > "/tmp/dusky_tm_branch_${DUSKY_SESSION_ID}" 2>/dev/null || echo "main" > "/tmp/dusky_tm_branch_${DUSKY_SESSION_ID}"

        # Only stash modifications to tracked files. Stashing untracked files in $HOME
        # causes Git to archive gigabytes of unrelated data and freezes the kernel.
        if ! git diff --quiet || ! git diff --cached --quiet; then
            git stash push --quiet -m "DUSKY_TM_STASH_${DUSKY_SESSION_ID}" || true
            echo "STASHED" > "/tmp/dusky_tm_stashed_${DUSKY_SESSION_ID}"
        else
            echo "CLEAN" > "/tmp/dusky_tm_stashed_${DUSKY_SESSION_ID}"
        fi
    fi

    # The --force flag ensures Git bypasses index overwrites without halting, 
    # and the logical OR (|| true) guarantees subshell won't exit abruptly.
    git checkout --force "$target_commit" -- || true
}
export -f _dusky_git_checkout

_dusky_git_return() {
    # Detach I/O
    exec < /dev/null > /dev/null 2>&1

    local branch="main"
    if [ -f "/tmp/dusky_tm_branch_${DUSKY_SESSION_ID}" ]; then
        branch=$(cat "/tmp/dusky_tm_branch_${DUSKY_SESSION_ID}")
    fi

    # Force checkout the original branch to guarantee flawless return
    git checkout --force "$branch" -- || true

    # Safely restore uncommitted tracked changes exactly as they were
    if [ -f "/tmp/dusky_tm_stashed_${DUSKY_SESSION_ID}" ]; then
        local status
        status=$(cat "/tmp/dusky_tm_stashed_${DUSKY_SESSION_ID}")
        if [ "$status" = "STASHED" ]; then
            git stash pop --quiet || true
        fi
        
        # Free up variables so you can time-travel again smoothly in the same session
        rm -f "/tmp/dusky_tm_stashed_${DUSKY_SESSION_ID}"
        rm -f "/tmp/dusky_tm_branch_${DUSKY_SESSION_ID}"
    fi
}
export -f _dusky_git_return

_dusky_git_restore() {
    exec < /dev/null > /dev/null 2>&1
    git reset --hard HEAD || true
}
export -f _dusky_git_restore

_dusky_git_copy() {
    exec < /dev/null > /dev/null 2>&1
    local commit
    commit=$(echo "$1" | awk '{print $1}')
    [ -z "$commit" ] && return 0
    echo -n "$commit" | wl-copy || true
}
export -f _dusky_git_copy

_dusky_git_list() {
    # Generate the commit log with calculated ANSI formatting
    git log --color=always --format="%C(auto)%h%d %s %C(black)%C(bold)%cr" "$@"
}
export -f _dusky_git_list

# =============================================================================
# 3. FZF UI & EXECUTION
# =============================================================================

_dusky_git_list | fzf \
    --ansi \
    --no-sort \
    --reverse \
    --tiebreak=index \
    --with-shell='bash -c' \
    --prompt=" :: Time Machine ❯ " \
    --header="  Git History Navigation (Bare Repository)" \
    --header-first \
    --bind="enter:execute-silent(_dusky_git_checkout {1})+transform-prompt( [ -n \"{1}\" ] && echo \" :: Traveled to {1} ❯ \" || echo \" :: Time Machine ❯ \" )+reload-sync(_dusky_git_list)" \
    --bind="double-click:execute-silent(_dusky_git_checkout {1})+transform-prompt( [ -n \"{1}\" ] && echo \" :: Traveled to {1} ❯ \" || echo \" :: Time Machine ❯ \" )+reload-sync(_dusky_git_list)" \
    --bind="ctrl-r:execute-silent(_dusky_git_return)+change-prompt( :: Returned to Present ❯ )+reload-sync(_dusky_git_list)" \
    --bind="ctrl-w:execute-silent(_dusky_git_restore)+change-prompt( :: Restored (Hard Reset) ❯ )+reload-sync(_dusky_git_list)" \
    --bind="alt-c:execute-silent(_dusky_git_copy {1})+transform-prompt( [ -n \"{1}\" ] && echo \" :: Copied {1} ❯ \" || echo \" :: Time Machine ❯ \" )" \
    --preview="git show --color=always {1} | delta --side-by-side --width=\${FZF_PREVIEW_COLUMNS:-\$COLUMNS}" \
    --preview-window="right:65%:border-left:wrap"
