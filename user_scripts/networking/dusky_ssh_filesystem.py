#!/usr/bin/env -S python3 -I
"""SSHFS remote manager for Arch Linux with multi-mount support and robust error recovery."""

import os
import sys

# This program should run as the normal user.
# It only needs escalation for pacman, not for mounting.
if os.geteuid() == 0 and any(
    var in os.environ
    for var in ("SUDO_USER", "SUDO_UID", "PKEXEC_UID", "DOAS_USER", "RUN0_UID")
):
    print(
        "[-] Run this script as your normal user, not via sudo/doas/run0/pkexec.\n"
        "    It will ask for administrative rights only when installing packages.",
        file=sys.stderr,
    )
    sys.exit(1)

import contextlib
import errno
import json
import re
import shlex
import shutil
import subprocess
import tempfile
import time
from collections.abc import Iterator
from pathlib import Path
from typing import Final, NamedTuple, NoReturn

try:
    HOME: Final[Path] = Path.home()
except (RuntimeError, KeyError) as exc:
    print(f"[-] Cannot determine home directory: {exc}", file=sys.stderr)
    sys.exit(1)

# --- Fixed paths ---
STATE_FILE: Final[Path] = HOME / ".config/dusky/settings/sshfiles/sshfs"
BASE_MOUNT_DIR: Final[Path] = HOME / "Documents/sshfs"

MAX_HISTORY: Final[int] = 10

# sshfs/FUSE/SSH options for a stable interactive mount.
SSHFS_OPTIONS: Final[tuple[str, ...]] = (
    "reconnect",
    "ServerAliveInterval=15",
    "ServerAliveCountMax=3",
    "ConnectTimeout=10",
    "StrictHostKeyChecking=accept-new",
)


def fail(message: str, code: int = 1) -> NoReturn:
    print(f"[-] {message}", file=sys.stderr)
    sys.exit(code)


def root_hint(path: Path) -> str:
    try:
        st = path.stat()
    except OSError:
        return ""
    if st.st_uid == 0 and os.geteuid() != 0:
        quoted = shlex.quote(str(path))
        return f" If owned by root, fix with: sudo chown -R {os.getuid()}:{os.getgid()} {quoted}"
    return ""


def find_executable(name: str) -> str | None:
    path = shutil.which(name)
    if path:
        return path

    for directory in ("/usr/local/bin", "/usr/bin", "/bin"):
        candidate = Path(directory, name)
        try:
            if candidate.is_file() and os.access(candidate, os.X_OK):
                return str(candidate)
        except OSError:
            continue
    return None


def read_input(prompt: str) -> str | None:
    try:
        return input(prompt).strip()
    except EOFError:
        return None


def confirm(prompt: str, default: bool = False) -> bool:
    answer = read_input(prompt)
    if answer is None:
        return default
    if not answer:
        return default
    return answer.lower() in {"y", "yes"}


class ParsedTarget(NamedTuple):
    user: str | None
    host: str
    port: int
    remote_path: str
    raw_input: str

    @property
    def sshfs_target_spec(self) -> str:
        prefix = f"{self.user}@" if self.user else ""
        path = self.remote_path if self.remote_path else "/"
        return f"{prefix}{self.host}:{path}"

    @property
    def canonical_string(self) -> str:
        prefix = f"{self.user}@" if self.user else ""
        path_part = self.remote_path if self.remote_path else "/"
        if self.port != 22:
            if path_part.startswith("/"):
                return f"ssh://{prefix}{self.host}:{self.port}{path_part}"
            else:
                return f"{prefix}{self.host}:{self.port}:{path_part}"
        else:
            return f"{prefix}{self.host}:{path_part}"


class ActiveMount(NamedTuple):
    source: str
    mount_point: Path
    fstype: str


