"""Tests for lagos_waste.charts."""

from pathlib import Path

from matplotlib.figure import Figure

from lagos_waste import charts


def test_daily_tonnage_chart_saves_png(tmp_path: Path) -> None:
    """The tonnage chart returns a figure and writes a PNG."""
    out = tmp_path / "tonnage.png"
    fig = charts.daily_tonnage_chart(
        [("Range", 13_000, 15_000, False), ("Point", 13_500, None, True)], "Title", "Source: S01", out
    )
    assert isinstance(fig, Figure)
    assert out.is_file() and out.stat().st_size > 0


def test_budget_chart_handles_missing_year(tmp_path: Path) -> None:
    """A year with no data is skipped without error."""
    out = tmp_path / "budget.png"
    fig = charts.budget_chart(["2021", "2023"], [19.5, None], [1.1, None], "Title", "Source: S11", out)
    assert isinstance(fig, Figure)
    assert out.is_file()


def test_trips_chart_saves_png(tmp_path: Path) -> None:
    """The trips chart writes a PNG with reported and derived rows."""
    out = tmp_path / "trips.png"
    charts.trips_chart([("Reported", 850, False), ("Derived", 1_350, True)], "Title", "Source: S07", out)
    assert out.is_file()


def test_grouped_hbar_saves(tmp_path) -> None:
    """One- and two-series horizontal bar charts are written to disk."""
    from lagos_waste import charts as ch
    ch.grouped_hbar(["a", "b"], [("x", [1, 2])], "t", "n", "Source: test", tmp_path / "one.png")
    ch.grouped_hbar(["a", "b"], [("x", [1, 2]), ("y", [3, 0])], "t", "n", "Source: test", tmp_path / "two.png")
    assert (tmp_path / "one.png").exists() and (tmp_path / "two.png").exists()
