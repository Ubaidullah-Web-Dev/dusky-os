#!/usr/bin/env python3
"""
Dusky Core Manager (Ultimate Edition)
Kernel 7.1+ | Python 3.14+ | Arch Linux Optimized
BSP-Aware | Race-Condition Immune | Live Dynamic TUI
"""

import os
import sys
import subprocess
import curses
import time
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
    from rich.align import Align
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
    """Safely reads volatile sysfs files to prevent I/O crashes."""
    try:
        if path.is_file():
            return path.read_text().strip()
    except OSError:
        pass
    return default

def hydrate_and_detect_topology() -> tuple[list[int], list[int], set[int]]:
    """Safely hydrates offline cores and polls for sysfs topology propagation."""
    p_cores: list[int] = []
    e_cores: list[int] = []
    locked_cores: set[int] = set()
    
    cpu_sysfs = Path("/sys/devices/system/cpu")
    cpu_nodes = sorted(
        [node for node in cpu_sysfs.glob("cpu[0-9]*") if node.is_dir()],
        key=lambda p: int(p.name[3:])
    )
    
    original_states: dict[int, str] = {}

    # HYDRATION PHASE
    for node in cpu_nodes:
        cpu_id = int(node.name[3:])
        online_file = node / "online"
        
        if not online_file.exists():
            locked_cores.add(cpu_id)
            continue
            
        current_state = safe_read(online_file)
        original_states[cpu_id] = current_state
        
        if current_state == "0":
            try:
                online_file.write_text("1")
                topology_dir = node / "topology"
                for _ in range(10): # Wait up to 50ms for kernel workers
                    if topology_dir.exists():
                        break
                    time.sleep(0.005)
            except OSError:
                pass

    # DETECTION PHASE
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

    # DEHYDRATION PHASE
    for cpu_id, original_state in original_states.items():
        if original_state == "0":
            try:
                Path(f"/sys/devices/system/cpu/cpu{cpu_id}/online").write_text("0")
            except OSError:
                pass

    return sorted(p_cores), sorted(e_cores), locked_cores

def get_core_status(cpu_id: int) -> bool:
    return safe_read(Path(f"/sys/devices/system/cpu/cpu{cpu_id}/online"), default="1") == "1"

def get_core_freq(cpu_id: int) -> str:
    """Reads live frequency. Fails silently to '---' if the core is sleeping/offline."""
    freq_path = Path(f"/sys/devices/system/cpu/cpu{cpu_id}/cpufreq/scaling_cur_freq")
    try:
        if freq_path.is_file():
            val = freq_path.read_text().strip()
            if val.isdigit():
                return f"{int(val) // 1000} MHz"
    except OSError:
        pass
    return "---"

def set_core_status(cpu_id: int, enable: bool) -> tuple[bool, str]:
    online_file = Path(f"/sys/devices/system/cpu/cpu{cpu_id}/online")
    target_state = "1" if enable else "0"
    
    if not online_file.exists():
         return False, "Hardware Blocked (BSP)"
    if safe_read(online_file) == target_state:
         return True, "Already in target state"
         
    try:
        online_file.write_text(target_state)
        if safe_read(online_file) == target_state:
             return True, "Success"
        return False, "Kernel overridden change"
    except OSError as e:
        return False, f"Locked ({e.strerror})"

