#!/usr/bin/env python3
"""
Clipboard Persistence Manager (Wayland/Arch Linux)
Architecture: Atomic IPC State, Strict umask / Python 3.14.6
"""

import os
import sys
import time
import argparse
import subprocess
import shutil
import tempfile
from pathlib import Path

# Enforce strict zero-trust permissions system-wide for this process.
# This mirrors the `umask 077` directive from the FZF script to protect sensitive clipboard data.
os.umask(0o077)

# =============================================================================
# ANSI Constants
# =============================================================================
C_RESET  = "\033[0m"
C_RED    = "\033[0;31m"
C_GREEN  = "\033[0;32m"
C_BLUE   = "\033[0;34m"
C_YELLOW = "\033[1;33m"
C_BOLD   = "\033[1m"

# =============================================================================
# Global Configuration
# =============================================================================
HOME = Path.home()
STATE_DIR = HOME / ".config" / "dusky" / "settings"

# These paths are strictly maintained to interface perfectly with your FZF script.
STATE_FILE = STATE_DIR / "clipboard_persistance"
DB_ENV_FILE = STATE_DIR / "cliphist_db_env"

QUIET_MODE = False

# =============================================================================
# Logging
# =============================================================================
def log_info(msg: str) -> None:
    if not QUIET_MODE: print(f"{C_BLUE}[INFO]{C_RESET} {msg}")

def log_success(msg: str) -> None:
    if not QUIET_MODE: print(f"{C_GREEN}[SUCCESS]{C_RESET} {msg}")

def log_warn(msg: str) -> None:
    if not QUIET_MODE: print(f"{C_YELLOW}[WARN]{C_RESET} {msg}")

def log_err(msg: str) -> None:
    print(f"{C_RED}[ERROR]{C_RESET} {msg}", file=sys.stderr)

# =============================================================================
# Core Logic
# =============================================================================
def write_atomic(target_path: Path, content: str) -> None:
    """
    Executes a POSIX atomic rename. This guarantees that external bash scripts
    sourcing this file will never read a partial or empty state, even if they 
    execute on the exact microsecond this function runs.
    """
    target_path.parent.mkdir(parents=True, exist_ok=True)
    
    fd, tmp_path = tempfile.mkstemp(dir=target_path.parent, text=True)
    try:
        with os.fdopen(fd, 'w', encoding="utf-8") as f:
            f.write(content)
        # Ensure atomic replacement across the filesystem
        os.replace(tmp_path, target_path)
    except Exception as e:
        # Cleanup temp file on critical failure
        if os.path.exists(tmp_path):
            os.remove(tmp_path)
        raise e

def update_config(mode: str) -> str:
    if mode == "ephemeral":
        runtime_dir = os.environ.get("XDG_RUNTIME_DIR", f"/run/user/{os.getuid()}")
        db_path = f"{runtime_dir}/cliphist.db"
        
        write_atomic(STATE_FILE, "false\n")
        write_atomic(DB_ENV_FILE, f'export CLIPHIST_DB_PATH="{db_path}"\n')
        
        log_success("Set to Ephemeral (RAM). State file updated.")
        
    elif mode == "persistent":
        cache_dir = os.environ.get("XDG_CACHE_HOME", str(HOME / ".cache"))
        target_dir = Path(cache_dir) / "cliphist"
        target_dir.mkdir(parents=True, exist_ok=True)
        db_path = f"{target_dir}/db"
        
        write_atomic(STATE_FILE, "true\n")
        write_atomic(DB_ENV_FILE, f'export CLIPHIST_DB_PATH="{db_path}"\n')
        
        log_success("Set to Persistent (Disk). State file updated.")
    
    else:
        raise ValueError("Critical IPC Failure: Invalid mode configuration.")
        
    return db_path