def parse_target(raw: str) -> ParsedTarget | None:
    """
    Validate and parse an SSH target string into a structured ParsedTarget.

    Accepted forms:
      - user@host (defaults to port 22, remote root directory /)
      - host (defaults to port 22, remote root directory /)
      - user@host: (remote root directory /)
      - user@host:/path (remote path)
      - user@host:2222 (port 2222, remote root directory /)
      - user@host:2222/path or user@host:2222:/path (port 2222, remote path)
      - ssh://[user@]host[:port][/path] (URI format)
    """
    target = raw.strip()
    if not target or target.startswith("-") or not target.isprintable():
        return None
    if any(ch in target for ch in "\r\n\t\v\f"):
        return None

    # Handle ssh:// style target
    if target.lower().startswith("ssh://"):
        rest = target[6:]
        if not rest:
            return None
        parts = rest.split("/", 1)
        authority = parts[0]
        remote_path = "/" + parts[1] if len(parts) > 1 else "/"
        if not authority:
            return None

        if "@" in authority:
            user, hostport = authority.rsplit("@", 1)
            if not user or ":" in user or "@" in user or "/" in user:
                return None
        else:
            user, hostport = None, authority

        if hostport.startswith("["):
            bracket_end = hostport.find("]")
            if bracket_end == -1:
                return None
            host = hostport[: bracket_end + 1]
            port_part = hostport[bracket_end + 1 :]
            port_str = port_part[1:] if port_part.startswith(":") else "22"
        elif ":" in hostport:
            host, port_str = hostport.rsplit(":", 1)
        else:
            host, port_str = hostport, "22"

        if not host or host.startswith("-"):
            return None

        try:
            port = int(port_str or 22)
            if not (1 <= port <= 65535):
                return None
        except ValueError:
            return None

        return ParsedTarget(
            user=user,
            host=host,
            port=port,
            remote_path=remote_path,
            raw_input=target,
        )

    # Standard / scp / user-friendly syntax
    user = None
    if "@" in target:
        user, rest = target.rsplit("@", 1)
        if not user or user.startswith("-") or ":" in user or "@" in user or "/" in user:
            return None
    else:
        rest = target

    if rest.startswith("["):
        bracket_end = rest.find("]")
        if bracket_end == -1:
            return None
        host = rest[: bracket_end + 1]
        after_host = rest[bracket_end + 1 :]
        if after_host.startswith(":"):
            after_host = after_host[1:]
    elif ":" in rest:
        host, after_host = rest.split(":", 1)
    else:
        host = rest
        after_host = ""

    if not host or host.startswith("-") or "/" in host or "@" in host:
        return None

    if not after_host:
        port = 22
        remote_path = "/"
    elif after_host.isdigit():
        port = int(after_host)
        if not (1 <= port <= 65535):
            return None
        remote_path = "/"
    elif ":" in after_host:
        parts = after_host.split(":", 1)
        if not parts[0].isdigit():
            return None
        port = int(parts[0])
        if not (1 <= port <= 65535):
            return None
        remote_path = parts[1] or "/"
    else:
        m = re.match(r"^(\d+)/(.*)$", after_host)
        if m and (1 <= int(m.group(1)) <= 65535):
            port = int(m.group(1))
            remote_path = "/" + m.group(2)
        else:
            port = 22
            remote_path = after_host or "/"

    return ParsedTarget(
        user=user,
        host=host,
        port=port,
        remote_path=remote_path,
        raw_input=target,
    )


def derive_mount_point(target: ParsedTarget, custom_path: str | None = None) -> Path:
    """Derive local mount path for a target."""
    if custom_path and custom_path.strip():
        c = custom_path.strip()
        p = Path(c).expanduser()
        if not p.is_absolute():
            return BASE_MOUNT_DIR / c
        return p

    host_clean = re.sub(r"[^\w.-]", "_", target.host)
    user_prefix = f"{target.user}_" if target.user and target.user != os.environ.get("USER") else ""

    path_clean = ""
    if target.remote_path and target.remote_path != "/":
        path_clean = "_" + re.sub(r"[^\w.-]", "_", target.remote_path.strip("/"))

    dir_name = f"{user_prefix}{host_clean}{path_clean}".strip("_")
    if not dir_name:
        dir_name = "default"

    return BASE_MOUNT_DIR / dir_name


def normalize_target(raw: str) -> str | None:
    parsed = parse_target(raw)
    return parsed.canonical_string if parsed else None


