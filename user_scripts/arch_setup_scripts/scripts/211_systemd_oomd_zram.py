#!/usr/bin/env python3
"""
Dynamic Hyprland OOM protection deployer - v3
Configures systemd-oomd slices, custom rulesets, and dusky-run wrapper.
Specifically tuned for systemd 261.1 on Arch Linux.
"""
from __future__ import annotations
import os, sys, subprocess, tempfile, shutil, filecmp
from pathlib import Path
from dataclasses import dataclass
from typing import Final

SELF_PATH: Final[Path] = Path(__file__).resolve()

def _bootstrap_rich() -> None:
    try:
        import rich; return
    except ImportError:
        pass
    subprocess.run(["sudo","pacman","-S","--needed","--noconfirm","python-rich"], check=False)
    os.execv(sys.executable, [sys.executable, str(SELF_PATH), *sys.argv[1:]])
_bootstrap_rich()

from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich import box

console: Final[Console] = Console()

PRESSURE_RULE: Final[str] = """[Rule]
MemoryPressureAbove=75%
LastingSec=20s
Action=kill-by-pgscan
"""

SWAP_RULE: Final[str] = """[Rule]
SwapUsageMax=90%
LastingSec=10s
Action=kill-by-swap
"""

# Valid for systemd 261: only auto|kill for MemoryPressure/Swap, only none|avoid|omit for Preference
APP_SLICE: Final[str] = """[Slice]
ManagedOOMMemoryPressure=kill
ManagedOOMSwap=kill
OOMRules=30-desktop-pressure 30-desktop-swap
"""

BACKGROUND_SLICE: Final[str] = """[Slice]
ManagedOOMMemoryPressure=kill
ManagedOOMSwap=kill
OOMRules=30-desktop-pressure 30-desktop-swap
"""

SESSION_SLICE: Final[str] = """[Slice]
ManagedOOMPreference=avoid
"""

# Scope units on systemd 261.1 do NOT accept OOMScoreAdjust. Keep OOMPolicy and Preference only.
# Compositor protection must stay via sudo choom in autostart.lua
COMPOSITOR_SCOPE: Final[str] = """[Scope]
OOMPolicy=continue
ManagedOOMPreference=avoid
"""

USER_MANAGER_SCORE: Final[str] = """[Service]
OOMScoreAdjust=-100
OOMPolicy=continue
"""

USER_CONF: Final[str] = """[Manager]
DefaultOOMScoreAdjust=100
"""

OOM_SHIELD: Final[str] = """[Service]
OOMScoreAdjust=-400
OOMPolicy=continue
"""

OOMD_TUNE: Final[str] = """[OOM]
DefaultMemoryPressureLimit=75%
DefaultMemoryPressureDurationSec=20s
SwapUsedLimit=90%
"""

CRITICAL_USER: Final[tuple[str,...]] = (
    "pipewire.service","wireplumber.service","pipewire-pulse.service",
    "xdg-desktop-portal.service","xdg-desktop-portal-hyprland.service",
    "xdg-desktop-portal-gtk.service","dbus-broker.service","mako.service",
)

# CORRECT wrapper for scope: raise own score, then let scope inherit it.
# This is the only unprivileged method because scope inherits execution environment.
DUSKY_RUN_WRAPPER: Final[str] = """#!/bin/bash
# dusky-run - makes apps more killable than compositor
# Scope units inherit oom_score_adj from parent, they do not reset it to 0.
# Unprivileged users may increase their own score (make more killable) without sudo.
set -euo pipefail
if [ $# -eq 0 ]; then echo "usage: dusky-run <cmd>" >&2; exit 1; fi
# 200 is allowed for unprivileged (increase), -200 would need root
echo 200 > /proc/self/oom_score_adj 2>/dev/null || true
exec systemd-run --user --scope --slice=app.slice --collect --quiet -- "$@"
"""

@dataclass(frozen=True, slots=True, kw_only=True)
class FileSpec:
    dest: Path
    content: str
    mode: int = 0o644
    desc: str

