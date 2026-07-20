#!/usr/bin/env python3
# dusky_interactive=true
# ==============================================================================
# DUSKY ARCH LINUX MASTER ORCHESTRATOR
# ==============================================================================
# Target: Arch Linux bleeding edge | Python 3.14+ | Textual 8.2.8+ | systemd 261+
# ==============================================================================

import argparse
import asyncio
import atexit
import base64
import codecs
import datetime
import fcntl
import functools
import hashlib
import json
import os
import pty
import pwd
import py_compile
import re
import select
import shlex
import shutil
import signal
import struct
import subprocess
import sys
import tempfile
import termios
import time
import tomllib

from collections import deque
from contextlib import suppress
from dataclasses import dataclass
from enum import Enum, auto
from pathlib import Path

from rich.console import Console
from rich.text import Text

from textual import work, on, events
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Container, Horizontal, Vertical
from textual.screen import ModalScreen
from textual.widgets import (
    Static,
    RichLog,
    ProgressBar,
    Button,
    Label,
    Tree,
    Input,
    OptionList,
    ContentSwitcher,
)
from textual.widgets.option_list import Option
from textual.widgets.tree import TreeNode


# ==============================================================================
# PATHS
# ==============================================================================
def _get_xdg_runtime_dir() -> Path:
    return Path(os.environ.get("XDG_RUNTIME_DIR", f"/run/user/{os.getuid()}"))


SCRIPT_DIR: Path = Path(__file__).resolve().parent
PROFILES_DIR: Path = SCRIPT_DIR / "profiles"

DOCUMENTS_ROOT: Path = Path.home() / "Documents"
LOG_BASE_DIR: Path = DOCUMENTS_ROOT / "logs"
STATE_BASE_DIR: Path = DOCUMENTS_ROOT

LOCK_FILE: Path = _get_xdg_runtime_dir() / "dusky-orchestra.lock"
ASKPASS_DIR: Path = _get_xdg_runtime_dir()

FALLBACK_ROWS: int = 40
FALLBACK_COLS: int = 120

_LOCK_FD: int | None = None


# ==============================================================================
# REGEX
# ==============================================================================
_INTERACTIVE_RE = re.compile(r"^\s*#\s*dusky_interactive\s*=\s*(?:true|1)\b", re.IGNORECASE)
_HEX_COLOR_RE = re.compile(r"^#(?:[0-9a-fA-F]{3,4}|[0-9a-fA-F]{6}|[0-9a-fA-F]{8})$")

ANSI_STRIP_REGEX = re.compile(
    r"\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~]|\][^\x07\x1b]*(?:\x07|\x1B\\))"
)

PCT_REGEX = re.compile(r"(?<!\d)(?:\d{1,2}|100)%")
SPEED_ETA_REGEX = re.compile(
    r"Total\s*\(\s*\d+\s*/\s*\d+\s*\).*?(\d+(?:\.\d+)?\s*[KMG]?i?B/s)\s+([\d:]+)",
    re.IGNORECASE,
)
ALT_SPEED_ETA_REGEX = re.compile(
    r"(\d+(?:\.\d+)?\s*[KMG]?i?B/s)\s+([\d:]+)",
    re.IGNORECASE,
)

BRACKET_NEWLINE_RE = re.compile(r"[\r\n]+")
SINGLE_NEWLINE_RE = re.compile(r"[\r\n]")


# ==============================================================================
# MODEL
# ==============================================================================
class TaskStatus(Enum):
    PENDING = auto()
    COMPLETED = auto()
    RUNNING = auto()
    FAILED = auto()
    SKIPPED = auto()


@dataclass(slots=True)
class OrchestratorTask:
    raw_entry: str
    mode: str
    script_name: str
    args: list[str]
    ignore_fail: bool
    interactive: bool = False
    force_flag: bool = False
    index: int = 0
    resolved_path: Path | None = None
    interpreter: str = "bash"
    state_key: str = ""
    status: TaskStatus = TaskStatus.PENDING
    error_msg: str | None = None


@dataclass(slots=True)
class ProfileConfig:
    filepath: Path
    name: str
    description: str
    post_script_delay: int
    git_enabled: bool
    git_dir: str
    git_work_tree: str
    git_remote: str
    search_dirs: list[str]
    conflict_resolutions: dict[str, str]
    tasks: list[OrchestratorTask]


# ==============================================================================
# UTILITIES
# ==============================================================================
def resolve_home(path_str: str) -> Path:
    return Path(os.path.expandvars(path_str.strip())).expanduser()


def safe_filename(name: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9._-]", "_", str(name)).strip("._")
    return cleaned or "unnamed"


def state_file_for(profile: ProfileConfig) -> Path:
    return STATE_BASE_DIR / f".install_state_{safe_filename(profile.name)}"


def load_completed_keys(profile: ProfileConfig) -> set[str]:
    sf = state_file_for(profile)
    if not sf.is_file():
        return set()
    try:
        return {
            line.strip()
            for line in sf.read_text(encoding="utf-8", errors="ignore").splitlines()
            if line.strip()
        }
    except OSError:
        return set()


def now_ts() -> str:
    return datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")


class RunLogger:
    def __init__(self, profile: ProfileConfig):
        self.enabled = False
        self.root: Path | None = None
        self.main_path: Path | None = None
        self._main = None
        self._task_files: dict[str, object] = {}

        try:
            stamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
            self.root = LOG_BASE_DIR / f"{stamp}_{safe_filename(profile.name)}"
            self.root.mkdir(parents=True, exist_ok=True)
            self.main_path = self.root / "orchestrator.log"
            self._main = open(self.main_path, "a", encoding="utf-8", errors="replace")
            self.enabled = True
            self.system(f"Logging started for profile: {profile.name}")
        except OSError:
            self.enabled = False

    def system(self, msg: str) -> None:
        if not self.enabled or self._main is None:
            return
        with suppress(OSError):
            self._main.write(f"[{now_ts()}] {msg}\n")
            self._main.flush()

    def _task_log_path(self, task: OrchestratorTask) -> Path:
        assert self.root is not None
        fname = f"{task.index:03d}_{safe_filename(task.script_name)}.log"
        return self.root / fname

    def open_task(self, task: OrchestratorTask) -> None:
        if not self.enabled:
            return
        if task.state_key in self._task_files:
            return
        with suppress(OSError):
            f = open(self._task_log_path(task), "a", encoding="utf-8", errors="replace")
            f.write(f"[{now_ts()}] TASK START: {task.script_name}\n")
            f.write(f"[{now_ts()}] MODE: {task.mode}\n")
            f.write(f"[{now_ts()}] PATH: {task.resolved_path}\n")
            f.write(f"[{now_ts()}] INTERPRETER: {task.interpreter or 'direct'}\n")
            f.write(f"[{now_ts()}] ARGS: {shlex.join(task.args)}\n\n")
            f.flush()
            self._task_files[task.state_key] = f

    def write_task(self, task: OrchestratorTask, line: str) -> None:
        if not self.enabled:
            return
        f = self._task_files.get(task.state_key)
        if f is None:
            return
        with suppress(OSError):
            f.write(line + "\n")

    def close_task(self, task: OrchestratorTask) -> None:
        if not self.enabled:
            return
        f = self._task_files.pop(task.state_key, None)
        if f is None:
            return
        with suppress(OSError):
            f.write(f"\n[{now_ts()}] TASK END: {task.script_name}\n")
            f.flush()
            f.close()

    def close_all(self) -> None:
        if not self.enabled:
            return
        for f in list(self._task_files.values()):
            with suppress(OSError):
                f.flush()
                f.close()
        self._task_files.clear()
        if self._main is not None:
            with suppress(OSError):
                self.system("Logging stopped.")
                self._main.flush()
                self._main.close()
                self._main = None


# ==============================================================================
# AUDIO
# ==============================================================================
class AudioNotifier:
    @classmethod
    @functools.cache
    def _get_player(cls) -> str | None:
        for bin_name in ("pw-play", "paplay"):
            if p := shutil.which(bin_name):
                return p
        return None

    @classmethod
    def play(cls, sound_type: str = "alert") -> None:
        player = cls._get_player()
        if not player:
            return

        sound_map = {
            "alert": "/usr/share/sounds/freedesktop/stereo/dialog-warning.oga",
            "info": "/usr/share/sounds/freedesktop/stereo/dialog-information.oga",
            "complete": "/usr/share/sounds/freedesktop/stereo/complete.oga",
        }
        target = Path(sound_map.get(sound_type, sound_map["alert"]))
        if not target.exists():
            fallback = Path("/usr/share/sounds/freedesktop/stereo/bell.oga")
            if fallback.exists():
                target = fallback
            else:
                return

        cmd = (
            [player, "--media-role=event", str(target)]
            if player.endswith("pw-play")
            else [player, str(target)]
        )

        with suppress(OSError):
            subprocess.Popen(
                cmd,
                start_new_session=True,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                close_fds=True,
            )


# ==============================================================================
# LOCK
# ==============================================================================
def get_lock_holders() -> str:
    if not LOCK_FILE.exists():
        return ""

    try:
        real_lock = LOCK_FILE.resolve()
    except Exception:
        return ""

    holders: list[str] = []
    proc_dir = Path("/proc")
    if not proc_dir.exists():
        return ""

    try:
        pids = [d for d in proc_dir.iterdir() if d.name.isdigit()]
    except PermissionError:
        return ""

    my_pid = str(os.getpid())

    for pid_dir in pids:
        if pid_dir.name == my_pid:
            continue

        fd_dir = pid_dir / "fd"
        try:
            if not fd_dir.exists():
                continue

            for fd_link in fd_dir.iterdir():
                try:
                    if fd_link.resolve() == real_lock:
                        cmdline_path = pid_dir / "cmdline"
                        cmd = ""
                        with suppress(PermissionError, OSError):
                            if cmdline_path.exists():
                                cmd = cmdline_path.read_text(errors="replace").replace("\x00", " ").strip()
                        if not cmd:
                            cmd = f"[pid {pid_dir.name}]"
                        holders.append(f"  - PID {pid_dir.name}: {cmd}")
                        break
                except (PermissionError, FileNotFoundError, OSError):
                    continue
        except (PermissionError, OSError):
            continue

    return "\n".join(holders)


def _cleanup_lock() -> None:
    global _LOCK_FD
    try:
        if _LOCK_FD is not None:
            with suppress(OSError):
                fcntl.flock(_LOCK_FD, fcntl.LOCK_UN)
            with suppress(OSError):
                os.close(_LOCK_FD)
            _LOCK_FD = None
            LOCK_FILE.unlink(missing_ok=True)
    except OSError:
        pass


