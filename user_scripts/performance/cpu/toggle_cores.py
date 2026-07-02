#!/usr/bin/env python3
"""
Advanced Intel P-Core/E-Core Hotplug Manager (Interactive Edition)
Kernel 7.1+ | Python 3.14+ | Arch Linux Optimized
"""

import os
import sys
import subprocess
import curses
from pathlib import Path
import argparse

# ==========================================
# 1. Auto-Privilege & Auto-Dependency System
# ==========================================
if os.geteuid() != 0:
    print("\033[93m[!] Elevating to root privileges for CPU management...\033[0m")
    os.execvp("sudo", ["sudo", sys.executable] + sys.argv)

try:
    from rich.console import Console
    from rich.table import Table
    from rich.panel import Panel
except ImportError:
    print("\033[93m[!] Missing 'rich' library. Auto-installing via pacman...\033[0m")
    try:
        subprocess.run(["pacman", "-S", "--needed", "--noconfirm", "python-rich"], check=True)
    except subprocess.CalledProcessError:
        print("\033[91m[X] Failed to install dependencies. Please run: sudo pacman -S python-rich\033[0m")
        sys.exit(1)
    os.execvp(sys.executable, [sys.executable] + sys.argv)

console = Console()

# ==========================================
# 2. Core I/O & Topology Logic
# ==========================================
def safe_read(path: Path, default: str = "") -> str:
    try:
        if path.is_file():
            return path.read_text().strip()
    except OSError:
        pass
    return default

def hydrate_and_detect_topology() -> tuple[list[int], list[int]]:
    p_cores: list[int] = []
    e_cores: list[int] = []
    
    cpu_sysfs = Path("/sys/devices/system/cpu")
    cpu_nodes = sorted(
        [node for node in cpu_sysfs.glob("cpu[0-9]*") if node.is_dir()],
        key=lambda p: int(p.name[3:])
    )
    
    original_states: dict[int, str] = {}

    for node in cpu_nodes:
        cpu_id = int(node.name[3:])
        online_file = node / "online"
        if online_file.exists():
            current_state = safe_read(online_file)
            original_states[cpu_id] = current_state
            if current_state == "0":
                try:
                    online_file.write_text("1")
                except OSError:
                    pass

    for node in cpu_nodes:
        cpu_id = int(node.name[3:])
        topology_dir = node / "topology"
        
        core_type_val = safe_read(topology_dir / "core_type")
        if core_type_val in ("1", "0x10", "intel_atom"):
            e_cores.append(cpu_id)
            continue
        elif core_type_val in ("2", "0x20", "intel_core", "0"):
            p_cores.append(cpu_id)
            continue

        core_cpus = safe_read(topology_dir / "core_cpus_list")
        if core_cpus and ("," in core_cpus or "-" in core_cpus):
            p_cores.append(cpu_id)
        else:
            e_cores.append(cpu_id)

    for cpu_id, original_state in original_states.items():
        if original_state == "0":
            try:
                Path(f"/sys/devices/system/cpu/cpu{cpu_id}/online").write_text("0")
            except OSError:
                pass

    return sorted(p_cores), sorted(e_cores)

def get_core_status(cpu_id: int) -> bool:
    return safe_read(Path(f"/sys/devices/system/cpu/cpu{cpu_id}/online"), default="1") == "1"

def set_core_status(cpu_id: int, enable: bool) -> tuple[bool, str]:
    online_file = Path(f"/sys/devices/system/cpu/cpu{cpu_id}/online")
    target_state = "1" if enable else "0"
    
    if not online_file.exists():
         return False, "Locked"
    if safe_read(online_file) == target_state:
         return True, "Already in target state"
         
    try:
        online_file.write_text(target_state)
        if safe_read(online_file) == target_state:
             return True, "Success"
        return False, "Ignored"
    except OSError as e:
        return False, "Locked"