def reload_daemons(db_path: str) -> None:
    if not QUIET_MODE: print()
    log_info("Live-reloading clipboard daemons in background...")
    
    # 1. Resolve Absolute Binary Paths (Zero-Trust PATH Execution)
    wl_paste_bin = shutil.which("wl-paste")
    cliphist_bin = shutil.which("cliphist")
    
    if not wl_paste_bin or not cliphist_bin:
        log_err("Required Wayland dependencies (wl-paste, cliphist) are missing from PATH.")
        sys.exit(1)
    
    # 2. Systemd / DBus Environment Sync
    daemon_env = os.environ.copy()
    daemon_env["CLIPHIST_DB_PATH"] = db_path
    
    try:
        subprocess.run(["systemctl", "--user", "import-environment", "CLIPHIST_DB_PATH"], 
                       env=daemon_env, timeout=5, check=False, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        subprocess.run(["dbus-update-activation-environment", "--systemd", "CLIPHIST_DB_PATH"], 
                       env=daemon_env, timeout=5, check=False, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except FileNotFoundError:
        log_warn("Systemd/DBus integration tools missing; environment not updated globally.")

    # 3. Terminate existing Wayland watchers
    subprocess.run(["pkill", "-9", "-f", r"wl-paste.*cliphist"], check=False, stderr=subprocess.DEVNULL)
    subprocess.run(["pkill", "-9", "-f", r"cliphist_db_env.*wl-paste"], check=False, stderr=subprocess.DEVNULL)
    time.sleep(0.35)
    
    # 4. Respawn the daemons via POSIX setsid() with absolute paths
    cmd_text = [wl_paste_bin, "--type", "text", "--watch", cliphist_bin, "store"]
    cmd_image = [wl_paste_bin, "--type", "image", "--watch", cliphist_bin, "store"]
    
    subprocess.Popen(cmd_text, env=daemon_env, start_new_session=True,
                     stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    subprocess.Popen(cmd_image, env=daemon_env, start_new_session=True,
                     stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    
    log_success("Daemons reloaded in background. New persistence mode is now active!")

def interactive_menu() -> str:
    sys.stdout.write("\033[2J\033[H")
    sys.stdout.flush()
    
    print(f"{C_BOLD}Clipboard Persistence Manager{C_RESET}")
    print(f"Target: {DB_ENV_FILE}\n")
    print(f"{C_BOLD}Which mode do you prefer?{C_RESET}\n")
    
    print(f"  {C_BOLD}1) Ephemeral (RAM-based){C_RESET}")
    print("     - Clipboard history is stored in RAM.")
    print(f"     - It {C_RED}disappears{C_RESET} when you reboot or shutdown.")
    print("     - Good for privacy and saving disk writes.\n")
    
    print(f"  {C_BOLD}2) Persistent (Disk-based){C_RESET}")
    print("     - Clipboard history is stored on your hard drive.")
    print(f"     - Your history {C_GREEN}stays available{C_RESET} even after you reboot.")
    print("     - Standard behavior for most users.\n")
    
    try:
        choice = input("Select option [1/2] (default: 1): ").strip()
    except (KeyboardInterrupt, EOFError):
        print()
        sys.exit(130)
        
    return "ephemeral" if choice == "1" or not choice else "persistent" if choice == "2" else ""

# =============================================================================
# Entry Point
# =============================================================================
def main():
    global QUIET_MODE

    if os.geteuid() == 0:
        log_err("Do NOT run this script as root/sudo.")
        sys.exit(1)

    parser = argparse.ArgumentParser(description="Clipboard Persistence Manager")
    group = parser.add_mutually_exclusive_group()
    group.add_argument('--ram', action='store_true', help="Set to Ephemeral (RAM)")
    group.add_argument('--disk', action='store_true', help="Set to Persistent (Disk)")
    parser.add_argument('--quiet', action='store_true', help="Suppress standard output")
    
    args = parser.parse_args()
    QUIET_MODE = args.quiet
    
    target_mode = ""
    if args.ram:
        target_mode = "ephemeral"
    elif args.disk:
        target_mode = "persistent"

    if not target_mode:
        if not sys.stdin.isatty():
            log_err("Interactive TTY required for menu.")
            log_info("Use --ram or --disk for non-interactive execution.")
            sys.exit(1)
            
        target_mode = interactive_menu()
        if not target_mode:
            log_err("Invalid selection. Exiting.")
            sys.exit(1)
    else:
        log_info(f"Applying {target_mode.capitalize()} settings...")

    try:
        db_path = update_config(target_mode)
        reload_daemons(db_path)
    except KeyboardInterrupt:
        sys.exit(130)

if __name__ == "__main__":
    main()
