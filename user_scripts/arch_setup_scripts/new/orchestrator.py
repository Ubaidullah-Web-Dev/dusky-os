#!/usr/bin/env python3
# dusky_interactive=true
# ==============================================================================
# DUSKY ARCH LINUX MASTER ORCHESTRATOR
# ==============================================================================
# Target: Arch Linux bleeding edge | Python 3.14+ | Textual 8.2.8+ | systemd 261+
# ==============================================================================
import sys

if sys.version_info < (3, 14):
    sys.stderr.write("[FATAL] Python 3.14+ is required.\n")
    sys.exit(1)

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
import re
import select
import shlex
import shutil
import signal
import sqlite3
import struct
import subprocess
import tempfile
import termios
import time
import tomllib
import uuid
from collections import deque
from contextlib import suppress, nullcontext
from dataclasses import dataclass, field
from enum import Enum
from importlib import metadata as importlib_metadata
from pathlib import Path

try:
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
except ImportError as exc:
    sys.stderr.write(f"[FATAL] Missing Python dependencies: {exc}\n")
    sys.stderr.write("Install: python-textual python-rich\n")
    sys.exit(8)

VERSION = "18.0.0"
SCRIPT_DIR: Path = Path(__file__).resolve().parent
PROFILES_DIR: Path = SCRIPT_DIR / "profiles"

ASCII_MODE = False
UNICODE_SYMBOLS = {
    "logo": "◈",
    "completed": "✔",
    "running": "●",
    "failed": "✘",
    "skipped": "○",
    "pending": "·",
    "sep": "│",
}
ASCII_SYMBOLS = {
    "logo": "DUSKY",
    "completed": "OK",
    "running": "RUN",
    "failed": "ERR",
    "skipped": "SKIP",
    "pending": "...",
    "sep": "|",
}


def S(key: str) -> str:
    return ASCII_SYMBOLS.get(key, key) if ASCII_MODE else UNICODE_SYMBOLS.get(key, key)


# ==============================================================================
# VERSION / RUNTIME GATES
# ==============================================================================
def version_tuple(value: str) -> tuple[int, ...]:
    parts: list[int] = []
    for part in re.split(r"[^0-9]+", value.strip()):
        if part:
            parts.append(int(part))
    return tuple(parts)


def check_runtime_versions() -> None:
    if sys.version_info < (3, 14):
        sys.stderr.write("[FATAL] Python 3.14+ is required.\n")
        sys.exit(1)

    try:
        textual_version = importlib_metadata.version("textual")
        parsed = (version_tuple(textual_version) + (0, 0, 0))[:3]
        if parsed < (8, 2, 8):
            sys.stderr.write(
                f"[FATAL] Textual 8.2.8+ is required. Installed: {textual_version}\n"
            )
            sys.exit(1)
    except Exception:
        # If metadata is unavailable but import worked, continue.
        pass


def ensure_not_root(allow_root: bool) -> None:
    if os.geteuid() != 0:
        return
    if allow_root:
        return
    if os.environ.get("SUDO_USER"):
        sys.stderr.write(
            "[FATAL] Run this orchestrator as your normal user, not via sudo.\n"
            "       If you truly intend to run as root, pass --allow-root.\n"
        )
    else:
        sys.stderr.write(
            "[FATAL] Running as root is not intended. Use --allow-root to force.\n"
        )
    sys.exit(13)


# ==============================================================================
# XDG / PATHS
# ==============================================================================
@functools.cache
def target_user_pw() -> pwd.struct_passwd:
    if os.geteuid() == 0:
        sudo_user = os.environ.get("SUDO_USER")
        if sudo_user and sudo_user != "root":
            with suppress(KeyError):
                return pwd.getpwnam(sudo_user)
        return pwd.getpwuid(0)
    return pwd.getpwuid(os.getuid())


def user_home() -> Path:
    return Path(target_user_pw().pw_dir)


def xdg_state_home() -> Path:
    default = user_home() / ".local" / "state"
    if os.geteuid() == 0 and target_user_pw().pw_uid != 0:
        return default
    env = os.environ.get("XDG_STATE_HOME")
    return Path(env).expanduser() if env else default


def xdg_data_home() -> Path:
    default = user_home() / ".local" / "share"
    if os.geteuid() == 0 and target_user_pw().pw_uid != 0:
        return default
    env = os.environ.get("XDG_DATA_HOME")
    return Path(env).expanduser() if env else default


def xdg_cache_home() -> Path:
    default = user_home() / ".cache"
    if os.geteuid() == 0 and target_user_pw().pw_uid != 0:
        return default
    env = os.environ.get("XDG_CACHE_HOME")
    return Path(env).expanduser() if env else default


def ensure_dir(path: Path, mode: int = 0o700) -> Path:
    path.mkdir(parents=True, exist_ok=True)
    with suppress(OSError):
        path.chmod(mode)
    return path


def safe_dir(primary: Path, fallback: Path, mode: int = 0o700) -> Path:
    try:
        return ensure_dir(primary, mode)
    except OSError:
        return ensure_dir(fallback, mode)


@functools.cache
def runtime_dir() -> Path:
    pw = target_user_pw()
    candidates: list[Path] = []

    if os.geteuid() == 0 and pw.pw_uid != 0:
        candidates.append(Path(f"/run/user/{pw.pw_uid}") / "dusky")
    else:
        env = os.environ.get("XDG_RUNTIME_DIR")
        if env:
            candidates.append(Path(env) / "dusky")
        candidates.append(Path(f"/run/user/{pw.pw_uid}") / "dusky")

    candidates.append(Path(tempfile.gettempdir()) / f"dusky-{pw.pw_uid}" / "run")

    for candidate in candidates:
        try:
            return ensure_dir(candidate, 0o700)
        except OSError:
            continue

    return ensure_dir(Path.cwd() / ".dusky-run", 0o700)


@functools.cache
def state_dir() -> Path:
    pw = target_user_pw()
    return safe_dir(
        xdg_state_home() / "dusky" / "state",
        Path(tempfile.gettempdir()) / f"dusky-{pw.pw_uid}" / "state",
    )


@functools.cache
def logs_dir() -> Path:
    pw = target_user_pw()
    return safe_dir(
        xdg_state_home() / "dusky" / "logs",
        Path(tempfile.gettempdir()) / f"dusky-{pw.pw_uid}" / "logs",
    )


@functools.cache
def backups_dir() -> Path:
    pw = target_user_pw()
    return safe_dir(
        xdg_data_home() / "dusky" / "backups",
        Path(tempfile.gettempdir()) / f"dusky-{pw.pw_uid}" / "backups",
    )


@functools.cache
def cache_dir() -> Path:
    pw = target_user_pw()
    return safe_dir(
        xdg_cache_home() / "dusky",
        Path(tempfile.gettempdir()) / f"dusky-{pw.pw_uid}" / "cache",
    )


@functools.cache
def askpass_dir() -> Path:
    return ensure_dir(cache_dir() / "askpass", 0o700)


def lock_path() -> Path:
    return runtime_dir() / "orchestrator.lock"


# ==============================================================================
# REGEX
# ==============================================================================
_INTERACTIVE_RE = re.compile(
    r"^\s*#\s*dusky_interactive\s*=\s*(?:true|1)\b",
    re.IGNORECASE,
)
_HEX_COLOR_RE = re.compile(r"^#(?:[0-9a-fA-F]{3,4}|[0-9a-fA-F]{6}|[0-9a-fA-F]{8})$")
ANSI_STRIP_REGEX = re.compile(
    r"\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~]|\][^\x07\x1b]*(?:\x07|\x1B\\))"
)
PCT_REGEX = re.compile(r"(?<!\d)(?:100(?:\.0+)?|\d{1,2}(?:\.\d+)?)%")
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
class TaskStatus(str, Enum):
    PENDING = "pending"
    COMPLETED = "completed"
    RUNNING = "running"
    FAILED = "failed"
    SKIPPED = "skipped"


@dataclass(slots=True, kw_only=True)
class OrchestratorTask:
    raw_entry: str
    mode: str
    script_name: str
    args: list[str] = field(default_factory=list)
    ignore_fail: bool = False
    interactive: bool = False
    force_flag: bool = False
    condition: str | None = None
    timeout: float | None = None
    index: int = 0
    resolved_path: Path | None = None
    interpreter: str = "bash"
    checksum: str = ""
    state_key: str = ""
    status: TaskStatus = TaskStatus.PENDING
    error_msg: str | None = None
    duration: float = 0.0


@dataclass(slots=True, kw_only=True)
class ProfileConfig:
    filepath: Path
    name: str
    description: str = ""
    post_script_delay: int = 0
    git_enabled: bool = False
    git_dir: str = "~/dusky"
    git_work_tree: str = "~/"
    git_remote: str = "origin"
    search_dirs: list[str] = field(default_factory=list)
    conflict_resolutions: dict[str, str] = field(default_factory=dict)
    tasks: list[OrchestratorTask] = field(default_factory=list)
    policy: dict = field(default_factory=dict)


# ==============================================================================
# UTILITIES
# ==============================================================================
def resolve_home(path_str: str) -> Path:
    p = Path(os.path.expandvars(path_str.strip())).expanduser()
    if not p.is_absolute():
        p = SCRIPT_DIR / p
    return p


def safe_filename(name: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9._-]", "_", str(name)).strip("._")
    return cleaned or "unnamed"


