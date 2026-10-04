"""Summaries of the tagged news record in `data/processed/complaints.csv` (notebook 02).

`complaints.csv` holds one row per article and LGA. Article-level summaries therefore
de-duplicate on `article_id` before counting.
"""

from __future__ import annotations

import pandas as pd

from lagos_waste.geo import LGAS
from lagos_waste.paths import DATA_PROCESSED
from lagos_waste.tagging import MULTI_VALUES, split_multi

COMPLAINTS_PATH = DATA_PROCESSED / "complaints.csv"
NON_LGA = ["Lagos-wide", "unspecified"]


def load_complaints() -> pd.DataFrame:
    """Read complaints.csv with text columns kept as strings and dates parsed."""
    df = pd.read_csv(COMPLAINTS_PATH, dtype=str, keep_default_na=False)
    df["date"] = pd.to_datetime(df["date"])
    return df


def articles(complaints: pd.DataFrame) -> pd.DataFrame:
    """One row per article (LGA columns dropped)."""
    return complaints.drop(columns=["lga"]).drop_duplicates("article_id").reset_index(drop=True)


def lga_weeks(complaints: pd.DataFrame) -> pd.DataFrame:
    """Distinct LGA and ISO-week pairs, so several reports of one event in one week count once [A07]."""
    iso = complaints["date"].dt.isocalendar()
    out = complaints.assign(week=iso["year"].astype(str) + "-W" + iso["week"].astype(str).str.zfill(2))
    return out[["lga", "week"]].drop_duplicates()


def counts_by_lga(complaints: pd.DataFrame) -> pd.DataFrame:
    """Per LGA: all relevant articles, service-failure articles and service-failure LGA-weeks.

    All 20 LGAs are listed, with zeros where no article was found; `Lagos-wide` and
    `unspecified` rows follow the LGAs.
    """
    failure = complaints[complaints["is_service_failure"] == "yes"]
    table = pd.DataFrame({"lga": LGAS + NON_LGA})
    table["articles"] = table["lga"].map(complaints.groupby("lga")["article_id"].nunique())
    table["failure_articles"] = table["lga"].map(failure.groupby("lga")["article_id"].nunique())
    table["failure_lga_weeks"] = table["lga"].map(lga_weeks(failure).groupby("lga").size())
    table = table.fillna(0)
    for col in ["articles", "failure_articles", "failure_lga_weeks"]:
        table[col] = table[col].astype(int)
    lgas = table[table["lga"].isin(LGAS)].sort_values(["failure_articles", "articles", "lga"],
                                                     ascending=[False, False, True])
    return pd.concat([lgas, table[table["lga"].isin(NON_LGA)]], ignore_index=True)


def problem_shares(complaints: pd.DataFrame, failure_only: bool = False) -> pd.DataFrame:
    """Number and share of articles describing each problem type (an article can describe several)."""
    arts = articles(complaints)
    if failure_only:
        arts = arts[arts["is_service_failure"] == "yes"]
    rows = []
    for problem in sorted(MULTI_VALUES["problem_types"] - {"none"}):
        n = int(arts["problem_types"].map(lambda v, p=problem: p in split_multi(v)).sum())
        rows.append({"problem_type": problem, "articles": n, "share_pct": round(100 * n / max(len(arts), 1), 1)})
    return pd.DataFrame(rows).sort_values(["articles", "problem_type"], ascending=[False, True]).reset_index(drop=True)


def blame_by_source(complaints: pd.DataFrame) -> pd.DataFrame:
    """Articles assigning blame to each actor, split by who assigns it (one count per article and actor)."""
    arts = articles(complaints)
    long = arts.assign(blamed=arts["blamed"].map(split_multi)).explode("blamed", ignore_index=True)
    long = long[long["blamed"] != "none_stated"]
    table = pd.crosstab(long["blamed"], long["blame_source"])
    table["total"] = table.sum(axis=1)
    return table.sort_values("total", ascending=False)


def type_by_year(complaints: pd.DataFrame) -> pd.DataFrame:
    """Articles per publication year and article type."""
    arts = articles(complaints)
    return pd.crosstab(arts["date"].dt.year.rename("year"), arts["article_type"])
