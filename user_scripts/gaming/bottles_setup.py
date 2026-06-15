#!/usr/bin/env python3
import subprocess
import sys
import os
import re

try:
    from rich.console import Console
    from rich.panel import Panel
    from rich.prompt import Confirm, Prompt
except ImportError:
    print("\n[CRITICAL ERROR] The 'rich' library is not installed.")
    print("Please install it before running this script.")
    print("Run: sudo pacman -S python-rich")
    sys.exit(1)

console = Console()

def check_root_and_locks():
    """Ensure proper privileges and check for pacman database locks."""
    if os.geteuid() == 0:
        console.print("[bold red]Do not run this script as root. Run it as your normal user, and sudo will be invoked securely when needed.[/bold red]")
        sys.exit(1)
        
    if os.path.exists("/var/lib/pacman/db.lck"):
        console.print("[bold red]Pacman database is locked (/var/lib/pacman/db.lck).[/bold red]")
        console.print("Another package manager is running, or a previous installation crashed.")
        console.print("Please resolve this by running: sudo rm /var/lib/pacman/db.lck")
        sys.exit(1)

def is_multilib_enabled() -> bool:
    """Parses pacman.conf to check if [multilib] is active."""
    try:
        with open('/etc/pacman.conf', 'r') as f:
            content = f.read()
            if re.search(r'^\s*\[multilib\]', content, re.MULTILINE):
                return True
    except FileNotFoundError:
        console.print("[bold red]Critical system file /etc/pacman.conf not found![/bold red]")
        sys.exit(1)
    return False

def get_installed_flatpaks() -> list:
    """Dynamically fetches a list of all installed Flatpak Application IDs."""
    try:
        result = subprocess.run(
            ["flatpak", "list", "--app", "--columns=application"],
            capture_output=True, text=True, check=True
        )
        # Filter out empty lines
        return [app_id.strip() for app_id in result.stdout.split('\n') if app_id.strip()]
    except subprocess.CalledProcessError:
        return []

def integrate_desktop_entries():
    """
    Idempotently symlinks Flatpak .desktop files to the user's local applications directory
    and flushes the DB. This guarantees instant visibility in launchers like Rofi/Wofi.
    Also cleans up dead symlinks from previously uninstalled flatpaks.
    """
    user_apps_dir = os.path.expanduser("~/.local/share/applications")
    os.makedirs(user_apps_dir, exist_ok=True)
    
    system_export_dir = "/var/lib/flatpak/exports/share/applications"
    user_export_dir = os.path.expanduser("~/.local/share/flatpak/exports/share/applications")
    
    installed_apps = get_installed_flatpaks()
    integrated_count = 0

    # 1. Clean up broken symlinks (in case flatpaks were removed)
    for filename in os.listdir(user_apps_dir):
        file_path = os.path.join(user_apps_dir, filename)
        if os.path.islink(file_path) and not os.path.exists(file_path):
            os.remove(file_path)

    # 2. Bridge active Flatpak desktop entries
    for app_id in installed_apps:
        desktop_file = f"{app_id}.desktop"
        target_path = None
        
        # Prioritize system-wide installations, fallback to user-specific
        if os.path.exists(os.path.join(system_export_dir, desktop_file)):
            target_path = os.path.join(system_export_dir, desktop_file)
        elif os.path.exists(os.path.join(user_export_dir, desktop_file)):
            target_path = os.path.join(user_export_dir, desktop_file)
            
        if target_path:
            symlink_path = os.path.join(user_apps_dir, desktop_file)
            
            # Idempotent create/update
            if os.path.lexists(symlink_path):
                if os.path.islink(symlink_path) and os.readlink(symlink_path) == target_path:
                    continue # Already correctly linked
                os.remove(symlink_path) # Remove incorrect symlink or physical file collision
            
            os.symlink(target_path, symlink_path)
            integrated_count += 1
            
    # 3. Flush the desktop application cache for immediate Rofi parsing
    subprocess.run(["update-desktop-database", user_apps_dir], capture_output=True)

def run_command(command: str, description: str, critical: bool = True):
    """Executes a shell command with an interactive Rich status spinner."""
    console.print(f"\n[bold cyan]Target:[/bold cyan] {description}")
    console.print(f"[bold black on white] {command} [/bold black on white]")
    
    if not Confirm.ask("[bold yellow]Execute this step?[/bold yellow]", default=True):
        console.print("[dim]Skipped by user.[/dim]")
        return True

    with console.status(f"[bold green]Executing: {command}...[/bold green]", spinner="dots"):
        try:
            # We pipe stdout to hide the raw output behind the spinner.
            process = subprocess.run(
                command, 
                shell=True, 
                check=True, 
                stdout=subprocess.PIPE, 
                stderr=subprocess.PIPE,
                text=True
            )
            console.print("[bold green]✔ Success![/bold green]")
            return True
        except subprocess.CalledProcessError as e:
            console.print(f"[bold red]✘ Failed with exit code {e.returncode}[/bold red]")
            error_output = e.stderr.strip() if e.stderr else e.stdout.strip()
            console.print(Panel(error_output, title="Terminal Error Output", border_style="red"))
            
            if critical:
                console.print("[bold red]A critical step failed. Aborting the script to maintain system stability.[/bold red]")
                sys.exit(1)
            return False