def now_iso() -> str:
    return datetime.datetime.now(datetime.UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def now_ts() -> str:
    return datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def file_checksum(path: Path) -> str:
    try:
        h = hashlib.blake2b(digest_size=16)
        with open(path, "rb") as f:
            for chunk in iter(lambda: f.read(1 << 20), b""):
                h.update(chunk)
        return h.hexdigest()
    except OSError:
        return ""


# ==============================================================================
# STATE STORE
# ==============================================================================
class StateStore:
    DONE = {
        "completed",
        "skipped",
        "skipped_condition",
        "ignored",
        "manual",
    }

    def __init__(self, profile: ProfileConfig):
        self.path = state_dir() / f"{safe_filename(profile.name)}.db"
        self.conn = sqlite3.connect(self.path)
        self.conn.execute(
            """
            CREATE TABLE IF NOT EXISTS state (
                state_key TEXT PRIMARY KEY,
                status TEXT NOT NULL,
                script TEXT,
                checksum TEXT,
                exit_code INTEGER,
                note TEXT,
                updated TEXT
            )
            """
        )
        self.conn.commit()

    def statuses(self) -> dict[str, str]:
        cur = self.conn.execute("SELECT state_key, status FROM state")
        return {str(k): str(v) for k, v in cur.fetchall()}

    @classmethod
    def is_done(cls, status: str | None) -> bool:
        return bool(status) and status in cls.DONE

    def mark(
        self,
        task: OrchestratorTask,
        status: str,
        exit_code: int | None = None,
        note: str = "",
    ) -> None:
        self.conn.execute(
            """
            INSERT OR REPLACE INTO state
                (state_key, status, script, checksum, exit_code, note, updated)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                task.state_key,
                status,
                task.script_name,
                task.checksum,
                exit_code,
                note,
                now_iso(),
            ),
        )
        self.conn.commit()

    def reset(self) -> None:
        with suppress(Exception):
            self.conn.close()
        self.path.unlink(missing_ok=True)

    def close(self) -> None:
        with suppress(Exception):
            self.conn.close()


def reset_state_for_profile(profile: ProfileConfig) -> None:
    path = state_dir() / f"{safe_filename(profile.name)}.db"
    path.unlink(missing_ok=True)
    print(f"Reset state for {profile.name} at {path}")


# ==============================================================================
# LOGGER
# ==============================================================================
class RunLogger:
    def __init__(self, profile: ProfileConfig, run_id: str):
        self.enabled = False
        self.root: Path | None = None
        self.main_path: Path | None = None
        self._main = None
        self._task_files: dict[str, object] = {}
        self._task_counts: dict[str, int] = {}
        self.run_id = run_id

        try:
            stamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
            self.root = logs_dir() / f"{stamp}_{safe_filename(profile.name)}_{run_id}"
            ensure_dir(self.root, 0o700)
            self.main_path = self.root / "orchestrator.log"
            self._main = open(self.main_path, "a", encoding="utf-8", errors="replace")
            self.enabled = True
            self.system(f"Logging started for profile: {profile.name}")
            self.system(f"Run ID: {run_id}")
        except OSError:
            self.enabled = False

    def system(self, msg: str) -> None:
        if not self.enabled or self._main is None:
            return
        with suppress(OSError):
            self._main.write(f"[{now_ts()}] {msg}\n")
            self._main.flush()

    def task_log_path(self, task: OrchestratorTask) -> Path:
        if self.root is None:
            return Path("/dev/null")
        return self.root / f"{task.index:03d}_{safe_filename(task.script_name)}.log"

    def open_task(self, task: OrchestratorTask, cmd: list[str]) -> None:
        if not self.enabled:
            return
        if task.state_key in self._task_files:
            self.write_task(task, f"[{now_ts()}] RETRY")
            return

        with suppress(OSError):
            f = open(self.task_log_path(task), "a", encoding="utf-8", errors="replace")
            f.write(f"[{now_ts()}] TASK START: {task.script_name}\n")
            f.write(f"[{now_ts()}] MODE: {task.mode}\n")
            f.write(f"[{now_ts()}] PATH: {task.resolved_path}\n")
            f.write(f"[{now_ts()}] INTERPRETER: {task.interpreter or 'direct'}\n")
            f.write(f"[{now_ts()}] ARGS: {shlex.join(task.args)}\n")
            f.write(f"[{now_ts()}] COMMAND: {shlex.join(cmd)}\n")
            f.write(f"[{now_ts()}] CONDITION: {task.condition or 'always'}\n")
            f.flush()
            self._task_files[task.state_key] = f
            self._task_counts[task.state_key] = 0

    def write_task(self, task: OrchestratorTask, line: str) -> None:
        if not self.enabled:
            return
        f = self._task_files.get(task.state_key)
        if f is None:
            return
        with suppress(OSError):
            f.write(line + "\n")
            count = self._task_counts.get(task.state_key, 0) + 1
            self._task_counts[task.state_key] = count
            if count % 25 == 0:
                f.flush()

    def close_task(
        self,
        task: OrchestratorTask,
        status: str = "",
        exit_code: int | None = None,
        duration: float = 0.0,
    ) -> None:
        if not self.enabled:
            return
        f = self._task_files.pop(task.state_key, None)
        if f is None:
            return
        with suppress(OSError):
            f.write(f"\n[{now_ts()}] TASK END: {task.script_name}\n")
            f.write(f"[{now_ts()}] STATUS: {status}\n")
            f.write(f"[{now_ts()}] EXIT CODE: {exit_code}\n")
            f.write(f"[{now_ts()}] DURATION: {duration:.2f}s\n")
            f.flush()
            f.close()

    def write_report(
        self,
        profile: ProfileConfig,
        tasks: list[OrchestratorTask],
        statuses: dict[str, str],
        counters: dict[str, int],
    ) -> None:
        if not self.enabled or self.root is None:
            return

        report = {
            "run_id": self.run_id,
            "generated": now_iso(),
            "profile": profile.name,
            "profile_file": str(profile.filepath),
            "version": VERSION,
            "python": sys.version,
            "user": target_user_pw().pw_name,
            "uid": target_user_pw().pw_uid,
            "home": str(user_home()),
            "counters": counters,
            "tasks": [],
        }

        lines = [
            "# Dusky Orchestrator Report",
            "",
            f"- Run ID: `{self.run_id}`",
            f"- Generated: `{now_iso()}`",
            f"- Profile: `{profile.name}`",
            f"- Version: `{VERSION}`",
            "",
            "## Tasks",
            "",
        ]

        for task in tasks:
            status = statuses.get(task.state_key, "pending")
            item = {
                "index": task.index,
                "script": task.script_name,
                "mode": task.mode,
                "status": status,
                "path": str(task.resolved_path),
                "args": task.args,
                "condition": task.condition,
                "duration": task.duration,
                "checksum": task.checksum,
            }
            report["tasks"].append(item)
            lines.append(
                f"{task.index:03d}. [{task.mode}] {task.script_name} -> {status} ({task.duration:.2f}s)"
            )

        with suppress(OSError):
            (self.root / "report.json").write_text(
                json.dumps(report, indent=2, default=str),
                encoding="utf-8",
            )
            (self.root / "report.md").write_text("\n".join(lines) + "\n", encoding="utf-8")

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
# NOTIFIERS / INHIBITOR
# ==============================================================================
class AudioNotifier:
    enabled = True

    @classmethod
    @functools.cache
    def _get_player(cls) -> str | None:
        for bin_name in ("pw-play", "paplay"):
            if p := shutil.which(bin_name):
                return p
        return None

    @classmethod
    def play(cls, sound_type: str = "alert") -> None:
        if not cls.enabled:
            return

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


class DesktopNotifier:
    enabled = True

    @classmethod
    def notify(cls, title: str, body: str, urgency: str = "normal") -> None:
        if not cls.enabled:
            return
        if not shutil.which("notify-send"):
            return
        with suppress(OSError):
            subprocess.Popen(
                ["notify-send", "--app-name=Dusky Orchestrator", f"--urgency={urgency}", title, body],
                start_new_session=True,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                close_fds=True,
            )


class SleepInhibitor:
    def __init__(self, enabled: bool = True):
        self.proc = None
        if not enabled:
            return
        if not shutil.which("systemd-inhibit") or not shutil.which("sleep"):
            return
        with suppress(OSError):
            self.proc = subprocess.Popen(
                [
                    "systemd-inhibit",
                    "--what=idle:sleep",
                    "--who=Dusky Orchestrator",
                    "--why=System setup running",
                    "--mode=block",
                    "sleep",
                    "infinity",
                ],
                start_new_session=True,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                close_fds=True,
            )

    def close(self) -> None:
        if self.proc is None:
            return
        with suppress(Exception):
            self.proc.terminate()
            self.proc.wait(timeout=3)
        with suppress(Exception):
            self.proc.kill()
        self.proc = None


# ==============================================================================
# LOCK
# ==============================================================================
_LOCK_FD: int | None = None


def get_lock_holders() -> str:
    lp = lock_path()
    if not lp.exists():
        return ""

    try:
        real_lock = lp.resolve()
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
            lock_path().unlink(missing_ok=True)
    except OSError:
        pass


def acquire_lock() -> bool:
    global _LOCK_FD

    lp = lock_path()
    with suppress(OSError):
        ensure_dir(lp.parent, 0o700)

    try:
        fd = os.open(str(lp), os.O_CREAT | os.O_RDWR | os.O_CLOEXEC, 0o600)
    except Exception as e:
        sys.stderr.write(f"[ERROR] Could not open lock file {lp}: {e}\n")
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
    _sudoers_path: Path | None = None
    _mode: str = "none"  # none | root | nopasswd | password

    ENV_KEEP = [
        "HOME",
        "USER",
        "LOGNAME",
        "SHELL",
        "PATH",
        "TERM",
        "COLORTERM",
        "LANG",
        "LC_ALL",
        "LC_CTYPE",
        "TZ",
        "XDG_RUNTIME_DIR",
        "XDG_CONFIG_HOME",
        "XDG_CACHE_HOME",
        "XDG_STATE_HOME",
        "XDG_DATA_HOME",
        "XDG_SESSION_TYPE",
        "XDG_CURRENT_DESKTOP",
        "DBUS_SESSION_BUS_ADDRESS",
        "DISPLAY",
        "WAYLAND_DISPLAY",
        "XAUTHORITY",
        "SSH_AUTH_SOCK",
        "SSH_AGENT_PID",
        "SUDO_ASKPASS",
        "PYTHONUNBUFFERED",
        "PYTHONUTF8",
        "PYTHONDONTWRITEBYTECODE",
        "PAGER",
        "SYSTEMD_PAGER",
        "GIT_PAGER",
        "EDITOR",
        "VISUAL",
        "QT_QPA_PLATFORMTHEME",
        "GTK_THEME",
        "XCURSOR_THEME",
        "XCURSOR_SIZE",
        "MOZ_ENABLE_WAYLAND",
        "LIBVA_DRIVER_NAME",
        "VDPAU_DRIVER",
        "SDL_VIDEODRIVER",
        "ZDOTDIR",
    ]

    @classmethod
    def mode_name(cls) -> str:
        return cls._mode

    @classmethod
    def _remove_stale_askpass_files(cls) -> None:
        with suppress(OSError):
            for p in askpass_dir().glob(".dusky_askpass_*"):
                with suppress(OSError):
                    p.unlink(missing_ok=True)

    @classmethod
    def cleanup(cls) -> None:
        if cls._sudoers_path is not None:
            env = os.environ.copy()
            if cls._askpass_path is not None:
                env["SUDO_ASKPASS"] = str(cls._askpass_path)

            for cmd in (
                ["sudo", "-n", "rm", "-f", str(cls._sudoers_path)],
                ["sudo", "-A", "rm", "-f", str(cls._sudoers_path)],
            ):
                try:
                    res = subprocess.run(
                        cmd,
                        env=env,
                        stdin=subprocess.DEVNULL,
                        stdout=subprocess.DEVNULL,
                        stderr=subprocess.DEVNULL,
                        timeout=5,
                    )
                    if res.returncode == 0:
                        break
                except Exception:
                    pass

        if cls._askpass_path is not None:
            with suppress(OSError):
                cls._askpass_path.unlink(missing_ok=True)

        cls._askpass_path = None
        cls._sudoers_path = None

    @classmethod
    def _write_askpass(cls, password: str) -> Path:
        ensure_dir(askpass_dir(), 0o700)
        encoded = base64.b64encode(password.encode("utf-8")).decode("ascii")
        interpreter = sys.executable or shutil.which("python3") or "/usr/bin/env python3"

        script = (
            f"#!{interpreter}\n"
            "import base64, sys\n"
            f"sys.stdout.write(base64.b64decode('{encoded}').decode('utf-8'))\n"
            "sys.stdout.write('\\n')\n"
        )

        fd, path = tempfile.mkstemp(prefix=".dusky_askpass_", dir=str(askpass_dir()))
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(script)
        os.chmod(path, 0o700)
        return Path(path)

    @classmethod
    def _remove_stale_sudoers_files(cls, env: dict[str, str]) -> None:
        script = r"""
for f in /etc/sudoers.d/99_dusky_*; do
    [ -f "$f" ] || continue
    pid=$(sed -n 's/^# pid=//p' "$f" | head -n1)
    if [ -n "$pid" ] && ! kill -0 "$pid" 2>/dev/null; then
        rm -f "$f"
    fi
done
"""
        with suppress(Exception):
            subprocess.run(
                ["sudo", "-A", "sh"],
                input=script,
                text=True,
                env=env,
                stdin=subprocess.PIPE,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                timeout=10,
            )

    @classmethod
    def _write_sudoers_dropin(cls, env: dict[str, str]) -> None:
        username = target_user_pw().pw_name
        safe_user = re.sub(r"[^A-Za-z0-9._-]", "_", username)
        path = Path(f"/etc/sudoers.d/99_dusky_{safe_user}_{os.getpid()}")
        env_vars = " ".join(cls.ENV_KEEP)

        content = (
            f"# pid={os.getpid()} ts={int(time.time())}\n"
            f"Defaults:{username} timestamp_type=global\n"
            f"Defaults:{username} env_keep += \"{env_vars} DUSKY_*\"\n"
        )

        shell_cmd = (
            "mkdir -p /etc/sudoers.d && "
            f"umask 077 && cat > {shlex.quote(str(path))} && "
            f"chmod 0440 {shlex.quote(str(path))}"
        )

        try:
            proc = subprocess.run(
                ["sudo", "-A", "sh", "-c", shell_cmd],
                input=content,
                text=True,
                env=env,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.PIPE,
                timeout=10,
            )
            if proc.returncode != 0:
                return

            check = subprocess.run(
                ["sudo", "-A", "visudo", "-c", "-f", str(path)],
                env=env,
                stdin=subprocess.DEVNULL,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                timeout=10,
            )
            if check.returncode == 0:
                cls._sudoers_path = path
            else:
                with suppress(Exception):
                    subprocess.run(
                        ["sudo", "-A", "rm", "-f", str(path)],
                        env=env,
                        stdin=subprocess.DEVNULL,
                        stdout=subprocess.DEVNULL,
                        stderr=subprocess.DEVNULL,
                        timeout=5,
                    )
        except Exception:
            return

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

            cls._remove_stale_sudoers_files(env)
            cls._write_sudoers_dropin(env)
            return True, ""

        err = (proc.stderr or "").strip()
        with suppress(OSError):
            askpass.unlink(missing_ok=True)
        return False, err or "sudo authentication failed"

    @classmethod
    def detect_nopasswd(cls) -> bool:
        if os.geteuid() == 0:
            cls._mode = "root"
            return True

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
                cls._sudoers_path = None
                cls._mode = "nopasswd"
                return True

        return False

    @classmethod
    def refresh_sync(cls) -> bool:
        if os.geteuid() == 0:
            cls._mode = "root"
            return True

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
        if cls._mode == "root":
            return []
        if cls._mode == "nopasswd":
            return ["sudo", "-n", "--"]
        if cls._mode == "password" and cls._askpass_path is not None:
            return ["sudo", "-A", "--"]
        return ["sudo", "--"]

    @classmethod
    def preflight(
        cls,
        cli_password: str | None = None,
        password_file: Path | None = None,
    ) -> bool:
        if os.geteuid() == 0:
            cls._mode = "root"
            sys.stdout.write("[DUSKY PRE-FLIGHT] Running as root. No sudo escalation needed.\n")
            return True

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
                text = password_file.read_text(encoding="utf-8", errors="ignore")
                if text:
                    password = text.splitlines()[0].rstrip("\r\n")

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
    base_dir = user_home()
    generated = base_dir / ".config/matugen/generated/dusky_tui.json"
    if generated.exists():
        return generated

    generated_fresh = base_dir / ".config/matugen/generated_fresh/dusky_tui.json"
    if generated_fresh.exists():
        return generated_fresh

    return generated


def _color_value(value: object) -> str | None:
    if isinstance(value, str):
        return value.strip()
    if isinstance(value, dict):
        for key in ("hex", "color", "value", "rgb"):
            v = value.get(key)
            if isinstance(v, str):
                return v.strip()
    return None


def _pick_color(data: dict, names: list[str], fallback: str) -> str:
    for name in names:
        if name in data:
            c = _color_value(data[name])
            if c and _HEX_COLOR_RE.match(c):
                return c
    return fallback


def load_palette() -> dict[str, str]:
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
        return default_palette

    try:
        raw = json.loads(theme_file.read_text(encoding="utf-8"))
    except Exception:
        return default_palette

    candidates: list[dict] = []
    if isinstance(raw, dict):
        candidates.append(raw)
        for key in ("dark", "light", "colors", "palette", "tones", "theme"):
            value = raw.get(key)
            if isinstance(value, dict):
                candidates.append(value)

    merged: dict = {}
    for candidate in reversed(candidates):
        merged.update(candidate)

    if not merged:
        return default_palette

    return {
        "bg": _pick_color(merged, ["bg", "background", "base", "surface"], default_palette["bg"]),
        "fg": _pick_color(merged, ["fg", "foreground", "text", "on_surface"], default_palette["fg"]),
        "accent": _pick_color(merged, ["accent", "primary", "secondary"], default_palette["accent"]),
        "warning": _pick_color(merged, ["warning", "warn", "tertiary"], default_palette["warning"]),
        "success": _pick_color(merged, ["success", "green"], default_palette["success"]),
        "muted": _pick_color(merged, ["muted", "outline", "surface_variant"], default_palette["muted"]),
        "error": _pick_color(merged, ["error", "danger", "red"], default_palette["error"]),
    }


def build_app_css(p: dict[str, str]) -> str:
    return f"""
Screen {{
    background: {p['bg']};
    color: {p['fg']};
}}

#top_header {{
    height: 1;
    dock: top;
    background: {p['bg']};
    color: {p['accent']};
    text-style: bold;
    padding: 0 1;
}}

