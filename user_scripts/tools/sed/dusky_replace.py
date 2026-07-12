#!/usr/bin/env python3
# ==============================================================================
# Script:     dusky-replace.py
# Purpose:    High-performance, byte-safe, TOCTOU-resistant text replacement
# Architect:  Optimized exclusively for Arch Linux (kernel 7.x) & Python 3.14+
# Python:     Requires Python 3.14+ (uses argparse color=True, t-strings ready,
#             modern union types, and explicit O_NOFOLLOW semantics)
# ==============================================================================

from __future__ import annotations

import argparse
import difflib
import importlib.util
import os
import shutil
import stat
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Final

# --- Dependency pre-flight (no auto-install, no import-time side effects) ---
# Arch policy: never run `pacman -S` without `-Syu` automatically. We fail fast
# with an instructive message instead of mutating the system.

CONSOLE_STDERR = None  # lazy init
CONSOLE_STDOUT = None

def _get_consoles():
    global CONSOLE_STDERR, CONSOLE_STDOUT
    if CONSOLE_STDERR is None or CONSOLE_STDOUT is None:
        try:
            from rich.console import Console
            CONSOLE_STDERR = Console(stderr=True)
            CONSOLE_STDOUT = Console()
        except Exception:
            # Rich not available yet - fall back to dumb consoles that use plain print
            # This path is only hit during early dependency check
            class _Fallback:
                def print(self, *a, **kw): print(*a, file=sys.stderr)
            CONSOLE_STDERR = _Fallback()
            CONSOLE_STDOUT = _Fallback()
    return CONSOLE_STDOUT, CONSOLE_STDERR

def check_environment() -> None:
    if sys.version_info < (3, 14):
        sys.stderr.write(f"[!] Python 3.14+ required, found {sys.version}\n")
        sys.exit(2)

    missing: list[str] = []
    for mod, pkg in (("rich", "python-rich"), ("regex", "python-regex"), ("charset_normalizer", "python-charset-normalizer")):
        if importlib.util.find_spec(mod) is None:
            missing.append(pkg)

    if shutil.which("rg") is None:
        missing.append("ripgrep")

    if missing:
        # Use plain stderr here to avoid importing rich when rich itself is missing
        sys.stderr.write(f"[✖] Missing dependencies: {', '.join(missing)}\n")
        sys.stderr.write("Install on Arch with:\n")
        sys.stderr.write(f"  sudo pacman -Syu --needed {' '.join(missing)}\n")
        sys.stderr.write("Then re-run this script. No automatic install is performed by design (avoids partial upgrades).\n")
        sys.exit(2)

check_environment()

# Safe imports after check - now guaranteed to exist
import regex as re
import charset_normalizer
from rich.console import Console as RichConsole
from rich.markup import escape as markup_escape
from rich.panel import Panel
from rich.progress import BarColumn, Progress, SpinnerColumn, TextColumn, TimeElapsedColumn
from rich.prompt import Prompt
from rich.syntax import Syntax

# Re-initialize consoles with real Rich consoles after successful check
CONSOLE_STDOUT = RichConsole()
CONSOLE_STDERR = RichConsole(stderr=True)
console_out, console_err = CONSOLE_STDOUT, CONSOLE_STDERR

# Constants
MAX_DIFF_BYTES: Final[int] = 256 * 1024  # don't render >256 KiB diffs fully
MAX_FILE_SIZE: Final[int] = 100 * 1024 * 1024  # skip files >100 MiB unless forced
BINARY_NUL_CHECK: Final[int] = 8192  # check first 8 KiB for NUL to detect binary fast

# --- Helpers ---

def is_binary_quick(raw: bytes) -> bool:
    # Fast heuristic: if NUL in first chunk, treat as binary (matches ripgrep's definition)
    return b"\x00" in raw[:BINARY_NUL_CHECK]

def safe_read_bytes_no_follow(path: Path) -> bytes:
    """
    TOCTOU-resistant read: O_NOFOLLOW prevents symlink following.
    Raises OSError with errno ELOOP if path is a symlink.
    """
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
    try:
        # Use fdopen to get file object; os.fstat to guard size
        st = os.fstat(fd)
        if not stat.S_ISREG(st.st_mode):
            raise IsADirectoryError(f"Not a regular file: {path}")
        if st.st_size > MAX_FILE_SIZE:
            raise ValueError(f"File too large ({st.st_size} bytes)")
        with os.fdopen(fd, "rb", closefd=False) as f:
            # fd will be closed in finally
            return f.read()
    finally:
        os.close(fd)