def main():
    console.clear()
    console.print(Panel.fit(
        "[bold magenta]Arch Linux Universal Gaming Architecture[/bold magenta]\n"
        "[white]Idempotent automated installer for Drivers, Steam, Bottles, Gamescope, & Flatpaks.[/white]",
        border_style="magenta"
    ))

    # Pre-flight checks
    check_root_and_locks()

    # Cache sudo credentials upfront so it doesn't hang waiting for a password later
    subprocess.run("sudo -v", shell=True, check=True)

    # Step 1: System Sync
    run_command(
        "sudo pacman -Syu --noconfirm",
        "Synchronize package databases and apply core system updates."
    )

    # Step 2: Intelligent Multilib Configuration
    if is_multilib_enabled():
        console.print(Panel(
            "The \[multilib] repository is [bold green]ALREADY ENABLED[/bold green].\n"
            "Your system is natively configured for 32-bit gaming libraries.",
            style="green"
        ))
    else:
        console.print(Panel(
            "The \[multilib] repository is [bold red]NOT ENABLED[/bold red].\n"
            "This is MANDATORY for Steam and Wine to process 32-bit Windows instructions.",
            style="yellow"
        ))
        run_command(
            "sudo sed -i '/^#\\[multilib\\]/{s/^#//;n;s/^#//}' /etc/pacman.conf && sudo pacman -Syu --noconfirm",
            "Enable 32-bit multilib repository in pacman.conf and sync databases."
        )

    # Step 3: GPU Drivers (Vulkan Translation)
    console.print("\n[bold cyan]Select your GPU Vendor for strictly required Vulkan Drivers:[/bold cyan]")
    console.print("1. AMD (Radeon)")
    console.print("2. NVIDIA (GeForce)")
    console.print("3. Intel (Arc/iGPU)")
    console.print("4. Skip (I manage my own graphics drivers)")
    
    gpu_choice = Prompt.ask("Enter choice", choices=["1", "2", "3", "4"], default="4")
    
    if gpu_choice == "1":
        run_command(
            "sudo pacman -S --needed --noconfirm vulkan-radeon lib32-vulkan-radeon mesa lib32-mesa",
            "Install strictly required AMD native and 32-bit Vulkan/Mesa drivers."
        )
    elif gpu_choice == "2":
        run_command(
            "sudo pacman -S --needed --noconfirm nvidia-utils lib32-nvidia-utils",
            "Install strictly required NVIDIA proprietary utilities and 32-bit Vulkan drivers."
        )
    elif gpu_choice == "3":
        run_command(
            "sudo pacman -S --needed --noconfirm vulkan-intel lib32-vulkan-intel mesa lib32-mesa",
            "Install strictly required Intel native and 32-bit Vulkan/Mesa drivers."
        )

    # Step 4: Core Native Gaming Tools
    # Included lutris for general-purpose game management, gamescope for micro-compositing/upscaling, and desktop-file-utils for Rofi bridging
    run_command(
        "sudo pacman -S --needed --noconfirm steam lutris wine flatpak gamemode lib32-gamemode mangohud lib32-mangohud gamescope desktop-file-utils",
        "Install Steam, Lutris, System Wine, Flatpak daemon, Gamescope, GameMode, MangoHud, and Utils."
    )

    # Step 5: Flatpak Repository Initialization
    run_command(
        "flatpak remote-add --user --if-not-exists flathub https://dl.flathub.org/repo/flathub.flatpakrepo && "
        "flatpak remote-add --system --if-not-exists flathub https://dl.flathub.org/repo/flathub.flatpakrepo",
        "Initialize Flathub remote server for application downloads (user & system scopes)."
    )

    # Step 6: Flatpak Gaming Ecosystem
    flatpak_apps = [
        ("Bottles", "com.usebottles.bottles"),
        ("Flatseal", "com.github.tchx84.Flatseal"),
        ("ProtonPlus", "com.vysp3r.ProtonPlus")
    ]

    for app_name, app_id in flatpak_apps:
        run_command(
            f"sudo flatpak install --system flathub {app_id} -y",
            f"Install {app_name} securely via Flatpak sandbox.",
            critical=False 
        )

    # Step 7: Automated Bottles Permission Override
    # This automatically bypasses the sandbox restriction for secondary drives without needing manual Flatseal tweaks
    run_command(
        "sudo flatpak override --system --filesystem=host com.usebottles.bottles",
        "Grant Bottles global filesystem permissions to natively detect secondary/game drives.",
        critical=False
    )

    # Step 8: Rofi / Application Menu Integration
    with console.status("[bold green]Bridging Flatpaks into Rofi/Wofi Application Launchers...[/bold green]", spinner="dots"):
        integrate_desktop_entries()
    console.print("[bold green]✔ Application Launcher integration complete![/bold green]")

    # Final Summary
    console.print(Panel.fit(
        "[bold green]✔ Architecture Established![/bold green]\n"
        "Your Arch Linux system is fully armed for native games, Proton, and modern Windows repacks.\n\n"
        "[bold]Immediate Next Steps:[/bold]\n"
        "1. Open your [cyan]Rofi[/cyan] menu — your Flatpaks and native apps like [cyan]Steam[/cyan] and [cyan]Lutris[/cyan] are ready to launch.\n"
        "2. Note: [cyan]Bottles[/cyan] has already been auto-configured to detect your secondary storage drives.\n"
        "3. Use [cyan]Lutris[/cyan] to centralize your GOG, Epic Games, and Amazon libraries.\n"
        "4. Use [cyan]Bottles[/cyan] for isolated environments and executing independent game installers (.exe / .msi).\n"
        "5. [bold red]CRITICAL (If using Heavy Repacks):[/bold red] Check the 'Limit installer to 2GB' box in Bottles to prevent Out-Of-Memory crashes.",
        border_style="green"
    ))

if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        console.print("\n\n[bold red]Script terminated abruptly by user. Exiting safely.[/bold red]")
        sys.exit(0)
