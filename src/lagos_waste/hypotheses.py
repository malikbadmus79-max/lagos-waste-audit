"""LGA indicator table and rank correlations for the hypothesis tests (notebook 03)."""

from __future__ import annotations

import pandas as pd
from scipy.stats import spearmanr

from lagos_waste import news_analysis as na
from lagos_waste.paths import DATA_PROCESSED

COVERAGE_PATH = DATA_PROCESSED / "coverage_by_lga.csv"
DISTANCE_PATH = DATA_PROCESSED / "site_distance_by_lga.csv"
SURVEY_PATH = DATA_PROCESSED / "survey_clean.csv"
INDICATORS_PATH = DATA_PROCESSED / "lga_indicators.csv"


def survey_counts(survey: pd.DataFrame) -> pd.DataFrame:
    """Per LGA: survey responses and responses reporting a last collection over 14 days ago."""
    g = survey.groupby("lga")
    return pd.DataFrame({
        "survey_responses": g.size(),
        "survey_gap_over_14_days": g["gap_over_14_days"].apply(lambda s: int((s == "yes").sum())),
    }).reset_index()


def lga_indicators(coverage: pd.DataFrame, distance: pd.DataFrame, news: pd.DataFrame,
                   survey: pd.DataFrame) -> pd.DataFrame:
    """One row per LGA joining operator coverage, site distance, news counts and survey counts."""
    out = coverage.drop(columns=["source_id"], errors="ignore")
    out = out.merge(distance.drop(columns=["source_id"], errors="ignore"), on="lga", how="left")
    out = out.merge(news[["lga", "articles", "failure_articles", "failure_lga_weeks"]], on="lga", how="left")
    out = out.merge(survey_counts(survey), on="lga", how="left")
    for col in ["survey_responses", "survey_gap_over_14_days"]:
        out[col] = out[col].fillna(0).astype(int)
    out["failure_articles_per_million_npc"] = (out["failure_articles"] / out["population_2006_npc"] * 1e6).round(2)
    out["source_id"] = "S16;S17;S18;S19;S20;S21;complaints.csv"
    return out


def build_indicators() -> pd.DataFrame:
    """Read the processed inputs and return the LGA indicator table."""
    survey = pd.read_csv(SURVEY_PATH, dtype=str, keep_default_na=False)
    news = na.counts_by_lga(na.load_complaints())
    return lga_indicators(pd.read_csv(COVERAGE_PATH), pd.read_csv(DISTANCE_PATH), news, survey)


def spearman_table(df: pd.DataFrame, xs: list[str], ys: list[str]) -> pd.DataFrame:
    """Spearman rank correlation and two-sided p-value for each x and y pair, over rows with both values."""
    rows = []
    for x in xs:
        for y in ys:
            pair = df[[x, y]].dropna()
            rho, p = spearmanr(pair[x], pair[y])
            rows.append({"x": x, "y": y, "n": len(pair), "rho": round(float(rho), 2), "p_value": round(float(p), 3)})
    return pd.DataFrame(rows)