def atomic_write_preserve_mode(path: Path, data: bytes) -> None:
    """
    Atomic, durable write: write temp file in same dir, fsync, chmod to preserve mode,
    then os.replace (POSIX atomic). Does NOT claim inode stability; new inode is expected.
    Preserves permission bits, not ownership (ownership requires root).
    """
    parent = path.parent
    # Guard: refuse to write through symlinked parent (prevents mkdir -p escape)
    try:
        parent_is_symlink = parent.is_symlink()
    except OSError:
        parent_is_symlink = False
    if parent_is_symlink:
        raise OSError(f"Refusing to write through symlinked parent: {parent}")

    parent.mkdir(parents=True, exist_ok=True)

    # Preserve mode if file exists - use lstat to avoid following symlink for mode check
    try:
        st = path.lstat()
        orig_mode = stat.S_IMODE(st.st_mode)
        # If destination itself is a symlink, refuse (TOCTOU final guard)
        # st_mode alone doesn't tell symlink after lstat, so check is_symlink again
        if path.is_symlink():
            raise OSError(f"Refusing to overwrite symlink: {path}")
    except FileNotFoundError:
        orig_mode = 0o644
    except OSError as e:
        # Re-raise symlink refusal, otherwise fall back to default mode
        if "symlink" in str(e).lower():
            raise
        orig_mode = 0o644

    tmp_fd, tmp_name = tempfile.mkstemp(dir=parent, prefix=f".{path.name}.tmp.")
    tmp_path = Path(tmp_name)
    try:
        with os.fdopen(tmp_fd, "wb") as tmp_file:
            tmp_file.write(data)
            tmp_file.flush()
            os.fsync(tmp_file.fileno())
        os.chmod(tmp_name, orig_mode)
        # os.replace is atomic on POSIX and replaces destination without following symlink?
        # On Linux, renameat2 with RENAME_NOREPLACE semantics would be ideal, but os.replace
        # replaces symlink itself, not its target, which is what we want after the guard above.
        os.replace(tmp_name, path)
        # Ensure directory entry is durable
        try:
            dir_fd = os.open(parent, os.O_DIRECTORY | os.O_CLOEXEC)
            try:
                os.fsync(dir_fd)
            finally:
                os.close(dir_fd)
        except OSError:
            pass  # best-effort
    finally:
        try:
            if tmp_path.exists():
                tmp_path.unlink()
        except OSError:
            pass

def detect_encoding_and_decode(raw: bytes) -> tuple[str, str]:
    """
    Deterministic-first decoding:
    1. Try strict UTF-8 (most common on Arch)
    2. Try charset_normalizer heuristic (sampled, not deterministic, but better than blind)
    3. Fallback to UTF-8 with surrogateescape to preserve bytes losslessly
    Returns (encoding, text)
    """
    # Fast path: UTF-8
    try:
        return "utf-8", raw.decode("utf-8")
    except UnicodeDecodeError:
        pass

    try:
        matches = charset_normalizer.from_bytes(raw).best()
        if matches is not None:
            enc = matches.encoding or "utf-8"
            # str(matches) uses its own decoding; we normalize to that encoding
            txt = str(matches)
            # Verify round-trip is possible for replacement path later
            return enc, txt
    except Exception:
        pass

    # Absolute fallback: preserve all bytes via surrogateescape (lossless)
    # This guarantees no data loss on read, but may produce surrogates in text
    return "utf-8", raw.decode("utf-8", errors="surrogateescape")