def acquire_lock() -> bool:
    global _LOCK_FD

    with suppress(OSError):
        LOCK_FILE.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        STATE_BASE_DIR.mkdir(parents=True, exist_ok=True)
        LOG_BASE_DIR.mkdir(parents=True, exist_ok=True)

    try:
        fd = os.open(str(LOCK_FILE), os.O_CREAT | os.O_RDWR | os.O_CLOEXEC, 0o600)
    except Exception as e:
        sys.stderr.write(f"[ERROR] Could not open lock file {LOCK_FILE}: {e}\n")
        return False

    try:
        fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        _LOCK_FD = fd
        atexit.register(_cleanup_lock)
        return True
    except BlockingIOError:
        sys.stderr.write("[ERROR] Another instance is already running.\n")
        holders = get_lock_holders()
        if holders:
            sys.stderr.write(holders + "\n")
        with suppress(OSError):
            os.close(fd)
        return False
    except OSError as e:
        sys.stderr.write(f"[ERROR] Failed to acquire lock: {e}\n")
        with suppress(OSError):
            os.close(fd)
        return False


# ==============================================================================
# SUDO ENGINE
# ==============================================================================
class SudoEngine:
    _password: str | None = None
    _askpass_path: Path | None = None
    _mode: str = "none"  # none | nopasswd | password

    @classmethod
    def mode_name(cls) -> str:
        return cls._mode

    @classmethod
    def _remove_stale_askpass_files(cls) -> None:
        with suppress(OSError):
            for p in ASKPASS_DIR.glob(".dusky_askpass_*"):
                with suppress(OSError):
                    p.unlink(missing_ok=True)

    @classmethod
    def cleanup(cls) -> None:
        if cls._askpass_path is not None:
            env = os.environ.copy()
            env["SUDO_ASKPASS"] = str(cls._askpass_path)
            for cmd in (["sudo", "-A", "rm", "-f", "/etc/sudoers.d/99_dusky_tty_tickets"], ["sudo", "-n", "rm", "-f", "/etc/sudoers.d/99_dusky_tty_tickets"]):
                try:
                    res = subprocess.run(cmd, env=env, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=5)
                    if res.returncode == 0:
                        break
                except Exception:
                    pass
            with suppress(OSError):
                cls._askpass_path.unlink(missing_ok=True)
        cls._askpass_path = None

    @classmethod
    def _write_askpass(cls, password: str) -> Path:
        ASKPASS_DIR.mkdir(parents=True, exist_ok=True)
        encoded = base64.b64encode(password.encode("utf-8")).decode("ascii")

        script = (
            "#!/usr/bin/env python3\n"
            "import base64, sys\n"
            f"sys.stdout.write(base64.b64decode('{encoded}').decode('utf-8') + '\\n')\n"
        )

        fd, path = tempfile.mkstemp(prefix=".dusky_askpass_", dir=str(ASKPASS_DIR))
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(script)

        os.chmod(path, 0o700)
        return Path(path)

    @classmethod
    def env_extra(cls) -> dict[str, str]:
        if cls._askpass_path is not None:
            return {"SUDO_ASKPASS": str(cls._askpass_path)}
        return {}

    @classmethod
    def set_password(cls, password: str) -> tuple[bool, str]:
        cls.cleanup()
        cls._remove_stale_askpass_files()

        try:
            askpass = cls._write_askpass(password)
        except OSError as e:
            return False, f"Failed to create askpass helper: {e}"

        env = os.environ.copy()
        env["SUDO_ASKPASS"] = str(askpass)

        try:
            proc = subprocess.run(
                ["sudo", "-A", "-v"],
                env=env,
                stdin=subprocess.DEVNULL,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.PIPE,
                text=True,
                timeout=30,
            )
        except subprocess.TimeoutExpired:
            with suppress(OSError):
                askpass.unlink(missing_ok=True)
            return False, "sudo authentication timed out"
        except OSError as e:
            with suppress(OSError):
                askpass.unlink(missing_ok=True)
            return False, str(e)

        if proc.returncode == 0:
            cls._password = password
            cls._askpass_path = askpass
            cls._mode = "password"
            atexit.register(cls.cleanup)
            
            # Write tty_tickets override so child PTYs share cached credentials
            username = pwd.getpwuid(os.getuid()).pw_name
            with suppress(Exception):
                subprocess.run(
                    ["sudo", "-A", "sh", "-c", f"mkdir -p /etc/sudoers.d && echo 'Defaults:{username} !tty_tickets' > /etc/sudoers.d/99_dusky_tty_tickets && chmod 0440 /etc/sudoers.d/99_dusky_tty_tickets"],
                    env=env,
                    stdin=subprocess.DEVNULL,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    timeout=10,
                )
            return True, ""

        err = (proc.stderr or "").strip()
        with suppress(OSError):
            askpass.unlink(missing_ok=True)
        return False, err or "sudo authentication failed"

    @classmethod
    def detect_nopasswd(cls) -> bool:
        if not shutil.which("sudo"):
            return False

        with suppress(Exception):
            proc = subprocess.run(
                ["sudo", "-n", "-v"],
                stdin=subprocess.DEVNULL,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                timeout=15,
            )
            if proc.returncode == 0:
                cls._password = None
                cls._askpass_path = None
                cls._mode = "nopasswd"
                return True

        return False

    @classmethod
    def refresh_sync(cls) -> bool:
        if not shutil.which("sudo"):
            return False

        if cls._mode == "nopasswd":
            cmd = ["sudo", "-n", "-v"]
            env = os.environ.copy()
        elif cls._mode == "password" and cls._askpass_path is not None:
            cmd = ["sudo", "-A", "-v"]
            env = os.environ.copy()
            env["SUDO_ASKPASS"] = str(cls._askpass_path)
        else:
            return cls.detect_nopasswd()

        try:
            proc = subprocess.run(
                cmd,
                env=env,
                stdin=subprocess.DEVNULL,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                timeout=20,
            )
            return proc.returncode == 0
        except Exception:
            return False

    @classmethod
    def sudo_prefix(cls) -> list[str]:
        if cls._mode == "nopasswd":
            return ["sudo", "-n", "--"]
        if cls._mode == "password" and cls._askpass_path is not None:
            return ["sudo", "-A", "--"]
        return ["sudo", "--"]

    @classmethod
    def preflight(cls, cli_password: str | None = None, password_file: Path | None = None) -> bool:
        if not shutil.which("sudo"):
            sys.stderr.write("[FATAL] sudo is required but not installed.\n")
            return False

        sys.stdout.write("[DUSKY PRE-FLIGHT] Securing administrative privileges...\n")

        if cls.detect_nopasswd():
            sys.stdout.write("[DUSKY PRE-FLIGHT] Passwordless sudo detected.\n")
            return True

        password: str | None = cli_password

        if password is None and password_file is not None:
            with suppress(OSError):
                password = password_file.read_text(encoding="utf-8", errors="ignore").splitlines()[0].rstrip("\n")

        if password is not None:
            ok, err = cls.set_password(password)
            if ok:
                sys.stdout.write("[DUSKY PRE-FLIGHT] Sudo credentials cached for this session.\n")
                return True
            sys.stderr.write(f"[ERROR] Provided sudo password failed: {err}\n")

        if sys.stdin.isatty():
            import getpass

            for attempt in range(1, 4):
                try:
                    password = getpass.getpass(f"[sudo] password for {getpass.getuser()}: ")
                except (EOFError, KeyboardInterrupt):
                    sys.stderr.write("\n[FATAL] Sudo authentication cancelled.\n")
                    return False

                ok, err = cls.set_password(password)
                if ok:
                    sys.stdout.write("[DUSKY PRE-FLIGHT] Sudo credentials cached for this session.\n")
                    return True

                sys.stderr.write(f"[ERROR] Authentication failed ({attempt}/3): {err}\n")

        sys.stderr.write("[FATAL] Sudo authentication failed. Aborting.\n")
        return False

    @staticmethod
    async def maintain_heartbeat(error_callback=None) -> None:
        fail_count = 0
        try:
            while True:
                await asyncio.sleep(45)
                ok = await asyncio.to_thread(SudoEngine.refresh_sync)
                if ok:
                    fail_count = 0
                else:
                    fail_count += 1
                    if error_callback is not None and fail_count == 1:
                        error_callback("Sudo heartbeat failed. Admin credentials may need renewal.")
        except asyncio.CancelledError:
            pass


# ==============================================================================
# THEME
# ==============================================================================
def get_theme_path() -> Path:
    target_user = os.environ.get("TARGET_USER") or os.environ.get("SUDO_USER")
    base_dir = Path.home()

    if target_user:
        with suppress(KeyError):
            pw = pwd.getpwnam(target_user.strip())
            base_dir = Path(pw.pw_dir)

    generated = base_dir / ".config/matugen/generated/dusky_tui.json"
    if generated.exists():
        return generated

    generated_fresh = base_dir / ".config/matugen/generated_fresh/dusky_tui.json"
    if generated_fresh.exists():
        return generated_fresh

    return generated


def _build_css_from_palette(palette: dict[str, str]) -> str:
    bg = palette["bg"]
    fg = palette["fg"]
    accent = palette["accent"]
    warning = palette["warning"]
    success = palette["success"]
    muted = palette["muted"]
    error_c = palette["error"]

    return f"""
Screen {{
    background: {bg};
    color: {fg};
    layout: vertical;
}}

#top_header {{
    height: 1;
    dock: top;
    background: {muted};
    color: {accent};
    text-style: bold;
    padding: 0 1;
}}

#main_dashboard {{
    layout: horizontal;
    height: 1fr;
}}

#left_pane {{
    width: 36%;
    border-right: solid {muted};
    background: {bg};
    padding: 0 1;
    height: 100%;
}}

#right_pane {{
    width: 64%;
    height: 100%;
    layout: vertical;
    background: {bg};
}}

#telemetry_box {{
    height: 5;
    border-bottom: solid {muted};
    padding: 0 1;
    layout: vertical;
}}

#status_label {{
    text-style: bold;
    color: {accent};
}}

#speed_label {{
    color: {warning};
    text-style: italic;
}}

#progress_bar {{
    width: 100%;
    margin-top: 1;
    height: 1;
}}

RichLog {{
    height: 1fr;
    border: none;
    background: {bg};
    color: {fg};
    scrollbar-gutter: stable;
    scrollbar-size: 1 1;
}}

Tree {{
    background: {bg};
    color: {fg};
}}

#footer {{
    height: 1;
    dock: bottom;
    background: {muted};
    layout: horizontal;
    padding: 0 1;
}}

.footer-shortcut {{
    padding: 0 1;
    color: {fg};
}}

.footer-sep {{
    color: {warning};
}}

#footer_status {{
    color: {success};
    text-style: italic;
}}

TaskSearchScreen, ConflictModalScreen, ManualModalScreen, SudoPasswordScreen {{
    align: center middle;
    background: rgba(0,0,0,0.78);
}}

#search_dialog {{
    width: 70;
    height: 75%;
    background: {bg};
    border: solid {accent};
    padding: 1 2;
}}

#search_list {{
    height: 1fr;
    border: none;
    background: {bg};
    color: {fg};
}}

#modal_dialog, #manual_dialog, #sudo_dialog {{
    width: 78;
    height: auto;
    background: {bg};
    padding: 1 2;
}}

#modal_dialog {{
    border: heavy {error_c};
}}

#manual_dialog {{
    border: heavy {accent};
}}

#sudo_dialog {{
    border: heavy {warning};
}}

#modal_title {{
    text-align: center;
    text-style: bold;
    color: {error_c};
    margin-bottom: 1;
}}

#manual_title {{
    text-align: center;
    text-style: bold;
    color: {accent};
    margin-bottom: 1;
}}

#sudo_title {{
    text-align: center;
    text-style: bold;
    color: {warning};
    margin-bottom: 1;
}}

#error_details {{
    color: {warning};
    margin-bottom: 1;
    max-height: 14;
    overflow-y: auto;
}}

#button_bar {{
    layout: horizontal;
    align: center middle;
    height: 3;
}}

Button {{
    height: 1;
    min-width: 16;
    border: none;
    margin: 0 1;
    padding: 0;
}}

Input {{
    background: {bg};
    border: tall {accent};
    color: {fg};
}}
"""


