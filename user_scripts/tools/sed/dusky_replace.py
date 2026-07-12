#!/usr/bin/env python
# ==============================================================================
# Script:     dusky-replace.py
# Purpose:    Intelligently find and replace text across directories.
# Architect:  Optimized exclusively for Arch Linux & Python 3.14+
# ==============================================================================

import sys
import os
import subprocess
import difflib
import argparse
from pathlib import Path

# --- Arch Linux Native Bootstrapper ---
def bootstrap_dependencies():
    """Auto-installs missing Arch packages natively via pacman."""
    missing_pkgs = []
    
    try:
        import rich
    except ImportError:
        missing_pkgs.append("python-rich")
        
    try:
        import regex
    except ImportError:
        missing_pkgs.append("python-regex")
        
    try:
        import charset_normalizer
    except ImportError:
        missing_pkgs.append("python-charset-normalizer")
        
    # Verify ripgrep binary is in PATH
    if not any(os.access(os.path.join(path, "rg"), os.X_OK) for path in os.environ.get("PATH", "").split(os.pathsep)):
        missing_pkgs.append("ripgrep")
        
    if missing_pkgs:
        print(f"[*] Missing dependencies detected: {', '.join(missing_pkgs)}")
        print("[*] Elevating via pacman for seamless installation...")
        try:
            subprocess.run(["sudo", "pacman", "-S", "--needed", "--noconfirm"] + missing_pkgs, check=True)
            print("[✔] Dependencies installed. Reloading environment...")
            os.execv(sys.executable, [sys.executable] + sys.argv)
        except subprocess.CalledProcessError:
            print(f"[✖] Pacman failed. Install manually: sudo pacman -S --needed {' '.join(missing_pkgs)}")
            sys.exit(1)

bootstrap_dependencies()

# Import the ultra-robust PCRE2-compliant regex engine
import regex as re
import charset_normalizer
from rich.console import Console
from rich.prompt import Prompt
from rich.progress import track
from rich.panel import Panel
from rich.syntax import Syntax

console = Console()

def display_diff(path: Path, old_text: str, new_text: str):
    """Generates and renders a beautifully syntax-highlighted unified diff."""
    diff_lines = list(difflib.unified_diff(
        old_text.splitlines(keepends=True),
        new_text.splitlines(keepends=True),
        fromfile=f"a/{path}",
        tofile=f"b/{path}",
        n=3
    ))
    
    if not diff_lines:
        return

    diff_str = "".join(diff_lines)
    syntax = Syntax(diff_str, "diff", theme="monokai", background_color="default")
    console.print(Panel(syntax, title=f"[bold blue]Diff: {path}", border_style="blue"))

def safe_write_file(path: Path, new_bytes: bytes):
    """
    Executes a high-speed write using EAFP to test permissions natively.
    Falls back to a secure `sudo tee` pipeline if the user lacks write access,
    guaranteeing POSIX inode stability and permission preservation.
    """
    try:
        # Standard fast-path write
        path.write_bytes(new_bytes)
    except PermissionError:
        prompt_msg = f"\n[sudo] Password required to edit protected file ({path.name}): "
        try:
            subprocess.run(
                ["sudo", "-p", prompt_msg, "tee", str(path)],
                input=new_bytes,
                stdout=subprocess.DEVNULL,
                check=True
            )
        except subprocess.CalledProcessError:
            console.print(f"[bold red][✖] Elevated write failed on {path}. Check for immutable flags (`lsattr`).[/]")