#main_dashboard {{
    layout: horizontal;
    height: 1fr;
}}

#left_pane {{
    width: 38%;
    border-right: solid {p['muted']};
    background: {p['bg']};
    padding: 0 1;
    height: 100%;
}}

#right_pane {{
    width: 62%;
    height: 100%;
    layout: vertical;
    background: {p['bg']};
}}

#telemetry_box {{
    height: 5;
    border-bottom: solid {p['muted']};
    padding: 0 1;
    layout: vertical;
}}

#status_label {{
    text-style: bold;
    color: {p['accent']};
}}

#speed_label {{
    color: {p['warning']};
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
    background: {p['bg']};
    color: {p['fg']};
    scrollbar-size: 1 1;
}}

Tree {{
    background: {p['bg']};
    color: {p['fg']};
}}

#footer {{
    height: 1;
    dock: bottom;
    background: {p['bg']};
    layout: horizontal;
    padding: 0 1;
}}

.footer-shortcut {{
    padding: 0 1;
    color: {p['accent']};
}}

.footer-sep {{
    color: {p['muted']};
}}

#footer_status {{
    color: {p['success']};
    text-style: italic;
}}

TaskSearchScreen, ConflictModalScreen, ManualModalScreen, SudoPasswordScreen, ConfirmQuitScreen, HelpScreen {{
    align: center middle;
    background: rgba(0,0,0,0.72);
}}

#search_dialog {{
    width: 78;
    height: 75%;
    background: {p['bg']};
    border: solid {p['accent']};
    padding: 1 2;
}}

#search_list {{
    height: 1fr;
    border: none;
    background: {p['bg']};
    color: {p['fg']};
}}

#modal_dialog, #manual_dialog, #sudo_dialog, #confirm_dialog, #help_dialog {{
    width: 82;
    height: auto;
    background: {p['bg']};
    padding: 1 2;
}}

#modal_dialog {{
    border: heavy {p['error']};
}}

#manual_dialog {{
    border: heavy {p['accent']};
}}

#sudo_dialog {{
    border: heavy {p['warning']};
}}

#confirm_dialog {{
    border: heavy {p['warning']};
}}

#help_dialog {{
    border: heavy {p['accent']};
    height: 70%;
}}

#modal_title {{
    text-align: center;
    text-style: bold;
    color: {p['error']};
    margin-bottom: 1;
}}

#manual_title {{
    text-align: center;
    text-style: bold;
    color: {p['accent']};
    margin-bottom: 1;
}}

#sudo_title {{
    text-align: center;
    text-style: bold;
    color: {p['warning']};
    margin-bottom: 1;
}}