def load_dusky_theme() -> str:
    default_palette = {
        "bg": "#0a1612",
        "fg": "#d8e6df",
        "accent": "#00e0b8",
        "warning": "#a0d0cb",
        "success": "#8dd2da",
        "muted": "#1a2e28",
        "error": "#ffb4ab",
    }

    theme_file = get_theme_path()
    if not theme_file.exists():
        return _build_css_from_palette(default_palette)

    try:
        data = json.loads(theme_file.read_text(encoding="utf-8"))

        def safe(c: str, fallback: str) -> str:
            if not isinstance(c, str):
                return fallback
            c = c.strip()
            return c if _HEX_COLOR_RE.match(c) else fallback

        palette = {k: safe(data.get(k), default_palette[k]) for k in default_palette}
        return _build_css_from_palette(palette)
    except Exception:
        return _build_css_from_palette(default_palette)


# ==============================================================================
# PROFILE PARSER
# ==============================================================================
def parse_task_entry(raw_entry: str, index: int) -> OrchestratorTask:
    raw = raw_entry.strip()
    parts = [p.strip() for p in raw.split("|")]

    if len(parts) == 1:
        mode, flags, cmd = "U", "", parts[0]
    elif len(parts) == 2:
        mode, cmd = parts
        flags = ""
    elif len(parts) == 3:
        mode, flags, cmd = parts
    else:
        raise ValueError(f"Malformed entry: {raw_entry}")

    ignore_fail = False
    interactive = False
    force_flag = False

    for flag in flags.split(","):
        f = flag.strip().lower()
        if f in ("true", "ignore", "ignore-fail"):
            ignore_fail = True
        elif f in ("interactive", "tui", "prompt"):
            interactive = True
        elif f in ("force", "--force"):
            force_flag = True

    cmd_tokens = shlex.split(cmd.strip())
    if not cmd_tokens:
        raise ValueError(f"Empty command in entry: {raw_entry}")

    if cmd_tokens[0] == "true" and len(cmd_tokens) > 1:
        ignore_fail = True
        cmd_tokens = cmd_tokens[1:]

    return OrchestratorTask(
        raw_entry=raw,
        mode=mode.strip().upper(),
        script_name=cmd_tokens[0],
        args=cmd_tokens[1:],
        ignore_fail=ignore_fail,
        interactive=interactive,
        force_flag=force_flag,
        index=index,
    )


def load_profile(filepath: Path) -> ProfileConfig:
    with open(filepath, "rb") as f:
        data = tomllib.load(f)

    p_data = data.get("profile", {})
    g_data = data.get("git", {})
    s_data = data.get("search_dirs", {})
    c_data = data.get("conflict_resolutions", {})
    seq_data = data.get("sequence", {})

    tasks: list[OrchestratorTask] = []
    for i, line in enumerate(seq_data.get("scripts", []), start=1):
        line = str(line).strip()
        if not line or line.startswith("#"):
            continue
        tasks.append(parse_task_entry(line, i))

    try:
        post_delay = int(p_data.get("post_script_delay", 0))
    except Exception:
        post_delay = 0

    return ProfileConfig(
        filepath=filepath,
        name=str(p_data.get("name", filepath.stem)).strip(),
        description=str(p_data.get("description", "")).strip(),
        post_script_delay=max(0, post_delay),
        git_enabled=bool(g_data.get("enabled", False)),
        git_dir=str(g_data.get("git_dir", "~/dusky")).strip(),
        git_work_tree=str(g_data.get("work_tree", "~/")).strip(),
        git_remote=str(g_data.get("remote", "origin")).strip(),
        search_dirs=[str(resolve_home(str(d))) for d in s_data.get("dirs", []) if str(d).strip()],
        conflict_resolutions={
            str(k).strip(): str(v).strip()
            for k, v in c_data.items()
            if str(k).strip() and str(v).strip()
        },
        tasks=tasks,
    )


def discover_profiles() -> list[ProfileConfig]:
    if not PROFILES_DIR.exists():
        sys.stderr.write(f"[FATAL] Profiles directory missing: {PROFILES_DIR}\n")
        sys.exit(1)

    profiles: list[ProfileConfig] = []
    for f in sorted(PROFILES_DIR.glob("*.toml")):
        try:
            profiles.append(load_profile(f))
        except Exception as e:
            sys.stderr.write(f"[ERROR] Failed to load profile {f.name}: {e}\n")

    return profiles


def _script_metadata(path: Path) -> tuple[bool, str, str]:
    try:
        with open(path, "rb") as f:
            head = f.read(4)
            raw = f.read(8192)
        text = raw.decode("utf-8", errors="ignore")
        return head == b"\x7fELF", text.splitlines()[0].strip() if text else "", text
    except OSError:
        return False, "", ""


def _interpreter_from_shebang(first_line: str) -> str | None:
    if not first_line.startswith("#!"):
        return None

    shebang = first_line[2:].strip()
    if not shebang:
        return None

    try:
        parts = shlex.split(shebang)
    except ValueError:
        parts = shebang.split()

    if not parts:
        return None

    if parts[0].endswith("/env") and len(parts) > 1:
        parts = parts[1:]
        while parts and parts[0].startswith("-"):
            parts = parts[1:]

    if not parts:
        return None

    prog = Path(parts[0]).name

    if "python" in prog:
        if "python2" in prog:
            return "python2"
        return "python"

    if prog in ("bash", "sh", "zsh", "dash", "fish"):
        return prog

    return prog


def resolve_and_validate_manifest(profile: ProfileConfig) -> bool:
    success = True
    search_dir_cache: dict[str, bool] = {}
    occurrence: dict[tuple[str, str, str], int] = {}

    for task in profile.tasks:
        args_key = shlex.join(task.args)
        key_tuple = (task.mode, task.script_name, args_key)
        occ = occurrence.get(key_tuple, 0)
        occurrence[key_tuple] = occ + 1

        key_material = f"{task.mode}|{task.script_name}|{args_key}|{occ}".encode("utf-8")
        task.state_key = hashlib.blake2b(key_material, digest_size=16).hexdigest()

        if "/" in task.script_name:
            cand = resolve_home(task.script_name)
            if cand.is_file():
                task.resolved_path = cand
        else:
            if task.script_name in profile.conflict_resolutions:
                cand = resolve_home(profile.conflict_resolutions[task.script_name])
                if cand.is_file():
                    task.resolved_path = cand

            if task.resolved_path is None:
                matches: list[Path] = []
                for d in profile.search_dirs:
                    p = Path(d) / task.script_name
                    key = str(p)
                    exists = search_dir_cache.get(key)
                    if exists is None:
                        exists = p.is_file()
                        search_dir_cache[key] = exists
                    if exists:
                        matches.append(p)

                if len(matches) == 1:
                    task.resolved_path = matches[0]
                elif len(matches) > 1:
                    sys.stderr.write(f"[CONFLICT] Multiple versions of {task.script_name} found:\n")
                    for m in matches:
                        sys.stderr.write(f"  - {m}\n")
                    success = False

        if task.resolved_path is None:
            sys.stderr.write(f"[MISSING] Could not find {task.script_name} in search dirs.\n")
            success = False
            continue

        is_elf, first_line, full_head = _script_metadata(task.resolved_path)

        for line in full_head.splitlines()[:20]:
            if _INTERACTIVE_RE.search(line):
                task.interactive = True
                break

        shebang_interp = _interpreter_from_shebang(first_line)
        executable = os.access(task.resolved_path, os.X_OK)

        if is_elf:
            task.interpreter = ""
        elif shebang_interp == "python2":
            sys.stderr.write(f"[WARNING] {task.script_name} uses python2 shebang; forcing current Python.\n")
            task.interpreter = sys.executable
        elif shebang_interp:
            if executable and shebang_interp in ("bash", "sh", "zsh", "dash", "fish", "python"):
                # Direct execution honors the actual shebang.
                task.interpreter = ""
            else:
                if shebang_interp == "python":
                    task.interpreter = sys.executable
                elif shebang_interp in ("bash", "sh", "zsh", "dash", "fish"):
                    task.interpreter = shutil.which(shebang_interp) or shebang_interp
                else:
                    task.interpreter = shebang_interp
        else:
            suffix = task.resolved_path.suffix.lower()
            if suffix == ".py":
                task.interpreter = sys.executable
            elif suffix == ".sh":
                task.interpreter = shutil.which("bash") or "bash"
            elif suffix == ".fish":
                task.interpreter = shutil.which("fish") or "fish"
            elif executable:
                task.interpreter = ""
            else:
                task.interpreter = shutil.which("bash") or "bash"

    return success


# ==============================================================================
# GIT SELF UPDATE
# ==============================================================================
def _git_env() -> dict[str, str]:
    env = os.environ.copy()
    env.update(
        {
            "GIT_TERMINAL_PROMPT": "0",
            "GIT_SSH_COMMAND": "ssh -o BatchMode=yes",
            "GIT_PAGER": "cat",
            "PAGER": "cat",
        }
    )
    return env


def _git_run(cmd: list[str], timeout: int = 60) -> subprocess.CompletedProcess:
    return subprocess.run(
        cmd,
        env=_git_env(),
        capture_output=True,
        text=True,
        timeout=timeout,
    )


def _git_check(cmd: list[str], timeout: int = 60) -> str:
    proc = _git_run(cmd, timeout=timeout)
    if proc.returncode != 0:
        raise subprocess.CalledProcessError(proc.returncode, cmd, proc.stdout, proc.stderr)
    return proc.stdout.strip()


def _proc_holds_file(path: Path) -> bool:
    try:
        real = path.resolve()
    except Exception:
        return False

    proc_dir = Path("/proc")
    if not proc_dir.exists():
        return False

    for pid_dir in proc_dir.iterdir():
        if not pid_dir.name.isdigit():
            continue
        fd_dir = pid_dir / "fd"
        if not fd_dir.exists():
            continue
        with suppress(OSError):
            for fd_link in fd_dir.iterdir():
                with suppress(OSError):
                    if fd_link.resolve() == real:
                        return True
    return False


