"""Tests for lagos_waste.hypotheses."""

import pandas as pd

from lagos_waste import hypotheses as hy


def test_survey_counts_per_lga() -> None:
    """Responses and long gaps are counted per LGA."""
    s = pd.DataFrame({"lga": ["Alimosho", "Alimosho", "Epe"], "gap_over_14_days": ["yes", "", "yes"]})
    out = hy.survey_counts(s).set_index("lga")
    assert out.loc["Alimosho", "survey_responses"] == 2 and out.loc["Alimosho", "survey_gap_over_14_days"] == 1


def test_lga_indicators_join_and_rate() -> None:
    """Tables join on LGA, missing survey counts become 0 and the per-million rate is computed."""
    cov = pd.DataFrame({"lga": ["Agege", "Epe"], "population_2006_npc": [500_000, 200_000], "source_id": ["x", "x"]})
    dist = pd.DataFrame({"lga": ["Agege", "Epe"], "km_to_nearest_site": [7.4, 52.4]})
    news = pd.DataFrame({"lga": ["Agege", "Epe"], "articles": [7, 2], "failure_articles": [4, 0],
                         "failure_lga_weeks": [4, 0]})
    survey = pd.DataFrame({"lga": ["Epe"], "gap_over_14_days": ["yes"]})
    out = hy.lga_indicators(cov, dist, news, survey).set_index("lga")
    assert out.loc["Agege", "survey_responses"] == 0 and out.loc["Epe", "survey_gap_over_14_days"] == 1
    assert out.loc["Agege", "failure_articles_per_million_npc"] == 8.0


def test_spearman_table_perfect_rank_order() -> None:
    """Identical rank orders give rho of 1; reversed give -1."""
    df = pd.DataFrame({"a": [1, 2, 3, 4], "b": [10, 20, 30, 40], "c": [4, 3, 2, 1]})
    out = hy.spearman_table(df, ["a"], ["b", "c"]).set_index("y")
    assert out.loc["b", "rho"] == 1.0 and out.loc["c", "rho"] == -1.0 and out.loc["b", "n"] == 4