#confirm_title {{
    text-align: center;
    text-style: bold;
    color: {p['warning']};
    margin-bottom: 1;
}}

#help_title {{
    text-align: center;
    text-style: bold;
    color: {p['accent']};
    margin-bottom: 1;
}}

#error_details {{
    color: {p['warning']};
    margin-bottom: 1;
    max-height: 16;
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
    background: {p['bg']};
    border: tall {p['accent']};
    color: {p['fg']};
}}
"""


def build_selector_css(p: dict[str, str]) -> str:
    return f"""
Screen {{
    align: center middle;
    background: {p['bg']};
    color: {p['fg']};
}}

#selector_container {{
    width: 92;
    height: auto;
    border: heavy {p['accent']};
    background: {p['bg']};
    padding: 1 2;
}}

#title {{
    text-align: center;
    text-style: bold;
    color: {p['accent']};
    margin-bottom: 1;
}}

OptionList {{
    height: auto;
    border: none;
    background: {p['bg']};
    color: {p['fg']};
}}

.help_text {{
    text-align: center;
    color: {p['warning']};
    text-style: italic;
    margin-top: 1;
}}
"""


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
    condition: str | None = None
    timeout: float | None = None

    for flag in flags.split(","):
        f = flag.strip().lower()
        if not f:
            continue

        if f in ("true", "ignore", "ignore-fail"):
            ignore_fail = True
        elif f in ("interactive", "tui", "prompt"):
            interactive = True
        elif f in ("force", "--force"):
            force_flag = True
        elif f.startswith("if:"):
            condition = flag.strip()[3:]
        elif f.startswith("timeout:"):
            with suppress(ValueError):
                timeout = float(flag.strip()[8:])

    cmd_tokens = shlex.split(cmd.strip())
    if not cmd_tokens:
        raise ValueError(f"Empty command in entry: {raw_entry}")

    if cmd_tokens[0] == "true" and len(cmd_tokens) > 1:
        ignore_fail = True
        cmd_tokens = cmd_tokens[1:]

    if "--force" in cmd_tokens:
        force_flag = True

    return OrchestratorTask(
        raw_entry=raw,
        mode=mode.strip().upper(),
        script_name=cmd_tokens[0],
        args=cmd_tokens[1:],
        ignore_fail=ignore_fail,
        interactive=interactive,
        force_flag=force_flag,
        condition=condition,
        timeout=timeout,
        index=index,
    )


def parse_task_table(table: dict, index: int) -> OrchestratorTask:
    cmd = str(table.get("cmd") or table.get("script") or table.get("path") or "").strip()
    if not cmd:
        raise ValueError(f"Task table at index {index} missing cmd/script/path")

    args_raw = table.get("args", [])
    if isinstance(args_raw, str):
        args = shlex.split(args_raw)
    elif isinstance(args_raw, list):
        args = [str(x) for x in args_raw]
    else:
        args = []

    flags = str(table.get("flags", ""))
    ignore_fail = bool(table.get("ignore_fail", False))
    interactive = bool(table.get("interactive", False))
    force_flag = bool(table.get("force", False))
    condition = table.get("condition")
    timeout = table.get("timeout")

    for flag in flags.split(","):
        f = flag.strip().lower()
        if not f:
            continue
        if f in ("true", "ignore", "ignore-fail"):
            ignore_fail = True
        elif f in ("interactive", "tui", "prompt"):
            interactive = True
        elif f in ("force", "--force"):
            force_flag = True
        elif f.startswith("if:"):
            condition = flag.strip()[3:]
        elif f.startswith("timeout:"):
            with suppress(ValueError):
                timeout = float(flag.strip()[8:])

    if "--force" in args:
        force_flag = True

    try:
        timeout_value = float(timeout) if timeout is not None else None
    except Exception:
        timeout_value = None

    return OrchestratorTask(
        raw_entry=json.dumps(table, default=str),
        mode=str(table.get("mode", "U")).strip().upper(),
        script_name=cmd,
        args=args,
        ignore_fail=ignore_fail,
        interactive=interactive,
        force_flag=force_flag,
        condition=str(condition).strip() if condition else None,
        timeout=timeout_value,
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
    policy_data = data.get("policy", {})

    tasks: list[OrchestratorTask] = []

    for i, line in enumerate(seq_data.get("scripts", []), start=1):
        line = str(line).strip()
        if not line or line.startswith("#"):
            continue
        tasks.append(parse_task_entry(line, i))

    offset = len(tasks) + 1
    for i, table in enumerate(seq_data.get("tasks", []), start=offset):
        if isinstance(table, dict):
            tasks.append(parse_task_table(table, i))

    try:
        post_delay = int(p_data.get("post_script_delay", 0))
    except Exception:
        post_delay = 0

    search_dirs: list[str] = []
    seen: set[str] = set()
    for d in s_data.get("dirs", []):
        resolved = str(resolve_home(str(d)))
        if resolved not in seen:
            seen.add(resolved)
            search_dirs.append(resolved)

    policy = policy_data if isinstance(policy_data, dict) else {}

    return ProfileConfig(
        filepath=filepath,
        name=str(p_data.get("name", filepath.stem)).strip(),
        description=str(p_data.get("description", "")).strip(),
        post_script_delay=max(0, post_delay),
        git_enabled=bool(g_data.get("enabled", False)),
        git_dir=str(g_data.get("git_dir", "~/dusky")).strip(),
        git_work_tree=str(g_data.get("work_tree", "~/")).strip(),
        git_remote=str(g_data.get("remote", "origin")).strip(),
        search_dirs=search_dirs,
        conflict_resolutions={
            str(k).strip(): str(v).strip()
            for k, v in c_data.items()
            if str(k).strip() and str(v).strip()
        },
        tasks=tasks,
        policy=policy,
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


# ==============================================================================
# SCRIPT DISCOVERY
# ==============================================================================
def _script_metadata(path: Path) -> tuple[bool, str, str]:
    try:
        with open(path, "rb") as f:
            data = f.read(16384)
    except OSError:
        return False, "", ""

    head = data[:4]
    text = data.decode("utf-8", errors="ignore")
    if text.startswith("\ufeff"):
        text = text.lstrip("\ufeff")

    first_line = text.splitlines()[0].strip() if text else ""
    return head == b"\x7fELF", first_line, text


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

        if "/" in task.script_name:
            cand = resolve_home(task.script_name)
            if cand.is_file():
                task.resolved_path = cand
        elif task.script_name in profile.conflict_resolutions:
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
                if task.script_name in profile.conflict_resolutions:
                    cand = resolve_home(profile.conflict_resolutions[task.script_name])
                    if cand.is_file():
                        task.resolved_path = cand
                    else:
                        sys.stderr.write(f"[CONFLICT] Resolution for {task.script_name} is invalid: {cand}\n")
                        success = False
                else:
                    sys.stderr.write(f"[CONFLICT] Multiple versions of {task.script_name} found:\n")
                    for m in matches:
                        sys.stderr.write(f"  - {m}\n")
                    success = False

        if task.resolved_path is None:
            sys.stderr.write(f"[MISSING] Could not find {task.script_name} in search dirs.\n")
            success = False
            task.checksum = ""
        else:
            task.checksum = file_checksum(task.resolved_path)

        key_material = f"{task.mode}|{task.script_name}|{args_key}|{occ}|{task.checksum}".encode("utf-8")
        task.state_key = hashlib.blake2b(key_material, digest_size=16).hexdigest()

        if task.resolved_path is None:
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
        elif shebang_interp:
            if executable and shebang_interp in ("bash", "sh", "zsh", "dash", "fish", "python"):
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
# CONDITIONS
# ==============================================================================
class ConditionEvaluator:
    def __init__(self):
        self.cache: dict[str, bool] = {}

    def check(self, condition: str | None) -> bool:
        if not condition:
            return True

        cond = condition.strip()
        if cond.lower() in ("always", "true", "yes"):
            return True
        if cond.lower() in ("never", "false", "no"):
            return False

        if cond in self.cache:
            return self.cache[cond]

        result = self._eval(cond)
        self.cache[cond] = result
        return result

    def _eval(self, cond: str) -> bool:
        kind, _, value = cond.partition(":")
        kind = kind.strip().lower()
        value = value.strip()

        if kind == "not":
            return not self.check(value)

        if kind == "wayland":
            return bool(os.environ.get("WAYLAND_DISPLAY"))

        if kind == "x11":
            return bool(os.environ.get("DISPLAY"))

        if kind == "graphical":
            return bool(os.environ.get("WAYLAND_DISPLAY") or os.environ.get("DISPLAY"))

        if kind == "ssh":
            return bool(os.environ.get("SSH_CONNECTION") or os.environ.get("SSH_TTY"))

        if kind == "desktop":
            session = os.environ.get("XDG_SESSION_TYPE", "").lower()
            if session in ("wayland", "x11", "mir"):
                return True
            return self.check("graphical") and not self.check("ssh")

        if kind == "battery":
            return self._has_battery()

        if kind == "btrfs":
            return self._root_is_btrfs()

        if kind == "vm":
            return self._is_vm()

        if kind == "baremetal":
            return not self._is_vm()

        if kind == "command":
            return bool(shutil.which(value))

        if kind == "path":
            return Path(value).expanduser().exists()

        if kind == "missing":
            return not Path(value).expanduser().exists()

        if kind == "file":
            return Path(value).expanduser().is_file()

        if kind == "dir":
            return Path(value).expanduser().is_dir()

        if kind == "package":
            return self._package_installed(value)

        if kind == "group":
            return self._user_in_group(value)

        if kind == "gpu":
            return self._gpu(value.lower())

        if kind == "service_active":
            return self._run(["systemctl", "is-active", "--quiet", value])

        if kind == "user_service_active":
            return self._run(["systemctl", "--user", "is-active", "--quiet", value])

        if kind == "env":
            return bool(os.environ.get(value))

        return False

    def _run(self, cmd: list[str]) -> bool:
        with suppress(Exception):
            return subprocess.run(
                cmd,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                timeout=5,
            ).returncode == 0
        return False

    def _output(self, cmd: list[str]) -> str:
        with suppress(Exception):
            proc = subprocess.run(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.DEVNULL,
                text=True,
                timeout=5,
            )
            if proc.returncode == 0:
                return proc.stdout.strip()
        return ""

    def _has_battery(self) -> bool:
        base = Path("/sys/class/power_supply")
        if not base.exists():
            return False
        with suppress(OSError):
            for entry in base.iterdir():
                type_file = entry / "type"
                if type_file.exists():
                    if type_file.read_text(errors="ignore").strip() == "Battery":
                        return True
        return False

    def _root_is_btrfs(self) -> bool:
        with suppress(OSError):
            for line in Path("/proc/mounts").read_text(errors="ignore").splitlines():
                parts = line.split()
                if len(parts) >= 3 and parts[1] == "/" and parts[2] == "btrfs":
                    return True
        return False

    def _is_vm(self) -> bool:
        if shutil.which("systemd-detect-virt"):
            with suppress(Exception):
                proc = subprocess.run(
                    ["systemd-detect-virt", "--vm", "--quiet"],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    timeout=5,
                )
                return proc.returncode == 0

        dmi = Path("/sys/class/dmi/id/sys_vendor")
        if dmi.exists():
            with suppress(OSError):
                vendor = dmi.read_text(errors="ignore").lower()
                return any(x in vendor for x in ("qemu", "kvm", "vmware", "virtualbox", "bochs"))

        return False

    def _package_installed(self, name: str) -> bool:
        if not shutil.which("pacman"):
            return False
        return self._run(["pacman", "-Qq", name])

    def _user_in_group(self, group: str) -> bool:
        user = target_user_pw().pw_name
        groups = self._output(["id", "-nG", user])
        return group in groups.split()

    def _gpu(self, kind: str) -> bool:
        if kind == "nvidia":
            return Path("/sys/module/nvidia").exists() or self._lspci_contains("nvidia")
        if kind == "intel":
            return (
                Path("/sys/module/i915").exists()
                or Path("/sys/module/xe").exists()
                or self._lspci_contains("intel")
            )
        if kind == "amd":
            return Path("/sys/module/amdgpu").exists() or self._lspci_contains("amd")
        return False

    def _lspci_contains(self, needle: str) -> bool:
        if not shutil.which("lspci"):
            return False
        out = self._output(["lspci"])
        return needle.lower() in out.lower()


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
            "GIT_OPTIONAL_LOCKS": "0",
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

    entries = sorted(
        [p for p in base.iterdir() if p.is_dir() and p.name.startswith("dusky_backup_")],
        reverse=True,
    )
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


def validate_updated_sources(my_path: Path, wrapper_path: Path) -> None:
    compile(my_path.read_bytes(), str(my_path), "exec")

    if wrapper_path.exists():
        subprocess.run(
            ["bash", "-n", str(wrapper_path)],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            timeout=30,
            check=True,
        )

    if PROFILES_DIR.exists():
        for profile_file in PROFILES_DIR.glob("*.toml"):
            with open(profile_file, "rb") as f:
                tomllib.load(f)

    subprocess.run(
        [sys.executable, str(my_path), "--version"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        timeout=45,
        check=True,
    )


def run_git_self_update(
    profile: ProfileConfig,
    update_only: bool = False,
    offline: bool = False,
    assume_yes: bool = False,
) -> bool:
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
            _git_check(base_cmd + ["fetch", profile.git_remote], timeout=90)
            fetch_success = True
            break
        except Exception:
            if attempt < 5:
                sys.stdout.write(f"[WARN] Fetch attempt {attempt}/5 failed. Retrying in 2s...\n")
                time.sleep(2)

    if not fetch_success:
        sys.stderr.write("[ERROR] Git fetch failed after 5 attempts. Continuing without update.\n")
        return False

    my_path = Path(__file__).resolve()
    wrapper_path = my_path.with_name("orchestrator.sh")

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

            choice = "2" if assume_yes else "1"
            if not assume_yes and sys.stdin.isatty():
                r, _, _ = select.select([sys.stdin], [], [], 60)
                if r:
                    choice = sys.stdin.readline().strip()

            if choice != "2":
                sys.stdout.write("Aborting update by user request.\n")
                return False

        tracked_files: set[str] = set()
        incoming_files: set[str] = set()
        collisions: list[str] = []

        with suppress(Exception):
            tracked_out = _git_check(base_cmd + ["ls-files", "-z"])
            tracked_files = {x for x in tracked_out.split("\0") if x}

        with suppress(Exception):
            incoming_out = _git_check(base_cmd + ["ls-tree", "-r", "-z", "--name-only", remote_ref])
            incoming_files = {x for x in incoming_out.split("\0") if x}

        for inc in incoming_files:
            target_file = work_tree / inc
            if target_file.exists() and inc not in tracked_files:
                collisions.append(inc)

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

        if (changed_files or collisions) and not assume_yes:
            sys.stdout.write("\n[LOCAL CHANGES DETECTED]\n")
            sys.stdout.write(f"  Modified tracked files: {len(changed_files)}\n")
            sys.stdout.write(f"  Untracked incoming collisions: {len(collisions)}\n")
            sys.stdout.write("  1) Abort [DEFAULT]\n")
            sys.stdout.write("  2) Backup and reset to upstream\n")
            sys.stdout.write("Choice [1-2] (default: 1): ")
            sys.stdout.flush()

            choice = "1"
            if sys.stdin.isatty():
                r, _, _ = select.select([sys.stdin], [], [], 60)
                if r:
                    choice = sys.stdin.readline().strip()

            if choice != "2":
                sys.stdout.write("Aborting update by user request.\n")
                return False

        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_root = backups_dir() / f"dusky_backup_{timestamp}_{remote_head[:7]}"
        ensure_dir(backup_root, 0o700)
        _clean_old_backups(backups_dir(), keep=10)

        collision_dir = backup_root / "untracked_collisions"
        user_mods_dir = backup_root / "user_mods"
        needs_merge_dir = backup_root / "needs_merge"

        def restore_collisions() -> None:
            if not collision_dir.exists():
                return
            for src in collision_dir.rglob("*"):
                if src.is_file():
                    rel = src.relative_to(collision_dir)
                    dest = work_tree / rel
                    if not dest.exists():
                        with suppress(OSError):
                            dest.parent.mkdir(parents=True, exist_ok=True)
                            shutil.copy2(src, dest)

        def restore_user_mods() -> None:
            if not user_mods_dir.exists():
                return
            for src in user_mods_dir.rglob("*"):
                if src.is_file():
                    rel = src.relative_to(user_mods_dir)
                    dest = work_tree / rel
                    with suppress(OSError):
                        dest.parent.mkdir(parents=True, exist_ok=True)
                        shutil.copy2(src, dest)

        if collisions:
            sys.stdout.write(f"[WARN] Backing up {len(collisions)} untracked work-tree collisions...\n")
            ensure_dir(collision_dir, 0o700)
            for coll in collisions:
                src = work_tree / coll
                dest = collision_dir / coll
                with suppress(OSError):
                    _move_to_backup(src, dest)

        orch_backup = backup_root / "orchestrator.py"
        with suppress(OSError):
            shutil.copy2(my_path, orch_backup)

        if changed_files:
            ensure_dir(user_mods_dir, 0o700)
            sys.stdout.write(f"[WARN] Backing up {len(changed_files)} modified tracked files...\n")
            for path in changed_files:
                src = work_tree / path
                if src.exists() and src.is_file():
                    dest = user_mods_dir / path
                    dest.parent.mkdir(parents=True, exist_ok=True)
                    with suppress(OSError):
                        shutil.copy2(src, dest)

        sys.stdout.write(f"[GIT] Updating from {local_head[:7]} to {remote_head[:7]}...\n")
        _git_check(base_cmd + ["reset", "--hard", remote_head], timeout=180)

        if changed_files:
            sys.stdout.write("[GIT] Processing local edits...\n")
            restored = 0
            merged = 0

            for path, old_oid in changed_files.items():
                backup_file = user_mods_dir / path
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
                        ensure_dir(needs_merge_dir, 0o700)
                        conflict_dest = needs_merge_dir / path
                        conflict_dest.parent.mkdir(parents=True, exist_ok=True)
                        with suppress(OSError):
                            shutil.copy2(backup_file, conflict_dest)
                        merged += 1
                else:
                    ensure_dir(needs_merge_dir, 0o700)
                    conflict_dest = needs_merge_dir / path
                    conflict_dest.parent.mkdir(parents=True, exist_ok=True)
                    with suppress(OSError):
                        shutil.copy2(backup_file, conflict_dest)
                    merged += 1

            if restored:
                sys.stdout.write(f"[GIT] Restored {restored} safe local edits.\n")
            if merged:
                sys.stdout.write(f"[WARN] {merged} files had upstream conflicts. Saved in: {needs_merge_dir}\n")

        try:
            validate_updated_sources(my_path, wrapper_path)
        except Exception as e:
            sys.stderr.write(f"[ERROR] Updated orchestrator failed validation: {e}\n")
            sys.stdout.write("[GIT] Rolling back to previous HEAD...\n")
            with suppress(Exception):
                _git_check(base_cmd + ["reset", "--hard", local_head], timeout=180)
            if orch_backup.exists():
                with suppress(OSError):
                    shutil.copy2(orch_backup, my_path)
            restore_collisions()
            restore_user_mods()
            return False

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
            return Text(S("completed"), style="green")
        case TaskStatus.RUNNING:
            return Text(S("running"), style="yellow")
        case TaskStatus.FAILED:
            return Text(S("failed"), style="red")
        case TaskStatus.SKIPPED:
            return Text(S("skipped"), style="dim")
        case _:
            return Text(S("pending"), style="dim")


def _task_label(task: OrchestratorTask) -> Text:
    txt = Text()
    txt.append(f"{task.index:03d} ")
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
            yield Static(f"{S('logo')} Fuzzy Task Search", id="search_title")
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
            txt.append(f"{item.index:03d} ")
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
        self._finished = False

    def compose(self) -> ComposeResult:
        with Container(id="modal_dialog"):
            yield Static(
                Text(f"{S('failed')} EXECUTION FAULT: {self.script_name}", style="bold red"),
                id="modal_title",
            )

            details = Text()
            details.append("Command:\n", style="bold")
            details.append(self.command + "\n", style="dim")
            details.append("Exit code: ", style="bold")
            details.append(str(self.exit_code) + "\n", style="red bold")
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

    def _done(self, value: str) -> None:
        if self._finished:
            return
        self._finished = True
        self.dismiss(value)

    def on_button_pressed(self, event: Button.Pressed) -> None:
        match event.button.id:
            case "btn_retry":
                self._done("retry")
            case "btn_manual":
                self._done("manual")
            case "btn_skip":
                self._done("skip")
            case _:
                self._done("abort")

    def on_key(self, event: events.Key) -> None:
        key = event.key.lower()
        match key:
            case "r":
                self._done("retry")
            case "m":
                self._done("manual")
            case "s":
                self._done("skip")
            case "a" | "escape" | "q":
                self._done("abort")


class ManualModalScreen(ModalScreen[str]):
    def __init__(self, script_name: str, command: str):
        super().__init__()
        self.script_name = script_name
        self.command = command
        self._finished = False

    def compose(self) -> ComposeResult:
        with Container(id="manual_dialog"):
            yield Static(
                Text(f"{S('running')} MANUAL OVERRIDE: {self.script_name}", style="bold cyan"),
                id="manual_title",
            )

            details = Text()
            details.append("Command:\n", style="bold")
            details.append(self.command, style="dim")
            yield Static(details)

            with Horizontal(id="button_bar"):
                yield Button("Proceed [Y]", variant="success", id="btn_yes")
                yield Button("Skip [S]", variant="warning", id="btn_skip")
                yield Button("Quit [Q]", variant="error", id="btn_quit")

    def _done(self, value: str) -> None:
        if self._finished:
            return
        self._finished = True
        self.dismiss(value)

    def on_button_pressed(self, event: Button.Pressed) -> None:
        match event.button.id:
            case "btn_yes":
                self._done("yes")
            case "btn_skip":
                self._done("skip")
            case _:
                self._done("quit")

    def on_key(self, event: events.Key) -> None:
        key = event.key.lower()
        match key:
            case "y":
                self._done("yes")
            case "s":
                self._done("skip")
            case "q" | "escape":
                self._done("quit")


class SudoPasswordScreen(ModalScreen[bool]):
    BINDINGS = [Binding("escape", "cancel", "Cancel")]

    def compose(self) -> ComposeResult:
        with Container(id="sudo_dialog"):
            yield Static(f"{S('logo')} Sudo Authentication Required", id="sudo_title")
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
            self.query_one("#sudo_error", Static).update(
                Text(f"Authentication failed: {err}", style="red")
            )
            self.query_one("#sudo_password", Input).value = ""

    async def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "btn_auth":
            await self._submit()
        else:
            self.dismiss(False)

    @on(Input.Submitted)
    async def on_input_submitted(self, event: Input.Submitted) -> None:
        event.stop()
        await self._submit()

    def action_cancel(self) -> None:
        self.dismiss(False)


class ConfirmQuitScreen(ModalScreen[str]):
    BINDINGS = [Binding("escape", "cancel", "Cancel")]

    def compose(self) -> ComposeResult:
        with Container(id="confirm_dialog"):
            yield Static(f"{S('failed')} Abort Orchestrator?", id="confirm_title")
            yield Static("This will terminate the active sequence.", id="confirm_text")
            with Horizontal(id="button_bar"):
                yield Button("Abort [A]", variant="error", id="btn_abort")
                yield Button("Cancel [C]", variant="primary", id="btn_cancel")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        self.dismiss("abort" if event.button.id == "btn_abort" else "cancel")

    def on_key(self, event: events.Key) -> None:
        key = event.key.lower()
        if key == "a":
            self.dismiss("abort")
        elif key in ("c", "escape", "q"):
            self.dismiss("cancel")

    def action_cancel(self) -> None:
        self.dismiss("cancel")


class HelpScreen(ModalScreen[None]):
    BINDINGS = [Binding("escape", "dismiss", "Dismiss")]

    def compose(self) -> ComposeResult:
        with Container(id="help_dialog"):
            yield Static(f"{S('logo')} Dusky Orchestrator Help", id="help_title")
            text = Text()
            text.append("Global Keys\n", style="bold")
            text.append("  Ctrl+F   Search tasks\n")
            text.append("  Ctrl+Q   Quit / abort\n")
            text.append("  ?        Help\n\n")
            text.append("During Task Execution\n", style="bold")
            text.append("  Keys are forwarded to the running task.\n")
            text.append("  Ctrl+F opens search without stopping the task.\n")
            text.append("  Ctrl+Q aborts immediately.\n\n")
            text.append("Interactive Tasks\n", style="bold")
            text.append("  The TUI suspends and gives the task full control.\n")
            text.append("  When the task exits, the TUI returns.\n")
            yield Static(text)
            with Horizontal(id="button_bar"):
                yield Button("Close", variant="primary", id="btn_close")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        self.dismiss(None)

    def action_dismiss(self) -> None:
        self.dismiss(None)


class AppFooter(Horizontal):
    def compose(self) -> ComposeResult:
        yield Label("[Ctrl+F] Search", classes="footer-shortcut")
        yield Label("[Ctrl+Q] Quit", classes="footer-shortcut")
        yield Label("[?] Help", classes="footer-shortcut")
        yield Label(f" {S('sep')} ", classes="footer-sep")
        yield Label("Engine: active", id="footer_status")


class ProfileSelectorApp(App):
    ENABLE_COMMAND_PALETTE = False
    CSS = ""

    def __init__(self, profiles: list[ProfileConfig]):
        super().__init__()
        self.profiles = profiles
        self.selected_profile: ProfileConfig | None = None

    def compose(self) -> ComposeResult:
        with Container(id="selector_container"):
            yield Static(f"{S('logo')} DUSKY ARCH MASTER ORCHESTRATOR", id="title")

            options = []
            for i, p in enumerate(self.profiles):
                prefix = "> " if i == 0 else "  "
                options.append(
                    Option(f"{prefix}{i + 1}. {p.name:<25} {p.description}", id=str(i))
                )

            yield OptionList(*options, id="profiles_list")
            yield Static("Enter select | 1-9 quick select | Esc quit", classes="help_text")

    @on(OptionList.OptionSelected)
    def on_selected(self, event: OptionList.OptionSelected) -> None:
        idx: int | None = None
        if event.option and event.option.id is not None:
            idx = int(str(event.option.id))
        elif event.option_index is not None:
            idx = event.option_index

        if idx is not None and 0 <= idx < len(self.profiles):
            self.selected_profile = self.profiles[idx]
            self.exit(0)

    def on_key(self, event: events.Key) -> None:
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
        Binding("ctrl+q", "quit_app", "Quit", priority=True),
        Binding("question_mark", "help", "Help"),
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

        self.run_id = uuid.uuid4().hex[:8]
        self.state = StateStore(profile)
        self.statuses = self.state.statuses()
        self.progressed: set[str] = set()
        self.counters: dict[str, int] = {}
        self.conditions = ConditionEvaluator()

        self.tree_widget = Tree(f"{S('logo')} Execution Sequence")
        self.log_widget = RichLog(
            id="pty_log",
            highlight=False,
            markup=False,
            wrap=True,
            max_lines=6000,
        )
        self.progress_bar = ProgressBar(show_eta=False, show_percentage=False, id="progress_bar")
        self.status_label = Label("Initializing orchestrator sequence...", id="status_label")
        self.speed_label = Label("Status: pre-flight | ETA: --:--", id="speed_label")

        self.tree_nodes_map: dict[str, TreeNode] = {}
        self.logger = RunLogger(profile, self.run_id)
        self._log_widgets: dict[str | None, RichLog] = {}
        self._ui_buffer: list[tuple[str | None, Text]] = []
        self._ui_flush_timer = None
        self._telemetry: dict[str, str] = {}
        self._telemetry_timer = None

    def compose(self) -> ComposeResult:
        with Horizontal(id="top_header"):
            yield Static(f"{S('logo')} DUSKY ORCHESTRATOR  [{self.profile.name}]", id="header_title")

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
                            max_lines=6000,
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
            status = self.statuses.get(t.state_key)
            if StateStore.is_done(status):
                if status in ("skipped", "skipped_condition"):
                    self.update_task_node_by_key(t.state_key, TaskStatus.SKIPPED)
                else:
                    self.update_task_node_by_key(t.state_key, TaskStatus.COMPLETED)
                self._mark_progress(t)

        self.run_execution_pipeline()

    def on_unmount(self) -> None:
        self._kill_active_child_sync()
        self.logger.close_all()
        self.state.close()
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
                with suppress(Exception):
                    self.tree_widget.select_node(node)
                    self.tree_widget.scroll_to_node(node)
                for t in self.tasks:
                    if t.state_key == state_key:
                        self.log_system(f"Fuzzy finder navigated to: {t.script_name}")
                        break

        self.push_screen(TaskSearchScreen(self.tasks), on_search_selected)

    async def action_quit_app(self) -> None:
        if self.active_task:
            resp = await self.push_screen_wait(ConfirmQuitScreen())
            if resp != "abort":
                return

        self.log_system("Quit requested. Terminating pipeline...", is_err=True)
        self.exit(1 if self.active_task else 0)

    def action_help(self) -> None:
        if isinstance(self.screen, ModalScreen):
            return
        self.push_screen(HelpScreen())

    def on_key(self, event: events.Key) -> None:
        if isinstance(self.screen, ModalScreen):
            return

        if self.current_pty_master is not None:
            if event.key == "ctrl+f":
                self.action_open_search()
                event.stop()
                return

            if event.key == "ctrl+q":
                self.log_system("Emergency abort requested from PTY session.", is_err=True)
                self.exit(1)
                event.stop()
                return

            data = self._pty_key_bytes(event)
            if data:
                with suppress(OSError):
                    os.write(self.current_pty_master, data)
                event.stop()

    def _pty_key_bytes(self, event: events.Key) -> bytes:
        key = event.key

        if event.is_printable and event.character:
            return event.character.encode("utf-8")

        simple = {
            "enter": b"\r",
            "escape": b"\x1b",
            "tab": b"\t",
            "shift+tab": b"\x1b[Z",
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
            "f1": b"\x1bOP",
            "f2": b"\x1bOQ",
            "f3": b"\x1bOR",
            "f4": b"\x1bOS",
            "f5": b"\x1b[15~",
            "f6": b"\x1b[17~",
            "f7": b"\x1b[18~",
            "f8": b"\x1b[19~",
            "f9": b"\x1b[20~",
            "f10": b"\x1b[21~",
            "f11": b"\x1b[23~",
            "f12": b"\x1b[24~",
        }

        if key in simple:
            return simple[key]

        if key.startswith("ctrl+"):
            rest = key[5:]
            if rest == "space" or rest == "@":
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

    def _mark_progress(self, task: OrchestratorTask) -> None:
        if task.state_key in self.progressed:
            return
        self.progressed.add(task.state_key)
        self.progress_bar.advance(1)

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

    def _queue_telemetry(
        self,
        pct: str | None = None,
        speed: str | None = None,
        eta: str | None = None,
    ) -> None:
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

        if pct and self.active_task:
            self.status_label.update(f"{S('running')} {self.active_task.script_name} ({pct})")

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
        if "\x1b" not in clean and any(
            k in lower for k in ("error", "failed", "warning", "conflict", "exists in filesystem")
        ):
            text = Text(clean, style="bold red")
        else:
            try:
                text = Text.from_ansi(clean)
            except Exception:
                text = Text(stripped)

        self._queue_ui(text, self.active_task.state_key if self.active_task else None)

    @staticmethod
    def _set_pty_size(fd: int) -> None:
        try:
            size = os.get_terminal_size()
            winsize = struct.pack("HHHH", size.lines, size.columns, 0, 0)
            fcntl.ioctl(fd, termios.TIOCSWINSZ, winsize)
        except (OSError, ValueError):
            with suppress(OSError):
                winsize = struct.pack("HHHH", 40, 120, 0, 0)
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

    def _kill_active_child_sync(self) -> None:
        pid = self.active_child_pid
        if pid is None:
            return

        with suppress(ProcessLookupError, PermissionError, OSError):
            os.killpg(pid, signal.SIGTERM)

        time.sleep(0.2)

        with suppress(ProcessLookupError, PermissionError, OSError):
            os.killpg(pid, signal.SIGKILL)

    def _task_env(self, task: OrchestratorTask) -> dict[str, str]:
        env = os.environ.copy()

        for k in (
            "LD_PRELOAD",
            "LD_AUDIT",
            "LD_DEBUG",
            "LD_LIBRARY_PATH",
            "LD_ORIGIN_PATH",
            "LD_PROFILE",
            "LD_SHOW_AUXV",
            "LD_USE_LOAD_BIAS",
            "PYTHONSTARTUP",
            "PYTHONHOME",
            "PYTHONPATH",
            "PERL5LIB",
            "RUBYLIB",
            "NODE_OPTIONS",
        ):
            env.pop(k, None)

        pw = target_user_pw()
        home = str(Path(pw.pw_dir))
        shell = pw.pw_shell or "/bin/bash"

        env.update(
            {
                "HOME": home,
                "USER": pw.pw_name,
                "LOGNAME": pw.pw_name,
                "SHELL": shell,
                "TERM": env.get("TERM", "xterm-256color"),
                "COLORTERM": env.get("COLORTERM", "truecolor"),
                "PYTHONUNBUFFERED": "1",
                "PYTHONUTF8": "1",
                "PYTHONDONTWRITEBYTECODE": "1",
                "PAGER": "cat",
                "SYSTEMD_PAGER": "cat",
                "GIT_PAGER": "cat",
                "DUSKY_VERSION": VERSION,
                "DUSKY_RUN_ID": self.run_id,
                "DUSKY_PROFILE_NAME": self.profile.name,
                "DUSKY_PROFILE_FILE": str(self.profile.filepath),
                "DUSKY_TASK_SCRIPT": task.script_name,
                "DUSKY_TASK_PATH": str(task.resolved_path),
                "DUSKY_TASK_MODE": task.mode,
                "DUSKY_TASK_INDEX": str(task.index),
                "DUSKY_TASK_STATE_KEY": task.state_key,
                "DUSKY_TASK_LOG_FILE": str(self.logger.task_log_path(task)),
                "DUSKY_USER": pw.pw_name,
                "DUSKY_TARGET_USER": pw.pw_name,
                "DUSKY_USER_HOME": home,
                "DUSKY_LOG_DIR": str(self.logger.root or logs_dir()),
                "DUSKY_STATE_DIR": str(state_dir()),
                "DUSKY_BACKUP_DIR": str(backups_dir()),
                "DUSKY_FORCE": "1" if (self.force_flag or task.force_flag) else "0",
                "DUSKY_INTERACTIVE": "1" if task.interactive else "0",
            }
        )

        if task.interactive:
            if not env.get("EDITOR"):
                env["EDITOR"] = shutil.which("nano") or shutil.which("vim") or "true"
            if not env.get("VISUAL"):
                env["VISUAL"] = env["EDITOR"]
        else:
            env["EDITOR"] = "true"
            env["VISUAL"] = "true"

        if SudoEngine._askpass_path is not None:
            env["SUDO_ASKPASS"] = str(SudoEngine._askpass_path)

        return env

    def _task_command(self, task: OrchestratorTask) -> list[str]:
        assert task.resolved_path is not None

        args = list(task.args)
        if (self.force_flag or task.force_flag) and "--force" not in args:
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

        critical_keys = [
            "HOME",
            "USER",
            "LOGNAME",
            "SHELL",
            "PATH",
            "TERM",
            "COLORTERM",
            "LANG",
            "LC_ALL",
            "DISPLAY",
            "WAYLAND_DISPLAY",
            "XDG_RUNTIME_DIR",
            "XDG_CONFIG_HOME",
            "XDG_CACHE_HOME",
            "XDG_STATE_HOME",
            "XDG_DATA_HOME",
            "XDG_SESSION_TYPE",
            "XDG_CURRENT_DESKTOP",
            "DBUS_SESSION_BUS_ADDRESS",
            "SSH_AUTH_SOCK",
            "SUDO_ASKPASS",
            "PYTHONUNBUFFERED",
            "PYTHONUTF8",
            "PYTHONDONTWRITEBYTECODE",
            "PAGER",
            "SYSTEMD_PAGER",
            "GIT_PAGER",
            "EDITOR",
            "VISUAL",
        ]

        env_pairs = [f"{k}={full_env[k]}" for k in critical_keys if k in full_env]
        for k, v in full_env.items():
            if k.startswith("DUSKY_"):
                env_pairs.append(f"{k}={v}")

        if task.mode == "S":
            prefix = SudoEngine.sudo_prefix()
            if prefix:
                return prefix + ["env"] + env_pairs + inner

        return inner

    async def execute_pty_command(
        self,
        cmd: list[str],
        env: dict[str, str],
        timeout: float = 0.0,
    ) -> tuple[bool, int | None, str]:
        try:
            master_fd, slave_fd = pty.openpty()
        except OSError as e:
            self.log_system(f"PTY allocation failed: {e}", is_err=True)
            return False, None, "PTY allocation failed"

        self.current_pty_master = master_fd
        self._set_pty_size(slave_fd)

        transport: asyncio.Transport | None = None
        proc: asyncio.subprocess.Process | None = None
        file_obj = None
        decoder = codecs.getincrementaldecoder("utf-8")(errors="replace")
        last_lines: deque[str] = deque(maxlen=40)
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
            reader = asyncio.StreamReader(limit=1024 * 1024)
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

                    if len(line_buffer) > 1_000_000:
                        with suppress(Exception):
                            self.handle_pty_line(line_buffer[:1_000_000], last_lines)
                        line_buffer = line_buffer[-100_000:]

                    while True:
                        m = SINGLE_NEWLINE_RE.search(line_buffer)
                        if not m:
                            break

                        idx = m.start()
                        line = line_buffer[:idx]
                        line_buffer = line_buffer[idx + 1:]

                        if line:
                            with suppress(Exception):
                                self.handle_pty_line(line, last_lines)

            read_task = asyncio.create_task(read_loop())

            try:
                async with asyncio.timeout(timeout if timeout > 0 else None):
                    code = await proc.wait()

                try:
                    await asyncio.wait_for(asyncio.shield(read_task), timeout=2.0)
                except (TimeoutError, asyncio.TimeoutError):
                    read_task.cancel()
                    with suppress(asyncio.CancelledError, Exception):
                        await read_task
                except Exception:
                    pass

                self._flush_ui()
                return code == 0, code, "\n".join(last_lines)

            except (TimeoutError, asyncio.TimeoutError):
                await self._kill_proc(proc)
                read_task.cancel()
                with suppress(asyncio.CancelledError, Exception):
                    await read_task
                self._flush_ui()
                return False, None, "\n".join(last_lines)

            except asyncio.CancelledError:
                await self._kill_proc(proc)
                read_task.cancel()
                with suppress(asyncio.CancelledError, Exception):
                    await read_task
                raise

            finally:
                if not read_task.done():
                    read_task.cancel()
                    with suppress(asyncio.CancelledError, Exception):
                        await read_task

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
            elif file_obj is not None:
                with suppress(Exception):
                    file_obj.close()
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

        cm = self.suspend() if hasattr(self, "suspend") else nullcontext()

        with cm:
            sys.stdout.flush()
            sys.stderr.flush()

            old_attr = None
            with suppress(termios.error, OSError):
                old_attr = termios.tcgetattr(sys.stdin.fileno())

            try:
                sys.stdout.write("\x1b[2J\x1b[H")
                sys.stdout.flush()

                print(f"\n--- INTERACTIVE WORKFLOW: {task.script_name} ---")
                print(f"Executing: {shlex.join(cmd)}\n")

                proc = await asyncio.create_subprocess_exec(*cmd, env=env)

                try:
                    code = await proc.wait()
                except asyncio.CancelledError:
                    await self._kill_proc(proc)
                    raise

                return code == 0, code, "interactive session"

            except Exception as e:
                return False, None, str(e)

            finally:
                if old_attr:
                    with suppress(termios.error, OSError):
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

        timeout = task.timeout if task.timeout is not None else self.task_timeout
        return await self.execute_pty_command(cmd, env, timeout=timeout)

    def finish_task(
        self,
        task: OrchestratorTask,
        status: str,
        exit_code: int | None = None,
        note: str = "",
    ) -> None:
        self.state.mark(task, status, exit_code, note)
        self.statuses[task.state_key] = status

        if status in ("completed", "ignored", "manual"):
            self.update_task_node_by_key(task.state_key, TaskStatus.COMPLETED)
        elif status in ("skipped", "skipped_condition"):
            self.update_task_node_by_key(task.state_key, TaskStatus.SKIPPED)
        else:
            self.update_task_node_by_key(task.state_key, TaskStatus.FAILED)

        self._mark_progress(task)
        self.counters[status] = self.counters.get(status, 0) + 1
        self.logger.close_task(task, status, exit_code, task.duration)

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
                if StateStore.is_done(self.statuses.get(task.state_key)):
                    continue

                if task.condition and not self.conditions.check(task.condition):
                    self.log_system(f"Condition not met, skipping: {task.script_name} ({task.condition})")
                    self.finish_task(task, "skipped_condition", None, f"condition:{task.condition}")
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

                    self.finish_task(task, "skipped", None, "missing file")
                    continue

                if self.manual:
                    self.status_label.update(f"{S('running')} Pending manual approval: {task.script_name}")
                    cmd_preview = shlex.join(self._task_command(task))
                    action = await self.push_screen_wait(ManualModalScreen(task.script_name, cmd_preview))

                    if action == "skip":
                        self.finish_task(task, "skipped", None, "manual skip")
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
                        self.finish_task(task, "skipped", None, "sudo unavailable")
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

                self.logger.open_task(task, cmd)
                start = time.monotonic()
                success, code, last = await self._execute_task_cmd(task, cmd, env)
                task.duration = time.monotonic() - start

                resolved = False

                while not success and not resolved:
                    if task.ignore_fail:
                        self.log_system(f"Task failed but marked ignore-fail. Continuing: {task.script_name}")
                        self.finish_task(task, "ignored", code, last)
                        resolved = True
                        success = True
                        break

                    self.state.mark(task, "failed", code, last)
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
                            start = time.monotonic()
                            success, code, last = await self._execute_task_cmd(task, cmd, env)
                            task.duration = time.monotonic() - start

                        case "manual":
                            self.log_system(f"Manual intervention TTY: {task.script_name}...")
                            m_success, m_code, m_last = await self._execute_suspended(task, cmd, env)
                            if m_success:
                                self.finish_task(task, "manual", m_code, "manual override")
                                resolved = True
                                success = True
                            else:
                                code = m_code
                                last = m_last
                                self.log_system("Manual intervention failed.", is_err=True)

                        case "skip":
                            self.finish_task(task, "skipped", code, last)
                            resolved = True

                        case _:
                            self.log_system("User aborted execution sequence.", is_err=True)
                            self.exit(1)
                            return

                if success and not resolved:
                    self.finish_task(task, "completed", code, "")
                    self.log_system(f"Successfully completed: {task.script_name}")

                self.active_task = None

                if self.profile.post_script_delay > 0:
                    await asyncio.sleep(self.profile.post_script_delay)

            self.status_label.update(f"{S('completed')} All orchestrator sequences completed successfully!")
            self.speed_label.update("Status: idle | ETA: 00:00")

            with suppress(Exception):
                self.query_one("#footer_status", Label).update("Engine: complete")

            self.log_system("Execution sequence finished. All system targets resolved.")
            self.logger.write_report(self.profile, self.tasks, self.statuses, self.counters)

            AudioNotifier.play("complete")
            DesktopNotifier.notify("Dusky Orchestrator", "Setup completed successfully.", "normal")

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
    parser.add_argument("--yes", "-y", action="store_true", help="Assume yes for destructive git update prompts")
    parser.add_argument("--sudo-password", help="Provide sudo password non-interactively")
    parser.add_argument("--sudo-password-file", help="Read sudo password from file")
    parser.add_argument("--task-timeout", type=float, default=0.0, help="Per-task timeout in seconds (0 disables)")
    parser.add_argument("--allow-root", action="store_true", help="Allow running as root (not recommended)")
    parser.add_argument("--ascii", action="store_true", help="Use ASCII symbols instead of Unicode")
    parser.add_argument("--no-audio", action="store_true", help="Disable audio notifications")
    parser.add_argument("--no-notify", action="store_true", help="Disable desktop notifications")
    parser.add_argument("--no-inhibit", action="store_true", help="Do not inhibit sleep/idle")
    parser.add_argument("--doctor", action="store_true", help="Run environment diagnostics and exit")
    parser.add_argument("--version", action="version", version=f"Dusky Orchestrator {VERSION}")

    return parser.parse_args()


def run_doctor() -> None:
    print("Dusky Orchestrator Doctor")
    print("=========================")
    print(f"Version:        {VERSION}")
    print(f"Python:         {sys.version.split()[0]}")
    print(f"Executable:     {sys.executable}")
    print(f"UID/EUID:       {os.getuid()}/{os.geteuid()}")
    print(f"Target user:    {target_user_pw().pw_name}")
    print(f"Home:           {user_home()}")
    print(f"State dir:      {state_dir()}")
    print(f"Logs dir:       {logs_dir()}")
    print(f"Backups dir:    {backups_dir()}")
    print(f"Cache dir:      {cache_dir()}")
    print(f"Runtime dir:    {runtime_dir()}")
    print(f"Profiles dir:   {PROFILES_DIR}")

    try:
        import textual

        print(f"Textual:        {getattr(textual, '__version__', 'unknown')}")
    except Exception as e:
        print(f"Textual:        unavailable ({e})")

    try:
        import rich

        print(f"Rich:           {getattr(rich, '__version__', 'unknown')}")
    except Exception as e:
        print(f"Rich:           unavailable ({e})")

    print(f"git:            {shutil.which('git') or 'missing'}")
    print(f"sudo:           {shutil.which('sudo') or 'missing'}")
    print(f"pacman:         {shutil.which('pacman') or 'missing'}")
    print(f"systemctl:      {shutil.which('systemctl') or 'missing'}")

    if PROFILES_DIR.exists():
        profiles = sorted(PROFILES_DIR.glob("*.toml"))
        print(f"Profiles found: {len(profiles)}")
        for p in profiles:
            print(f"  - {p.name}")
    else:
        print("Profiles found: 0")


def main() -> None:
    args = parse_command_line()

    global ASCII_MODE
    if args.ascii:
        ASCII_MODE = True

    if args.doctor:
        run_doctor()
        sys.exit(0)

    check_runtime_versions()
    ensure_not_root(args.allow_root)

    profiles = discover_profiles()
    if not profiles:
        Console(stderr=True).print("[bold yellow]:: No profiles found in profiles/ directory.[/bold yellow]")
        sys.exit(1)

    palette = load_palette()
    ProfileSelectorApp.CSS = build_selector_css(palette)

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

    locked = False

    if args.reset or args.reset_and_run:
        if not locked:
            if not acquire_lock():
                sys.exit(1)
            locked = True
        reset_state_for_profile(selected_profile)
        if args.reset and not args.reset_and_run:
            sys.exit(0)

    if args.list_scripts:
        print(f"Sequence for {selected_profile.name}:")
        for t in selected_profile.tasks:
            print(f"{t.index:3d}. [{t.mode}] {t.script_name} {shlex.join(t.args)}".rstrip())
        sys.exit(0)

    if not locked:
        if not acquire_lock():
            sys.exit(1)
        locked = True

    if args.git_update_only:
        run_git_self_update(
            selected_profile,
            update_only=True,
            offline=args.offline,
            assume_yes=args.yes,
        )
        sys.exit(0)

    if not args.no_git_update and not args.offline:
        if run_git_self_update(
            selected_profile,
            update_only=False,
            offline=False,
            assume_yes=args.yes,
        ):
            sys.exit(0)

    if not resolve_and_validate_manifest(selected_profile):
        Console(stderr=True).print("[bold red]Manifest validation failed.[/bold red]")
        sys.exit(1)

    if args.dry_run:
        temp_state = StateStore(selected_profile)
        statuses = temp_state.statuses()
        temp_state.close()

        print("Dry-run validation complete.\n")
        for t in selected_profile.tasks:
            state = statuses.get(t.state_key, "pending")
            print(f"{t.index:03d}. [{t.mode}] {t.script_name}")
            print(f"    path:        {t.resolved_path}")
            print(f"    interpreter: {t.interpreter or 'direct'}")
            print(f"    args:        {shlex.join(t.args)}")
            print(f"    interactive: {t.interactive}")
            print(f"    condition:   {t.condition or 'always'}")
            print(f"    timeout:     {t.timeout if t.timeout is not None else args.task_timeout}")
            print(f"    checksum:    {t.checksum}")
            print(f"    state:       {state}")
            print()

        sys.exit(0)

    temp_state = StateStore(selected_profile)
    statuses = temp_state.statuses()
    temp_state.close()

    has_sudo = any(
        t.mode == "S" and not StateStore.is_done(statuses.get(t.state_key))
        for t in selected_profile.tasks
    )

    if has_sudo:
        password_file = Path(args.sudo_password_file).expanduser() if args.sudo_password_file else None
        if not SudoEngine.preflight(cli_password=args.sudo_password, password_file=password_file):
            sys.exit(1)

    policy = selected_profile.policy

    manual = args.manual or bool(policy.get("manual", False))
    stop_on_fail = args.stop_on_fail or bool(policy.get("stop_on_fail", False))
    force = args.force or bool(policy.get("force", False))

    task_timeout = max(0.0, args.task_timeout)
    if task_timeout == 0.0:
        with suppress(Exception):
            task_timeout = max(0.0, float(policy.get("task_timeout", 0.0)))

    AudioNotifier.enabled = (not args.no_audio) and bool(policy.get("audio", True))
    DesktopNotifier.enabled = (not args.no_notify) and bool(policy.get("notify", True))
    inhibit_enabled = (not args.no_inhibit) and bool(policy.get("inhibit_sleep", True))

    inhibitor = SleepInhibitor(inhibit_enabled)

    try:
        DuskyOrchestratorApp.CSS = build_app_css(palette)

        app = DuskyOrchestratorApp(
            profile=selected_profile,
            has_sudo=has_sudo,
            manual=manual,
            stop_on_fail=stop_on_fail,
            force=force,
            task_timeout=task_timeout,
        )
        app.run()
        sys.exit(app.return_code or 0)

    except KeyboardInterrupt:
        Console(stderr=True).print("\n[bold red]:: Interrupted by user.[/]")
        sys.exit(130)

    finally:
        inhibitor.close()
        SudoEngine.cleanup()


if __name__ == "__main__":
    main()