def _clear_stale_git_locks(git_dir: Path) -> bool:
    locks = [
        "index.lock",
        "config.lock",
        "packed-refs.lock",
        "shallow.lock",
        "HEAD.lock",
        "ORIG_HEAD.lock",
        "FETCH_HEAD.lock",
    ]

    for lock_name in locks:
        lock_file = git_dir / lock_name
        if not lock_file.exists():
            continue

        if _proc_holds_file(lock_file):
            sys.stderr.write(f"[ERROR] Git lock {lock_file} is open by a live process. Aborting git update.\n")
            return False

        with suppress(OSError):
            age = time.time() - lock_file.stat().st_mtime
            if age > 60:
                lock_file.unlink(missing_ok=True)
                sys.stdout.write(f"[GIT] Cleared stale Git lock: {lock_name}\n")
            else:
                sys.stderr.write(f"[ERROR] Git lock {lock_file} is too recent to safely auto-clear. Aborting.\n")
                return False

    return True


def _remote_ref(base_cmd: list[str], remote: str) -> str:
    with suppress(Exception):
        _git_check(base_cmd + ["remote", "set-head", remote, "-a"], timeout=30)

    with suppress(Exception):
        out = _git_check(base_cmd + ["symbolic-ref", f"refs/remotes/{remote}/HEAD"], timeout=20)
        return out.removeprefix("refs/remotes/")

    for branch in ("main", "master"):
        ref = f"{remote}/{branch}"
        with suppress(Exception):
            _git_check(base_cmd + ["rev-parse", ref], timeout=20)
            return ref

    raise RuntimeError("Could not determine upstream branch (tried main/master).")


def _clean_old_backups(base: Path, keep: int = 10) -> None:
    if not base.exists():
        return

    entries = sorted([p for p in base.iterdir() if p.is_dir()], reverse=True)
    for old in entries[keep:]:
        with suppress(OSError):
            shutil.rmtree(old, ignore_errors=True)


def _move_to_backup(src: Path, dest: Path) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)

    if src.is_dir() and not src.is_symlink():
        shutil.copytree(src, dest, symlinks=True)
        shutil.rmtree(src, ignore_errors=True)
    else:
        shutil.move(src, dest)


def run_git_self_update(profile: ProfileConfig, update_only: bool = False, offline: bool = False) -> bool:
    if offline or not profile.git_enabled:
        return False

    if not shutil.which("git"):
        sys.stdout.write("[WARN] git not installed. Skipping self-update.\n")
        return False

    git_dir = resolve_home(profile.git_dir)
    work_tree = resolve_home(profile.git_work_tree)

    if not git_dir.exists():
        sys.stdout.write(f"[WARN] Git dir not found ({git_dir}). Skipping self-update.\n")
        return False

    if not _clear_stale_git_locks(git_dir):
        return False

    base_cmd = ["git", f"--git-dir={git_dir}", f"--work-tree={work_tree}"]
    sys.stdout.write("[GIT] Fetching upstream updates...\n")

    fetch_success = False
    for attempt in range(1, 6):
        try:
            _git_check(base_cmd + ["fetch", profile.git_remote], timeout=60)
            fetch_success = True
            break
        except Exception:
            if attempt < 5:
                sys.stdout.write(f"[WARN] Fetch attempt {attempt}/5 failed. Retrying in 2s...\n")
                time.sleep(2)

    if not fetch_success:
        sys.stderr.write("[ERROR] Git fetch failed after 5 attempts. Continuing without update.\n")
        return False

    try:
        local_head = _git_check(base_cmd + ["rev-parse", "HEAD"])
        remote_ref = _remote_ref(base_cmd, profile.git_remote)
        remote_head = _git_check(base_cmd + ["rev-parse", remote_ref])

        if local_head == remote_head:
            sys.stdout.write("[GIT] Orchestrator is up to date.\n")
            return False

        try:
            merge_base = _git_check(base_cmd + ["merge-base", "HEAD", remote_head])
        except Exception:
            merge_base = ""

        if merge_base != local_head and local_head != remote_head:
            sys.stdout.write("\n[DIVERGED HISTORY] Local history diverges from upstream.\n")
            sys.stdout.write("  1) Abort (keep current state) [DEFAULT]\n")
            sys.stdout.write("  2) Reset to upstream [RECOMMENDED]\n")
            sys.stdout.write("Choice [1-2] (default: 1): ")
            sys.stdout.flush()

            if sys.stdin.isatty():
                r, _, _ = select.select([sys.stdin], [], [], 60)
                choice = "1"
                if r:
                    choice = sys.stdin.readline().strip()
                if choice != "2":
                    sys.stdout.write("Aborting update by user request.\n")
                    return False
            else:
                sys.stderr.write("[ERROR] Non-interactive mode and diverged history. Aborting update.\n")
                return False

        sys.stdout.write(f"[GIT] Updating from {local_head[:7]} to {remote_head[:7]}...\n")

        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_base = DOCUMENTS_ROOT / "dusky_backups"
        backup_base.mkdir(parents=True, exist_ok=True)
        _clean_old_backups(backup_base, keep=10)

        collision_dir = backup_base / f"untracked_collisions_{timestamp}"

        with suppress(Exception):
            tracked_out = _git_check(base_cmd + ["ls-files", "-z"])
            tracked_files = set(tracked_out.split("\0"))

            incoming_out = _git_check(base_cmd + ["ls-tree", "-r", "-z", "--name-only", remote_ref])
            incoming_files = set(incoming_out.split("\0"))

            collisions = []
            for inc in incoming_files:
                if not inc:
                    continue
                target_file = work_tree / inc
                if target_file.exists() and inc not in tracked_files:
                    collisions.append(inc)

            if collisions:
                sys.stdout.write(f"[WARN] Found {len(collisions)} untracked work-tree collisions. Backing up...\n")
                collision_dir.mkdir(parents=True, exist_ok=True)
                for coll in collisions:
                    src = work_tree / coll
                    dest = collision_dir / coll
                    with suppress(OSError):
                        _move_to_backup(src, dest)

        changed_files: dict[str, str] = {}
        with suppress(Exception):
            diff_output = _git_check(base_cmd + ["diff-index", "-z", "--raw", "--no-renames", "HEAD"])
            if diff_output:
                parts = diff_output.split("\0")
                i = 0
                while i < len(parts) - 1:
                    meta = parts[i]
                    path = parts[i + 1]
                    i += 2
                    if not meta:
                        continue
                    meta_tokens = meta.split()
                    if len(meta_tokens) >= 5:
                        old_oid = meta_tokens[2]
                        status = meta_tokens[4][0]
                        if status != "D":
                            changed_files[path] = old_oid

        my_path = Path(__file__).resolve()
        wrapper_path = my_path.with_name("orchestrator.sh")

        try:
            h_before = hashlib.sha256(my_path.read_bytes()).hexdigest()
        except OSError:
            h_before = ""

        try:
            wrapper_before = hashlib.sha256(wrapper_path.read_bytes()).hexdigest() if wrapper_path.exists() else ""
        except OSError:
            wrapper_before = ""

        orch_backup = backup_base / f"orchestrator_{timestamp}.py"
        with suppress(OSError):
            shutil.copy2(my_path, orch_backup)

        backup_dir = None
        needs_merge_dir = None

        if changed_files:
            backup_dir = backup_base / f"user_mods_{timestamp}"
            needs_merge_dir = backup_base / f"needs_merge_{timestamp}"
            backup_dir.mkdir(parents=True, exist_ok=True)
            sys.stdout.write(f"[WARN] Local changes detected. Backing up {len(changed_files)} files...\n")

            for path in changed_files:
                src = work_tree / path
                if src.exists() and src.is_file():
                    dest = backup_dir / path
                    dest.parent.mkdir(parents=True, exist_ok=True)
                    with suppress(OSError):
                        shutil.copy2(src, dest)

        sys.stdout.write("[GIT] Performing hard reset to match upstream...\n")
        _git_check(base_cmd + ["reset", "--hard", remote_head], timeout=120)

        if changed_files and backup_dir is not None:
            sys.stdout.write("[GIT] Processing local edits...\n")
            restored = 0
            merged = 0

            for path, old_oid in changed_files.items():
                backup_file = backup_dir / path
                if not backup_file.exists():
                    continue

                try:
                    tree_out = _git_check(base_cmd + ["ls-tree", "HEAD", "--", path])
                    new_oid = tree_out.split()[2] if tree_out else ""
                except Exception:
                    new_oid = ""

                target_file = work_tree / path

                if new_oid == old_oid or not new_oid:
                    try:
                        target_file.parent.mkdir(parents=True, exist_ok=True)
                        tmp_file = target_file.parent / f".{target_file.name}.dusky_tmp"
                        shutil.copy2(backup_file, tmp_file)
                        os.replace(tmp_file, target_file)
                        restored += 1
                    except OSError:
                        if needs_merge_dir is not None:
                            conflict_dest = needs_merge_dir / path
                            conflict_dest.parent.mkdir(parents=True, exist_ok=True)
                            with suppress(OSError):
                                shutil.copy2(backup_file, conflict_dest)
                            merged += 1
                else:
                    if needs_merge_dir is not None:
                        conflict_dest = needs_merge_dir / path
                        conflict_dest.parent.mkdir(parents=True, exist_ok=True)
                        with suppress(OSError):
                            shutil.copy2(backup_file, conflict_dest)
                        merged += 1

            if restored:
                sys.stdout.write(f"[GIT] Restored {restored} safe edits.\n")
            if merged and needs_merge_dir is not None:
                sys.stdout.write(f"[WARN] {merged} files had upstream conflicts. Saved in: {needs_merge_dir}\n")

            with suppress(OSError):
                shutil.rmtree(backup_dir, ignore_errors=True)

        try:
            py_compile.compile(str(my_path), doraise=True)
        except Exception as e:
            sys.stderr.write(f"[ERROR] Updated orchestrator failed validation: {e}\n")
            if orch_backup.exists():
                with suppress(OSError):
                    shutil.copy2(orch_backup, my_path)
                sys.stdout.write("[GIT] Restored previous orchestrator.py.\n")
            return False

        try:
            h_after = hashlib.sha256(my_path.read_bytes()).hexdigest()
        except OSError:
            h_after = ""

        try:
            wrapper_after = hashlib.sha256(wrapper_path.read_bytes()).hexdigest() if wrapper_path.exists() else ""
        except OSError:
            wrapper_after = ""

        sys.stdout.write("[GIT] Update applied. Restarting orchestrator...\n")
        SudoEngine.cleanup()

        if wrapper_path.exists():
            with suppress(OSError):
                os.chmod(wrapper_path, 0o755)
            os.execv(str(wrapper_path), [str(wrapper_path)] + sys.argv[1:])

        os.execv(sys.executable, [sys.executable] + sys.argv)
        return True

    except subprocess.CalledProcessError as e:
        stderr = ""
        if e.stderr:
            stderr = str(e.stderr).strip()
        sys.stderr.write(f"[WARN] Git operation failed: {e}\n")
        if stderr:
            sys.stderr.write(stderr + "\n")
        return False
    except Exception as e:
        sys.stderr.write(f"[WARN] Git update failed: {e}\n")
        return False


