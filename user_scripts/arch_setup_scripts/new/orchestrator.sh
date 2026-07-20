#!/usr/bin/env bash
# ==============================================================================
# ARCH LINUX MASTER ORCHESTRATOR WRAPPER
# ==============================================================================
# Bleeding-edge Arch bootstrap wrapper.
# Installs only missing dependencies, then hands off to the Python orchestrator.
# ==============================================================================

set -Eeuo pipefail

SCRIPT_DIR="$(dirname "$(realpath "${BASH_SOURCE[0]}")")"
readonly SCRIPT_DIR
readonly ORCHESTRATOR_PY="${SCRIPT_DIR}/orchestrator.py"
readonly NETWORK_SCRIPT="${SCRIPT_DIR}/scripts/003_network_connect.sh"

declare -g RED="" GREEN="" YELLOW="" BLUE="" BOLD="" RESET=""

if [[ -t 1 ]]; then
    RED=$'\e[1;31m'
    GREEN=$'\e[1;32m'
    YELLOW=$'\e[1;33m'
    BLUE=$'\e[1;34m'
    BOLD=$'\e[1m'
    RESET=$'\e[0m'
fi

log() {
    local level="$1"
    local msg="$2"
    local color=""

    case "$level" in
        INFO)    color="$BLUE" ;;
        SUCCESS) color="$GREEN" ;;
        WARN)    color="$YELLOW" ;;
        ERROR)   color="$RED" ;;
        RUN)     color="$BOLD" ;;
    esac

    printf "%s[%s]%s %s\n" "${color}" "${level}" "${RESET}" "${msg}"
}

trap 'log ERROR "Wrapper failed at line ${LINENO}."' ERR

check_internet() {
    if command -v curl >/dev/null 2>&1; then
        if curl -fsS --max-time 5 https://archlinux.org >/dev/null 2>&1; then
            return 0
        fi
    fi

    if command -v getent >/dev/null 2>&1; then
        if getent hosts archlinux.org >/dev/null 2>&1; then
            return 0
        fi
    fi

    if command -v resolvectl >/dev/null 2>&1; then
        if resolvectl query archlinux.org >/dev/null 2>&1; then
            return 0
        fi
    fi

    if ping -n -q -c 1 -W 2 1.1.1.1 >/dev/null 2>&1; then
        return 0
    fi

    return 1
}

require_internet() {
    if check_internet; then
        log SUCCESS "Internet connection verified."
        return 0
    fi

    log WARN "No internet connection detected."

    if [[ -x "$NETWORK_SCRIPT" ]]; then
        log RUN "Launching network configuration script..."
        "$NETWORK_SCRIPT" || true

        if check_internet; then
            log SUCCESS "Internet connection established."
            return 0
        fi
    fi

    log ERROR "Internet is required to install missing dependencies."
    exit 1
}

choose_python() {
    if [[ -x /usr/bin/python ]]; then
        printf "/usr/bin/python"
        return 0
    fi

    if command -v python >/dev/null 2>&1; then
        command -v python
        return 0
    fi

    return 1
}

pkg_installed() {
    pacman -Qq "$1" >/dev/null 2>&1
}

main() {
    if [[ ! -f "$ORCHESTRATOR_PY" ]]; then
        log ERROR "Cannot find python orchestrator at: $ORCHESTRATOR_PY"
        exit 1
    fi

    local -a missing_pkgs=()

    if ! pkg_installed python; then
        missing_pkgs+=("python")
    fi

    if ! pkg_installed python-textual; then
        missing_pkgs+=("python-textual")
    fi

    if ! pkg_installed python-rich; then
        missing_pkgs+=("python-rich")
    fi

    if ! pkg_installed git; then
        missing_pkgs+=("git")
    fi

    if (( ${#missing_pkgs[@]} > 0 )); then
        require_internet

        log INFO "Administrative privileges required to install missing dependencies."
        if ! sudo -v; then
            log ERROR "Sudo authentication failed. Cannot install dependencies."
            exit 1
        fi

        if [[ -f /var/lib/pacman/db.lck ]]; then
            log WARN "Pacman lock file detected: /var/lib/pacman/db.lck"
            log WARN "If no pacman process is running, remove it manually and rerun."
        fi

        log RUN "Installing missing packages: ${missing_pkgs[*]}"
        sudo pacman -Syu --needed --noconfirm "${missing_pkgs[@]}"

        log SUCCESS "All dependencies satisfied."
    else
        log SUCCESS "All dependencies already satisfied."
    fi

    local PYTHON_BIN
    if ! PYTHON_BIN="$(choose_python)"; then
        log ERROR "Python interpreter not found after dependency bootstrap."
        exit 1
    fi

    log RUN "Launching Dusky Orchestrator..."
    exec env \
        PYTHONUNBUFFERED=1 \
        PYTHONUTF8=1 \
        PYTHONDONTWRITEBYTECODE=1 \
        "$PYTHON_BIN" "$ORCHESTRATOR_PY" "$@"
}

main "$@"