def main():
    parser = argparse.ArgumentParser(description="Dusky Replace: High-performance, byte-safe text replacement tool for Arch Linux.")
    parser.add_argument("search", help="The PCRE2 regex pattern to find.")
    parser.add_argument("replace", help="The text to replace matches with.")
    parser.add_argument("target_dir", help="Directory to search within.")
    args = parser.parse_args()

    target = Path(args.target_dir)
    if not target.is_dir():
        console.print(f"[bold red][✖] Target directory '{target}' does not exist.[/]")
        sys.exit(1)

    try:
        # V1 flag strictly enforces PCRE-standard behavior matching ripgrep
        search_pattern = re.compile(args.search, flags=re.MULTILINE | re.V1)
    except re.error as e:
        console.print(f"[bold red][✖] Invalid PCRE2 regex pattern: {e}[/]")
        sys.exit(1)

    console.print(f"[bold cyan]Searching for files matching pattern in {target}...[/]")
    
    # -U ensures whole-file matching parity between ripgrep and Python
    rg_proc = subprocess.run(
        ["rg", "-l", "-0", "-U", "--pcre2", "--", args.search, str(target)],
        capture_output=True,
        text=True
    )
    
    match rg_proc.returncode:
        case 1:
            console.print("[bold green][i] No matches found. Exiting cleanly.[/]")
            sys.exit(0)
        case 2:
            console.print(f"[bold red][✖] ripgrep encountered an error: {rg_proc.stderr}[/]")
            sys.exit(1)
            
    files = [Path(p) for p in rg_proc.stdout.split("\0") if p]
    
    console.print(f"\n[bold]Found {len(files)} files containing matches.[/]")
    console.print("  [bold cyan][1][/] Interactive (Preview diffs and confirm per-file)")
    console.print("  [bold cyan][2][/] Batch All   (Fast silent replacement)")
    console.print("  [bold cyan][3][/] Dry Run     (Preview diffs only)")
    console.print("  [bold red][q][/] Quit")
    
    choice = Prompt.ask("\nChoose execution method", choices=["1", "2", "3", "q"], default="1")
    
    if choice == "q":
        console.print("[yellow]Aborting as requested.[/]")
        sys.exit(0)

    mode_interactive = (choice == "1")
    mode_batch = (choice == "2")
    mode_dry = (choice == "3")
    
    batch_override = mode_batch
    processed_count = 0

    # track() renders a dynamic UI. If batch_override is active from the start, we use it.
    iterable = track(files, description="Processing...") if mode_batch else files

    try:
        for file_path in iterable:
            try:
                raw_bytes = file_path.read_bytes()
            except OSError as e:
                console.print(f"[yellow][!] IO Error on {file_path}. Skipping. ({e})[/]")
                continue

            # Deterministic encoding extraction ensures we never corrupt ISO-8859/Windows-1252 files
            best_match = charset_normalizer.from_bytes(raw_bytes).best()
            
            if best_match is not None:
                detected_encoding = best_match.encoding
                original_text = str(best_match)
            else:
                # Absolute fallback if normalizer fails on heavy binary sludge
                detected_encoding = "utf-8"
                original_text = raw_bytes.decode(detected_encoding, errors="surrogateescape")
                
            new_text, sub_count = search_pattern.subn(args.replace, original_text)
            
            if sub_count == 0:
                continue
                
            if mode_dry or (mode_interactive and not batch_override):
                display_diff(file_path, original_text, new_text)
                
            if mode_dry:
                continue

            if not batch_override:
                action = Prompt.ask(
                    f"Apply changes to [cyan]{file_path}[/]? ([green]y[/]/[red]n[/]/[yellow]q[/]uit/[magenta]a[/]ll)", 
                    choices=["y", "n", "q", "a"], 
                    default="y"
                )
                
                match action:
                    case "q":
                        console.print("[yellow]Aborted by user.[/]")
                        break
                    case "n":
                        continue
                    case "a":
                        batch_override = True
            
            # Serialize payload to memory first. If this fails, the original file remains entirely untouched.
            output_bytes = new_text.encode(detected_encoding, errors="surrogateescape")
            
            safe_write_file(file_path, output_bytes)
            processed_count += 1
            
            # Only print granular updates if we didn't start in strict batch mode to prevent UI collision
            if not mode_batch:
                console.print(f"[green][✔] Updated {file_path} ({detected_encoding})[/]")
                
    except KeyboardInterrupt:
        console.print("\n[bold red][!] Script interrupted by user.[/]")
        sys.exit(130)

    console.print(f"\n[bold green]Done! Successfully updated {processed_count} files.[/]")

if __name__ == "__main__":
    main()