# ==============================================================================
# UI HELPERS
# ==============================================================================
def _status_badge(status: TaskStatus) -> Text:
    match status:
        case TaskStatus.COMPLETED:
            return Text("✔", style="green")
        case TaskStatus.RUNNING:
            return Text("◐", style="yellow")
        case TaskStatus.FAILED:
            return Text("✘", style="red")
        case TaskStatus.SKIPPED:
            return Text("○", style="dim")
        case _:
            return Text("○", style="dim")


def _task_label(task: OrchestratorTask) -> Text:
    txt = Text()
    txt.append(f"{task.index:02d} ")
    txt.append_text(_status_badge(task.status))
    txt.append(f" [{task.mode}] {task.script_name}")
    return txt


class TaskSearchScreen(ModalScreen[str | None]):
    BINDINGS = [
        Binding("escape", "dismiss_modal", "Dismiss"),
        Binding("ctrl+n", "cursor_down", "Down"),
        Binding("ctrl+p", "cursor_up", "Up"),
    ]

    def __init__(self, tasks: list[OrchestratorTask]):
        super().__init__()
        self.tasks = tasks
        self.results: list[str] = []

    def compose(self) -> ComposeResult:
        with Container(id="search_dialog"):
            yield Static("◈ Fuzzy Task Search", id="search_title")
            yield Input(placeholder="Search tasks...", id="search_input")
            yield OptionList(id="search_list")

    def on_mount(self) -> None:
        self.query_one("#search_input", Input).focus()
        self._update_results("")

    def on_input_changed(self, event: Input.Changed) -> None:
        self._update_results(event.value)

    def _update_results(self, query: str) -> None:
        ol = self.query_one(OptionList)
        ol.clear_options()
        self.results.clear()

        query_lower = query.lower().strip()
        query_no_space = query_lower.replace(" ", "")

        if not query_lower:
            scored = [(0, t) for t in self.tasks[:200]]
        else:
            scored_results: list[tuple[int, OrchestratorTask]] = []

            for item in self.tasks:
                target = item.script_name.lower()
                args_text = " ".join(item.args).lower()
                haystack = f"{target} {args_text}"
                score = 0

                if query_lower == target:
                    score += 100
                elif target.startswith(query_lower):
                    score += 50
                elif query_lower in target:
                    score += 30
                elif query_lower in haystack:
                    score += 18

                if query_no_space and query_no_space in target.replace(" ", "").replace("-", "").replace("_", ""):
                    score += 20

                s_idx = q_idx = 0
                match_positions: list[int] = []
                while s_idx < len(target) and q_idx < len(query_no_space):
                    if target[s_idx] == query_no_space[q_idx]:
                        match_positions.append(s_idx)
                        q_idx += 1
                    s_idx += 1

                if q_idx == len(query_no_space) and query_no_space:
                    if len(match_positions) > 1:
                        spread = (match_positions[-1] - match_positions[0]) - (len(match_positions) - 1)
                        score += max(0, 15 - spread)
                    else:
                        score += 15
                    score += 5

                if score > 0:
                    scored_results.append((score, item))

            scored_results.sort(key=lambda x: (-x[0], x[1].index))
            scored = scored_results

        options: list[Option] = []
        for _, item in scored[:200]:
            txt = Text()
            txt.append(f"{item.index:02d} ")
            txt.append_text(_status_badge(item.status))
            txt.append(f" [{item.mode}] ", style="bold yellow")
            txt.append(item.script_name, style="bold white")
            if item.args:
                txt.append(" " + shlex.join(item.args), style="dim")
            options.append(Option(txt, id=item.state_key))
            self.results.append(item.state_key)

        ol.add_options(options)

    @on(OptionList.OptionSelected)
    def on_selected(self, event: OptionList.OptionSelected) -> None:
        if event.option and event.option.id:
            self.dismiss(str(event.option.id))
        elif event.option_index is not None and event.option_index < len(self.results):
            self.dismiss(self.results[event.option_index])

    @on(Input.Submitted)
    def on_input_submitted(self, event: Input.Submitted) -> None:
        event.stop()
        ol = self.query_one(OptionList)
        if ol.highlighted is not None and ol.highlighted < len(self.results):
            self.dismiss(self.results[ol.highlighted])
        elif self.results:
            self.dismiss(self.results[0])

    def action_cursor_down(self) -> None:
        self.query_one(OptionList).action_cursor_down()

    def action_cursor_up(self) -> None:
        self.query_one(OptionList).action_cursor_up()

    def action_dismiss_modal(self) -> None:
        self.dismiss(None)


class ConflictModalScreen(ModalScreen[str]):
    def __init__(self, script_name: str, command: str, exit_code: int | None, error_msg: str):
        super().__init__()
        self.script_name = script_name
        self.command = command
        self.exit_code = exit_code
        self.error_msg = error_msg

    def compose(self) -> ComposeResult:
        with Container(id="modal_dialog"):
            yield Static(Text(f"⚠ EXECUTION FAULT: {self.script_name}", style="bold red"), id="modal_title")

            details = Text()
            details.append("Command:\n", style="bold")
            details.append(self.command + "\n\n", style="dim")
            details.append("Exit code: ", style="bold")
            details.append(str(self.exit_code) + "\n\n", style="red bold")
            details.append("Diagnostics:\n", style="bold")
            details.append(self.error_msg, style="yellow")

            yield Static(details, id="error_details")

            with Horizontal(id="button_bar"):
                yield Button("Retry [R]", variant="primary", id="btn_retry")
                yield Button("Manual TTY [M]", variant="warning", id="btn_manual")
                yield Button("Skip [S]", variant="error", id="btn_skip")
                yield Button("Abort [A]", variant="default", id="btn_abort")

    def on_mount(self) -> None:
        AudioNotifier.play("alert")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        match event.button.id:
            case "btn_retry":
                self.dismiss("retry")
            case "btn_manual":
                self.dismiss("manual")
            case "btn_skip":
                self.dismiss("skip")
            case _:
                self.dismiss("abort")

    def on_key(self, event) -> None:
        key = getattr(event, "key", "").lower()
        match key:
            case "r":
                self.dismiss("retry")
            case "m":
                self.dismiss("manual")
            case "s":
                self.dismiss("skip")
            case "a" | "escape" | "q":
                self.dismiss("abort")


class ManualModalScreen(ModalScreen[str]):
    def __init__(self, script_name: str, command: str):
        super().__init__()
        self.script_name = script_name
        self.command = command

    def compose(self) -> ComposeResult:
        with Container(id="manual_dialog"):
            yield Static(Text(f"⏸ MANUAL OVERRIDE: {self.script_name}", style="bold cyan"), id="manual_title")

            details = Text()
            details.append("Command:\n", style="bold")
            details.append(self.command, style="dim")
            yield Static(details)

            with Horizontal(id="button_bar"):
                yield Button("Proceed [Y]", variant="success", id="btn_yes")
                yield Button("Skip [S]", variant="warning", id="btn_skip")
                yield Button("Quit [Q]", variant="error", id="btn_quit")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        match event.button.id:
            case "btn_yes":
                self.dismiss("yes")
            case "btn_skip":
                self.dismiss("skip")
            case _:
                self.dismiss("quit")

    def on_key(self, event) -> None:
        key = getattr(event, "key", "").lower()
        match key:
            case "y":
                self.dismiss("yes")
            case "s":
                self.dismiss("skip")
            case "q" | "escape":
                self.dismiss("quit")


class SudoPasswordScreen(ModalScreen[bool]):
    BINDINGS = [Binding("escape", "cancel", "Cancel")]

    def compose(self) -> ComposeResult:
        with Container(id="sudo_dialog"):
            yield Static("◈ Sudo Authentication Required", id="sudo_title")
            yield Input(placeholder="sudo password", password=True, id="sudo_password")
            yield Static("", id="sudo_error")
            with Horizontal(id="button_bar"):
                yield Button("Authenticate", variant="primary", id="btn_auth")
                yield Button("Cancel", variant="default", id="btn_cancel")

    def on_mount(self) -> None:
        self.query_one("#sudo_password", Input).focus()

    async def _submit(self) -> None:
        pw = self.query_one("#sudo_password", Input).value
        ok, err = await asyncio.to_thread(SudoEngine.set_password, pw)
        if ok:
            self.dismiss(True)
        else:
            self.query_one("#sudo_error", Static).update(Text(f"Authentication failed: {err}", style="red"))

    async def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "btn_auth":
            await self._submit()
        else:
            self.dismiss(False)

    async def on_input_submitted(self, event: Input.Submitted) -> None:
        event.stop()
        await self._submit()

    def action_cancel(self) -> None:
        self.dismiss(False)


class AppFooter(Horizontal):
    def compose(self) -> ComposeResult:
        yield Label("[Ctrl+F] Search", classes="footer-shortcut")
        yield Label("[M] Manual", classes="footer-shortcut")
        yield Label("[S] Skip", classes="footer-shortcut")
        yield Label("[Q] Quit", classes="footer-shortcut")
        yield Label(" │ ", classes="footer-sep")
        yield Label("Engine: active", id="footer_status")


class ProfileSelectorApp(App):
    ENABLE_COMMAND_PALETTE = False

    CSS = """
Screen {
    align: center middle;
    background: #0a1612;
    color: #d8e6df;
}

#selector_container {
    width: 88;
    height: auto;
    border: heavy #00e0b8;
    background: #0f221d;
    padding: 1 2;
}

#title {
    text-align: center;
    text-style: bold;
    color: #00e0b8;
    margin-bottom: 1;
}

OptionList {
    height: auto;
    border: none;
    background: #0f221d;
    color: #d8e6df;
}

.help_text {
    text-align: center;
    color: #a0d0cb;
    text-style: italic;
    margin-top: 1;
}
"""

    def __init__(self, profiles: list[ProfileConfig]):
        super().__init__()
        self.profiles = profiles
        self.selected_profile: ProfileConfig | None = None

    def compose(self) -> ComposeResult:
        with Container(id="selector_container"):
            yield Static("◈ DUSKY ARCH MASTER ORCHESTRATOR", id="title")

            options = []
            for i, p in enumerate(self.profiles):
                prefix = "❯ " if i == 0 else "  "
                options.append(Option(f"{prefix}{i + 1}. {p.name:<25} {p.description}", id=str(i)))

            yield OptionList(*options, id="profiles_list")
            yield Static("Enter select | 1-9 quick select | Esc quit", classes="help_text")

    def on_option_list_option_selected(self, event: OptionList.OptionSelected) -> None:
        if event.option_id is not None:
            self.selected_profile = self.profiles[int(event.option_id)]
        elif event.option_index is not None:
            self.selected_profile = self.profiles[event.option_index]
        self.exit(0)

    def on_key(self, event) -> None:
        if event.key == "escape":
            self.exit(1)
            return

        if event.character and event.character in "123456789":
            idx = int(event.character) - 1
            if 0 <= idx < len(self.profiles):
                self.selected_profile = self.profiles[idx]
                self.exit(0)


