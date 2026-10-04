"""Tests for lagos_waste.news_analysis."""

import pandas as pd

from lagos_waste import news_analysis as na


def complaints() -> pd.DataFrame:
    """Three articles: one failure report in two LGAs, a same-week repeat, and an enforcement story."""
    rows = [
        ("a1", "2026-03-02", "Alimosho", "yes", "service_failure_report", "missed_collection;waste_pileup", "psp_operators", "resident"),
        ("a1", "2026-03-02", "Agege", "yes", "service_failure_report", "missed_collection;waste_pileup", "psp_operators", "resident"),
        ("a2", "2026-03-04", "Alimosho", "yes", "official_statement", "missed_collection", "residents;psp_operators", "official"),
        ("a3", "2026-05-10", "Mushin", "no", "enforcement", "illegal_dumping", "residents", "official"),
        ("a4", "2026-05-11", "Lagos-wide", "no", "policy_or_investment", "none", "none_stated", "none"),
    ]
    df = pd.DataFrame(rows, columns=["article_id", "date", "lga", "is_service_failure", "article_type",
                                     "problem_types", "blamed", "blame_source"])
    df["date"] = pd.to_datetime(df["date"])
    return df


def test_counts_by_lga_lists_all_lgas_and_dedupes_weeks() -> None:
    """Every LGA appears; two failure articles in one LGA and week give one LGA-week."""
    t = na.counts_by_lga(complaints()).set_index("lga")
    assert len(t) == 22
    assert t.loc["Alimosho", "failure_articles"] == 2 and t.loc["Alimosho", "failure_lga_weeks"] == 1
    assert t.loc["Mushin", "articles"] == 1 and t.loc["Mushin", "failure_articles"] == 0
    assert t.loc["Epe", "articles"] == 0
    assert list(t.index[-2:]) == ["Lagos-wide", "unspecified"]


def test_problem_shares_count_articles_not_rows() -> None:
    """An article in two LGAs is counted once."""
    t = na.problem_shares(complaints(), failure_only=True).set_index("problem_type")
    assert t.loc["missed_collection", "articles"] == 2 and t.loc["missed_collection", "share_pct"] == 100.0
    assert t.loc["waste_pileup", "articles"] == 1


def test_blame_by_source_excludes_none_stated() -> None:
    """Blame counts are per article and actor, split by source."""
    t = na.blame_by_source(complaints())
    assert "none_stated" not in t.index
    assert t.loc["psp_operators", "total"] == 2 and t.loc["residents", "official"] == 2