# ==========================================
# 3. Interactive UI (Curses)
# ==========================================
def interactive_mode(stdscr, p_cores: list[int], e_cores: list[int]):
    curses.curs_set(0) # Hide cursor
    curses.start_color()
    curses.use_default_colors()
    
    # Setup Colors
    curses.init_pair(1, curses.COLOR_BLUE, -1)   # P-Core color
    curses.init_pair(2, curses.COLOR_GREEN, -1)  # E-Core / Online color
    curses.init_pair(3, curses.COLOR_RED, -1)    # Offline color
    curses.init_pair(4, curses.COLOR_BLACK, curses.COLOR_WHITE) # Highlight

    all_cores = sorted(p_cores + e_cores)
    current_row = 0
    feedback_msg = ""

    while True:
        stdscr.clear()
        
        # Header
        stdscr.addstr(0, 0, " Live CPU Core Manager ", curses.A_REVERSE | curses.color_pair(2))
        stdscr.addstr(1, 0, "Controls: ", curses.A_BOLD)
        stdscr.addstr(1, 10, "[↑/↓] Navigate  [SPACE] Toggle Core  [E] E-Cores Only  [P] P-Cores Only  [A] All Cores  [Q] Quit")
        
        if feedback_msg:
            stdscr.addstr(2, 0, f" Status: {feedback_msg} ", curses.color_pair(3) | curses.A_BOLD)
        else:
            stdscr.addstr(2, 0, " " * 50)

        stdscr.addstr(4, 2, f"{'CORE':<6} | {'ARCHITECTURE':<20} | {'STATE':<10}", curses.A_UNDERLINE)

        # Core List
        for idx, core in enumerate(all_cores):
            is_online = get_core_status(core)
            
            arch = "P-Core (Performance)" if core in p_cores else "E-Core (Efficiency)"
            arch_color = curses.color_pair(1) if core in p_cores else curses.color_pair(2)
            
            status_str = "Online" if is_online else "Sleeping"
            status_color = curses.color_pair(2) if is_online else curses.color_pair(3)
            
            y_pos = 5 + idx
            
            # Row Highlighting
            if idx == current_row:
                stdscr.addstr(y_pos, 2, f"CPU {core:02d} | {arch:<20} | {status_str:<10}", curses.color_pair(4))
            else:
                stdscr.addstr(y_pos, 2, f"CPU {core:02d} | ", curses.A_NORMAL)
                stdscr.addstr(y_pos, 11, f"{arch:<20}", arch_color)
                stdscr.addstr(y_pos, 34, f"| {status_str:<10}", status_color)

        stdscr.refresh()
        
        # Input Handling
        key = stdscr.getch()
        feedback_msg = ""
        
        if key == curses.KEY_UP and current_row > 0:
            current_row -= 1
        elif key == curses.KEY_DOWN and current_row < len(all_cores) - 1:
            current_row += 1
        elif key == ord(' '): # Spacebar
            core = all_cores[current_row]
            current_state = get_core_status(core)
            success, msg = set_core_status(core, enable=not current_state)
            if not success:
                feedback_msg = f"CPU {core:02d}: {msg}"
        elif key in (ord('e'), ord('E')):
            for c in p_cores: set_core_status(c, False)
            for c in e_cores: set_core_status(c, True)
            feedback_msg = "Maximum Power Saving Mode Activated"
        elif key in (ord('p'), ord('P')):
            for c in e_cores: set_core_status(c, False)
            for c in p_cores: set_core_status(c, True)
            feedback_msg = "High Performance Mode Activated"
        elif key in (ord('a'), ord('A')):
            for c in all_cores: set_core_status(c, True)
            feedback_msg = "All Cores Online"
        elif key in (ord('q'), ord('Q')):
            break

# ==========================================
# 4. CLI Fallback & Formatting
# ==========================================
def display_status_table(p_cores: list[int], e_cores: list[int]) -> None:
    table = Table(title="Live CPU Core Topology & ACPI Status", show_header=True, header_style="bold cyan")
    table.add_column("Logical Core ID", justify="center")
    table.add_column("Microarchitecture", justify="center")
    table.add_column("Kernel Hotplug State", justify="center")
    
    for core in sorted(p_cores + e_cores):
        arch = "[bold blue]P-Core (Performance)[/bold blue]" if core in p_cores else "[bold green]E-Core (Efficiency)[/bold green]"
        status = get_core_status(core)
        status_str = "[bold green]Online (Active)[/bold green]" if status else "[bold red]Offline (Sleeping)[/bold red]"
        table.add_row(f"CPU {core:02d}", arch, status_str)
        
    console.print(table)

def batch_process_cores(cores: list[int], enable: bool, action_name: str) -> None:
    console.print(f"[bold yellow]Initiating {action_name} Sequence...[/bold yellow]")
    for core in cores:
        success, msg = set_core_status(core, enable=enable)
        color = "green" if success else "yellow"
        console.print(f"CPU {core:02d}: [{color}]{msg}[/{color}]")

def main() -> None:
    p_cores, e_cores = hydrate_and_detect_topology()
    all_known_cores = p_cores + e_cores

    if not e_cores:
        console.print(Panel("[bold red]Symmetric Topology Detected![/bold red] No E-cores found.", border_style="red"))
        sys.exit(1)

    # Launch Interactive UI if run without arguments
    if len(sys.argv) == 1:
        curses.wrapper(interactive_mode, p_cores, e_cores)
        sys.exit(0)

    # Proceed with CLI parsing if arguments exist
    parser = argparse.ArgumentParser(description="Advanced Hybrid Core Hotplug Manager")
    subparsers = parser.add_subparsers(dest="command", required=True)

    subparsers.add_parser("interactive", help="Launch the Live TUI (Default if no args)")
    subparsers.add_parser("status", help="View topology and core states")
    subparsers.add_parser("ecores-only", help="Disable P-Cores, Enable E-Cores")
    subparsers.add_parser("pcores-only", help="Disable E-Cores, Enable P-Cores")
    subparsers.add_parser("all-cores", help="Enable all cores")

    args = parser.parse_args()

    match args.command:
        case "interactive":
            curses.wrapper(interactive_mode, p_cores, e_cores)
        case "status":
            display_status_table(p_cores, e_cores)
        case "ecores-only":
            batch_process_cores(e_cores, enable=True, action_name="E-Core Wakeup")
            batch_process_cores(p_cores, enable=False, action_name="P-Core Shutdown")
            console.print(Panel("[bold green]Power Saving Mode Activated (E-Cores Only).[/bold green]", border_style="green"))
            display_status_table(p_cores, e_cores)
        case "pcores-only":
            batch_process_cores(p_cores, enable=True, action_name="P-Core Wakeup")
            batch_process_cores(e_cores, enable=False, action_name="E-Core Shutdown")
            console.print(Panel("[bold green]High Performance Mode Activated (P-Cores Only).[/bold green]", border_style="green"))
            display_status_table(p_cores, e_cores)
        case "all-cores":
            batch_process_cores(all_known_cores, enable=True, action_name="Global Wakeup")
            console.print(Panel("[bold green]Maximum Throughput Activated (All Cores Online).[/bold green]", border_style="green"))
            display_status_table(p_cores, e_cores)

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        sys.exit(130)