def _unescape_proc_field(field: bytes) -> bytes:
    """Unescape octal sequences from /proc/mounts fields."""
    out = bytearray()
    i = 0
    while i < len(field):
        if field[i] == 0x5C and i + 4 <= len(field):
            digits = field[i + 1 : i + 4]
            if all(0x30 <= b <= 0x37 for b in digits):
                value = int(digits.decode("ascii"), 8)
                if value <= 0xFF:
                    out.append(value)
                    i += 4
                    continue
        out.append(field[i])
        i += 1
    return bytes(out)


def _mount_entries() -> Iterator[tuple[str, str, str]]:
    """Yield (source, target, fstype) from /proc/mounts."""
    try:
        with open("/proc/mounts", "rb") as handle:
            for line in handle:
                fields = line.rstrip(b"\n").split(b" ")
                if len(fields) < 3:
                    continue

                source = os.fsdecode(_unescape_proc_field(fields[0]))
                target = os.fsdecode(_unescape_proc_field(fields[1]))
                fstype = os.fsdecode(_unescape_proc_field(fields[2]))
                yield source, target, fstype
    except OSError:
        return


def get_active_mounts() -> list[ActiveMount]:
    """Return all active SSHFS mounts under BASE_MOUNT_DIR or mounted by sshfs."""
    active: list[ActiveMount] = []
    base_str = os.path.normpath(str(BASE_MOUNT_DIR))
    for source, target, fstype in _mount_entries():
        if fstype == "fuse.sshfs" or fstype.startswith("fuse."):
            norm_target = os.path.normpath(target)
            if norm_target == base_str or norm_target.startswith(base_str + os.sep):
                active.append(ActiveMount(source, Path(target), fstype))
    return active


def get_mount_info_for(mount_point: Path) -> tuple[str, str] | None:
    """Return (source, fstype) if mount_point is currently mounted."""
    wanted = os.path.normpath(str(mount_point))
    for source, target, fstype in _mount_entries():
        if os.path.normpath(target) == wanted:
            return source, fstype
    return None


def cleanup_stale_mount(mount_point: Path) -> bool:
    """Attempt a lazy unmount to clean up stale/broken FUSE mounts."""
    fusermount = find_executable("fusermount3")
    if not fusermount:
        return False
    with contextlib.suppress(OSError):
        subprocess.run(
            [fusermount, "-u", "-z", str(mount_point)],
            check=False,
            text=True,
            capture_output=True,
        )
    return wait_until_unmounted(mount_point, timeout=2.0)


def state_destination() -> Path:
    """Preserve symlinks on STATE_FILE."""
    if STATE_FILE.is_symlink():
        try:
            return STATE_FILE.resolve(strict=False)
        except OSError:
            return STATE_FILE
    return STATE_FILE


def write_state(history: list[str]) -> None:
    """Atomically write state JSON."""
    destination = state_destination()
    text = json.dumps({"history": history}, indent=4, ensure_ascii=False) + "\n"

    fd, tmp_name = tempfile.mkstemp(
        prefix=destination.name + ".",
        suffix=".tmp",
        dir=destination.parent,
    )
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as handle:
            handle.write(text)
            handle.flush()
            os.fsync(handle.fileno())

        os.chmod(tmp_name, 0o600)
        os.replace(tmp_name, destination)
    except BaseException:
        with contextlib.suppress(OSError):
            os.unlink(tmp_name)
        raise

    with contextlib.suppress(OSError):
        dir_fd = os.open(destination.parent, os.O_DIRECTORY)
        try:
            os.fsync(dir_fd)
        finally:
            os.close(dir_fd)


def load_state() -> list[str]:
    """Load history from STATE_FILE."""
    try:
        raw = STATE_FILE.read_text(encoding="utf-8")
    except FileNotFoundError:
        return []
    except (OSError, UnicodeDecodeError) as exc:
        print(f"[!] Cannot read state file: {exc}", file=sys.stderr)
        return []

    try:
        data = json.loads(raw)
    except json.JSONDecodeError as exc:
        print(f"[!] State file is corrupt; starting with empty history ({exc}).", file=sys.stderr)
        return []

    if isinstance(data, dict):
        history = data.get("history", [])
    elif isinstance(data, list):
        history = data
    else:
        history = []

    if not isinstance(history, list):
        return []

    cleaned: list[str] = []
    for item in history:
        if not isinstance(item, str):
            continue
        normalized = normalize_target(item)
        if normalized and normalized not in cleaned:
            cleaned.append(normalized)

    return cleaned[:MAX_HISTORY]