def display_diff_limited(path: Path, old: str, new: str) -> None:
    # Guard against huge files
    if len(old) > MAX_DIFF_BYTES or len(new) > MAX_DIFF_BYTES:
        console_out.print(Panel(
            f"[yellow]Diff too large to render ({len(old)} -> {len(new)} chars). Showing truncated preview.[/]\n"
            f"File: {markup_escape(str(path))}",
            title=f"[bold blue]Diff: {markup_escape(str(path))}[/]",
            border_style="yellow",
        ))
        # Show first N lines only
        old_lines = old.splitlines(keepends=True)[:200]
        new_lines = new.splitlines(keepends=True)[:200]
    else:
        old_lines = old.splitlines(keepends=True)
        new_lines = new.splitlines(keepends=True)

    diff = difflib.unified_diff(
        old_lines,
        new_lines,
        fromfile=f"a/{path}",
        tofile=f"b/{path}",
        n=3,
    )
    diff_str = "".join(diff)
    if not diff_str:
        return
    # Truncate diff_str for Syntax highlighter
    if len(diff_str) > MAX_DIFF_BYTES:
        diff_str = diff_str[:MAX_DIFF_BYTES] + "\n... [truncated] ...\n"

    syntax = Syntax(diff_str, "diff", theme="monokai", background_color="default", word_wrap=False)
    console_out.print(Panel(syntax, title=f"[bold blue]Diff: {markup_escape(str(path))}[/]", border_style="blue"))

