#!/usr/bin/env python3
"""
Helper script for core_runner to change CPU online/offline status.
Designed to run with elevated privileges via NOPASSWD sudoers.
Includes retry logic for handling transient EBUSY states during hotunplug.
"""
import sys
import argparse
import time
import errno
from pathlib import Path

def set_core_state(cpu_id: int, state: str) -> None:
    if cpu_id == 0 and state == "0":
        # CPU 0 is BSP and cannot be offlined on most platforms, but check safety anyway
        print(f"Skipping core {cpu_id} offlining: BSP must remain online.", file=sys.stderr)
        return
        
    path = Path(f"/sys/devices/system/cpu/cpu{cpu_id}/online")
    if not path.exists():
        if state == "1":
            # If online file doesn't exist, core might be permanently online (like core 0)
            return
        else:
            raise FileNotFoundError(f"State file {path} not found.")
            
    max_retries = 20
    retry_delay = 0.1  # 100ms
    
    for attempt in range(max_retries):
        try:
            path.write_text(state)
            return  # Success
        except PermissionError:
            print(f"Permission denied: Make sure this script is run as root or via sudo.", file=sys.stderr)
            sys.exit(1)
        except OSError as e:
            if state == "0" and e.errno == errno.EBUSY and attempt < max_retries - 1:
                # EBUSY is transient, wait and retry
                time.sleep(retry_delay)
                continue
            print(f"OS Error writing state '{state}' to core {cpu_id}: {e}", file=sys.stderr)
            sys.exit(1)

def parse_cpu_list(cpu_list_str: str) -> list[int]:
    cores = []
    for part in cpu_list_str.split(','):
        part = part.strip()
        if not part:
            continue
        if part.isdigit():
            cores.append(int(part))
        else:
            print(f"Invalid core ID: {part}", file=sys.stderr)
            sys.exit(1)
    return cores

def main() -> None:
    parser = argparse.ArgumentParser(description="CPU Core State Helper")
    parser.add_argument("--online", type=str, help="Comma-separated CPU IDs to online")
    parser.add_argument("--offline", type=str, help="Comma-separated CPU IDs to offline")
    
    args = parser.parse_args()
    
    if not args.online and not args.offline:
        parser.print_help()
        sys.exit(1)
        
    if args.online:
        for cpu in parse_cpu_list(args.online):
            set_core_state(cpu, "1")
            
    if args.offline:
        for cpu in parse_cpu_list(args.offline):
            set_core_state(cpu, "0")

if __name__ == "__main__":
    main()
