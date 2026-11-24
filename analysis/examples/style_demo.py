"""Render one made-up chart at both sizes to review the house style.

Run from the repo root: analysis/.venv/Scripts/python analysis/examples/style_demo.py
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

os.environ.setdefault("MPLBACKEND", "Agg")
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from lib import style  # noqa: E402

AREAS = ["Pass offense", "Run offense", "Pass defense", "Run defense", "Third down", "Red zone"]
RANKS = [9, 14, 11, 29, 17, 12]  # made up; 1 is best, 32 is worst
PROBLEM = "Run defense"


def render(size: style.Size) -> Path:
    fig, ax = style.new_figure(size)
    rows = list(reversed(range(len(AREAS))))
    ax.barh(rows, RANKS, color=style.highlight(AREAS, {PROBLEM}), height=0.5)
    ax.set_yticks([])
    for row, area, rank in zip(rows, AREAS, RANKS):
        color = style.ACCENT if area == PROBLEM else style.TEXT_2
        ax.text(0, row + 0.3, area, color=color, va="bottom",
                fontproperties=style.font("body_bold"), fontsize=style.px(style.TEXT_PX["label"]))
        ax.text(rank + 0.4, row, f"{rank}", color=color, va="center",
                fontproperties=style.font("number"), fontsize=style.px(style.TEXT_PX["label"]))
    ax.set_xlim(0, 34)
    ax.set_xticks([1, 16, 32])
    ax.set_xlabel("League rank (32 is worst)")
    ax.spines["left"].set_visible(False)
    style.finish(
        fig, ax,
        title="Sample: run defense is the one big problem",
        subtitle="Made-up numbers to check the chart style",
        source="Source: demo data, not real · data through week 6",
    )
    return style.export(fig, "style-demo", size)


if __name__ == "__main__":
    for size in style.SIZES:
        print(render(size))
