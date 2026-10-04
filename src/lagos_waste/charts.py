"""Static charts for the official numbers audit (notebook 01).

Each function returns a matplotlib Figure and, when given a path, saves it as PNG.
Colours follow a validated two-slot categorical palette; text uses neutral ink.
"""

from __future__ import annotations

import math
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.figure import Figure  # noqa: E402

SURFACE = "#fcfcfb"
TEXT_PRIMARY = "#0b0b0b"
TEXT_SECONDARY = "#52514e"
GRID = "#e4e3df"
SERIES_1 = "#2a78d6"
SERIES_2 = "#eb6834"


def _style(ax: plt.Axes) -> None:
    """Apply recessive axes and grid."""
    ax.set_facecolor(SURFACE)
    for side in ("top", "right", "left"):
        ax.spines[side].set_visible(False)
    ax.spines["bottom"].set_color(GRID)
    ax.tick_params(colors=TEXT_SECONDARY, labelsize=9, length=0)
    ax.grid(axis="x", color=GRID, linewidth=0.8)
    ax.set_axisbelow(True)


def _finish(fig: Figure, title: str, source: str, path: Path | None) -> Figure:
    """Add title and source line, then save if a path is given."""
    fig.patch.set_facecolor(SURFACE)
    fig.suptitle(title, x=0.02, ha="left", fontsize=12, fontweight="bold", color=TEXT_PRIMARY)
    fig.text(0.02, 0.015, source, fontsize=7.5, color=TEXT_SECONDARY, ha="left")
    fig.tight_layout(rect=(0, 0.05, 1, 0.94))
    if path is not None:
        path.parent.mkdir(parents=True, exist_ok=True)
        fig.savefig(path, dpi=200, facecolor=SURFACE)
    return fig


def daily_tonnage_chart(
    rows: list[tuple[str, float, float | None, bool]],
    title: str,
    source: str,
    path: Path | None = None,
) -> Figure:
    """Horizontal comparison of daily tonnage figures.

    Each row is (label, low, high, highlight). A row with a high value is drawn
    as a range bar; a row without one is drawn as a single bar. Highlighted rows
    use the second palette slot.
    """
    fig, ax = plt.subplots(figsize=(8.5, 3.9))
    _style(ax)
    labels = [r[0] for r in rows]
    for i, (_, low, high, highlight) in enumerate(rows):
        colour = SERIES_2 if highlight else SERIES_1
        if high is None:
            ax.barh(i, low, height=0.5, color=colour)
            ax.text(low + 200, i, f"{low:,.0f}", va="center", fontsize=9, color=TEXT_PRIMARY)
        else:
            ax.barh(i, high - low, left=low, height=0.5, color=colour)
            ax.barh(i, low, height=0.5, color=colour, alpha=0.18)
            ax.text(high + 200, i, f"{low:,.0f} to {high:,.0f}", va="center", fontsize=9, color=TEXT_PRIMARY)
    ax.set_yticks(range(len(rows)), labels, fontsize=9, color=TEXT_PRIMARY)
    ax.invert_yaxis()
    ax.set_xlabel("Tonnes per day", fontsize=9, color=TEXT_SECONDARY)
    ax.xaxis.set_major_formatter(matplotlib.ticker.StrMethodFormatter("{x:,.0f}"))
    ax.set_xlim(0, max((r[2] or r[1]) for r in rows) * 1.22)
    return _finish(fig, title, source, path)