# ==========================================
# 3. Interactive UI (Curses with Vim Keys)
# ==========================================
def interactive_mode(stdscr, p_cores: list[int], e_cores: list[int], locked_cores: set[int]) -> None:
    curses.curs_set(0)
    curses.start_color()
    curses.use_default_colors()
    
    # Vibrant Color Setup
    curses.init_pair(1, curses.COLOR_CYAN, -1)     # P-Core
    curses.init_pair(2, curses.COLOR_GREEN, -1)    # E-Core / Online
    curses.init_pair(3, curses.COLOR_RED, -1)      # Offline / Sleeping
    curses.init_pair(4, curses.COLOR_BLACK, curses.COLOR_WHITE) # UI Highlight
    curses.init_pair(5, curses.COLOR_YELLOW, -1)   # BSP Locked
    curses.init_pair(6, curses.COLOR_MAGENTA, -1)  # Headers

    # Set getch() to be non-blocking with a 1-second timeout for live frequency polling
    stdscr.timeout(1000)

    all_cores = sorted(p_cores + e_cores)
    current_row = 0
    feedback_msg = ""
    last_key_was_g = False

    while True:
        stdscr.clear()
        max_y, max_x = stdscr.getmaxyx()
        
        if max_y < 12:
            stdscr.addstr(1, 0, "Terminal too small!", curses.color_pair(3) | curses.A_BOLD)
            stdscr.refresh()
            stdscr.getch()
            continue

        # Centered Heading
        title = " Dusky Core Manager "
        start_x = max(0, (max_x - len(title)) // 2)
        stdscr.addstr(0, start_x, title, curses.A_REVERSE | curses.A_BOLD | curses.color_pair(6))
        
        # Feedback Notification
        if feedback_msg:
            msg_str = f" Status: {feedback_msg} "
            msg_x = max(0, (max_x - len(msg_str)) // 2)
            stdscr.addstr(1, msg_x, msg_str, curses.color_pair(3) | curses.A_BOLD)
            
        # Controls Layout
        stdscr.addstr(2, 2, "Controls: ", curses.A_BOLD | curses.color_pair(6))
        stdscr.addstr(2, 12, "[j/k] Nav  [Ctrl+u/d] Jump  [gg/G] Top/Bottom  [SPACE] Toggle  [Q] Quit")
        stdscr.addstr(3, 2, "Batch:    ", curses.A_BOLD | curses.color_pair(6))
        stdscr.addstr(3, 12, "[E] E-Cores Only  [P] P-Cores Only  [A] All Cores")

        # Table Header
        stdscr.addstr(5, 2, f"{'CORE':<8} | {'ARCHITECTURE':<12} | {'STATE':<12} | {'FREQUENCY'}", curses.A_UNDERLINE | curses.A_BOLD)

        visible_rows = max_y - 7 
        half_page = visible_rows // 2
        
        start_row = max(0, current_row - visible_rows // 2)
        end_row = min(len(all_cores), start_row + visible_rows)
        
        if end_row - start_row < visible_rows and len(all_cores) > visible_rows:
            start_row = max(0, len(all_cores) - visible_rows)
            end_row = len(all_cores)

        # Dynamic Core Rendering
        for idx in range(start_row, end_row):
            core = all_cores[idx]
            is_locked = core in locked_cores
            is_online = get_core_status(core)
            
            arch = "P-Core" if core in p_cores else "E-Core"
            arch_color = curses.color_pair(1) | curses.A_BOLD if core in p_cores else curses.color_pair(2) | curses.A_BOLD
            
            if is_locked:
                status_str = "BSP Locked"
                status_color = curses.color_pair(5) | curses.A_BOLD
                freq_str = get_core_freq(core)
            else:
                if is_online:
                    status_str = "Online"
                    status_color = curses.color_pair(2) | curses.A_BOLD
                    freq_str = get_core_freq(core)
                else:
                    status_str = "Sleeping"
                    status_color = curses.color_pair(3) | curses.A_DIM
                    freq_str = "---"
            
            y_pos = 6 + (idx - start_row)
            
            # Cursor Highlight vs Standard Row
            if idx == current_row:
                stdscr.addstr(y_pos, 2, f"CPU {core:02d}   | {arch:<12} | {status_str:<12} | {freq_str:<10}", curses.color_pair(4))
            else:
                stdscr.addstr(y_pos, 2, f"CPU {core:02d}   | ", curses.A_NORMAL)
                stdscr.addstr(y_pos, 13, f"{arch:<12}", arch_color)
                stdscr.addstr(y_pos, 28, f"| {status_str:<12}", status_color)
                stdscr.addstr(y_pos, 43, f"| {freq_str:<10}", curses.A_NORMAL)

        stdscr.refresh()
        
        # Keystroke parsing
        key = stdscr.getch()
        feedback_msg = ""
        
        # Timeout triggered (no key pressed in 1s), just restart loop to refresh frequencies
        if key == curses.ERR:
            continue
            
        # Navigation
        if key in (curses.KEY_UP, ord('k')):
            if current_row > 0: current_row -= 1
        elif key in (curses.KEY_DOWN, ord('j')):
            if current_row < len(all_cores) - 1: current_row += 1
        elif key == 4: 
            current_row = min(len(all_cores) - 1, current_row + half_page)
        elif key == 21: 
            current_row = max(0, current_row - half_page)
        elif key == ord('G'):
            current_row = len(all_cores) - 1
        elif key == ord('g'):
            if last_key_was_g:
                current_row = 0
                last_key_was_g = False
            else:
                last_key_was_g = True
                continue 
                
        # Action Logic
        elif key == ord(' '):
            core = all_cores[current_row]
            if core in locked_cores:
                feedback_msg = f"CPU {core:02d} is the Bootstrap Processor (Immutable)."
            else:
                current_state = get_core_status(core)
                success, msg = set_core_status(core, enable=not current_state)
                if not success:
                    feedback_msg = f"CPU {core:02d}: {msg}"
                    
        elif key in (ord('e'), ord('E')):
            for c in p_cores:
                if c not in locked_cores: set_core_status(c, False)
            for c in e_cores: 
                if c not in locked_cores: set_core_status(c, True)
            feedback_msg = "Power Saving Mode Activated"
            
        elif key in (ord('p'), ord('P')):
            for c in e_cores:
                if c not in locked_cores: set_core_status(c, False)
            for c in p_cores:
                if c not in locked_cores: set_core_status(c, True)
            feedback_msg = "Performance Mode Activated"
            
        elif key in (ord('a'), ord('A')):
            for c in all_cores:
                if c not in locked_cores: set_core_status(c, True)
            feedback_msg = "All Cores Online"
            
        elif key in (ord('q'), ord('Q')):
            break
            
        last_key_was_g = False 

# ==========================================
# 4. CLI Fallback & Formatting
# ==========================================
def parse_core_args(args_list: list[str], valid_cores: list[int]) -> list[int]:
    cores = set()
    try:
        for arg in args_list:
            if "-" in arg:
                start, end = sorted(map(int, arg.split("-")))
                cores.update(range(start, end + 1))
            else:
                cores.add(int(arg))
                
        invalid_cores = [c for c in cores if c not in valid_cores]
        if invalid_cores:
            console.print(f"[bold red]Hardware Error:[/bold red] CPUs {invalid_cores} do not exist.")
            sys.exit(1)
            
        return sorted(list(cores))
    except ValueError:
        console.print("[bold red]Error:[/bold red] Invalid format. Use numbers or ranges (e.g., 1 2 12-15)")
        sys.exit(1)

def display_status_table(p_cores: list[int], e_cores: list[int], locked_cores: set[int]) -> None:
    # Centered Rich Header
    title_panel = Panel("[bold magenta]Dusky Core Manager[/bold magenta]", border_style="cyan", expand=False)
    console.print(Align.center(title_panel))
    
    table = Table(show_header=True, header_style="bold cyan", expand=True)
    table.add_column("CORE", justify="center")
    table.add_column("ARCHITECTURE", justify="center")
    table.add_column("STATE", justify="center")
    table.add_column("FREQUENCY", justify="center")
    
    for core in sorted(p_cores + e_cores):
        arch = "[bold cyan]P-Core[/bold cyan]" if core in p_cores else "[bold green]E-Core[/bold green]"
        
        if core in locked_cores:
            status_str = "[bold yellow]BSP Locked[/bold yellow]"
            freq_str = get_core_freq(core)
        else:
            status = get_core_status(core)
            if status:
                status_str = "[bold green]Online[/bold green]"
                freq_str = get_core_freq(core)
            else:
                status_str = "[bold red]Sleeping[/bold red]"
                freq_str = "---"
                
        table.add_row(f"CPU {core:02d}", arch, status_str, freq_str)
        
    console.print(table)

def batch_process_cores(cores: list[int], enable: bool, action_name: str, locked_cores: set[int]) -> None:
    console.print(f"[bold yellow]Initiating {action_name} Sequence...[/bold yellow]")
    for core in cores:
        if core in locked_cores:
            continue
        success, msg = set_core_status(core, enable=enable)
        color = "green" if success else "yellow"
        console.print(f"CPU {core:02d}: [{color}]{msg}[/{color}]")

def main() -> None:
    p_cores, e_cores, locked_cores = hydrate_and_detect_topology()
    all_known_cores = p_cores + e_cores

    if not e_cores:
        console.print(Panel("[bold red]Symmetric Topology Detected![/bold red] No E-cores found.", border_style="red"))
        sys.exit(1)

    if len(sys.argv) == 1:
        curses.wrapper(interactive_mode, p_cores, e_cores, locked_cores)
        sys.exit(0)

    parser = argparse.ArgumentParser(description="Advanced Hybrid Core Hotplug Manager")
    subparsers = parser.add_subparsers(dest="command", required=True)

    subparsers.add_parser("interactive", help="Launch the Live TUI (Default if no args)")
    subparsers.add_parser("status", help="View topology and core states")
    subparsers.add_parser("ecores-only", help="Disable P-Cores, Enable E-Cores")
    subparsers.add_parser("pcores-only", help="Disable E-Cores, Enable P-Cores")
    subparsers.add_parser("all-cores", help="Enable all cores")

    toggle_p = subparsers.add_parser("toggle", help="Toggle state of specific cores")
    toggle_p.add_argument("cores", nargs="+", help="Core IDs (e.g., 1 2 or 12-15)")
    
    enable_p = subparsers.add_parser("enable", help="Enable specific cores")
    enable_p.add_argument("cores", nargs="+", help="Core IDs (e.g., 12-15)")
    
    disable_p = subparsers.add_parser("disable", help="Disable specific cores")
    disable_p.add_argument("cores", nargs="+", help="Core IDs (e.g., 1 2 3)")

    args = parser.parse_args()

    match args.command:
        case "interactive":
            curses.wrapper(interactive_mode, p_cores, e_cores, locked_cores)
        case "status":
            display_status_table(p_cores, e_cores, locked_cores)
        case "ecores-only":
            batch_process_cores(e_cores, enable=True, action_name="E-Core Wakeup", locked_cores=locked_cores)
            batch_process_cores(p_cores, enable=False, action_name="P-Core Shutdown", locked_cores=locked_cores)
            console.print(Panel("[bold green]Power Saving Mode Activated (E-Cores Only).[/bold green]", border_style="green"))
            display_status_table(p_cores, e_cores, locked_cores)
        case "pcores-only":
            batch_process_cores(p_cores, enable=True, action_name="P-Core Wakeup", locked_cores=locked_cores)
            batch_process_cores(e_cores, enable=False, action_name="E-Core Shutdown", locked_cores=locked_cores)
            console.print(Panel("[bold green]High Performance Mode Activated (P-Cores Only).[/bold green]", border_style="green"))
            display_status_table(p_cores, e_cores, locked_cores)
        case "all-cores":
            batch_process_cores(all_known_cores, enable=True, action_name="Global Wakeup", locked_cores=locked_cores)
            console.print(Panel("[bold green]Maximum Throughput Activated (All Cores Online).[/bold green]", border_style="green"))
            display_status_table(p_cores, e_cores, locked_cores)
        case "enable":
            target_cores = parse_core_args(args.cores, all_known_cores)
            batch_process_cores(target_cores, enable=True, action_name="Targeted Wakeup", locked_cores=locked_cores)
            display_status_table(p_cores, e_cores, locked_cores)
        case "disable":
            target_cores = parse_core_args(args.cores, all_known_cores)
            batch_process_cores(target_cores, enable=False, action_name="Targeted Shutdown", locked_cores=locked_cores)
            display_status_table(p_cores, e_cores, locked_cores)
        case "toggle":
            target_cores = parse_core_args(args.cores, all_known_cores)
            console.print("[bold yellow]Initiating Targeted Toggle Sequence...[/bold yellow]")
            for core in target_cores:
                if core in locked_cores:
                    console.print(f"CPU {core:02d}: [yellow]Skipped (BSP/Immutable)[/yellow]")
                    continue
                current_state = get_core_status(core)
                success, msg = set_core_status(core, enable=not current_state)
                color = "green" if success else "yellow"
                action = "Enabled" if not current_state else "Disabled"
                console.print(f"CPU {core:02d} -> {action}: [{color}]{msg}[/{color}]")
            display_status_table(p_cores, e_cores, locked_cores)

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        sys.exit(130)
