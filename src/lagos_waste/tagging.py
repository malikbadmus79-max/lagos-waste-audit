"""Validation, progress tracking, hand-check sampling and output for news article tags.

The protocol is in `docs/tagging_protocol.md`. Commands (from the repository root):

    python -m lagos_waste.tagging status      progress and the next batch of article IDs
    python -m lagos_waste.tagging validate    check every tag row against the protocol
    python -m lagos_waste.tagging sample      draw the 50-article hand-check sample
    python -m lagos_waste.tagging accuracy    agreement between model tags and hand checks
    python -m lagos_waste.tagging duplicates  list articles published more than once
    python -m lagos_waste.tagging build       write data/processed/complaints.csv
"""

from __future__ import annotations

import argparse
import re

import pandas as pd

from lagos_waste.news import LGAS
from lagos_waste.paths import DATA_INTERIM, DATA_PROCESSED

INDEX_PATH = DATA_INTERIM / "news_index.csv"
TAGS_PATH = DATA_INTERIM / "news_tags.csv"
SAMPLE_PATH = DATA_INTERIM / "handcheck_sample.csv"
COMPLAINTS_PATH = DATA_PROCESSED / "complaints.csv"

TAG_COLUMNS = [
    "article_id", "relevant", "article_type", "problem_types", "lgas", "place_names", "blamed",
    "blame_source", "psp_named", "event_month", "evidence", "tagger", "tagged_on",
]
SINGLE_VALUES: dict[str, set[str]] = {
    "relevant": {"yes", "no"},
    "article_type": {"service_failure_report", "official_statement", "enforcement",
                     "policy_or_investment", "opinion", "other"},
    "blame_source": {"official", "resident", "journalist", "expert", "mixed", "none"},
    "psp_named": {"yes", "no"},
}
MULTI_VALUES: dict[str, set[str]] = {
    "problem_types": {"missed_collection", "waste_pileup", "illegal_dumping", "blocked_drains", "road_access",
                      "dumpsite_access", "fees_or_billing", "operator_capacity", "market_waste",
                      "other", "none"},
    "lgas": set(LGAS) | {"Lagos-wide", "unspecified"},
    "blamed": {"residents", "cart_pushers", "psp_operators", "lawma", "state_government", "local_government",
               "traders", "none_stated", "other"},
}
CHECK_FIELDS = ["relevant", "article_type", "problem_types", "lgas", "blamed"]
SAMPLE_RELEVANT = 30
SAMPLE_NOT_RELEVANT = 20
SAMPLE_SEED = 2026
BATCH_SIZE = 25
MAX_EVIDENCE_WORDS = 25


def split_multi(value: object) -> list[str]:
    """Split a ';'-separated cell into trimmed values."""
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return []
    return [v.strip() for v in str(value).split(";") if v.strip()]


def load_index() -> pd.DataFrame:
    """The article index, with outlet codes kept as strings."""
    return pd.read_csv(INDEX_PATH, dtype=str, keep_default_na=False)


def load_tags() -> pd.DataFrame:
    """Tag rows written so far; an empty frame if none exist."""
    if not TAGS_PATH.exists():
        return pd.DataFrame(columns=TAG_COLUMNS)
    return pd.read_csv(TAGS_PATH, dtype=str, keep_default_na=False)


