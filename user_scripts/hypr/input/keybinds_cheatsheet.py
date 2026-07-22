#!/usr/bin/env python3.14
"""
==============================================================================
  DUSKY · Hyprland Keybinds Cheatsheet
  Python 3.14.6+  ·  Catppuccin Mocha  ·  Arch Linux  ·  Hyprland
==============================================================================
  Glance window: any key dismisses  ·  Designed for kitty / floating rule
==============================================================================
"""

from __future__ import annotations

import sys
import termios
import tty
from dataclasses import dataclass
from enum import StrEnum
from typing import Final

from rich import box
from rich.align import Align
from rich.console import Console, Group
from rich.panel import Panel
from rich.rule import Rule
from rich.table import Table
from rich.text import Text

# ── runtime gate ────────────────────────────────────────────────────────────
if sys.version_info < (3, 14):
    sys.exit(
        f"│ FATAL │ Python 3.14+ required  ·  running {sys.version.split()[0]}"
    )

# ── palette · Catppuccin Mocha (exact upstream hex) ─────────────────────────
class Mocha:
    ROSEWATER = "#f5e0dc"
    FLAMINGO  = "#f2cdcd"
    PINK      = "#f5c2e7"
    MAUVE     = "#cba6f7"
    RED       = "#f38ba8"
    MAROON    = "#eba0ac"
    PEACH     = "#fab387"
    YELLOW    = "#f9e2af"
    GREEN     = "#a6e3a1"
    TEAL      = "#94e2d5"
    SKY       = "#89dceb"
    SAPPHIRE  = "#74c7ec"
    BLUE      = "#89b4fa"
    LAVENDER  = "#b4befe"
    TEXT      = "#cdd6f4"
    SUBTEXT1  = "#bac2de"
    SUBTEXT0  = "#a6adc8"
    OVERLAY2  = "#9399b2"
    OVERLAY1  = "#7f849c"
    OVERLAY0  = "#6c7086"
    SURFACE2  = "#585b70"
    SURFACE1  = "#45475a"
    SURFACE0  = "#313244"
    BASE      = "#1e1e2e"
    MANTLE    = "#181825"
    CRUST     = "#11111b"


C = Mocha  # short alias used everywhere below

# ── domain ──────────────────────────────────────────────────────────────────
class Tag(StrEnum):
    PRIMARY = "primary"
    ACCENT  = "accent"
    DANGER  = "danger"
    WARNING = "warning"
    INFO    = "info"
    SUCCESS = "success"
    MUTED   = "muted"


def tag_fg(tag: Tag) -> str:
    """Python 3.14 structural match → foreground colour."""
    match tag:
        case Tag.PRIMARY: return C.BLUE
        case Tag.ACCENT:  return C.MAUVE
        case Tag.DANGER:  return C.RED
        case Tag.WARNING: return C.PEACH
        case Tag.INFO:    return C.SKY
        case Tag.SUCCESS: return C.GREEN
        case Tag.MUTED:   return C.SUBTEXT0


MODS: Final[frozenset[str]] = frozenset({
    "SUPER", "ALT", "CTRL", "SHIFT", "MOUSE", "DRAG", "SCROLL", "PRINT",
})


@dataclass(frozen=True, slots=True)
class Bind:
    keys: tuple[str, ...]
    action: str
    tag: Tag = Tag.PRIMARY
    ctx: str = ""          # short context / backend tool


@dataclass(frozen=True, slots=True)
class Category:
    title: str
    icon: str
    accent: str
    binds: tuple[Bind, ...]


