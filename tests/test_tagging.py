"""Tests for lagos_waste.tagging."""

import pandas as pd
import pytest

from lagos_waste import tagging


def tag_row(**overrides) -> dict:
    """A valid tag row, with optional overrides."""
    row = {
        "article_id": "businessday-1", "relevant": "yes", "article_type": "service_failure_report",
        "problem_types": "waste_pileup;missed_collection", "lgas": "Alimosho", "place_names": "Ikotun",
        "blamed": "psp_operators", "blame_source": "resident", "psp_named": "no", "event_month": "2025-03",
        "evidence": "Residents of Ikotun report refuse uncollected for three weeks.", "tagger": "claude-code",
        "tagged_on": "2026-10-03",
    }
    row.update(overrides)
    return row


INDEX = pd.DataFrame({
    "article_id": ["businessday-1", "businessday-2", "nannews-3"],
    "outlet": ["businessday", "businessday", "nannews"],
    "date": ["2025-03-10", "2025-04-01", "2026-01-05"],
    "url": ["u1", "u2", "u3"],
    "title": ["t1", "t2", "t3"],
})
IDS = set(INDEX["article_id"])


def test_valid_row_passes() -> None:
    """A row that follows the protocol has no problems."""
    assert tagging.validate_tags(pd.DataFrame([tag_row()]), IDS) == []


@pytest.mark.parametrize(
    ("override", "fragment"),
    [
        ({"relevant": "maybe"}, "relevant"),
        ({"problem_types": "flooding"}, "problem_types"),
        ({"lgas": "Lekki"}, "lgas"),
        ({"blamed": ""}, "blamed is empty"),
        ({"event_month": "March 2025"}, "event_month"),
        ({"article_id": "punch-9"}, "not in news_index"),
        ({"evidence": " ".join(["word"] * 26)}, "evidence longer"),
        ({"relevant": "no"}, "relevant=no requires"),
        ({"tagged_on": "3/10/2026"}, "tagged_on"),
    ],
)
def test_invalid_values_are_reported(override: dict, fragment: str) -> None:
    """Each kind of protocol violation is reported."""
    problems = tagging.validate_tags(pd.DataFrame([tag_row(**override)]), IDS)
    assert any(fragment in p for p in problems), problems


def test_duplicates_are_reported() -> None:
    """The same article tagged twice is reported."""
    tags = pd.DataFrame([tag_row(), tag_row()])
    assert any("duplicate" in p for p in tagging.validate_tags(tags, IDS))


def test_blank_event_month_allowed() -> None:
    """event_month may be blank when the date of the event is not stated."""
    assert tagging.validate_tags(pd.DataFrame([tag_row(event_month="")]), IDS) == []


def test_next_batch_skips_tagged() -> None:
    """The next batch lists untagged articles in index order."""
    tags = pd.DataFrame([tag_row()])
    assert tagging.next_batch(INDEX, tags, size=5) == ["businessday-2", "nannews-3"]


def test_sample_is_reproducible() -> None:
    """The same seed draws the same sample, with empty check columns."""
    tags = pd.DataFrame([tag_row(article_id=f"a{i}") for i in range(80)])
    s1, s2 = tagging.draw_sample(tags), tagging.draw_sample(tags)
    assert len(s1) == 50 and list(s1["article_id"]) == list(s2["article_id"])
    assert (s1["check_lgas"] == "").all()


def test_field_agrees() -> None:
    """'ok' and equal values agree; list order does not matter."""
    assert tagging.field_agrees("a;b", "ok", multi=True)
    assert tagging.field_agrees("a;b", "b; a", multi=True)
    assert not tagging.field_agrees("a;b", "a", multi=True)
    assert tagging.field_agrees("yes", "yes", multi=False)


def test_accuracy_counts_only_checked_rows() -> None:
    """Agreement is computed over rows with a filled check column."""
    sample = pd.DataFrame([tag_row(article_id="a1"), tag_row(article_id="a2"), tag_row(article_id="a3")])
    for f in tagging.CHECK_FIELDS:
        sample[f"check_{f}"] = ""
    sample.loc[0, "check_lgas"] = "ok"
    sample.loc[1, "check_lgas"] = "Ikeja"
    acc = tagging.accuracy(sample).set_index("field")
    assert acc.loc["lgas", "checked"] == 2 and acc.loc["lgas", "agree"] == 1
    assert acc.loc["lgas", "agreement_pct"] == 50.0


def test_normalise_title() -> None:
    """Case, punctuation and spacing differences are ignored."""
    assert tagging.normalise_title("LAWMA seals  Ladipo market!") == tagging.normalise_title("lawma seals ladipo market")


