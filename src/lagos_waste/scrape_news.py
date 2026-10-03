"""Command-line entry point for collecting news articles.

Usage (from the repository root, with the virtual environment active):

    python -m lagos_waste.scrape_news --since 2021-01-01 --until 2026-09-30

Outputs:
    data/raw/news/articles.csv      all candidates with excerpt and relevance flag (not version-controlled)
    data/raw/news/text/<id>.txt     extracted article text (not version-controlled)
    data/interim/news_index.csv     relevant articles, metadata only (version-controlled)
    data/interim/news_scrape_log.csv  one row per outlet and search term
"""

from __future__ import annotations

import argparse
import csv
from datetime import datetime, timezone
from pathlib import Path

from lagos_waste import news
from lagos_waste.paths import DATA_INTERIM, DATA_RAW

NEWS_RAW = DATA_RAW / "news"
TEXT_DIR = NEWS_RAW / "text"
INDEX_FIELDS = ["article_id", "outlet", "date", "url", "title", "search_terms", "text_status", "relevance_basis"]
RAW_FIELDS = INDEX_FIELDS + ["relevant", "excerpt"]
LOG_FIELDS = ["run_at", "outlet", "search_term", "pages", "found", "relevant", "status"]
CANDIDATE_FIELDS = ["article_id", "outlet", "date", "url", "title", "excerpt", "search_terms"]
# Outlet codes renamed after earlier runs; "nan" is read as a missing value by pandas.
RENAMED_OUTLETS = {"nan": "nannews"}


def write_csv(path: Path, rows: list[dict], fields: list[str], append: bool = False) -> None:
    """Write rows to a UTF-8 CSV with the given columns, optionally appending to an existing file."""
    path.parent.mkdir(parents=True, exist_ok=True)
    if append and path.exists():
        with path.open(encoding="utf-8") as fh:
            existing_header = fh.readline().strip().split(",")
        if existing_header != fields:
            append = False  # older file with different columns is replaced
    add_header = not (append and path.exists())
    with path.open("a" if append else "w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=fields, extrasaction="ignore")
        if add_header:
            writer.writeheader()
        writer.writerows(rows)


def load_previous(path: Path, text_dir: Path) -> list[dict]:
    """Read candidates saved by earlier runs, renaming outdated outlet codes and their text files."""
    if not path.exists():
        return []
    with path.open(encoding="utf-8", newline="") as fh:
        rows = list(csv.DictReader(fh))
    out = []
    for row in rows:
        rec = {k: row.get(k, "") for k in CANDIDATE_FIELDS}
        old = rec["outlet"]
        if old in RENAMED_OUTLETS:
            new = RENAMED_OUTLETS[old]
            old_id = rec["article_id"]
            rec["outlet"] = new
            rec["article_id"] = new + old_id[len(old):]
            old_text = text_dir / f"{old_id}.txt"
            new_text = text_dir / f"{rec['article_id']}.txt"
            if old_text.exists() and not new_text.exists():
                old_text.rename(new_text)
        out.append(rec)
    return out


def fetch_texts(client: news.PoliteClient, records: list[dict]) -> None:
    """Download and extract text for each record, skipping files already saved."""
    TEXT_DIR.mkdir(parents=True, exist_ok=True)
    for i, rec in enumerate(records, start=1):
        path = TEXT_DIR / f"{rec['article_id']}.txt"
        if path.exists():
            rec["text_status"] = "saved"
            continue
        if not client.allowed(rec["url"]):
            rec["text_status"] = "blocked by robots.txt"
            continue
        try:
            resp = client.get(rec["url"])
            text = news.extract_text(resp.text) if resp.ok else None
        except Exception as exc:  # network and parser errors are logged, not fatal
            rec["text_status"] = f"error: {type(exc).__name__}"
            continue
        if text:
            path.write_text(text, encoding="utf-8")
            rec["text_status"] = "saved"
        else:
            rec["text_status"] = f"no text (http {resp.status_code})"
        if i % 25 == 0:
            print(f"  text {i}/{len(records)}")


def assess_relevance(records: list[dict]) -> None:
    """Mark each record relevant using the full text where saved, otherwise the excerpt."""
    for rec in records:
        path = TEXT_DIR / f"{rec['article_id']}.txt"
        if rec.get("text_status") == "saved" and path.exists():
            text = path.read_text(encoding="utf-8")
            rec["relevance_basis"] = "full text"
        else:
            text = rec.get("excerpt", "")
            rec["relevance_basis"] = "excerpt"
        rec["relevant"] = news.is_relevant(rec["title"], text)


def main(argv: list[str] | None = None) -> None:
    """Run the collection for the selected outlets and date range."""
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--since", default="2021-01-01")
    parser.add_argument("--until", default="2026-09-30")
    parser.add_argument("--outlets", nargs="+", default=list(news.OUTLETS), choices=list(news.OUTLETS))
    parser.add_argument("--max-pages", type=int, default=None, help="limit pages per search term (for a test run)")
    parser.add_argument("--no-text", action="store_true", help="skip downloading article text")
    parser.add_argument("--fresh", action="store_true", help="ignore candidates saved by earlier runs")
    args = parser.parse_args(argv)

    client = news.PoliteClient()
    all_records: list[dict] = []
    all_log: list[dict] = []
    for outlet in args.outlets:
        print(f"{outlet}: searching")
        recs, log = news.collect_outlet(
            client, outlet, news.OUTLETS[outlet], news.SEARCH_TERMS, args.since, args.until, args.max_pages
        )
        all_records.extend(recs)
        all_log.extend(log)
        for row in log:
            print(f"  {row['search_term']!r}: {row['relevant']} relevant of {row['found']} ({row['status']})")

    run_at = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    for row in all_log:
        row["run_at"] = run_at
    previous = [] if args.fresh else load_previous(NEWS_RAW / "articles.csv", TEXT_DIR)
    records = news.deduplicate(all_records + previous)
    print(f"{len(previous)} candidates carried over from earlier runs")
    for rec in records:
        rec["text_status"] = "not fetched"
    print(f"{len(records)} unique candidate articles")
    if not args.no_text and records:
        fetch_texts(client, records)
    assess_relevance(records)
    relevant = [r for r in records if r["relevant"]]
    print(f"{len(relevant)} relevant after checking {'full text' if not args.no_text else 'excerpts'}")

    write_csv(NEWS_RAW / "articles.csv", records, RAW_FIELDS)
    write_csv(DATA_INTERIM / "news_index.csv", relevant, INDEX_FIELDS)
    write_csv(DATA_INTERIM / "news_scrape_log.csv", all_log, LOG_FIELDS, append=not args.fresh)
    print("Wrote data/interim/news_index.csv, data/interim/news_scrape_log.csv and data/raw/news/")


if __name__ == "__main__":
    main()