# ── catalogue · 4×9 · intentional symmetry ──────────────────────────────────
CATALOGUE: Final[tuple[Category, ...]] = (
    Category(
        title="LAUNCHERS  &  SEARCH",
        icon="󰀻",
        accent=C.BLUE,
        binds=(
            Bind(("SUPER", "Q"),             "Launch Terminal",         Tag.PRIMARY, "kitty"),
            Bind(("SUPER", "W"),             "Launch Web Browser",      Tag.PRIMARY, "Zen · Firefox"),
            Bind(("SUPER", "E"),             "Launch File Manager",     Tag.PRIMARY, "Thunar · Yazi"),
            Bind(("SUPER", "R"),             "Open Text Editor",        Tag.PRIMARY, "Neovim · VSCode"),
            Bind(("ALT", "SPACE"),           "App Launcher / Search",   Tag.ACCENT,  "Rofi dmenu"),
            Bind(("SUPER", "SPACE"),         "System Quick Menu",       Tag.ACCENT,  "Rofi system"),
            Bind(("SUPER", "V"),             "Clipboard Manager",       Tag.INFO,    "history & paste"),
            Bind(("SUPER", "G"),             "Image Search & Lens",     Tag.INFO,    "select → search"),
            Bind(("SUPER", "CTRL", "SPACE"), "Emoji Picker & Insert",   Tag.ACCENT,  "Rofi emoji"),
        ),
    ),
    Category(
        title="WINDOW  TILING  &  POSITION",
        icon="󰝣",
        accent=C.GREEN,
        binds=(
            Bind(("SUPER", "C"),                   "Close Focused Window",  Tag.DANGER,  "kill active"),
            Bind(("SUPER", "A"),                   "Toggle Fullscreen",     Tag.WARNING, "monocle"),
            Bind(("SUPER", "D"),                   "Toggle Smart Float",    Tag.INFO,    "floating"),
            Bind(("SUPER", "Y"),                   "Toggle Window Split",   Tag.INFO,    "vert · horiz"),
            Bind(("SUPER", "X"),                   "Pin Window (Sticky)",   Tag.INFO,    "all workspaces"),
            Bind(("SUPER", "SHIFT", "A"),          "Maximize Window",       Tag.WARNING, "fill screen"),
            Bind(("SUPER", "H  J  K  L"),          "Focus Directionally",   Tag.MUTED,   "vim keys"),
            Bind(("SUPER", "SHIFT", "H  J  K  L"), "Move Window Position",  Tag.MUTED,   "swap tile"),
            Bind(("SUPER", "DRAG"),                "Move or Resize Window", Tag.MUTED,   "LMB · RMB"),
        ),
    ),
    Category(
        title="WORKSPACES  &  NAVIGATION",
        icon="󰽙",
        accent=C.MAUVE,
        binds=(
            Bind(("SUPER", "1 … 9"),           "Switch Workspace 1–9",    Tag.PRIMARY, "direct jump"),
            Bind(("SUPER", "SHIFT", "1 … 9"),  "Move Window → WS 1–9",    Tag.WARNING, "take tile"),
            Bind(("SUPER", "ALT", "1 … 9"),    "Silent Move → WS",        Tag.MUTED,   "background"),
            Bind(("SUPER", "TAB"),             "Last Active Workspace",   Tag.ACCENT,  "quick toggle"),
            Bind(("SUPER", "Z"),               "Toggle Scratchpad",       Tag.ACCENT,  "dropdown term"),
            Bind(("SUPER", "SHIFT", "Z"),      "Send to Scratchpad",      Tag.WARNING, "hide window"),
            Bind(("SUPER", "SHIFT", "M"),      "Special Spotify WS",      Tag.INFO,    "music space"),
            Bind(("SUPER", "SCROLL"),          "Cycle Workspaces",        Tag.MUTED,   "wheel ↑ ↓"),
            Bind(("SUPER", "SHIFT", "TAB"),    "Cycle Next Workspace",    Tag.ACCENT,  "ws sequence"),
        ),
    ),
    Category(
        title="SYSTEM  ·  TOOLS  ·  CONTROLS",
        icon="󰒓",
        accent=C.YELLOW,
        binds=(
            Bind(("SUPER", "M"),             "Lock Screen",             Tag.DANGER,  "hyprlock"),
            Bind(("ALT", "F4"),              "Power & Logout Menu",     Tag.DANGER,  "session"),
            Bind(("CTRL", "SHIFT", "ESC"),   "Activity Monitor",        Tag.INFO,    "btop TUI"),
            Bind(("SUPER", "S"),             "Quick Screenshot",        Tag.ACCENT,  "grim · slurp"),
            Bind(("SUPER", "SHIFT", "S"),    "Screenshot & Annotate",   Tag.ACCENT,  "swappy area"),
            Bind(("SUPER", "B"),             "Color Picker",            Tag.INFO,    "hyprpicker"),
            Bind(("SUPER", "ALT", "O"),      "AI · Ollama Chat TUI",    Tag.PRIMARY, "terminal LLM"),
            Bind(("ALT", "1  2  3"),         "Wi-Fi · BT · Audio TUI",  Tag.MUTED,   "system TUIs"),
            Bind(("SUPER", "SHIFT", "R"),    "Reload Hyprland Config",  Tag.DANGER,  "hot reload"),
        ),
    ),
)