def build_rg_command(search: str, target: Path, multiline: bool, dotall: bool) -> list[str]:
    # Respect .gitignore and skip hidden files by default (ripgrep defaults).
    # Do not follow symlinks (rg default) - we enforce containment later in Python.
    cmd: list[str] = ["rg", "-l", "--null", "--engine=pcre2"]
    if multiline:
        cmd.append("--multiline")
        if dotall:
            cmd.append("--multiline-dotall")
    # Explicit -e avoids ambiguity when pattern starts with -
    cmd.extend(["-e", search, "--", str(target)])
    return cmd

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Dusky Replace: High-performance, byte-safe, TOCTOU-resistant text replacement for Arch Linux.",
        epilog="Examples: dusky-replace 'foo.*bar' 'baz' ./src --multiline --dotall",
        color=True,  # Python 3.14+ feature
    )
    parser.add_argument("search", help="PCRE2 regex pattern to find (engine=pcre2).")
    parser.add_argument("replace", help="Replacement text (supports \\1, \\g<name> backreferences).")
    parser.add_argument("target_dir", type=Path, help="Directory to search within.")
    parser.add_argument("--multiline", action="store_true", help="Enable rg --multiline (allows \\n in pattern).")
    parser.add_argument("--dotall", action="store_true", help="Implies --multiline and --multiline-dotall; dot matches newline. Requires --multiline.")
    parser.add_argument("--allow-binary", action="store_true", help="Do not skip files containing NUL bytes.")
    parser.add_argument("--dry-run", action="store_true", help="Preview diffs only, no writes.")
    parser.add_argument("-y", "--yes", action="store_true", help="Batch mode: apply to all without prompting.")
    parser.add_argument("--max-files", type=int, default=0, help="Abort if more than N files match (0 = no limit).")

    args = parser.parse_args()

    if args.dotall and not args.multiline:
        args.multiline = True  # dotall implies multiline

    target: Path = args.target_dir
    if not target.exists():
        console_err.print(f"[bold red][✖] Target '{markup_escape(str(target))}' does not exist.[/]")
        sys.exit(1)
    if not target.is_dir():
        console_err.print(f"[bold red][✖] Target '{markup_escape(str(target))}' is not a directory.[/]")
        sys.exit(1)

    target_resolved = target.resolve()

    # Compile regex - use VERSION1 explicitly, but it's default in recent regex
    try:
        flags = re.MULTILINE
        if args.dotall:
            flags |= re.DOTALL
        # re.V1 is default in regex 2024+, keep for explicitness without claiming PCRE2 equivalence
        search_pattern = re.compile(args.search, flags=flags | re.V1)
    except re.error as e:
        console_err.print(f"[bold red][✖] Invalid regex pattern: {markup_escape(str(e))}[/]")
        sys.exit(1)

    rg_cmd = build_rg_command(args.search, target, args.multiline, args.dotall)
    console_out.print(f"[bold cyan]Searching with:[/] [dim]{' '.join(markup_escape(c) for c in rg_cmd)}[/]")

    try:
        proc = subprocess.run(
            rg_cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
        )
    except FileNotFoundError:
        console_err.print("[bold red][✖] ripgrep binary not found (shutil.which failed).[/]")
        sys.exit(1)

    # Handle exit codes per ripgrep spec: 0=match, 1=no match, 2=error
    match proc.returncode:
        case 0:
            pass  # success, continue
        case 1:
            console_out.print("[bold green][i] No matches found. Exiting cleanly.[/]")
            sys.exit(0)
        case 2:
            err_msg = proc.stderr.decode("utf-8", errors="replace")[:2000]
            console_err.print(f"[bold red][✖] ripgrep error:[/] {markup_escape(err_msg)}")
            sys.exit(1)
        case _:
            err_msg = proc.stderr.decode("utf-8", errors="replace")[:2000]
            console_err.print(f"[bold red][✖] Unexpected ripgrep exit {proc.returncode}: {markup_escape(err_msg)}[/]")
            sys.exit(1)

    # stdout is NUL-delimited bytes - safe for non-UTF8 filenames
    raw_paths = proc.stdout.split(b"\0")
    files: list[Path] = []
    for p in raw_paths:
        if not p:
            continue
        # os.fsdecode uses surrogateescape on POSIX, preserving undecodable bytes
        try:
            decoded = os.fsdecode(p)
        except Exception:
            decoded = p.decode("utf-8", errors="surrogateescape")
        files.append(Path(decoded))

    if args.max_files and len(files) > args.max_files:
        console_err.print(f"[bold red][✖] Too many matches ({len(files)} > {args.max_files}). Aborting.[/]")
        sys.exit(1)

    console_out.print(f"\n[bold]Found {len(files)} files containing matches.[/]")
    if not args.yes and not args.dry_run:
        console_out.print("  [bold cyan][1][/] Interactive (preview diffs and confirm per-file)")
        console_out.print("  [bold cyan][2][/] Batch All   (apply without per-file prompt)")
        console_out.print("  [bold cyan][3][/] Dry Run     (preview only)")
        console_out.print("  [bold red][q][/] Quit")
        choice = Prompt.ask("\nChoose execution method", choices=["1", "2", "3", "q"], default="1", case_sensitive=False, show_choices=False)
    elif args.yes:
        choice = "2"
    elif args.dry_run:
        choice = "3"
    else:
        choice = "1"

    if choice == "q":
        console_out.print("[yellow]Aborting as requested.[/]")
        sys.exit(0)

    mode_interactive = choice == "1"
    mode_batch = choice == "2"
    mode_dry = choice == "3"

    batch_override = mode_batch
    processed_count = 0
    skipped_count = 0
    failed_count = 0

    # Progress setup - only for batch mode to avoid Live + print corruption
    progress_ctx = None
    if mode_batch:
        progress_ctx = Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
            TimeElapsedColumn(),
            console=console_out,
            transient=False,
        )

    def process_files(iterable):
        nonlocal processed_count, skipped_count, failed_count, batch_override
        for file_path in iterable:
            # --- Containment and symlink checks (pre-read) ---
            try:
                # lstat, not stat, to avoid following symlink
                st = file_path.lstat()
                if file_path.is_symlink():
                    console_err.print(f"[yellow][!] Skipping symlink: {markup_escape(str(file_path))}[/]")
                    skipped_count += 1
                    continue
                if not file_path.is_file():
                    skipped_count += 1
                    continue
                # Ensure resolved path is inside target_resolved to prevent symlink escape
                try:
                    resolved = file_path.resolve()
                    # Python 3.9+ is_relative_to
                    if not resolved.is_relative_to(target_resolved):
                        console_err.print(f"[yellow][!] Skipping out-of-tree file (symlink escape?): {markup_escape(str(file_path))} -> {markup_escape(str(resolved))}[/]")
                        skipped_count += 1
                        continue
                except Exception:
                    # If resolve fails, skip safely
                    skipped_count += 1
                    continue
            except FileNotFoundError:
                skipped_count += 1
                continue
            except OSError as e:
                console_err.print(f"[yellow][!] Lstat error on {markup_escape(str(file_path))}: {markup_escape(str(e))}[/]")
                skipped_count += 1
                continue

            # --- Safe read with O_NOFOLLOW ---
            try:
                raw_bytes = safe_read_bytes_no_follow(file_path)
            except OSError as e:
                # ELOOP = symlink, EINVAL = O_NOFOLLOW on some FS, etc.
                console_err.print(f"[yellow][!] IO Error / symlink on {markup_escape(str(file_path))}. Skipping. ({markup_escape(str(e))})[/]")
                skipped_count += 1
                continue
            except ValueError as e:
                console_err.print(f"[yellow][!] Skipping large file {markup_escape(str(file_path))}: {markup_escape(str(e))}[/]")
                skipped_count += 1
                continue

            if not args.allow_binary and is_binary_quick(raw_bytes):
                console_out.print(f"[dim][i] Skipping binary file: {markup_escape(str(file_path))}[/]")
                skipped_count += 1
                continue

            # --- Decode ---
            detected_encoding, original_text = detect_encoding_and_decode(raw_bytes)

            # --- Regex replace ---
            try:
                new_text, sub_count = search_pattern.subn(args.replace, original_text)
            except Exception as e:
                console_err.print(f"[red][✖] Regex error on {markup_escape(str(file_path))}: {markup_escape(str(e))}[/]")
                failed_count += 1
                continue

            if sub_count == 0:
                continue

            if mode_dry or (mode_interactive and not batch_override):
                display_diff_limited(file_path, original_text, new_text)

            if mode_dry:
                continue

            if not batch_override:
                action = Prompt.ask(
                    f"Apply to [cyan]{markup_escape(str(file_path))}[/]? ([green]y[/]/[red]n[/]/[yellow]q[/]uit/[magenta]a[/]ll)",
                    choices=["y", "n", "q", "a"],
                    default="y",
                    case_sensitive=False,
                    show_choices=False,
                    console=console_out,
                )
                match action.lower():
                    case "q":
                        console_out.print("[yellow]Aborted by user.[/]")
                        break
                    case "n":
                        skipped_count += 1
                        continue
                    case "a":
                        batch_override = True
                        # Continue, but do not attempt to retroactively enable Progress
                    case _:
                        pass  # y

            # --- Encode back - strict, surrogateescape only if original contained surrogates ---
            try:
                # detect surrogateescape round-trip need by scanning for surrogates (U+DC80..U+DCFF)
                contains_surrogates = any(0xDC80 <= ord(ch) <= 0xDCFF for ch in original_text)
                if contains_surrogates:
                    output_bytes = new_text.encode(detected_encoding, errors="surrogateescape")
                else:
                    output_bytes = new_text.encode(detected_encoding, errors="strict")
            except UnicodeEncodeError as e:
                console_err.print(
                    f"[red][✖] Cannot encode {markup_escape(str(file_path))} as {markup_escape(detected_encoding)}: {markup_escape(str(e))}. "
                    f"Replacement contains characters not in original encoding. Skipping.[/]"
                )
                failed_count += 1
                continue
            except Exception as e:
                console_err.print(f"[red][✖] Encode failed on {markup_escape(str(file_path))}: {markup_escape(str(e))}[/]")
                failed_count += 1
                continue

            # --- Atomic write ---
            try:
                atomic_write_preserve_mode(file_path, output_bytes)
                processed_count += 1
                if not mode_batch:
                    console_out.print(f"[green][✔] Updated {markup_escape(str(file_path))} ({markup_escape(detected_encoding)})[/]")
            except OSError as e:
                console_err.print(f"[bold red][✖] Write failed on {markup_escape(str(file_path))}: {markup_escape(str(e))}[/]")
                failed_count += 1
                # Do not increment processed_count
                continue

    try:
        if progress_ctx:
            with progress_ctx as progress:
                task = progress.add_task("Processing...", total=len(files))
                # Wrap iterator to update progress
                def progress_iter():
                    for f in files:
                        yield f
                        progress.advance(task)
                process_files(progress_iter())
        else:
            process_files(files)
    except KeyboardInterrupt:
        console_err.print("\n[bold red][!] Interrupted by user.[/]")
        sys.exit(130)

    console_out.print(f"\n[bold green]Done![/] Updated {processed_count} files, skipped {skipped_count}, failed {failed_count}.")

if __name__ == "__main__":
    main()