def validate_tags(tags: pd.DataFrame, index_ids: set[str]) -> list[str]:
    """Return a list of protocol violations; an empty list means all rows pass."""
    problems: list[str] = []
    missing = [c for c in TAG_COLUMNS if c not in tags.columns]
    if missing:
        return [f"missing columns: {missing}"]
    dupes = tags["article_id"][tags["article_id"].duplicated()].tolist()
    if dupes:
        problems.append(f"duplicate article_id: {dupes}")
    for _, row in tags.iterrows():
        aid = row["article_id"]
        if aid not in index_ids:
            problems.append(f"{aid}: not in news_index.csv")
        for col, allowed in SINGLE_VALUES.items():
            if row[col] not in allowed:
                problems.append(f"{aid}: {col}={row[col]!r} not allowed")
        for col, allowed in MULTI_VALUES.items():
            values = split_multi(row[col])
            if not values:
                problems.append(f"{aid}: {col} is empty")
            bad = [v for v in values if v not in allowed]
            if bad:
                problems.append(f"{aid}: {col} has {bad}")
        if row["event_month"] and not re.fullmatch(r"20\d{2}-(0[1-9]|1[0-2])", row["event_month"]):
            problems.append(f"{aid}: event_month={row['event_month']!r} not YYYY-MM")
        if len(str(row["evidence"]).split()) > MAX_EVIDENCE_WORDS:
            problems.append(f"{aid}: evidence longer than {MAX_EVIDENCE_WORDS} words")
        if row["relevant"] == "no" and split_multi(row["problem_types"]) != ["none"]:
            problems.append(f"{aid}: relevant=no requires problem_types=none")
        if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", str(row["tagged_on"])):
            problems.append(f"{aid}: tagged_on not YYYY-MM-DD")
    return problems


def next_batch(index: pd.DataFrame, tags: pd.DataFrame, size: int = BATCH_SIZE) -> list[str]:
    """IDs of the next untagged articles, in index order."""
    done = set(tags["article_id"])
    return [a for a in index["article_id"] if a not in done][:size]


def draw_sample(
    tags: pd.DataFrame,
    index: pd.DataFrame | None = None,
    n_relevant: int = SAMPLE_RELEVANT,
    n_not_relevant: int = SAMPLE_NOT_RELEVANT,
    seed: int = SAMPLE_SEED,
) -> pd.DataFrame:
    """Hand-check sample stratified by relevance, with empty check columns.

    Relevant articles are over-sampled so that location and blame tags can be
    checked on enough rows; agreement is reported separately for each stratum.
    """
    parts = []
    for value, n in (("yes", n_relevant), ("no", n_not_relevant)):
        stratum = tags[tags["relevant"] == value]
        parts.append(stratum.sample(n=min(n, len(stratum)), random_state=seed))
    sample = pd.concat(parts).sort_values("article_id").copy()
    if index is not None:
        sample = sample.merge(index[["article_id", "title", "url"]], on="article_id", how="left")
    for field in CHECK_FIELDS:
        sample[f"check_{field}"] = ""
    sample["check_notes"] = ""
    return sample.reset_index(drop=True)


def field_agrees(model: str, check: str, multi: bool) -> bool:
    """True when the hand check is 'ok' or equals the model value (order-insensitive for lists)."""
    check = str(check).strip()
    if check.lower() == "ok":
        return True
    if multi:
        return set(split_multi(model)) == set(split_multi(check))
    return str(model).strip() == check


def accuracy(sample: pd.DataFrame) -> pd.DataFrame:
    """Share of checked rows where the model tag agrees with the hand check, per field and stratum."""
    rows = []
    groups = [("all", sample)] + [(f"relevant={v}", g) for v, g in sample.groupby("relevant")]
    for stratum, data in groups:
        for field in CHECK_FIELDS:
            checked = data[data[f"check_{field}"].astype(str).str.strip() != ""]
            multi = field in MULTI_VALUES
            agree = sum(field_agrees(m, c, multi) for m, c in zip(checked[field], checked[f"check_{field}"]))
            n = len(checked)
            rows.append({"stratum": stratum, "field": field, "checked": n, "agree": agree,
                         "agreement_pct": round(100 * agree / n, 1) if n else float("nan")})
    return pd.DataFrame(rows)


DUPLICATE_WINDOW_DAYS = 7
MERGED_FIELDS = ["problem_types", "lgas", "place_names", "blamed"]


def normalise_title(title: str) -> str:
    """Lower-case title with punctuation and repeated spaces removed."""
    return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9 ]", " ", str(title).lower())).strip()


TEXT_WINDOW_DAYS = 2
SHINGLE_WORDS = 5
CONTAINMENT_THRESHOLD = 0.8
TITLE_SIMILARITY_THRESHOLD = 0.8