def save_state(history: list[str], new_entry: str | None = None) -> list[str]:
    """Deduplicate, trim to MAX_HISTORY, and atomically save."""
    cleaned: list[str] = []
    candidates: list[str] = []

    if new_entry is not None:
        candidates.append(new_entry)
    candidates.extend(history)

    for item in candidates:
        normalized = normalize_target(item) if isinstance(item, str) else None
        if normalized and normalized not in cleaned:
            cleaned.append(normalized)

    cleaned = cleaned[:MAX_HISTORY]
    write_state(cleaned)
    return cleaned


def update_history(history: list[str], target: str) -> list[str]:
    try:
        return save_state(history, target)
    except OSError as exc:
        print(f"[!] Could not save state: {exc}", file=sys.stderr)
        hint = root_hint(state_destination()) or root_hint(state_destination().parent)
        if hint:
            print(hint, file=sys.stderr)
        return history


def ensure_state_file() -> None:
    if not state_destination().exists():
        try:
            write_state([])
        except OSError as exc:
            fail(f"Cannot create state file {STATE_FILE}: {exc}{root_hint(STATE_FILE.parent)}")


def ensure_directories() -> None:
    if not STATE_FILE.is_absolute() or not BASE_MOUNT_DIR.is_absolute():
        fail("State and mount paths must be absolute. Check HOME.")

    try:
        STATE_FILE.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    except OSError as exc:
        fail(f"Cannot create state directory {STATE_FILE.parent}: {exc}{root_hint(STATE_FILE.parent)}")

    destination = state_destination()

    if destination.is_dir():
        fail(f"{destination} is a directory; expected a state file.")

    if not os.access(destination.parent, os.W_OK | os.X_OK):
        fail(f"State directory {destination.parent} is not writable.{root_hint(destination.parent)}")

    if destination.exists() and not os.access(destination, os.R_OK | os.W_OK):
        fail(f"State file {destination} is not readable/writable.{root_hint(destination)}")

    try:
        BASE_MOUNT_DIR.mkdir(parents=True, exist_ok=True, mode=0o700)
    except OSError as exc:
        if exc.errno in (errno.ENOTCONN, errno.EBUSY):
            cleanup_stale_mount(BASE_MOUNT_DIR)
        else:
            fail(f"Cannot create base mount directory {BASE_MOUNT_DIR}: {exc}{root_hint(BASE_MOUNT_DIR.parent)}")


def install_package(package: str) -> bool:
    pacman = find_executable("pacman")
    if not pacman:
        print("[-] pacman not found.", file=sys.stderr)
        return False

    base: list[str] | None = None

    if os.geteuid() == 0:
        base = []
    else:
        for escalator in ("sudo", "doas", "run0"):
            path = find_executable(escalator)
            if path:
                base = [path]
                break

    if base is None:
        print(
            f"[-] No privilege command found (sudo/doas/run0). Install '{package}' manually.",
            file=sys.stderr,
        )
        return False

    cmd = base + [pacman, "-S", "--noconfirm", "--noprogressbar", package]

    print(f"[*] Installing '{package}' via pacman...")
    try:
        subprocess.run(cmd, check=True)
        return True
    except subprocess.CalledProcessError as exc:
        print(f"[-] pacman failed with exit code {exc.returncode}.", file=sys.stderr)
        if Path("/var/lib/pacman/db.lck").exists():
            print("    Hint: Pacman appears to be locked by another process.", file=sys.stderr)
        return False
    except OSError as exc:
        print(f"[-] Failed to run pacman: {exc}", file=sys.stderr)
        return False


def ensure_unmount_dependencies() -> bool:
    if find_executable("fusermount3"):
        return True

    print("[-] fusermount3 not found. Installing 'fuse3'...")
    if not install_package("fuse3"):
        return False

    return bool(find_executable("fusermount3"))


