"""The one chart style for every post: brand colors, bundled fonts, phone-sized text."""
from __future__ import annotations

import re
from collections.abc import Callable, Collection, Sequence
from dataclasses import dataclass
from functools import cache
from pathlib import Path
from typing import Literal

import matplotlib.image as mpimg
import matplotlib.pyplot as plt
from matplotlib import font_manager
from matplotlib.axes import Axes
from matplotlib.figure import Figure
from matplotlib.font_manager import FontProperties
from matplotlib.patches import FancyBboxPatch
from matplotlib.textpath import TextPath

Size = Literal["feed", "vertical"]
Role = Literal["title", "heading", "body", "body_bold", "number"]

ANALYSIS_DIR = Path(__file__).resolve().parents[1]
FONT_DIR = ANALYSIS_DIR / "fonts"
OUTPUT_DIR = ANALYSIS_DIR / "output"
LOGO = ANALYSIS_DIR / "thumbnails" / "logo.png"

ACCENT = "#09BDFE"  # sampled from the logo's tallest bar
BG = "#000000"
TEXT = "#f5f5f7"
TEXT_2 = "#9a9aa3"
GRAY = "#6b6b75"
GRAY_LOW = "#3a3a42"
HANDLE = "@numbersbehindthegame"

SIZES: dict[Size, tuple[int, int]] = {"feed": (1080, 1350), "vertical": (1080, 1920)}
DPI = 100
PT_PER_PX = 72 / DPI

# Pixel sizes at export, chosen to read on a phone held at arm's length.
TEXT_PX = {"title": 72, "subtitle": 36, "label": 34, "tick": 30, "source": 26}
TITLE_MAX_LINES = 2
LOGO_PX = 56
FOOTER_GAP = 30
# Below the axes: tick numbers, an axis label, then the two footer rows.
AXES_BOTTOM_CLEARANCE = 250

FONT_FILES: dict[Role, str] = {
    "title": "BarlowCondensed-ExtraBold.ttf",
    "heading": "BarlowCondensed-SemiBold.ttf",
    "body": "DMSans-Regular.ttf",
    "body_bold": "DMSans-SemiBold.ttf",
    "number": "JetBrainsMono-Medium.ttf",
}

# TikTok and Reels cover the top (account, tabs), the bottom (caption, sound) and
# a right column of buttons; the feed post has no overlay, only a margin.
SAFE_INSETS: dict[Size, tuple[int, int, int, int]] = {
    # top, right, bottom, left
    "feed": (56, 60, 50, 60),
    "vertical": (220, 140, 380, 60),
}


@dataclass(frozen=True)
class Box:
    left: int
    top: int
    right: int
    bottom: int

    @property
    def width(self) -> int:
        return self.right - self.left


@dataclass(frozen=True)
class Layout:
    width: int
    height: int
    safe: Box
    axes: Box
    footer_baseline: int

    @property
    def source_center(self) -> int:
        """The source line sits on its own row above the logo and handle."""
        return self.footer_baseline - LOGO_PX - FOOTER_GAP


def layout(size: Size) -> Layout:
    width, height = SIZES[size]
    top, right, bottom, left = SAFE_INSETS[size]
    safe = Box(left, top, width - right, height - bottom)
    # Room for a two-line title and a subtitle above.
    axes = Box(safe.left + 110, safe.top + 250, safe.right, safe.bottom - AXES_BOTTOM_CLEARANCE)
    return Layout(width, height, safe, axes, footer_baseline=safe.bottom)


def wrap_title(title: str, width_px: float, measure: Callable[[str], float]) -> list[str]:
    """Greedy word wrap; a title that needs more than two lines is too long to be the answer."""
    lines: list[str] = []
    for word in title.split():
        candidate = f"{lines[-1]} {word}" if lines else word
        if lines and measure(candidate) <= width_px:
            lines[-1] = candidate
        else:
            lines.append(word)
    if len(lines) > TITLE_MAX_LINES:
        raise ValueError(f"title needs {len(lines)} lines; shorten it to the answer: {title!r}")
    return lines


def highlight(labels: Sequence[str], keys: Collection[str]) -> list[str]:
    """ACCENT for the labels the point is about, GRAY for everything else."""
    return [ACCENT if label in keys else GRAY for label in labels]


def is_number(text: str) -> bool:
    return bool(re.fullmatch(r"[+\-−]?\$?[\d,]*\.?\d+%?", text.strip()))


def output_path(name: str, size: Size) -> Path:
    if not re.fullmatch(r"[a-z0-9][a-z0-9-]*", name):
        raise ValueError(f"chart name must be lowercase letters, digits and hyphens: {name!r}")
    return OUTPUT_DIR / f"{name}-{size}.png"


def font(role: Role) -> FontProperties:
    path = FONT_DIR / FONT_FILES[role]
    if not path.is_file():
        raise FileNotFoundError(f"missing bundled font {path.name} in {FONT_DIR}")
    return FontProperties(fname=path)