# ── pure render helpers ─────────────────────────────────────────────────────
def _pill(token: str) -> Text:
    """Single tactile keycap."""
    bare = token.strip()
    out = Text()
    if bare in MODS:
        # recessed modifier / gesture
        out.append(f" {bare} ", style=f"bold {C.TEXT} on {C.SURFACE0}")
    elif any(ch in bare for ch in ("…", "–", "  ")):
        # range or chord-cluster — warm so it reads as “family of keys”
        out.append(f" {bare} ", style=f"bold {C.YELLOW} on {C.BASE}")
    else:
        # primary alphanumeric
        out.append(f" {bare} ", style=f"bold {C.BLUE} on {C.SURFACE0}")
    return out


def chord(keys: tuple[str, ...]) -> Text:
    """Keycaps joined by a delicate +."""
    line = Text()
    for i, k in enumerate(keys):
        if i:
            line.append("+", style=f"bold {C.OVERLAY0}")
        line.append_text(_pill(k))
    return line


def action_cell(b: Bind) -> Text:
    """Status gem + colour-coded verb — intent before detail."""
    fg = tag_fg(b.tag)
    cell = Text()
    cell.append("●", style=fg)
    cell.append(" ")
    cell.append(b.action, style=f"bold {fg}")
    return cell


def build_card(cat: Category, index: int) -> Panel:
    """One category card — 3 scannable columns, zebra rows, no noise."""
    tbl = Table(
        show_header=True,
        header_style=f"bold {C.OVERLAY0}",
        show_edge=False,
        box=None,
        expand=True,
        pad_edge=False,
        padding=(0, 1),
        # zebra: calm mantle wash on alternating rows
        row_styles=["", f"on {C.MANTLE}"],
    )
    tbl.add_column("COMBINATION", justify="left", no_wrap=True, min_width=26, ratio=5)
    tbl.add_column("ACTION",      justify="left", no_wrap=True, min_width=22, ratio=5)
    tbl.add_column("CONTEXT",     justify="left", no_wrap=True, min_width=12, ratio=3)

    for b in cat.binds:
        ctx = Text(b.ctx, style=f"italic {C.OVERLAY1}") if b.ctx else Text("—", style=C.SURFACE1)
        tbl.add_row(chord(b.keys), action_cell(b), ctx)

    # title · index badge · icon · accent
    title = Text()
    title.append(f" {cat.icon} ", style=f"bold {cat.accent}")
    title.append(f" {index:02d} ", style=f"bold {C.CRUST} on {cat.accent}")
    title.append(f"  {cat.title} ", style=f"bold {cat.accent}")

    return Panel(
        tbl,
        title=title,
        title_align="left",
        border_style=cat.accent,
        box=box.ROUNDED,
        padding=(0, 1),
        expand=True,
    )


def build_header(total: int) -> Group:
    """Identity strip + modifier legend + bind count."""
    brand = Text()
    brand.append(" 󰌌 ", style=f"bold {C.CRUST} on {C.BLUE}")
    brand.append(" DUSKY ", style=f"bold {C.CRUST} on {C.BLUE}")
    brand.append(" KEYBINDS ", style=f"bold {C.BLUE} on {C.SURFACE0}")
    brand.append(" · Hyprland · Arch ", style=f"{C.SUBTEXT0} on {C.SURFACE0}")
    brand.append(f" · {total} binds ", style=f"bold {C.YELLOW} on {C.SURFACE0}")

    # modifier chips with human labels — teaches the legend instantly
    mods = Text()
    pairs = (
        (" SUPER ", "Win"),
        (" ALT ",   "Alt"),
        (" CTRL ",  "Ctrl"),
        (" SHIFT ", "Shift"),
        (" DRAG ",  "Mouse"),
        (" SCROLL ", "Wheel"),
    )
    for i, (key, label) in enumerate(pairs):
        if i:
            mods.append("  ", style="")
        mods.append(key, style=f"bold {C.TEXT} on {C.SURFACE0}")
        mods.append(f" {label}", style=C.OVERLAY1)

    return Group(
        Align.center(brand),
        Text(""),
        Align.center(mods),
        Text(""),
        Rule(style=C.SURFACE1, characters="─"),
    )