def test_duplicate_groups_within_window() -> None:
    """Same title within seven days maps to the earliest ID; a repeat months later does not."""
    index = pd.DataFrame({
        "article_id": ["b-2", "b-1", "b-3"],
        "date": ["2025-03-12", "2025-03-10", "2025-09-01"],
        "title": ["LAWMA shuts Ladipo market", "LAWMA shuts Ladipo market", "LAWMA shuts Ladipo market"],
    })
    canon = tagging.duplicate_groups(index)
    assert canon == {"b-1": "b-1", "b-2": "b-1", "b-3": "b-3"}


def test_merge_duplicates_unions_values() -> None:
    """Duplicate rows collapse to the earliest ID with combined values."""
    tags = pd.DataFrame([
        tag_row(article_id="b-1", problem_types="market_waste", blamed="traders"),
        tag_row(article_id="b-2", problem_types="market_waste;fees_or_billing", blamed="none_stated"),
    ])
    out = tagging.merge_duplicates(tags, {"b-1": "b-1", "b-2": "b-1"})
    assert len(out) == 1
    assert out.loc[0, "article_id"] == "b-1"
    assert out.loc[0, "problem_types"] == "market_waste;fees_or_billing"
    assert out.loc[0, "blamed"] == "traders"
    assert out.loc[0, "duplicate_ids"] == "b-2"


@pytest.mark.parametrize(
    ("article_type", "problems", "expected"),
    [
        ("service_failure_report", "waste_pileup", "yes"),
        ("enforcement", "market_waste;missed_collection", "yes"),
        ("enforcement", "illegal_dumping", "no"),
    ],
)
def test_is_service_failure(article_type: str, problems: str, expected: str) -> None:
    """Service failure means a failure report or a described missed collection."""
    assert tagging.is_service_failure(article_type, problems) == expected


def test_build_complaints_one_row_per_lga() -> None:
    """Relevant articles are expanded to one row per LGA; irrelevant ones are dropped."""
    tags = pd.DataFrame([
        tag_row(lgas="Alimosho;Ikeja"),
        tag_row(article_id="nannews-3", relevant="no", problem_types="none", lgas="unspecified"),
    ])
    out = tagging.build_complaints(INDEX, tags)
    assert list(out["lga"]) == ["Alimosho", "Ikeja"]
    assert set(out["outlet"]) == {"businessday"}
    assert set(out["is_service_failure"]) == {"yes"}


def test_build_complaints_collapses_duplicates() -> None:
    """Two copies of the same article produce one article in the output."""
    index = pd.DataFrame({
        "article_id": ["b-1", "b-2"], "outlet": ["businessday", "businessday"],
        "date": ["2025-03-10", "2025-03-11"], "url": ["u1", "u2"],
        "title": ["Refuse piles up in Ikotun", "Refuse piles up in Ikotun"],
    })
    tags = pd.DataFrame([tag_row(article_id="b-1"), tag_row(article_id="b-2", lgas="Alimosho;Ikeja")])
    out = tagging.build_complaints(index, tags)
    assert out["article_id"].unique().tolist() == ["b-1"]
    assert sorted(out["lga"]) == ["Alimosho", "Ikeja"]


def test_cart_pushers_is_an_allowed_blame_value() -> None:
    """Informal collectors have their own blame category."""
    assert tagging.validate_tags(pd.DataFrame([tag_row(blamed="cart_pushers;residents")]), IDS) == []


def test_text_containment_finds_retitled_duplicate() -> None:
    """A story republished under a new headline with an added paragraph is detected from its text."""
    base = " ".join(f"word{i}" for i in range(60))
    index = pd.DataFrame({
        "article_id": ["b-1", "b-2", "b-3"],
        "date": ["2023-10-09", "2023-10-09", "2023-10-09"],
        "title": ["Lagos markets reopened", "Lagos reopens Ladipo, Oyingbo markets", "Unrelated story"],
    })
    texts = {"b-1": base, "b-2": base + " extra paragraph on fees paid by traders", "b-3": "something else entirely " * 10}
    canon = tagging.duplicate_groups(index, texts)
    assert canon["b-2"] == "b-1" and canon["b-3"] == "b-3"


def test_containment_bounds() -> None:
    """Containment is 1 for a subset and 0 for an empty set."""
    a = tagging.shingles("one two three four five six seven")
    assert tagging.containment(a, a | {"x y z w v"}) == 1.0
    assert tagging.containment(set(), a) == 0.0
