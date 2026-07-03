#!/usr/bin/env bash
#
# nvidia-glx-workaround.sh
# Forces Mesa drivers and prevents NVIDIA GLX driver interference on the latest Arch Linux.

set -euo pipefail

if [ "$#" -eq 0 ]; then
    echo "Usage: $(basename "$0") <command> [args...]" >&2
    exit 1
fi

# 1. Native libglvnd Enforcements for Latest Arch Linux
# Force GLX to use Mesa.
export __GLX_VENDOR_LIBRARY_NAME="mesa"

# Force EGL to use Mesa. The modern libglvnd specification requires the exact path 
# to the vendor JSON configuration file for EGL overrides.
export __EGL_VENDOR_LIBRARY_FILENAMES="/usr/share/glvnd/egl_vendor.d/50_mesa.json"

# Disable Prime Offloading explicitly to prevent NVIDIA runtime hooks.
export __NV_PRIME_RENDER_OFFLOAD=0

# 2. Stub Interception (Multilib-Aware)
# Necessary for applications that bypass libglvnd and dlopen the driver directly.
STUB_BASE="${XDG_CACHE_HOME:-$HOME/.cache}/nvidia-glx-workaround"
STUB_64="$STUB_BASE/64"
STUB_32="$STUB_BASE/32"
TARGET_LIB="libGLX_nvidia.so.0"

# Only attempt compilation if the 64-bit stub doesn't exist
if [ ! -f "$STUB_64/$TARGET_LIB" ]; then
    if command -v gcc >/dev/null 2>&1; then
        mkdir -p "$STUB_64" "$STUB_32"
        STUB_SRC=$(mktemp)
        
        # C stub safely neuters the library to fail NVIDIA probes harmlessly.
        cat > "$STUB_SRC" << 'STUBEOF'
void* glXGetClientString(void *d, int n) { return (void*)0; }
void* glXQueryServerString(void *d, int s, int n) { return (void*)0; }
void* glXGetScreenSpec(void *d, int s, const char *t) { return (void*)0; }
void* glXGetProcAddress(const char *p) { return (void*)0; }
void* glXGetProcAddressARB(const char *p) { return (void*)0; }
STUBEOF
        
        # Compile 64-bit stub
        gcc -x c -m64 -shared -fPIC -O2 -o "$STUB_64/$TARGET_LIB" "$STUB_SRC" 2>/dev/null || true
        
        # Compile 32-bit stub (Fails gracefully if lib32-glibc/gcc-multilib is missing)
        gcc -x c -m32 -shared -fPIC -O2 -o "$STUB_32/$TARGET_LIB" "$STUB_SRC" 2>/dev/null || true
        
        rm -f "$STUB_SRC"
    else
        echo "Warning: gcc not found. Relying on libglvnd env vars only." >&2
    fi
fi

# 3. Inject stubs into the library path.
# ld.so gracefully skips shared objects with the wrong ELF class.
STUB_PATH=""
[ -f "$STUB_64/$TARGET_LIB" ] && STUB_PATH="$STUB_64"
[ -f "$STUB_32/$TARGET_LIB" ] && STUB_PATH="${STUB_PATH:+$STUB_PATH:}$STUB_32"

if [ -n "$STUB_PATH" ]; then
    export LD_LIBRARY_PATH="$STUB_PATH${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}"
fi

exec "$@"