def specs() -> list[FileSpec]:
    s: list[FileSpec] = [
        FileSpec(dest=Path("/etc/systemd/oomd/rules.d/30-desktop-pressure.oomrule"), content=PRESSURE_RULE, desc="pressure rule"),
        FileSpec(dest=Path("/etc/systemd/oomd/rules.d/30-desktop-swap.oomrule"), content=SWAP_RULE, desc="swap rule"),
        FileSpec(dest=Path("/etc/systemd/oomd.conf.d/10-desktop-tune.conf"), content=OOMD_TUNE, desc="oomd tune"),
        FileSpec(dest=Path("/etc/systemd/user/app.slice.d/10-oomd.conf"), content=APP_SLICE, desc="app.slice killable"),
        FileSpec(dest=Path("/etc/systemd/user/background.slice.d/10-oomd.conf"), content=BACKGROUND_SLICE, desc="background.slice killable"),
        FileSpec(dest=Path("/etc/systemd/user/session.slice.d/10-oomd-avoid.conf"), content=SESSION_SLICE, desc="session.slice avoid"),
        FileSpec(dest=Path("/etc/systemd/system/session-.scope.d/10-compositor-protect.conf"), content=COMPOSITOR_SCOPE, desc="compositor scope avoid+continue"),
        FileSpec(dest=Path("/etc/systemd/system/user@.service.d/10-oom-score.conf"), content=USER_MANAGER_SCORE, desc="user@ -100"),
        FileSpec(dest=Path("/etc/systemd/user.conf.d/10-oom-default.conf"), content=USER_CONF, desc="DefaultOOMScoreAdjust 100"),
        FileSpec(dest=Path("/usr/local/bin/dusky-run"), content=DUSKY_RUN_WRAPPER, mode=0o755, desc="dusky-run fixed v3"),
    ]
    for svc in CRITICAL_USER:
        s.append(FileSpec(dest=Path(f"/etc/systemd/user/{svc}.d/10-oom-shield.conf"), content=OOM_SHIELD, desc=f"shield {svc}"))
    return s

def atomic_install(spec: FileSpec) -> str:
    d = spec.dest; d.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=str(d.parent)); tp = Path(tmp)
    try:
        tp.write_text(spec.content, encoding="utf-8"); os.chmod(tp, spec.mode)
        if d.exists() and filecmp.cmp(str(tp), str(d), shallow=False): return "up-to-date"
        shutil.move(str(tp), str(d)); os.chmod(d, spec.mode); return "updated"
    finally:
        try: tp.unlink()
        except: pass
        try: os.close(fd)
        except: pass

def main() -> None:
    dry = "--dry-run" in sys.argv or "-n" in sys.argv
    if not dry and os.geteuid()!=0:
        console.print("[blue]Re-exec via sudo[/]"); os.execvp("sudo",["sudo",sys.executable,str(SELF_PATH),*sys.argv[1:]])
    console.print(Panel.fit("[bold cyan]Hyprland 0.55.4 + systemd 261.1 OOM fix v3 - VM validated[/]", box=box.DOUBLE))
    all_specs = specs()
    if dry:
        t=Table(box=box.SIMPLE_HEAVY); t.add_column("Dest"); t.add_column("Desc")
        for x in all_specs: t.add_row(str(x.dest), x.desc); console.print(t); return
    upd=0
    with Progress(SpinnerColumn(), TextColumn("{task.description}"), console=console) as p:
        task=p.add_task("Installing", total=len(all_specs))
        for sp in all_specs:
            st=atomic_install(sp); console.print(f"[green]{st.upper()}[/] {sp.dest}"); upd+=1; p.advance(task)
    for cmd in [["systemctl","unmask","systemd-oomd"],["systemctl","enable","--now","systemd-oomd"],["systemctl","daemon-reload"],["systemctl","--user","daemon-reload"]]:
        subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    console.print(Panel.fit(f"[bold green]✔ {upd} files deployed\n✔ Keep: hl.exec_cmd(\"sudo choom -n -250 -p $(pgrep -x Hyprland)\") in autostart.lua\n✔ Re-login required[/]", box=box.ROUNDED))

if __name__=="__main__": main()