# ==============================================================================
# MAIN APP
# ==============================================================================
class DuskyOrchestratorApp(App):
    ENABLE_COMMAND_PALETTE = False
    CSS = ""

    BINDINGS = [
        Binding("ctrl+f", "open_search", "Search Tasks", priority=True),
    ]

    def __init__(
        self,
        profile: ProfileConfig,
        has_sudo: bool,
        manual: bool,
        stop_on_fail: bool,
        force: bool,
        task_timeout: float,
    ):
        super().__init__()

        self.profile = profile
        self.tasks = profile.tasks
        self.has_sudo = has_sudo
        self.manual = manual
        self.stop_on_fail = stop_on_fail
        self.force_flag = force
        self.task_timeout = task_timeout

        self.active_child_pid: int | None = None
        self.current_pty_master: int | None = None
        self.active_task: OrchestratorTask | None = None
        self.sudo_task: asyncio.Task | None = None

        self.state_file = state_file_for(profile)
        self.completed_keys = load_completed_keys(profile)

        self.tree_widget = Tree("◈ Execution Sequence")
        self.log_widget = RichLog(id="pty_log", highlight=False, markup=False, wrap=True, max_lines=10000)
        self.progress_bar = ProgressBar(show_eta=False, show_percentage=False, id="progress_bar")
        self.status_label = Label("Initializing orchestrator sequence...", id="status_label")
        self.speed_label = Label("Status: pre-flight | ETA: --:--", id="speed_label")

        self.tree_nodes_map: dict[str, TreeNode] = {}
        self.logger = RunLogger(profile)

        self._log_widgets: dict[str | None, RichLog] = {}
        self._ui_buffer: list[tuple[str | None, Text]] = []
        self._ui_flush_timer = None

        self._telemetry: dict[str, str] = {}
        self._telemetry_timer = None

    def compose(self) -> ComposeResult:
        with Horizontal(id="top_header"):
            yield Static(f"◈ DUSKY ORCHESTRATOR  [{self.profile.name}]", id="header_title")

        with Horizontal(id="main_dashboard"):
            with Vertical(id="left_pane"):
                yield self.tree_widget

            with Vertical(id="right_pane"):
                with Container(id="telemetry_box"):
                    yield self.status_label
                    yield self.speed_label
                    yield self.progress_bar

                with ContentSwitcher(id="log_switcher"):
                    yield self.log_widget
                    for task in self.tasks:
                        yield RichLog(
                            id=f"log_{task.state_key}",
                            highlight=False,
                            markup=False,
                            wrap=True,
                            max_lines=10000,
                        )

        yield AppFooter(id="footer")

    def on_mount(self) -> None:
        with suppress(Exception):
            self.query_one("#log_switcher", ContentSwitcher).current = "pty_log"

        self.progress_bar.total = max(1, len(self.tasks))
        self.build_task_tree()

        sudo_mode = SudoEngine.mode_name() if self.has_sudo else "none"
        log_root = str(self.logger.root) if self.logger.root else "disabled"

        with suppress(Exception):
            self.query_one("#footer_status", Label).update(
                f"Engine: active | sudo: {sudo_mode} | logs: {log_root}"
            )

        self.log_system("Environment pre-flight validated. PTY engine online.")

        for t in self.tasks:
            if t.state_key in self.completed_keys:
                self.update_task_node_by_key(t.state_key, TaskStatus.COMPLETED)
                self.progress_bar.advance(1)

        self.run_execution_pipeline()

    def on_unmount(self) -> None:
        self.logger.close_all()
        SudoEngine.cleanup()

    def on_resize(self, event: events.Resize) -> None:
        if self.current_pty_master is not None:
            self._set_pty_size(self.current_pty_master)

    @on(Tree.NodeSelected)
    def on_node_selected(self, event: Tree.NodeSelected) -> None:
        node = event.node
        switcher = self.query_one("#log_switcher", ContentSwitcher)

        if node == self.tree_widget.root:
            switcher.current = "pty_log"
        elif node.data and isinstance(node.data, OrchestratorTask):
            switcher.current = f"log_{node.data.state_key}"

    def action_open_search(self) -> None:
        if isinstance(self.screen, ModalScreen):
            return

        def on_search_selected(state_key: str | None) -> None:
            if not state_key:
                return
            if node := self.tree_nodes_map.get(state_key):
                self.tree_widget.select_node(node)
                self.tree_widget.scroll_to_node(node)
                for t in self.tasks:
                    if t.state_key == state_key:
                        self.log_system(f"Fuzzy finder navigated to: {t.script_name}")
                        break

        self.push_screen(TaskSearchScreen(self.tasks), on_search_selected)

    def action_quit_orchestrator(self) -> None:
        self.log_system("Abort signal received. Terminating pipeline...", is_err=True)
        self.exit(1)

    def _on_key(self, event: events.Key) -> None:
        if isinstance(self.screen, ModalScreen):
            super()._on_key(event)
            return

        if self.current_pty_master is not None:
            if event.key == "ctrl+f":
                super()._on_key(event)
                return

            data = self._pty_key_bytes(event)
            if data:
                with suppress(OSError):
                    os.write(self.current_pty_master, data)

            event.stop()
            return

        if event.key in ("q", "ctrl+c"):
            self.action_quit_orchestrator()
            event.stop()
            return
        elif event.key == "/":
            self.action_open_search()
            event.stop()
            return

        super()._on_key(event)

    def _pty_key_bytes(self, event: events.Key) -> bytes:
        key = event.key

        if event.is_printable and event.character:
            return event.character.encode("utf-8")

        simple = {
            "enter": b"\r",
            "escape": b"\x1b",
            "tab": b"\t",
            "backspace": b"\x7f",
            "delete": b"\x1b[3~",
            "home": b"\x1b[H",
            "end": b"\x1b[F",
            "pageup": b"\x1b[5~",
            "pagedown": b"\x1b[6~",
            "up": b"\x1b[A",
            "down": b"\x1b[B",
            "right": b"\x1b[C",
            "left": b"\x1b[D",
            "insert": b"\x1b[2~",
        }

        if key in simple:
            return simple[key]

        if key.startswith("ctrl+"):
            rest = key[5:]
            if rest == "space":
                return b"\x00"
            if rest == "@":
                return b"\x00"
            if rest == "[":
                return b"\x1b"
            if rest == "\\":
                return b"\x1c"
            if rest == "]":
                return b"\x1d"
            if rest == "^":
                return b"\x1e"
            if rest == "_":
                return b"\x1f"
            if len(rest) == 1 and rest.isalpha():
                return bytes([ord(rest.lower()) - 96])

        return b""

    def build_task_tree(self) -> None:
        self.tree_widget.root.expand()
        for task in self.tasks:
            node = self.tree_widget.root.add_leaf(_task_label(task))
            node.data = task
            self.tree_nodes_map[task.state_key] = node

    def update_task_node_by_key(self, state_key: str, status: TaskStatus) -> None:
        node = self.tree_nodes_map.get(state_key)
        if node is None:
            return

        for t in self.tasks:
            if t.state_key == state_key:
                t.status = status
                node.label = _task_label(t)

                if status == TaskStatus.RUNNING:
                    with suppress(Exception):
                        self.tree_widget.select_node(node)
                        self.tree_widget.scroll_to_node(node)
                        self.query_one("#log_switcher", ContentSwitcher).current = f"log_{state_key}"
                break

    def _get_log_widget(self, key: str | None) -> RichLog | None:
        if key in self._log_widgets:
            return self._log_widgets[key]

        widget_id = "#pty_log" if key is None else f"#log_{key}"
        with suppress(Exception):
            w = self.query_one(widget_id, RichLog)
            self._log_widgets[key] = w
            return w

        return None

    def _queue_ui(self, text: Text, task_key: str | None = None) -> None:
        self._ui_buffer.append((None, text))
        if task_key is not None:
            self._ui_buffer.append((task_key, text))

        if len(self._ui_buffer) > 1200:
            self._flush_ui()
            return

        if self._ui_flush_timer is None:
            self._ui_flush_timer = self.set_timer(0.03, self._flush_ui)

    def _flush_ui(self) -> None:
        if self._ui_flush_timer is not None:
            with suppress(Exception):
                self._ui_flush_timer.stop()
            self._ui_flush_timer = None

        items = self._ui_buffer
        self._ui_buffer = []

        for key, text in items:
            widget = self._get_log_widget(key)
            if widget is not None:
                with suppress(Exception):
                    widget.write(text)

    def _queue_telemetry(self, pct: str | None = None, speed: str | None = None, eta: str | None = None) -> None:
        if pct:
            self._telemetry["pct"] = pct
        if speed and eta:
            self._telemetry["speed"] = speed
            self._telemetry["eta"] = eta

        if self._telemetry_timer is None:
            self._telemetry_timer = self.set_timer(0.2, self._flush_telemetry)

    def _flush_telemetry(self) -> None:
        if self._telemetry_timer is not None:
            with suppress(Exception):
                self._telemetry_timer.stop()
            self._telemetry_timer = None

        pct = self._telemetry.get("pct")
        speed = self._telemetry.get("speed")
        eta = self._telemetry.get("eta")

        if pct:
            self.status_label.update(f"⚡ Processing task sub-step... ({pct})")
        if speed and eta:
            self.speed_label.update(f"Throughput: {speed} | ETA: {eta}")

    def log_system(self, msg: str, is_err: bool = False) -> None:
        prefix_style = "bold red" if is_err else "bold cyan"
        text = Text.assemble(("[SYSTEM] ", prefix_style), (msg, ""))

        self.logger.system(msg)
        self._queue_ui(text, self.active_task.state_key if self.active_task else None)

    def handle_pty_line(self, line: str, last_lines: deque | None = None) -> None:
        clean = line.strip("\r\n")
        if not clean:
            return

        stripped = ANSI_STRIP_REGEX.sub("", clean) if "\x1b" in clean else clean

        if last_lines is not None and stripped.strip():
            last_lines.append(stripped.rstrip())

        if self.active_task is not None:
            self.logger.write_task(self.active_task, stripped)

        pct = speed = eta = None

        if "%" in stripped:
            if m := PCT_REGEX.search(stripped):
                pct = m.group(0)

        if "b/s" in stripped.lower():
            if m := SPEED_ETA_REGEX.search(stripped):
                speed, eta = m.group(1), m.group(2)
            elif m := ALT_SPEED_ETA_REGEX.search(stripped):
                speed, eta = m.group(1), m.group(2)

        if pct or speed:
            self._queue_telemetry(pct=pct, speed=speed, eta=eta)

        lower = stripped.lower()
        if "\x1b" not in clean and any(k in lower for k in ("error", "failed", "warning", "conflict", "exists in filesystem")):
            text = Text(clean, style="bold red")
        else:
            text = Text.from_ansi(clean)

        self._queue_ui(text, self.active_task.state_key if self.active_task else None)

    @staticmethod
    def _set_pty_size(fd: int) -> None:
        try:
            size = os.get_terminal_size()
            winsize = struct.pack("HHHH", size.lines, size.columns, 0, 0)
            fcntl.ioctl(fd, termios.TIOCSWINSZ, winsize)
        except (OSError, ValueError):
            with suppress(OSError):
                winsize = struct.pack("HHHH", FALLBACK_ROWS, FALLBACK_COLS, 0, 0)
                fcntl.ioctl(fd, termios.TIOCSWINSZ, winsize)

    async def _kill_proc(self, proc: asyncio.subprocess.Process | None) -> None:
        if proc is None or proc.returncode is not None:
            return

        with suppress(ProcessLookupError, PermissionError, OSError):
            os.killpg(proc.pid, signal.SIGTERM)

        with suppress(Exception):
            await asyncio.wait_for(proc.wait(), timeout=2.0)

        if proc.returncode is None:
            with suppress(ProcessLookupError, PermissionError, OSError):
                os.killpg(proc.pid, signal.SIGKILL)

            with suppress(Exception):
                await asyncio.wait_for(proc.wait(), timeout=1.0)

    def _task_env(self, task: OrchestratorTask) -> dict[str, str]:
        env = os.environ.copy()

        env.update(
            {
                "PYTHONUNBUFFERED": "1",
                "PYTHONUTF8": "1",
                "PYTHONDONTWRITEBYTECODE": "1",
                "PAGER": "cat",
                "SYSTEMD_PAGER": "cat",
                "GIT_PAGER": "cat",
                "EDITOR": "true",
                "VISUAL": "true",
                "DUSKY_PROFILE_NAME": self.profile.name,
                "DUSKY_PROFILE_FILE": str(self.profile.filepath),
                "DUSKY_TASK_SCRIPT": task.script_name,
                "DUSKY_TASK_PATH": str(task.resolved_path),
                "DUSKY_TASK_MODE": task.mode,
                "DUSKY_TASK_INDEX": str(task.index),
                "DUSKY_TASK_STATE_KEY": task.state_key,
                "DUSKY_USER": pwd.getpwuid(os.getuid()).pw_name,
                "DUSKY_USER_HOME": str(Path.home()),
                "DUSKY_LOG_DIR": str(self.logger.root or LOG_BASE_DIR),
                "DUSKY_FORCE": "1" if self.force_flag else "0",
            }
        )

        if SudoEngine._askpass_path is not None:
            env["SUDO_ASKPASS"] = str(SudoEngine._askpass_path)

        return env

    def _task_command(self, task: OrchestratorTask) -> list[str]:
        assert task.resolved_path is not None

        args = list(task.args)
        if self.force_flag and "--force" not in args:
            args.append("--force")

        if task.interpreter:
            interp = task.interpreter
            if interp.lower() in ("python", "python3"):
                interp = sys.executable
            else:
                interp = shutil.which(interp) or interp

            if Path(interp).name in ("python", "python3", "bash", "sh", "zsh", "dash"):
                inner = [interp, "--", str(task.resolved_path)] + args
            else:
                inner = [interp, str(task.resolved_path)] + args
        else:
            inner = [str(task.resolved_path)] + args

        full_env = self._task_env(task)
        wanted_keys = [
            "PATH",
            "TERM",
            "COLORTERM",
            "LANG",
            "LC_ALL",
            "DISPLAY",
            "WAYLAND_DISPLAY",
            "XDG_RUNTIME_DIR",
            "DBUS_SESSION_BUS_ADDRESS",
            "SSH_AUTH_SOCK",
            "PYTHONUNBUFFERED",
            "PYTHONUTF8",
            "PYTHONDONTWRITEBYTECODE",
            "PAGER",
            "SYSTEMD_PAGER",
            "GIT_PAGER",
            "EDITOR",
            "VISUAL",
            "DUSKY_PROFILE_NAME",
            "DUSKY_PROFILE_FILE",
            "DUSKY_TASK_SCRIPT",
            "DUSKY_TASK_PATH",
            "DUSKY_TASK_MODE",
            "DUSKY_TASK_INDEX",
            "DUSKY_TASK_STATE_KEY",
            "DUSKY_USER",
            "DUSKY_USER_HOME",
            "DUSKY_LOG_DIR",
            "DUSKY_FORCE",
        ]

        env_pairs = [f"{k}={full_env[k]}" for k in wanted_keys if k in full_env]

        if task.mode == "S":
            return SudoEngine.sudo_prefix() + ["env"] + env_pairs + inner

        return ["env"] + env_pairs + inner

    async def execute_pty_command(
        self,
        cmd: list[str],
        env: dict[str, str],
        timeout: float = 0.0,
    ) -> tuple[bool, int | None, str]:
        master_fd, slave_fd = pty.openpty()
        self.current_pty_master = master_fd
        self._set_pty_size(slave_fd)

        transport: asyncio.Transport | None = None
        proc: asyncio.subprocess.Process | None = None
        decoder = codecs.getincrementaldecoder("utf-8")(errors="replace")
        last_lines: deque[str] = deque(maxlen=25)
        line_buffer = ""

        try:
            proc = await asyncio.create_subprocess_exec(
                *cmd,
                stdin=slave_fd,
                stdout=slave_fd,
                stderr=slave_fd,
                env=env,
                close_fds=True,
                start_new_session=True,
            )

            with suppress(OSError):
                os.close(slave_fd)
            slave_fd = -1

            self.active_child_pid = proc.pid

            loop = asyncio.get_running_loop()
            reader = asyncio.StreamReader()
            protocol = asyncio.StreamReaderProtocol(reader)
            file_obj = os.fdopen(master_fd, "rb", buffering=0)
            master_fd = -1
            transport, _ = await loop.connect_read_pipe(lambda: protocol, file_obj)

            async def read_loop() -> None:
                nonlocal line_buffer
                while True:
                    try:
                        chunk = await reader.read(4096)
                    except Exception:
                        chunk = b""

                    if not chunk:
                        if line_buffer:
                            for line in BRACKET_NEWLINE_RE.split(line_buffer):
                                if line:
                                    with suppress(Exception):
                                        self.handle_pty_line(line, last_lines)
                            line_buffer = ""
                        break

                    try:
                        text = decoder.decode(chunk)
                    except Exception:
                        text = chunk.decode("utf-8", errors="replace")

                    line_buffer += text

                    while True:
                        m = SINGLE_NEWLINE_RE.search(line_buffer)
                        if not m:
                            break
                        idx = m.start()
                        line = line_buffer[:idx]
                        line_buffer = line_buffer[idx + 1 :]
                        if line:
                            with suppress(Exception):
                                self.handle_pty_line(line, last_lines)

            read_task = asyncio.create_task(read_loop())
            wait_task = asyncio.create_task(proc.wait())

            try:
                if timeout > 0:
                    done, pending = await asyncio.wait(
                        {read_task, wait_task},
                        timeout=timeout,
                        return_when=asyncio.FIRST_COMPLETED,
                    )
                    if not done:
                        await self._kill_proc(proc)
                        read_task.cancel()
                        with suppress(asyncio.CancelledError, Exception):
                            await read_task
                        self._flush_ui()
                        return False, None, "\n".join(last_lines)
                else:
                    done, pending = await asyncio.wait(
                        {read_task, wait_task},
                        return_when=asyncio.FIRST_COMPLETED,
                    )

                if wait_task in done:
                    try:
                        await asyncio.wait_for(read_task, timeout=2.0)
                    except (TimeoutError, asyncio.TimeoutError):
                        read_task.cancel()
                        with suppress(asyncio.CancelledError, Exception):
                            await read_task

                    code = wait_task.result()
                else:
                    try:
                        code = await asyncio.wait_for(wait_task, timeout=5.0)
                    except (TimeoutError, asyncio.TimeoutError):
                        await self._kill_proc(proc)
                        code = proc.returncode

                    if not read_task.done():
                        read_task.cancel()
                        with suppress(asyncio.CancelledError, Exception):
                            await read_task

                self._flush_ui()
                return code == 0, code, "\n".join(last_lines)

            finally:
                for t in (read_task, wait_task):
                    if not t.done():
                        t.cancel()

                with suppress(asyncio.CancelledError, Exception):
                    await read_task
                with suppress(asyncio.CancelledError, Exception):
                    await wait_task

        except asyncio.CancelledError:
            await self._kill_proc(proc)
            raise
        except Exception as e:
            self.log_system(f"PTY execution exception: {e}", is_err=True)
            return False, None, "\n".join(last_lines)
        finally:
            self.current_pty_master = None
            self.active_child_pid = None

            if transport is not None:
                with suppress(Exception):
                    transport.close()
            elif master_fd != -1:
                with suppress(OSError):
                    os.close(master_fd)

            if slave_fd != -1:
                with suppress(OSError):
                    os.close(slave_fd)

    async def _execute_suspended(
        self,
        task: OrchestratorTask,
        cmd: list[str],
        env: dict[str, str],
    ) -> tuple[bool, int | None, str]:
        self.log_system(f"Suspending TUI for interactive workflow: {task.script_name}...")

        with self.suspend():
            sys.stdout.flush()
            sys.stderr.flush()

            old_attr = None
            with suppress(termios.error):
                old_attr = termios.tcgetattr(sys.stdin.fileno())

            try:
                subprocess.run(["clear"], check=False)
                print(f"\n--- INTERACTIVE WORKFLOW: {task.script_name} ---")
                print(f"Executing: {shlex.join(cmd)}\n")

                proc = await asyncio.create_subprocess_exec(*cmd, env=env)
                code = await proc.wait()
                return code == 0, code, "interactive session"
            finally:
                if old_attr:
                    with suppress(termios.error):
                        termios.tcsetattr(sys.stdin.fileno(), termios.TCSADRAIN, old_attr)
                await asyncio.sleep(0.4)

    async def _ensure_sudo(self) -> bool:
        if not self.has_sudo:
            return True

        ok = await asyncio.to_thread(SudoEngine.refresh_sync)
        if ok:
            return True

        self.log_system("Sudo credentials expired. Re-authentication required.", is_err=True)
        return await self.push_screen_wait(SudoPasswordScreen())

    async def _execute_task_cmd(
        self,
        task: OrchestratorTask,
        cmd: list[str],
        env: dict[str, str],
    ) -> tuple[bool, int | None, str]:
        if task.interactive:
            return await self._execute_suspended(task, cmd, env)

        return await self.execute_pty_command(cmd, env, timeout=self.task_timeout)

    def _commit_task_state(self, task: OrchestratorTask) -> None:
        self.completed_keys.add(task.state_key)
        try:
            with open(self.state_file, "a", encoding="utf-8") as f:
                f.write(task.state_key + "\n")
                f.flush()
                os.fsync(f.fileno())
        except OSError as e:
            self.log_system(f"Failed to persist state for {task.script_name}: {e}", is_err=True)

    @work(name="execution_pipeline", exclusive=True)
    async def run_execution_pipeline(self) -> None:
        if self.has_sudo:
            self.sudo_task = asyncio.create_task(
                SudoEngine.maintain_heartbeat(
                    error_callback=lambda msg: self.log_system(msg, is_err=True)
                )
            )

        try:
            for task in self.tasks:
                if task.state_key in self.completed_keys:
                    continue

                if task.resolved_path is None:
                    self.update_task_node_by_key(task.state_key, TaskStatus.FAILED)
                    self.log_system(f"Missing file: {task.script_name}", is_err=True)

                    if self.stop_on_fail:
                        self.log_system("stop-on-fail active. Aborting pipeline.", is_err=True)
                        self.exit(1)
                        return

                    action = await self.push_screen_wait(
                        ConflictModalScreen(
                            task.script_name,
                            "unresolved",
                            None,
                            "File missing from disk. Target could not be resolved.",
                        )
                    )

                    if action == "abort":
                        self.log_system("User aborted execution sequence.", is_err=True)
                        self.exit(1)
                        return

                    self.update_task_node_by_key(task.state_key, TaskStatus.SKIPPED)
                    self.progress_bar.advance(1)
                    self.log_system(f"Skipped missing task: {task.script_name}", is_err=True)
                    continue

                if self.manual:
                    self.status_label.update(f"⏸ Pending manual approval: {task.script_name}")
                    cmd_preview = shlex.join(self._task_command(task))
                    action = await self.push_screen_wait(ManualModalScreen(task.script_name, cmd_preview))

                    if action == "skip":
                        self.update_task_node_by_key(task.state_key, TaskStatus.SKIPPED)
                        self.progress_bar.advance(1)
                        self.log_system(f"Manual override: skipped task {task.script_name}", is_err=True)
                        continue
                    elif action == "quit":
                        self.log_system("Manual override: aborting pipeline.", is_err=True)
                        self.exit(1)
                        return

                if task.mode == "S" and not await self._ensure_sudo():
                    self.update_task_node_by_key(task.state_key, TaskStatus.FAILED)
                    self.log_system("Sudo authentication unavailable.", is_err=True)

                    if self.stop_on_fail:
                        self.exit(1)
                        return

                    action = await self.push_screen_wait(
                        ConflictModalScreen(
                            task.script_name,
                            "sudo authentication",
                            None,
                            "Sudo authentication unavailable. Cannot run root task.",
                        )
                    )
                    if action == "skip":
                        self.update_task_node_by_key(task.state_key, TaskStatus.SKIPPED)
                        self.progress_bar.advance(1)
                        continue
                    self.exit(1)
                    return

                self.active_task = task
                self.update_task_node_by_key(task.state_key, TaskStatus.RUNNING)
                self.status_label.update(f"Executing: {task.script_name} [{task.mode}]")
                self.speed_label.update("Status: running | ETA: --:--")
                self.log_system(f">>> PROCESS INITIATED: {task.script_name}")

                cmd = self._task_command(task)
                env = self._task_env(task)

                self.logger.open_task(task)
                success, code, last = await self._execute_task_cmd(task, cmd, env)

                resolved = False

                while not success and not resolved:
                    if task.ignore_fail:
                        self.log_system(
                            f"Task failed but marked ignore-fail. Continuing: {task.script_name}"
                        )
                        success = True
                        break

                    self.update_task_node_by_key(task.state_key, TaskStatus.FAILED)

                    if self.stop_on_fail:
                        self.log_system("stop-on-fail active. Aborting pipeline.", is_err=True)
                        self.exit(1)
                        return

                    error_msg = f"Last output:\n{last}" if last else "No captured output."
                    action = await self.push_screen_wait(
                        ConflictModalScreen(task.script_name, shlex.join(cmd), code, error_msg)
                    )

                    match action:
                        case "retry":
                            self.log_system(f"Retrying task: {task.script_name}...")
                            self.update_task_node_by_key(task.state_key, TaskStatus.RUNNING)
                            success, code, last = await self._execute_task_cmd(task, cmd, env)

                        case "manual":
                            self.log_system(f"Manual intervention TTY: {task.script_name}...")
                            await self._execute_suspended(task, cmd, env)
                            self.update_task_node_by_key(task.state_key, TaskStatus.COMPLETED)
                            self.progress_bar.advance(1)
                            self._commit_task_state(task)
                            resolved = True

                        case "skip":
                            self.update_task_node_by_key(task.state_key, TaskStatus.SKIPPED)
                            self.progress_bar.advance(1)
                            self.log_system(f"Skipped task: {task.script_name}", is_err=True)
                            resolved = True

                        case _:
                            self.log_system("User aborted execution sequence.", is_err=True)
                            self.exit(1)
                            return

                if success and not resolved:
                    self.update_task_node_by_key(task.state_key, TaskStatus.COMPLETED)
                    self.progress_bar.advance(1)
                    self._commit_task_state(task)
                    self.log_system(f"Successfully completed: {task.script_name}")

                self.logger.close_task(task)

                if self.profile.post_script_delay > 0:
                    await asyncio.sleep(self.profile.post_script_delay)

                self.active_task = None

            self.status_label.update("✨ All orchestrator sequences completed successfully!")
            self.speed_label.update("Status: idle | ETA: 00:00")

            with suppress(Exception):
                self.query_one("#footer_status", Label).update("Engine: complete")

            self.log_system("Execution sequence finished. All system targets resolved.")
            AudioNotifier.play("complete")

        finally:
            self.active_task = None
            self._flush_ui()

            if self.sudo_task is not None:
                self.sudo_task.cancel()
                with suppress(asyncio.CancelledError):
                    await self.sudo_task