def budget_chart(
    years: list[str],
    recurrent: list[float | None],
    capital: list[float | None],
    title: str,
    source: str,
    path: Path | None = None,
) -> Figure:
    """Stacked vertical bars of recurrent and capital budget (in billions); None marks a missing year."""
    fig, ax = plt.subplots(figsize=(8.5, 4.2))
    _style(ax)
    ax.grid(axis="x", visible=False)
    ax.grid(axis="y", color=GRID, linewidth=0.8)
    x = range(len(years))
    for i, (rec, cap) in enumerate(zip(recurrent, capital)):
        if rec is None or cap is None or math.isnan(rec) or math.isnan(cap):
            ax.text(i, 1.5, "No LAWMA line\nlocated", ha="center", va="bottom", fontsize=8, color=TEXT_SECONDARY)
            continue
        ax.bar(i, rec, width=0.55, color=SERIES_1, edgecolor=SURFACE, linewidth=2,
               label="Recurrent" if i == 0 else None)
        ax.bar(i, cap, bottom=rec, width=0.55, color=SERIES_2, edgecolor=SURFACE, linewidth=2,
               label="Capital" if i == 0 else None)
        ax.text(i, rec + cap + 0.8, f"N{rec + cap:,.1f}bn", ha="center", fontsize=9, color=TEXT_PRIMARY)
    ax.set_xticks(list(x), years, fontsize=9, color=TEXT_PRIMARY)
    ax.set_ylabel("Naira, billions (nominal)", fontsize=9, color=TEXT_SECONDARY)
    totals = [r + c for r, c in zip(recurrent, capital)
              if r is not None and c is not None and not (math.isnan(r) or math.isnan(c))]
    ax.set_ylim(0, max(totals) * 1.18)
    ax.legend(frameon=False, fontsize=9, loc="upper left", labelcolor=TEXT_PRIMARY)
    return _finish(fig, title, source, path)


def trips_chart(
    rows: list[tuple[str, float, bool]],
    title: str,
    source: str,
    path: Path | None = None,
) -> Figure:
    """Horizontal bars of truck trips per day; derived rows are drawn hatched in outline."""
    fig, ax = plt.subplots(figsize=(8.5, 3.4))
    _style(ax)
    for i, (_, value, derived) in enumerate(rows):
        if derived:
            ax.barh(i, value, height=0.5, color=SURFACE, edgecolor=SERIES_2, hatch="///", linewidth=1.5)
        else:
            ax.barh(i, value, height=0.5, color=SERIES_1)
        ax.text(value + 15, i, f"{value:,.0f}", va="center", fontsize=9, color=TEXT_PRIMARY)
    ax.set_yticks(range(len(rows)), [r[0] for r in rows], fontsize=9, color=TEXT_PRIMARY)
    ax.invert_yaxis()
    ax.set_xlabel("Truck trips to disposal facilities per day", fontsize=9, color=TEXT_SECONDARY)
    ax.xaxis.set_major_formatter(matplotlib.ticker.StrMethodFormatter("{x:,.0f}"))
    ax.set_xlim(0, max(r[1] for r in rows) * 1.18)
    return _finish(fig, title, source, path)


def grouped_hbar(
    labels: list[str],
    series: list[tuple[str, list[float]]],
    title: str,
    xlabel: str,
    source: str,
    path: Path | None = None,
    value_format: str = "{:g}",
    xmax: float | None = None,
) -> Figure:
    """Horizontal bars for one or two series per label, with value labels; labels run top to bottom.

    `xmax` fixes the axis end (for example 100 for percentages); otherwise it follows the data.
    """
    n = len(series)
    fig, ax = plt.subplots(figsize=(8.5, 0.32 * len(labels) * max(n, 1) + 1.6))
    _style(ax)
    height = 0.8 / n
    top = max(max(vals) for _, vals in series) or 1
    for k, (name, vals) in enumerate(series):
        offset = (k - (n - 1) / 2) * height
        colour = (SERIES_1, SERIES_2)[k]
        ax.barh([i + offset for i in range(len(labels))], vals, height=height * 0.9, color=colour, label=name)
        for i, v in enumerate(vals):
            ax.text(v + top * 0.01, i + offset, value_format.format(v), va="center", fontsize=8, color=TEXT_PRIMARY)
    ax.set_yticks(range(len(labels)), labels, fontsize=9, color=TEXT_PRIMARY)
    ax.invert_yaxis()
    ax.set_xlabel(xlabel, fontsize=9, color=TEXT_SECONDARY)
    ax.set_xlim(0, xmax if xmax is not None else top * 1.15)
    ax.xaxis.set_major_locator(matplotlib.ticker.MaxNLocator(integer=True))
    if n > 1:
        ax.legend(frameon=False, fontsize=9, loc="lower left", bbox_to_anchor=(0, 1.0), ncol=2,
                  labelcolor=TEXT_PRIMARY)
    return _finish(fig, title, source, path)
