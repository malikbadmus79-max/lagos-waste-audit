"""Tests for lagos_waste.coverage."""

import pandas as pd
import pytest

from lagos_waste import coverage
from lagos_waste.geo import LGAS

TABLES = [[
    ["DOMESTIC AND COMMERCIAL PSP DIRECTORY", None, None, None, None, None, None],
    ["", "LOCAL GOVERNMENT/LCDA", "NAME OF PSP OPERATOR", "LOCAL GOVERNMENT/LCDA", "SLOTS/WARDS", "CONTACT", "DISTRICT"],
    ["1", "IGANDO-IKOTUN", "OPERATOR A", "IGANDO-IKOTUN", "IKOTUN", "x", "WEST II"],
    ["2", "EGBE IDIMU", "OPERATOR A", "EGBE IDIMU", "IDIMU", "x", "WEST II"],
    ["3", "EGBE IDIMU", "OPERATOR B", "EGBE IDIMU", "EGBE", "x", "WEST II"],
    ["3", "EGBE IDIMU", "OPERATOR B", "EGBE IDIMU", "EGBE II", "x", "WEST II"],
    ["", "", "", "", "", "", ""],
    ["1", "IRU/VI", "OPERATOR C", "IRU/VI", "VI", "x", "EAST 1"],
]]


def test_directory_rows_skip_headers_and_blanks() -> None:
    """Only numbered rows are kept."""
    rows = coverage.directory_rows(TABLES)
    assert len(rows) == 5 and set(rows["area"]) == {"IGANDO-IKOTUN", "EGBE IDIMU", "IRU/VI"}


def test_operators_by_lga_counts_distinct_operators_and_slots() -> None:
    """LCDAs roll up to their LGA; an operator in two LCDAs of one LGA counts once."""
    out = coverage.operators_by_lga(coverage.directory_rows(TABLES)).set_index("lga")
    assert len(out) == 20
    assert out.loc["Alimosho", "psp_operators"] == 2 and out.loc["Alimosho", "psp_ward_slots"] == 4
    assert out.loc["Eti-Osa", "psp_operators"] == 1 and out.loc["Epe", "psp_operators"] == 0


def test_unknown_area_is_rejected() -> None:
    """A directory area without an LGA mapping stops the build."""
    rows = pd.DataFrame({"area": ["NOWHERE"], "operator": ["X"], "ward": ["Y"]})
    with pytest.raises(ValueError):
        coverage.operators_by_lga(rows)


def test_area_mapping_covers_only_project_lgas() -> None:
    """Every mapped LGA is one of the 20 constitutional LGAs."""
    assert set(coverage.AREA_TO_LGA.values()) <= set(LGAS)


def test_state_population_parses_table_text() -> None:
    """Table 1.2 lines are parsed for all 20 LGAs."""
    text = "\n".join(f"{name} 1,000 2,000 3,000" for name in coverage.STATE_NAMES)
    out = coverage.state_population(text)
    assert len(out) == 20 and (out["population_2006_state"] == 3000).all()


def test_build_coverage_ratios_and_zero_operators() -> None:
    """Residents per operator are computed, and LGAs without operators get no ratio."""
    ops = pd.DataFrame({"lga": ["Agege", "Epe"], "psp_operators": [10, 0], "psp_ward_slots": [20, 0],
                        "directory_areas": [1, 0]})
    npc = pd.DataFrame({"lga": ["Agege", "Epe"], "population_2006": [100_000, 50_000]})
    state = pd.DataFrame({"lga": ["Agege", "Epe"], "population_2006_state": [200_000, 80_000]})
    out = coverage.build_coverage(ops, npc, state).set_index("lga")
    assert out.loc["Agege", "residents_per_operator_npc"] == 10_000
    assert out.loc["Agege", "residents_per_slot_state"] == 10_000
    assert pd.isna(out.loc["Epe", "residents_per_operator_npc"])