# ==============================================================================
# CLI
# ==============================================================================
def parse_command_line() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Dusky Arch Linux Orchestrator",
        epilog="Example: ./orchestrator.py --profile 01_main",
    )

    parser.add_argument("--profile", help="Execute specific profile (name, stem, or number)")
    parser.add_argument("--list", action="store_true", help="List all available profiles and exit")
    parser.add_argument("--list-scripts", action="store_true", help="List sequence of selected profile and exit")
    parser.add_argument("--reset", action="store_true", help="Reset state for selected profile and exit")
    parser.add_argument("--reset-and-run", action="store_true", help="Reset state for selected profile, then run")
    parser.add_argument("--dry-run", action="store_true", help="Validate everything but do not execute scripts")
    parser.add_argument("--force", action="store_true", help="Export DUSKY_FORCE=1 and pass --force to scripts")
    parser.add_argument("--manual", "-m", action="store_true", help="Prompt before executing every script")
    parser.add_argument("--stop-on-fail", action="store_true", help="Halt execution immediately if a script fails")
    parser.add_argument("--no-git-update", action="store_true", help="Skip git self-update")
    parser.add_argument("--git-update-only", action="store_true", help="Run git self-update and exit")
    parser.add_argument("--offline", action="store_true", help="Skip network-dependent git update")
    parser.add_argument("--sudo-password", help="Provide sudo password non-interactively")
    parser.add_argument("--sudo-password-file", help="Read sudo password from file")
    parser.add_argument("--task-timeout", type=float, default=0.0, help="Per-task timeout in seconds (0 disables)")
    parser.add_argument("--version", action="version", version="Dusky Orchestrator 17.0.0")

    return parser.parse_args()


