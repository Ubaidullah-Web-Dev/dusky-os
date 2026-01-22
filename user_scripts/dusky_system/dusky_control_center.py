#!/usr/bin/env python3
"""
Dusky Control Center
A GTK4/Libadwaita configuration launcher for the Dusky Dotfiles.

LAUNCH WITH: uwsm-app -- python3 dusky_control_center.py
"""
import sys
import os
import subprocess
import importlib.util
import shutil
# warnings module removed so all logs are visible
from typing import Optional, Dict, Any, List

# =============================================================================
# BRANDING & CONFIGURATION
# =============================================================================
APP_ID = "com.github.dusky.controlcenter"
APP_TITLE = "Dusky Control Center"
CONFIG_FILENAME = "dusky_config.yaml"

# Supported terminals in order of preference
TERMINALS = ("kitty", "foot", "alacritty", "wezterm", "gnome-terminal", "konsole", "xfce4-terminal")

# =============================================================================
# TERMINAL UTILITIES
# =============================================================================
def find_terminal() -> Optional[str]:
    """Return the first available terminal emulator, or None."""
    for term in TERMINALS:
        if shutil.which(term):
            return term
    return None

def build_terminal_cmd(terminal: str, title: str, shell_cmd: str, wait: bool = True) -> List[str]:
    """
    Construct a command list to run `shell_cmd` inside `terminal`.
    Handles specific flag quirks for different emulators.
    """
    if wait:
        # Keeps window open after command finishes so user can read output
        full_cmd = f'{shell_cmd}; echo ""; echo "Press Enter to close..."; read'
    else:
        full_cmd = shell_cmd

    if terminal == "kitty":
        return [terminal, "--title", title, "sh", "-c", full_cmd]
    if terminal == "foot":
        return [terminal, "--title", title, "sh", "-c", full_cmd]
    if terminal == "alacritty":
        return [terminal, "--title", title, "-e", "sh", "-c", full_cmd]
    if terminal == "wezterm":
        return [terminal, "start", "--", "sh", "-c", full_cmd]
    if terminal == "gnome-terminal":
        return [terminal, f"--title={title}", "--wait", "--", "sh", "-c", full_cmd]
    if terminal == "konsole":
        return [terminal, "--title", title, "-e", "sh", "-c", full_cmd]
    
    # Generic fallback
    return [terminal, "-e", "sh", "-c", full_cmd]

# =============================================================================
# DEPENDENCY BOOTSTRAP (Self-Healing)
# =============================================================================
def check_dependencies() -> None:
    """
    Checks for Python-GObject, PyYAML, GTK4, and Libadwaita.
    If missing, spawns a visible terminal to install them via pacman.
    """
    missing: List[str] = []

    # 1. Check Python Modules
    python_deps = {"gi": "python-gobject", "yaml": "python-yaml"}
    for module, package in python_deps.items():
        if importlib.util.find_spec(module) is None:
            if package not in missing:
                missing.append(package)

    # 2. Check System Libraries (only if Python bindings exist)
    if "python-gobject" not in missing:
        try:
            import gi
            gi.require_version("Gtk", "4.0")
            gi.require_version("Adw", "1")
            from gi.repository import Gtk, Adw # noqa
        except (ValueError, ImportError):
            if "gtk4" not in missing: missing.append("gtk4")
            if "libadwaita" not in missing: missing.append("libadwaita")

    if not missing:
        return

    # 3. Perform Installation
    print(f"[{APP_TITLE}] Missing dependencies: {', '.join(missing)}")
    
    terminal = find_terminal()
    if terminal is None:
        print("[ERROR] No terminal found. Install manually:")
        print(f"sudo pacman -S --needed {' '.join(missing)}")
        sys.exit(1)

    print(f"[{APP_TITLE}] Launching {terminal} for installation...")
    pacman_cmd = f"sudo pacman -S --needed {' '.join(missing)}"
    cmd = build_terminal_cmd(terminal, f"{APP_TITLE} Installer", pacman_cmd, wait=True)

    try:
        # We don't use DEVNULL here because we want the user to interact with sudo
        subprocess.check_call(cmd)
        print(f"[{APP_TITLE}] Restarting...")
        os.execv(sys.executable, [sys.executable] + sys.argv)
    except (subprocess.CalledProcessError, FileNotFoundError):
        print("[ERROR] Installation failed.")
        sys.exit(1)

# Run check immediately
check_dependencies()

# =============================================================================
# MAIN APPLICATION
# =============================================================================
import yaml
import gi
gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Gtk, Adw, Gio, GLib

def get_script_dir() -> str:
    return os.path.dirname(os.path.realpath(__file__))

def load_config() -> Dict[str, Any]:
    config_path = os.path.join(get_script_dir(), CONFIG_FILENAME)
    
    if not os.path.isfile(config_path):
        return _error_config(f"Config file missing: {CONFIG_FILENAME}")

    try:
        with open(config_path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)
            return data if data else {"pages": []}
    except Exception as e:
        return _error_config(str(e))

