"""Loading, validation and arithmetic checks for official Lagos waste statistics.

The dataset is `data/processed/official_stats.csv`. Every row carries a
`source_id` that must match an entry in `docs/sources.md`.
"""

from __future__ import annotations

import re
from datetime import date
from pathlib import Path

import pandas as pd

from lagos_waste.paths import DATA_PROCESSED, ROOT

OFFICIAL_STATS_PATH: Path = DATA_PROCESSED / "official_stats.csv"
SOURCES_PATH: Path = ROOT / "docs" / "sources.md"

REQUIRED_COLUMNS: list[str] = [
    "record_id",
    "period_start",
    "period_end",
    "metric",
    "value",
    "value_high",
    "unit",
    "value_type",
    "source_id",
    "note",
]
VALUE_TYPES: set[str] = {"reported", "derived"}
SOURCE_ID_PATTERN = re.compile(r"^S\d{2,}$")


def load_official_stats(path: Path = OFFICIAL_STATS_PATH) -> pd.DataFrame:
    """Read the official statistics CSV with parsed dates and numeric values."""
    df = pd.read_csv(path, dtype={"record_id": str, "source_id": str})
    df["period_start"] = pd.to_datetime(df["period_start"], format="%Y-%m-%d")
    df["period_end"] = pd.to_datetime(df["period_end"], format="%Y-%m-%d")
    df["value"] = pd.to_numeric(df["value"])
    df["value_high"] = pd.to_numeric(df["value_high"])
    return df


def source_ids_in_log(path: Path = SOURCES_PATH) -> set[str]:
    """Return the set of source IDs listed in the first column of the source log table."""
    ids: set[str] = set()
    for line in path.read_text(encoding="utf-8").splitlines():
        match = re.match(r"^\|\s*(S\d{2,})\s*\|", line)
        if match:
            ids.add(match.group(1))
    return ids


def validate_official_stats(df: pd.DataFrame, known_sources: set[str]) -> list[str]:
    """Return a list of validation problems; an empty list means the dataset passes."""
    problems: list[str] = []
    missing = [c for c in REQUIRED_COLUMNS if c not in df.columns]
    if missing:
        return [f"missing columns: {missing}"]
    if df["record_id"].duplicated().any():
        problems.append("duplicate record_id values")
    if (df["value"] < 0).any():
        problems.append("negative values")
    ranged = df["value_high"].notna()
    if (df.loc[ranged, "value_high"] < df.loc[ranged, "value"]).any():
        problems.append("value_high below value")
    if (df["period_end"] < df["period_start"]).any():
        problems.append("period_end before period_start")
    bad_types = set(df["value_type"]) - VALUE_TYPES
    if bad_types:
        problems.append(f"unknown value_type: {sorted(bad_types)}")
    bad_ids = {s for s in df["source_id"] if not SOURCE_ID_PATTERN.match(str(s))}
    if bad_ids:
        problems.append(f"malformed source_id: {sorted(bad_ids)}")
    unknown = set(df["source_id"]) - known_sources
    if unknown:
        problems.append(f"source_id not in docs/sources.md: {sorted(unknown)}")
    return problems


def days_in_period(start: date, end: date) -> int:
    """Number of calendar days from start to end, counting both ends [A01]."""
    days = (end - start).days + 1
    if days < 1:
        raise ValueError("end date is before start date")
    return days


def daily_average(total: float, start: date, end: date) -> float:
    """Average per calendar day of a total reported for a period [A01]."""
    return total / days_in_period(start, end)


def tonnes_per_trip(tonnes: float, trips: float) -> float:
    """Average load per truck trip implied by a tonnage and a trip count."""
    if trips <= 0:
        raise ValueError("trips must be positive")
    return tonnes / trips


def trips_to_tonnes(trips: float, payload: float = 10.0) -> float:
    """Tonnage implied by a trip count at an assumed payload per trip [A02]."""
    return trips * payload


def share_of(part: float, whole: float) -> float:
    """Part as a percentage of whole."""
    if whole <= 0:
        raise ValueError("whole must be positive")
    return 100.0 * part / whole