def ensure_mount_dependencies() -> bool:
    requirements = (
        ("sshfs", "sshfs"),
        ("fusermount3", "fuse3"),
        ("ssh", "openssh"),
    )

    for binary, package in requirements:
        if find_executable(binary):
            continue

        print(f"[-] '{binary}' not found. Installing '{package}'...")
        if not install_package(package):
            return False

        if not find_executable(binary):
            print(f"[-] '{binary}' is still missing after installing '{package}'.", file=sys.stderr)
            return False

    return True


def check_fuse_device() -> bool:
    fuse = Path("/dev/fuse")

    if not fuse.exists():
        print(
            "[-] /dev/fuse is missing. Install fuse3 and ensure the fuse kernel module is loaded.",
            file=sys.stderr,
        )
        return False

    if os.geteuid() != 0 and not os.access(fuse, os.R_OK | os.W_OK):
        print("[-] /dev/fuse is not accessible by your user.", file=sys.stderr)
        return False

    return True


def wait_until_unmounted(mount_point: Path, timeout: float = 2.0) -> bool:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if get_mount_info_for(mount_point) is None:
            return True
        time.sleep(0.1)
    return get_mount_info_for(mount_point) is None


def mount_appeared(mount_point: Path) -> bool:
    if get_mount_info_for(mount_point) is not None:
        return True

    if mount_point.is_symlink():
        with contextlib.suppress(OSError):
            return os.path.ismount(mount_point)

    return False


def wait_until_mounted(mount_point: Path, timeout: float = 5.0) -> bool:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if mount_appeared(mount_point):
            return True
        time.sleep(0.1)
    return mount_appeared(mount_point)


def unmount(
    target_path: Path | str | None = None,
    *,
    all_mounts: bool = False,
    lazy: bool = False,
    interactive: bool = False,
) -> bool:
    if all_mounts:
        mounts = get_active_mounts()
        if not mounts:
            print("[*] No active SSHFS connections to unmount.")
            return True
        success = True
        for m in mounts:
            print(f"[*] Unmounting {m.mount_point} ({m.source})...")
            if not unmount(m.mount_point, lazy=lazy, interactive=False):
                success = False
        return success

    if target_path is None:
        mounts = get_active_mounts()
        if not mounts:
            print("[*] Directory is not currently mounted.")
            return True

        if len(mounts) == 1:
            target_path = mounts[0].mount_point
        elif interactive:
            print("\nActive SSHFS Mounts:")
            for i, m in enumerate(mounts, 1):
                print(f"  {i}. {m.source} -> {m.mount_point}")
            print(f"  {len(mounts) + 1}. Unmount ALL connections")

            raw = read_input(f"Select connection to unmount (1-{len(mounts) + 1}) [1]: ")
            if raw is None:
                return False
            if raw == "" or raw == "1":
                target_path = mounts[0].mount_point
            elif raw == str(len(mounts) + 1) or raw.lower() in ("all", "a"):
                return unmount(all_mounts=True, lazy=lazy, interactive=False)
            else:
                try:
                    idx = int(raw)
                    if 1 <= idx <= len(mounts):
                        target_path = mounts[idx - 1].mount_point
                    else:
                        print("[-] Invalid selection.")
                        return False
                except ValueError:
                    print("[-] Invalid selection.")
                    return False
        else:
            target_path = mounts[0].mount_point

    target_p = Path(target_path).expanduser().resolve()
    info = get_mount_info_for(target_p)

    if info is None:
        fusermount = find_executable("fusermount3")
        if fusermount:
            with contextlib.suppress(OSError):
                subprocess.run(
                    [fusermount, "-u", str(target_p)],
                    check=False,
                    text=True,
                    capture_output=True,
                )
            if wait_until_unmounted(target_p):
                print("[+] Unmounted successfully.")
                return True
        print(f"[*] {target_p} is not currently mounted.")
        return True

    source, fstype = info

    if not (fstype == "fuse" or fstype.startswith("fuse.")):
        print(
            f"[-] {target_p} is mounted as '{fstype}', not FUSE. Refusing to unmount.",
            file=sys.stderr,
        )
        return False

    fusermount = find_executable("fusermount3")
    if not fusermount:
        if not ensure_unmount_dependencies():
            return False
        fusermount = find_executable("fusermount3")
        if not fusermount:
            return False

    cmd = [fusermount, "-u"]
    if lazy:
        cmd.append("-z")
    cmd.append(str(target_p))

    action = "Lazily unmounting" if lazy else "Unmounting"
    print(f"[*] {action} {target_p} ({source})...")

    try:
        proc = subprocess.run(cmd, check=False, text=True, capture_output=True)
    except OSError as exc:
        print(f"[-] Failed to run fusermount3: {exc}", file=sys.stderr)
        return False

    if proc.returncode == 0:
        if wait_until_unmounted(target_p):
            print("[+] Unmounted successfully.")
            return True
        print("[-] Unmount command succeeded but the mount is still present.", file=sys.stderr)
        return False

    if not lazy:
        return unmount(target_p, lazy=True, interactive=interactive)

    output = (proc.stderr or proc.stdout or "").strip()
    if output:
        print(output, file=sys.stderr)
    return False