def title_similarity(a: str, b: str) -> float:
    """Jaccard similarity of the word sets of two normalised titles."""
    wa, wb = set(normalise_title(a).split()), set(normalise_title(b).split())
    if not wa or not wb:
        return 0.0
    return len(wa & wb) / len(wa | wb)


def shingles(text: str, k: int = SHINGLE_WORDS) -> set[str]:
    """Set of k-word sequences in a normalised text."""
    words = normalise_title(text).split()
    return {" ".join(words[i:i + k]) for i in range(max(len(words) - k + 1, 0))}


def containment(a: set[str], b: set[str]) -> float:
    """Share of the smaller shingle set found in the other set."""
    if not a or not b:
        return 0.0
    return len(a & b) / min(len(a), len(b))


def duplicate_groups(index: pd.DataFrame, texts: dict[str, str] | None = None) -> dict[str, str]:
    """Map each article_id to the earliest article_id it duplicates.

    Two articles are duplicates when their normalised titles are identical or share
    at least 80% of their words within DUPLICATE_WINDOW_DAYS, or, when texts are given, when they were published
    within TEXT_WINDOW_DAYS and one text is at least 80% contained in the other.
    """
    df = index[["article_id", "date", "title"]].copy()
    df["norm"] = df["title"].map(normalise_title)
    df["dt"] = pd.to_datetime(df["date"])
    df = df.sort_values(["dt", "article_id"]).reset_index(drop=True)
    parent = {a: a for a in df["article_id"]}

    def find(a: str) -> str:
        while parent[a] != a:
            parent[a] = parent[parent[a]]
            a = parent[a]
        return a

    def union(a: str, b: str) -> None:
        ra, rb = find(a), find(b)
        if ra != rb:
            parent[rb] = ra  # rows are visited in date order, so ra is the earlier article

    sh = {a: shingles(t) for a, t in (texts or {}).items()}
    rows = list(df.itertuples(index=False))
    for i, r1 in enumerate(rows):
        for r2 in rows[i + 1:]:
            gap = (r2.dt - r1.dt).days
            if gap > DUPLICATE_WINDOW_DAYS:
                break
            if r1.norm == r2.norm or title_similarity(r1.norm, r2.norm) >= TITLE_SIMILARITY_THRESHOLD:
                union(r1.article_id, r2.article_id)
            elif gap <= TEXT_WINDOW_DAYS and r1.article_id in sh and r2.article_id in sh:
                if containment(sh[r1.article_id], sh[r2.article_id]) >= CONTAINMENT_THRESHOLD:
                    union(r1.article_id, r2.article_id)
    return {a: find(a) for a in df["article_id"]}


def load_texts(index: pd.DataFrame) -> dict[str, str]:
    """Saved article texts keyed by article_id; missing files are skipped."""
    from lagos_waste.scrape_news import TEXT_DIR

    texts = {}
    for aid in index["article_id"]:
        path = TEXT_DIR / f"{aid}.txt"
        if path.exists():
            texts[aid] = path.read_text(encoding="utf-8")
    return texts


def _union(values: pd.Series) -> str:
    """Combine ';'-separated values, keeping first-seen order and dropping placeholders when real values exist."""
    seen: list[str] = []
    for cell in values:
        for v in split_multi(cell):
            if v not in seen:
                seen.append(v)
    real = [v for v in seen if v not in {"none", "unspecified", "none_stated"}]
    return ";".join(real or seen)


def merge_duplicates(tags: pd.DataFrame, canonical: dict[str, str]) -> pd.DataFrame:
    """Collapse tag rows of duplicate articles onto the earliest article_id."""
    df = tags.copy()
    df["canonical_id"] = df["article_id"].map(lambda a: canonical.get(a, a))
    rows = []
    for cid, group in df.groupby("canonical_id", sort=False):
        first = group.sort_values("article_id", key=lambda s: s != cid).iloc[0].copy()
        for field in MERGED_FIELDS:
            first[field] = _union(group[field])
        first["article_id"] = cid
        first["duplicate_ids"] = ";".join(sorted(a for a in group["article_id"] if a != cid))
        rows.append(first)
    return pd.DataFrame(rows).drop(columns="canonical_id").reset_index(drop=True)


