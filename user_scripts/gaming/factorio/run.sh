#!/usr/bin/env bash
set -eo pipefail

# ── Config ────────────────────────────────────────────────
GAME_DIR="/mnt/zram1/game/Factorio-jc141"
NVIDIA_WRAPPER="/mnt/zram1/nvidia-glx-workaround.sh"
# ──────────────────────────────────────────────────────────

usage() {
    echo "Factorio launcher — auto-mounts DwarFS, applies NVIDIA GLX/EGL workaround, runs game."
    echo
    echo "Usage:  $(basename "$0") [--help|-h]"
    echo
    echo "Edit GAME_DIR and NVIDIA_WRAPPER at the top of the script to change paths."
    exit 0
}

[ "${1:-}" = "--help" ] || [ "${1:-}" = "-h" ] && usage

DWARFS_IMG="$GAME_DIR/files/game-root.dwarfs"
DWARFS_MNT="$GAME_DIR/files/.game-root-mnt"
OVERLAY_DIR="$GAME_DIR/files/game-root"
OVERLAY_STORAGE="$GAME_DIR/files/overlay-storage"
OVERLAY_WORK="$GAME_DIR/files/.game-root-work"
DWARFS_BIN="$GAME_DIR/files/dwarfs-binary"

mount_game() {
    local ram total cache
    total=$(awk '/MemTotal/{print $2}' /proc/meminfo)
    cache=$((total * 25 / 100))

    mkdir -p "$DWARFS_MNT" "$OVERLAY_STORAGE" "$OVERLAY_WORK" "$OVERLAY_DIR"
    chmod +x "$DWARFS_BIN"

    "$DWARFS_BIN" --tool=dwarfs "$DWARFS_IMG" "$DWARFS_MNT" \
        -o tidy_strategy=time -o tidy_interval=15m -o tidy_max_age=30m \
        -o cachesize="${cache}k" -o clone_fd

    fuse-overlayfs \
        -o squash_to_uid="$(id -u)" \
        -o squash_to_gid="$(id -g)" \
        -o lowerdir="$DWARFS_MNT",upperdir="$OVERLAY_STORAGE",workdir="$OVERLAY_WORK" \
        "$OVERLAY_DIR"

    echo "Mounted $GAME_DIR"
}

is_mounted() {
    [ -d "$OVERLAY_DIR" ] && [ -n "$(ls -A "$OVERLAY_DIR" 2>/dev/null)" ]
}

if ! is_mounted; then
    echo "Mounting game..."
    mount_game
else
    echo "Already mounted"
fi

GAME_BIN="$OVERLAY_DIR/bin/x64/factorio"

if [ ! -x "$GAME_BIN" ]; then
    echo "Error: $GAME_BIN not found" >&2
    exit 1
fi

exec "$NVIDIA_WRAPPER" "$GAME_BIN" "$@"