def mount(raw_target: str, custom_mount_path: str | None = None) -> bool:
    parsed = parse_target(raw_target)
    if parsed is None:
        print(
            "[-] Invalid target. Accepted forms: user@host, host, user@host:/path, user@host:port, or ssh://user@host[:port]/path.",
            file=sys.stderr,
        )
        return False

    mount_point = derive_mount_point(parsed, custom_mount_path)
    target_spec = parsed.sshfs_target_spec
    canonical = parsed.canonical_string

    info = get_mount_info_for(mount_point)
    if info is not None:
        is_healthy = False
        with contextlib.suppress(OSError):
            is_healthy = mount_point.is_dir() and os.access(mount_point, os.R_OK)

        if not is_healthy:
            print(f"[!] Existing mount at {mount_point} ({info[0]}) is unresponsive or broken. Cleaning up...")
            cleanup_stale_mount(mount_point)
        elif info[0] == target_spec or info[0] == canonical:
            print(f"[*] {mount_point} is already mounted to {canonical}.")
            return True
        else:
            print(f"[*] {mount_point} is currently mounted to {info[0]}. Unmounting to switch target...")
            if not unmount(mount_point, interactive=False):
                print("[-] Cannot mount while the existing mount is active.", file=sys.stderr)
                return False

    extra_options: list[str] = []
    if parsed.port != 22:
        extra_options.extend(["-p", str(parsed.port)])

    try:
        if not mount_point.is_symlink():
            mount_point.mkdir(parents=True, exist_ok=True, mode=0o700)

            if not mount_point.is_dir():
                print(f"[-] {mount_point} exists and is not a directory.", file=sys.stderr)
                return False

            try:
                if any(mount_point.iterdir()):
                    if not confirm(
                        f"[!] {mount_point} is not empty. Mounting will hide existing files. Continue? [y/N]: ",
                        default=False,
                    ):
                        print("[*] Mount cancelled.")
                        return False

                    extra_options.extend(("-o", "nonempty"))
            except OSError as exc:
                if exc.errno in (errno.ENOTCONN, errno.EBUSY):
                    print("[!] Stale mount detected. Attempting unmount...")
                    if not cleanup_stale_mount(mount_point):
                        print(f"[-] Stale mount cleanup failed: {exc}", file=sys.stderr)
                        return False
                else:
                    print(f"[-] Cannot inspect mountpoint: {exc}", file=sys.stderr)
                    return False
    except OSError as exc:
        if exc.errno in (errno.ENOTCONN, errno.EBUSY):
            print("[!] Stale mount detected on directory creation. Attempting cleanup...")
            cleanup_stale_mount(mount_point)
        else:
            print(f"[-] Cannot inspect mountpoint: {exc}", file=sys.stderr)
            return False

    if not ensure_mount_dependencies():
        return False

    if not check_fuse_device():
        return False

    sshfs = find_executable("sshfs")
    if not sshfs:
        print("[-] sshfs is missing.", file=sys.stderr)
        return False

    if mount_point.is_symlink():
        cleanup_stale_mount(mount_point)

    options = list(SSHFS_OPTIONS)

    if "SSHPASS" in os.environ and find_executable("sshpass"):
        options.append("ssh_command=sshpass -e ssh")

    cmd = [sshfs]
    for option in options:
        cmd.extend(("-o", option))

    if parsed.port != 22:
        cmd.extend(("-p", str(parsed.port)))

    if "nonempty" in extra_options:
        cmd.extend(("-o", "nonempty"))

    cmd.extend((target_spec, str(mount_point)))

    print(f"[*] Mounting {canonical} at {mount_point}...")

    try:
        proc = subprocess.run(
            cmd,
            check=False,
            text=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.PIPE,
        )
        if proc.returncode != 0:
            err = (proc.stderr or "").strip()
            print(
                f"[-] Mounting failed (exit code {proc.returncode}). "
                "Verify target, remote path, SSH credentials, and server SFTP access.",
                file=sys.stderr,
            )
            if err:
                print(f"    {err}", file=sys.stderr)
            return False
    except OSError as exc:
        print(f"[-] Failed to run sshfs: {exc}", file=sys.stderr)
        return False

    if wait_until_mounted(mount_point):
        print(f"[+] Successfully mounted. Access files at {mount_point}")
        return True

    print("[-] sshfs exited successfully but the mount did not appear.", file=sys.stderr)
    return False