def px(size_px: float) -> float:
    """Pixels at export to matplotlib points."""
    return size_px * PT_PER_PX


@cache
def apply_style() -> None:
    for role in FONT_FILES:
        font_manager.fontManager.addfont(font(role).get_file())
    plt.rcParams.update(
        {
            "font.family": font("body").get_name(),
            "font.size": px(TEXT_PX["label"]),
            "figure.facecolor": BG,
            "axes.facecolor": BG,
            "savefig.facecolor": BG,
            "text.color": TEXT,
            "axes.labelcolor": TEXT_2,
            "axes.edgecolor": GRAY_LOW,
            "axes.spines.top": False,
            "axes.spines.right": False,
            "axes.grid": False,
            "grid.color": GRAY_LOW,
            "xtick.color": TEXT_2,
            "ytick.color": TEXT_2,
            "xtick.labelsize": px(TEXT_PX["tick"]),
            "ytick.labelsize": px(TEXT_PX["tick"]),
            "axes.unicode_minus": True,
        }
    )


def _fraction(box: Box, fig_layout: Layout) -> tuple[float, float, float, float]:
    w, h = fig_layout.width, fig_layout.height
    return (box.left / w, 1 - box.bottom / h, box.width / w, (box.bottom - box.top) / h)


def new_figure(size: Size) -> tuple[Figure, Axes]:
    apply_style()
    fig_layout = layout(size)
    fig = plt.figure(figsize=(fig_layout.width / DPI, fig_layout.height / DPI), dpi=DPI)
    fig.set_label(size)
    ax = fig.add_axes(_fraction(fig_layout.axes, fig_layout))
    return fig, ax


def _title_width(text: str) -> float:
    return TextPath((0, 0), text, size=TEXT_PX["title"], prop=font("title")).get_extents().width


def _draw_credit(fig: Figure, fig_layout: Layout, y_px: int) -> None:
    right = fig_layout.safe.right
    logo_box = Box(right - LOGO_PX, y_px - LOGO_PX, right, y_px)
    logo_ax = fig.add_axes(_fraction(logo_box, fig_layout))
    logo_ax.set_axis_off()
    image = logo_ax.imshow(mpimg.imread(LOGO))
    # The logo's navy square is opaque, so it reads as a rounded app-icon tile.
    h, w = image.get_array().shape[:2]
    tile = FancyBboxPatch((0, 0), w, h, boxstyle=f"round,pad=0,rounding_size={w * 0.22}",
                          transform=logo_ax.transData, facecolor="none", edgecolor="none")
    logo_ax.add_patch(tile)
    image.set_clip_path(tile)
    fig.text(*_at(fig_layout, logo_box.left - 14, y_px - LOGO_PX / 2), HANDLE, ha="right", va="center", color=TEXT_2,
             fontproperties=font("body_bold"), fontsize=px(TEXT_PX["source"]))


def _at(fig_layout: Layout, x_px: float, y_px: float) -> tuple[float, float]:
    """Pixel position from the top-left to figure coordinates."""
    return x_px / fig_layout.width, 1 - y_px / fig_layout.height


def finish(fig: Figure, ax: Axes, *, title: str, source: str, subtitle: str | None = None) -> None:
    """Title that states the answer, source line and credit. Call after plotting."""
    fig_layout = layout(fig.get_label())
    safe = fig_layout.safe

    lines = wrap_title(title, safe.width, _title_width)
    title_px = TEXT_PX["title"]
    fig.text(*_at(fig_layout, safe.left, safe.top), "\n".join(lines), ha="left", va="top", color=TEXT,
             fontproperties=font("title"), fontsize=px(title_px), linespacing=1.0)
    if subtitle:
        sub_top = safe.top + len(lines) * title_px * 1.08 + 18
        fig.text(*_at(fig_layout, safe.left, sub_top), subtitle, ha="left", va="top", color=TEXT_2,
                 fontproperties=font("body"), fontsize=px(TEXT_PX["subtitle"]), wrap=True)

    fig.text(*_at(fig_layout, safe.left, fig_layout.source_center), source,
             ha="left", va="center", color=TEXT_2,
             fontproperties=font("body"), fontsize=px(TEXT_PX["source"]))
    _draw_credit(fig, fig_layout, fig_layout.footer_baseline)

    fig.canvas.draw()
    for label in ax.get_xticklabels() + ax.get_yticklabels():
        role: Role = "number" if is_number(label.get_text()) else "body"
        label.set_fontproperties(font(role))
        label.set_fontsize(px(TEXT_PX["tick"]))
    ax.xaxis.label.set_fontsize(px(TEXT_PX["label"]))
    ax.yaxis.label.set_fontsize(px(TEXT_PX["label"]))


def export(fig: Figure, name: str, size: Size) -> Path:
    if fig.get_label() != size:
        raise ValueError(f"figure was made as {fig.get_label()!r}, not {size!r}")
    path = output_path(name, size)
    path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(path, dpi=DPI, facecolor=BG)
    plt.close(fig)
    return path
