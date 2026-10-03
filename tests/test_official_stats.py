"""Tests for lagos_waste.official_stats."""

from datetime import date

import pandas as pd
import pytest

from lagos_waste import official_stats as os_


@pytest.fixture(scope="module")
def stats() -> pd.DataFrame:
    """The committed official statistics dataset."""
    return os_.load_official_stats()


def test_dataset_passes_validation(stats: pd.DataFrame) -> None:
    """Every row has valid dates, values, types and a logged source."""
    assert os_.validate_official_stats(stats, os_.source_ids_in_log()) == []


def test_source_log_contains_expected_ids() -> None:
    """The source log parser finds the logged IDs."""
    ids = os_.source_ids_in_log()
    assert {"S01", "S02", "S10", "S15"} <= ids


def test_validation_flags_unknown_source(stats: pd.DataFrame) -> None:
    """A source ID missing from the log is reported."""
    bad = stats.copy()
    bad.loc[0, "source_id"] = "S99"
    problems = os_.validate_official_stats(bad, os_.source_ids_in_log())
    assert any("S99" in p for p in problems)


def test_validation_flags_negative_value(stats: pd.DataFrame) -> None:
    """Negative values are reported."""
    bad = stats.copy()
    bad.loc[0, "value"] = -1
    assert "negative values" in os_.validate_official_stats(bad, os_.source_ids_in_log())


def test_days_in_period_counts_both_ends() -> None:
    """May has 31 days and a Monday-to-Sunday week has 7."""
    assert os_.days_in_period(date(2026, 5, 1), date(2026, 5, 31)) == 31
    assert os_.days_in_period(date(2026, 7, 28), date(2026, 8, 3)) == 7


def test_days_in_period_rejects_reversed_dates() -> None:
    """An end date before the start date raises an error."""
    with pytest.raises(ValueError):
        os_.days_in_period(date(2026, 5, 31), date(2026, 5, 1))


def test_may_2026_daily_average() -> None:
    """418,500 tonnes over May 2026 is 13,500 tonnes per day, not the stated 13,200."""
    avg = os_.daily_average(418_500, date(2026, 5, 1), date(2026, 5, 31))
    assert avg == pytest.approx(13_500)
    assert avg != pytest.approx(13_200)


def test_weekly_daily_average() -> None:
    """18,660 tonnes over 28 July to 3 August 2026 is about 2,666 tonnes per day."""
    avg = os_.daily_average(18_660, date(2026, 7, 28), date(2026, 8, 3))
    assert avg == pytest.approx(2_665.71, abs=0.01)


def test_tonnes_per_trip_is_exactly_ten() -> None:
    """Both S02 tonnage figures equal 10 tonnes per trip."""
    assert os_.tonnes_per_trip(18_660, 1_866) == pytest.approx(10.0)
    assert os_.tonnes_per_trip(3_490, 349) == pytest.approx(10.0)


def test_tonnes_per_trip_rejects_zero_trips() -> None:
    """Zero trips raises an error."""
    with pytest.raises(ValueError):
        os_.tonnes_per_trip(100, 0)


def test_trips_to_tonnes() -> None:
    """850 trips at 10 tonnes is 8,500 tonnes [A02]."""
    assert os_.trips_to_tonnes(850) == pytest.approx(8_500)
    assert os_.trips_to_tonnes(850, payload=8) == pytest.approx(6_800)


def test_share_of() -> None:
    """13,500 is 90% of 15,000 and 4,263 is about 32.8% of 13,000."""
    assert os_.share_of(13_500, 15_000) == pytest.approx(90.0)
    assert os_.share_of(4_263, 13_000) == pytest.approx(32.79, abs=0.01)


def test_budget_components_sum_to_total(stats: pd.DataFrame) -> None:
    """Recurrent plus capital expenditure equals total expenditure in every budget year."""
    budget = stats[stats["metric"].str.startswith("lawma_budget_")]
    wide = budget.pivot_table(index="source_id", columns="metric", values="value")
    for _, row in wide.iterrows():
        total = row["lawma_budget_recurrent_expenditure"] + row["lawma_budget_capital_expenditure"]
        assert total == pytest.approx(row["lawma_budget_total_expenditure"], abs=0.01)


def test_derived_rows_match_their_calculation(stats: pd.DataFrame) -> None:
    """Derived daily averages in the dataset equal the computed values."""
    derived = stats.set_index("record_id")
    assert derived.loc["R018", "value"] == pytest.approx(418_500 / 31)
    assert derived.loc["R025", "value"] == round(18_660 / 7)