def select_remote_user(parsed: ParsedTarget) -> ParsedTarget | None:
    default_user = parsed.user or os.environ.get("USER", "user")
    print("\nSelect remote account:")
    print(f"1. Normal user ({default_user}) [default]")
    print("2. Root (root)")

    choice = read_input(f"Select account (1/2) [{default_user}]: ")
    if choice is None:
        return None

    choice_str = choice.strip().lower()
    if choice_str in ("2", "root", "r"):
        selected_user = "root"
    elif choice_str in ("1", ""):
        selected_user = default_user
    else:
        selected_user = choice.strip()

    return ParsedTarget(
        user=selected_user,
        host=parsed.host,
        port=parsed.port,
        remote_path=parsed.remote_path,
        raw_input=parsed.raw_input,
    )


def print_usage() -> None:
    print("=== SSHFS Remote Manager ===")
    print("\nUsage:")
    print("  dusky_ssh_filesystem.py [TARGET] [MOUNT_PATH]  Mount target directly")
    print("  dusky_ssh_filesystem.py -u | --unmount [PATH|all] Unmount connection(s)")
    print("  dusky_ssh_filesystem.py -s | --status         Show all active mounts")
    print("  dusky_ssh_filesystem.py -h | --help           Show this help message")
    print("\nExamples:")
    print("  dusky_ssh_filesystem.py user@host")
    print("  dusky_ssh_filesystem.py root@host /home/dusk/Documents/sshfs/server1")
    print("  dusky_ssh_filesystem.py -u all")