def _error_config(message: str) -> Dict[str, Any]:
    return {"pages": [{"name": "Error", "groups": [{"title": "Error", "items": [{"title": "Config Error", "description": message}]}]}]}

class DuskyControlCenter(Adw.Application):
    def __init__(self):
        super().__init__(application_id=APP_ID, flags=Gio.ApplicationFlags.FLAGS_NONE)
        self.config = {}
        self._terminal = None

    def do_startup(self):
        Adw.Application.do_startup(self)
        self.config = load_config()
        self._terminal = find_terminal()

    def do_activate(self):
        # Acknowledge StyleManager to prevent "unsupported" warning in logs
        Adw.StyleManager.get_default()

        win = Adw.PreferencesWindow(application=self)
        
        # Window Configuration
        win_cfg = self.config.get("window", {})
        win.set_title(win_cfg.get("title", APP_TITLE))
        win.set_default_size(win_cfg.get("width", 950), win_cfg.get("height", 650))

        # Build Pages
        for page_data in self.config.get("pages", []):
            win.add(self._build_page(page_data))

        win.present()

    def _build_page(self, data):
        page = Adw.PreferencesPage()
        page.set_title(data.get("name", "Untitled"))
        page.set_icon_name(data.get("icon", "system-help-symbolic"))

        for group_data in data.get("groups", []):
            page.add(self._build_group(group_data))
        return page

    def _build_group(self, data):
        group = Adw.PreferencesGroup()
        # Escaping text prevents crashes on symbols like '&'
        group.set_title(GLib.markup_escape_text(data.get("title", "")))

        for item_data in data.get("items", []):
            group.add(self._build_row(item_data))
        return group

    def _build_row(self, data):
        row = Adw.ActionRow()
        row.set_title(GLib.markup_escape_text(data.get("title", "Unknown")))
        row.set_subtitle(GLib.markup_escape_text(data.get("description", "")))
        
        icon = data.get("icon", "text-x-generic-symbolic")
        row.add_prefix(Gtk.Image.new_from_icon_name(icon))

        btn = Gtk.Button(label="Run")
        btn.add_css_class("pill")
        btn.set_valign(Gtk.Align.CENTER)
        
        # Pass the whole data object to the handler
        btn.connect("clicked", self._on_run_clicked, data)
        
        row.add_suffix(btn)
        row.set_activatable_widget(btn)
        return row

    def _on_run_clicked(self, button, item_data):
        command = item_data.get("command", "")
        if not command.strip(): return

        expanded_cmd = os.path.expandvars(command)
        
        # Determine Execution Mode
        use_terminal = item_data.get("terminal", False)
        
        # Smart UWSM Check: 
        # If user explicitly set use_uwsm to False, respect it.
        # Otherwise, default to True unless the command already starts with "uwsm-app"
        config_uwsm = item_data.get("use_uwsm", True)
        
        # Avoid double wrapping if the user's config already has it
        if "uwsm-app" in expanded_cmd:
            use_uwsm = False
        else:
            use_uwsm = config_uwsm

        print(f"[{APP_TITLE}] Exec: {expanded_cmd} | Terminal: {use_terminal} | Wrap UWSM: {use_uwsm}")

        try:
            if use_terminal:
                self._spawn_terminal(expanded_cmd)
            else:
                self._spawn_process(expanded_cmd, use_uwsm)
        except Exception as e:
            print(f"Error: {e}")

    def _spawn_process(self, cmd, wrap_uwsm):
        args = ["uwsm-app", "--", "sh", "-c", cmd] if wrap_uwsm else cmd
        
        # shell=True is needed if we are NOT wrapping in UWSM array
        use_shell = not wrap_uwsm
        
        subprocess.Popen(
            args, 
            shell=use_shell, 
            start_new_session=True,
            stdin=subprocess.DEVNULL, 
            stdout=subprocess.DEVNULL, 
            stderr=subprocess.DEVNULL
        )

    def _spawn_terminal(self, cmd):
        if not self._terminal:
            print("No terminal found, running in background.")
            self._spawn_process(cmd, True)
            return

        # Build terminal args
        term_args = build_terminal_cmd(self._terminal, APP_TITLE, cmd, wait=True)
        
        # Terminals are GUI apps, so we ALWAYS wrap them in uwsm-app
        final_args = ["uwsm-app", "--"] + term_args
        
        subprocess.Popen(
            final_args, 
            start_new_session=True, 
            stdin=subprocess.DEVNULL, 
            stdout=subprocess.DEVNULL, 
            stderr=subprocess.DEVNULL
        )

if __name__ == "__main__":
    app = DuskyControlCenter()
    app.run(sys.argv)