def build_legend() -> Text:
    """Colour language key — one glance, no guessing."""
    items: tuple[tuple[str, Tag], ...] = (
        ("primary", Tag.PRIMARY),
        ("accent",  Tag.ACCENT),
        ("danger",  Tag.DANGER),
        ("warning", Tag.WARNING),
        ("info",    Tag.INFO),
        ("muted",   Tag.MUTED),
    )
    leg = Text()
    for i, (label, tag) in enumerate(items):
        if i:
            leg.append("   ", style="")
        fg = tag_fg(tag)
        leg.append("●", style=fg)
        leg.append(f" {label}", style=fg)
    return leg


def build_footer() -> Text:
    foot = Text()
    foot.append(" press ", style=C.OVERLAY1)
    foot.append(" any key ", style=f"bold {C.CRUST} on {C.MAUVE}")
    foot.append(" to dismiss ", style=C.OVERLAY1)
    foot.append(" · ", style=C.SURFACE2)
    foot.append("q", style=f"bold {C.MAUVE}")
    foot.append(" / ", style=C.SURFACE2)
    foot.append("Esc", style=f"bold {C.MAUVE}")
    foot.append(" / ", style=C.SURFACE2)
    foot.append("Ctrl+C", style=f"bold {C.MAUVE}")
    return foot


def render(console: Console) -> Panel:
    """Full dashboard — responsive 2×2 or stacked."""
    total = sum(len(c.binds) for c in CATALOGUE)
    cards = [build_card(cat, i) for i, cat in enumerate(CATALOGUE, 1)]

    # outer panel steals ~6 cols (borders + padding); break a little higher
    if console.width >= 120:
        grid = Table.grid(expand=True, padding=(0, 2))
        grid.add_column(ratio=1)
        grid.add_column(ratio=1)
        grid.add_row(cards[0], cards[1])
        grid.add_row(Text(""), Text(""))          # vertical breath
        grid.add_row(cards[2], cards[3])
    else:
        grid = Table.grid(expand=True, padding=(0, 0))
        grid.add_column(ratio=1)
        for i, card in enumerate(cards):
            grid.add_row(card)
            if i < len(cards) - 1:
                grid.add_row(Text(""))

    body = Group(
        build_header(total),
        Text(""),
        grid,
        Text(""),
        Rule(style=C.SURFACE1, characters="─"),
        Text(""),
        Align.center(build_legend()),
        Text(""),
        Align.center(build_footer()),
    )

    py = (
        f"{sys.version_info.major}."
        f"{sys.version_info.minor}."
        f"{sys.version_info.micro}"
    )
    return Panel(
        body,
        border_style=f"bold {C.BLUE}",
        box=box.DOUBLE_EDGE,
        padding=(1, 2),
        subtitle=f"[{C.OVERLAY0}]catppuccin mocha  ·  python {py}[/]",
        subtitle_align="right",
    )


# ── interaction ─────────────────────────────────────────────────────────────
def wait_for_key() -> None:
    """Raw single-keystroke barrier; always restore terminal attrs."""
    if not sys.stdin.isatty():
        return
    fd = sys.stdin.fileno()
    prev = termios.tcgetattr(fd)
    try:
        tty.setraw(fd)
        sys.stdin.read(1)
    except (KeyboardInterrupt, EOFError):
        pass
    finally:
        termios.tcsetattr(fd, termios.TCSADRAIN, prev)


def main() -> None:
    console = Console(highlight=False)
    console.clear()
    console.print(render(console))
    wait_for_key()


if __name__ == "__main__":
    main()