def main() -> int:
    ensure_directories()
    history = load_state()
    ensure_state_file()

    # CLI mode
    if len(sys.argv) > 1:
        arg = sys.argv[1].strip()
        if arg in ("-h", "--help"):
            print_usage()
            return 0
        elif arg in ("-u", "--unmount"):
            target_arg = sys.argv[2].strip() if len(sys.argv) > 2 else None
            if target_arg and target_arg.lower() in ("all", "a"):
                return 0 if unmount(all_mounts=True, interactive=False) else 1
            elif target_arg:
                return 0 if unmount(target_path=target_arg, interactive=False) else 1
            else:
                return 0 if unmount(interactive=False) else 1
        elif arg in ("-s", "--status"):
            active = get_active_mounts()
            if active:
                print(f"Active SSHFS Mounts ({len(active)} active):")
                for m in active:
                    print(f"  - {m.source} -> {m.mount_point} ({m.fstype})")
            else:
                print(f"No active mounts under {BASE_MOUNT_DIR}")
            return 0
        else:
            parsed = parse_target(arg)
            if not parsed:
                print(f"[-] Invalid target argument: '{arg}'", file=sys.stderr)
                return 1
            custom_path = sys.argv[2].strip() if len(sys.argv) > 2 else None
            if mount(parsed.canonical_string, custom_path):
                update_history(history, parsed.canonical_string)
                return 0
            return 1

    print("=== SSHFS Remote Manager ===")

    while True:
        active = get_active_mounts()
        if active:
            print(f"\nActive SSHFS Mounts ({len(active)} active):")
            for i, m in enumerate(active, 1):
                print(f"  {i}. {m.source} -> {m.mount_point}")
        else:
            print(f"\nNo active mounts in {BASE_MOUNT_DIR}")

        menu: list[tuple[str, str]] = [
            ("1", "Connect to a new server (mount alongside existing connections)")
        ]
        if history:
            menu.append(("2", "Connect to a recently used server"))
        if active:
            menu.append(("3", "Unmount a connection"))
        else:
            menu.append(("3", "Unmount connection"))
        menu.append(("4", "Exit"))

        print("\nOptions:")
        for key, label in menu:
            default_str = " [default]" if key == "1" else ""
            print(f"{key}. {label}{default_str}")

        choice = read_input(f"\nSelect an option ({'/'.join(key for key, _ in menu)}) [1]: ")
        if choice is None:
            print("\n[*] Exiting...")
            break

        if choice == "":
            choice = "1"
        else:
            choice = choice.lower()
            if choice.isdecimal():
                choice = str(int(choice))

        match choice:
            case "1":
                prompt_default = f" [{history[0]}]" if history else ""
                target_raw = read_input(
                    f"Enter SSH target (e.g., user@host, host:/path, or user@host:port){prompt_default}: "
                )
                if target_raw is None:
                    print("\n[*] Exiting...")
                    break

                if not target_raw:
                    if history:
                        target_raw = history[0]
                        print(f"[*] Defaulting to most recent: {target_raw}")
                    else:
                        print("[*] No target entered. Returning to menu.")
                        continue

                parsed = parse_target(target_raw)
                if parsed is None:
                    print(
                        "[-] Invalid target. Examples: user@host, host, user@host:/path, user@host:port, or ssh://user@host[:port]/path.",
                        file=sys.stderr,
                    )
                    continue

                parsed_with_user = select_remote_user(parsed)
                if parsed_with_user is None:
                    print("\n[*] Exiting...")
                    break

                default_dir = derive_mount_point(parsed_with_user)
                folder_input = read_input(f"Enter local mount path [{default_dir}]: ")
                custom_path = folder_input.strip() if folder_input and folder_input.strip() else None

                if mount(parsed_with_user.canonical_string, custom_path):
                    history = update_history(history, parsed_with_user.canonical_string)

            case "2" if history:
                print("\nRecent connections:")
                for i, entry in enumerate(history, 1):
                    default_str = " [default]" if i == 1 else ""
                    print(f"  {i}. {entry}{default_str}")

                raw = read_input(f"Select connection (1-{len(history)}) [1]: ")
                if raw is None:
                    print("\n[*] Exiting...")
                    break

                if raw == "":
                    index = 1
                else:
                    try:
                        index = int(raw)
                    except ValueError:
                        print("[-] Invalid selection.")
                        continue

                if not 1 <= index <= len(history):
                    print("[-] Invalid selection.")
                    continue

                target = history[index - 1]
                parsed = parse_target(target)
                if parsed is None:
                    print("[-] Invalid entry in history.")
                    continue

                parsed_with_user = select_remote_user(parsed)
                if parsed_with_user is None:
                    print("\n[*] Exiting...")
                    break

                default_dir = derive_mount_point(parsed_with_user)
                folder_input = read_input(f"Enter local mount path [{default_dir}]: ")
                custom_path = folder_input.strip() if folder_input and folder_input.strip() else None

                if mount(parsed_with_user.canonical_string, custom_path):
                    history = update_history(history, parsed_with_user.canonical_string)

            case "3":
                unmount(interactive=True)

            case "4" | "q" | "quit" | "exit":
                print("[*] Exiting...")
                break

            case _:
                print("[-] Invalid option. Please enter a valid number.")

    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        print("\n[*] Exiting...")
        sys.exit(0)
    except BrokenPipeError:
        with contextlib.suppress(OSError):
            sys.stdout.close()
        sys.exit(0)