def is_service_failure(article_type: str, problem_types: str) -> str:
    """'yes' for service failure reports or any article describing missed collection."""
    return "yes" if article_type == "service_failure_report" or "missed_collection" in split_multi(problem_types) else "no"


def build_complaints(index: pd.DataFrame, tags: pd.DataFrame, texts: dict[str, str] | None = None) -> pd.DataFrame:
    """One row per relevant (de-duplicated) article and LGA, joined to article metadata."""
    relevant = tags[tags["relevant"] == "yes"]
    merged = merge_duplicates(relevant, duplicate_groups(index, texts)).merge(
        index[["article_id", "outlet", "date", "url", "title"]], on="article_id", how="left"
    )
    merged["is_service_failure"] = [
        is_service_failure(t, p) for t, p in zip(merged["article_type"], merged["problem_types"])
    ]
    merged["lga"] = merged["lgas"].map(split_multi)
    out = merged.explode("lga")
    cols = ["article_id", "outlet", "date", "event_month", "lga", "is_service_failure", "article_type",
            "problem_types", "blamed", "blame_source", "psp_named", "place_names", "duplicate_ids",
            "url", "title"]
    return out[cols].sort_values(["date", "article_id", "lga"]).reset_index(drop=True)


def main(argv: list[str] | None = None) -> None:
    """Command-line entry point."""
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("command", choices=["status", "validate", "sample", "accuracy", "duplicates", "build"])
    args = parser.parse_args(argv)
    index, tags = load_index(), load_tags()

    if args.command == "status":
        batch = next_batch(index, tags)
        print(f"{len(tags)} of {len(index)} articles tagged; {len(index) - len(tags)} remaining")
        print("Next batch:" if batch else "All articles tagged.")
        for aid in batch:
            print(f"  {aid}")
    elif args.command == "validate":
        problems = validate_tags(tags, set(index["article_id"]))
        print(f"{len(tags)} rows checked; {len(problems)} problems")
        for p in problems:
            print(f"  {p}")
    elif args.command == "sample":
        if SAMPLE_PATH.exists():
            print(f"{SAMPLE_PATH.name} already exists; delete it first to redraw")
            return
        sample = draw_sample(tags, index)
        sample.to_csv(SAMPLE_PATH, index=False)
        print(f"Wrote {SAMPLE_PATH} ({len(sample)} rows: "
              f"{(sample['relevant'] == 'yes').sum()} relevant, {(sample['relevant'] == 'no').sum()} not relevant)")
    elif args.command == "accuracy":
        sample = pd.read_csv(SAMPLE_PATH, dtype=str, keep_default_na=False)
        print(accuracy(sample).to_string(index=False))
    elif args.command == "duplicates":
        canonical = duplicate_groups(index, load_texts(index))
        groups: dict[str, list[str]] = {}
        for aid, cid in canonical.items():
            groups.setdefault(cid, []).append(aid)
        dupes = {c: sorted(m) for c, m in groups.items() if len(m) > 1}
        print(f"{len(dupes)} duplicate groups")
        for cid, members in dupes.items():
            print(f"  {cid}: {', '.join(m for m in members if m != cid)}")
    elif args.command == "build":
        out = build_complaints(index, tags, load_texts(index))
        COMPLAINTS_PATH.parent.mkdir(parents=True, exist_ok=True)
        out.to_csv(COMPLAINTS_PATH, index=False)
        n_fail = out.loc[out["is_service_failure"] == "yes", "article_id"].nunique()
        print(f"Wrote {COMPLAINTS_PATH}: {out['article_id'].nunique()} articles "
              f"({n_fail} service failure), {len(out)} article-LGA rows")


if __name__ == "__main__":
    main()