def main() -> None:
    args = parse_command_line()
    profiles = discover_profiles()

    if not profiles:
        Console(stderr=True).print("[bold yellow]:: No profiles found in profiles/ directory.[/bold yellow]")
        sys.exit(1)

    if args.list:
        for i, p in enumerate(profiles, start=1):
            print(f"{i:2d}. {p.filepath.stem}: {p.name} ({p.description})")
        sys.exit(0)

    selected_profile: ProfileConfig | None = None

    if args.profile:
        if args.profile.isdigit():
            idx = int(args.profile) - 1
            if 0 <= idx < len(profiles):
                selected_profile = profiles[idx]
        else:
            for p in profiles:
                if p.name == args.profile or p.filepath.stem == args.profile:
                    selected_profile = p
                    break

        if selected_profile is None:
            Console(stderr=True).print(f"[bold red]Profile '{args.profile}' not found.[/bold red]")
            sys.exit(1)
    else:
        selector = ProfileSelectorApp(profiles)
        selector.run()
        selected_profile = selector.selected_profile
        if selected_profile is None:
            sys.exit(1)

    if args.reset or args.reset_and_run:
        sf = state_file_for(selected_profile)
        if sf.exists():
            try:
                sf.unlink()
                print(f"Reset state for {selected_profile.name} at {sf}")
            except Exception as e:
                sys.stderr.write(f"Failed to reset state {sf}: {e}\n")
        else:
            print(f"No state file found for {selected_profile.name}.")

        if args.reset and not args.reset_and_run:
            sys.exit(0)

    if args.list_scripts:
        print(f"Sequence for {selected_profile.name}:")
        for t in selected_profile.tasks:
            print(f"{t.index:3d}. [{t.mode}] {t.script_name} {shlex.join(t.args)}".rstrip())
        sys.exit(0)

    if not acquire_lock():
        sys.exit(1)

    if args.git_update_only:
        run_git_self_update(selected_profile, update_only=True, offline=args.offline)
        sys.exit(0)

    if not args.no_git_update and not args.offline:
        if run_git_self_update(selected_profile, update_only=False, offline=False):
            sys.exit(0)

    if not resolve_and_validate_manifest(selected_profile):
        Console(stderr=True).print("[bold red]Manifest validation failed.[/bold red]")
        sys.exit(1)

    if args.dry_run:
        completed = load_completed_keys(selected_profile)

        print("Dry-run validation complete.\n")
        for t in selected_profile.tasks:
            state = "completed" if t.state_key in completed else "pending"
            print(f"{t.index:02d}. [{t.mode}] {t.script_name}")
            print(f"    path:        {t.resolved_path}")
            print(f"    interpreter: {t.interpreter or 'direct'}")
            print(f"    args:        {shlex.join(t.args)}")
            print(f"    interactive: {t.interactive}")
            print(f"    state:       {state}")
            print()

        sys.exit(0)

    completed = load_completed_keys(selected_profile)
    has_sudo = any(t.mode == "S" and t.state_key not in completed for t in selected_profile.tasks)

    if has_sudo:
        password_file = Path(args.sudo_password_file).expanduser() if args.sudo_password_file else None
        if not SudoEngine.preflight(cli_password=args.sudo_password, password_file=password_file):
            sys.exit(1)

    try:
        DuskyOrchestratorApp.CSS = load_dusky_theme()

        app = DuskyOrchestratorApp(
            profile=selected_profile,
            has_sudo=has_sudo,
            manual=args.manual,
            stop_on_fail=args.stop_on_fail,
            force=args.force,
            task_timeout=max(0.0, args.task_timeout),
        )
        app.run()
    except KeyboardInterrupt:
        Console(stderr=True).print("\n[bold red]:: Interrupted by user.[/]")
        sys.exit(130)
    finally:
        SudoEngine.cleanup()


if __name__ == "__main__":
    main()
