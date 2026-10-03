"""Tests for lagos_waste.news and lagos_waste.scrape_news (no network access)."""

from urllib.parse import parse_qs, urlparse

import pytest

from lagos_waste import news, scrape_news

PAYLOAD = [
    {
        "id": 101,
        "date": "2026-06-12T09:30:00",
        "link": "https://guardian.ng/a/",
        "title": {"rendered": "LAWMA evacuates 418,500 tonnes of waste in May"},
        "excerpt": {"rendered": "<p>The Lagos Waste Management Authority &amp; PSP operators&#8230;</p>"},
    },
    {
        "id": 102,
        "date": "2026-06-13T10:00:00",
        "link": "https://guardian.ng/b/",
        "title": {"rendered": "Lagos traffic eases on Third Mainland Bridge"},
        "excerpt": {"rendered": "<p>Motorists reported shorter journeys.</p>"},
    },
]


class FakeResponse:
    """Minimal stand-in for requests.Response."""

    def __init__(self, status: int, payload, total_pages: int = 1) -> None:
        self.status_code = status
        self.ok = 200 <= status < 300
        self._payload = payload
        self.headers = {"X-WP-TotalPages": str(total_pages)}

    def json(self):
        return self._payload


class FakeClient:
    """Client that serves canned responses and records requested URLs."""

    def __init__(self, responses: list[FakeResponse], allow: bool = True) -> None:
        self.responses = list(responses)
        self.allow = allow
        self.urls: list[str] = []

    def allowed(self, url: str) -> bool:
        return self.allow

    def get(self, url: str) -> FakeResponse:
        self.urls.append(url)
        return self.responses.pop(0)


def test_clean_html_strips_tags_and_entities() -> None:
    """Tags are removed and entities decoded."""
    assert news.clean_html("<p>A &amp; B&#8230;</p>") == "A & B…"


def test_search_url_parameters() -> None:
    """The search URL carries the term, date window, page and field list."""
    url = news.search_url("https://guardian.ng/", "LAWMA", "2021-01-01", "2026-09-30", page=3)
    parts = urlparse(url)
    q = parse_qs(parts.query)
    assert parts.path == "/wp-json/wp/v2/posts"
    assert q["search"] == ["LAWMA"]
    assert q["after"] == ["2021-01-01T00:00:00"]
    assert q["before"] == ["2026-09-30T23:59:59"]
    assert q["page"] == ["3"]
    assert q["per_page"] == ["100"]


def test_parse_posts_builds_records() -> None:
    """Posts become records with outlet-prefixed IDs and ISO dates."""
    recs = news.parse_posts(PAYLOAD, "guardian", "LAWMA")
    assert recs[0]["article_id"] == "guardian-101"
    assert recs[0]["date"] == "2026-06-12"
    assert recs[0]["excerpt"].startswith("The Lagos Waste Management Authority & PSP")
    assert recs[0]["search_terms"] == "LAWMA"


@pytest.mark.parametrize(
    ("title", "excerpt", "expected"),
    [
        ("LAWMA clears blackspots", "", True),
        ("Refuse piles up in Alimosho", "", True),
        ("Waste crisis in Abuja", "Residents complain", False),
        ("Lagos traffic eases", "Motorists reported shorter journeys", False),
    ],
)
def test_is_relevant(title: str, excerpt: str, expected: bool) -> None:
    """Relevance needs a waste term and a Lagos place name."""
    assert news.is_relevant(title, excerpt) is expected


def test_deduplicate_merges_terms() -> None:
    """Duplicate URLs collapse into one record listing every search term."""
    a = {"article_id": "g-1", "url": "u1", "date": "2026-01-02", "search_terms": "LAWMA"}
    b = {"article_id": "g-1", "url": "u1", "date": "2026-01-02", "search_terms": "waste Lagos"}
    c = {"article_id": "g-2", "url": "u2", "date": "2026-01-01", "search_terms": "LAWMA"}
    out = news.deduplicate([a, b, c])
    assert [r["article_id"] for r in out] == ["g-2", "g-1"]
    assert out[1]["search_terms"] == "LAWMA;waste Lagos"


def test_collect_outlet_pages_and_filters_broad_term() -> None:
    """Two pages are read; for a broad term only relevant posts are kept."""
    client = FakeClient([FakeResponse(200, PAYLOAD, total_pages=2), FakeResponse(200, PAYLOAD[:1], total_pages=2)])
    recs, log = news.collect_outlet(client, "guardian", "https://guardian.ng", ["waste Lagos"], "2026-01-01", "2026-12-31")
    assert len(client.urls) == 2
    assert len(recs) == 2
    assert log == [{"outlet": "guardian", "search_term": "waste Lagos", "pages": 2, "found": 3, "relevant": 2, "status": "ok"}]


def test_collect_outlet_keeps_all_hits_for_precise_term() -> None:
    """Every hit for a precise term such as Olusosun is kept as a candidate."""
    client = FakeClient([FakeResponse(200, PAYLOAD, total_pages=1)])
    recs, _ = news.collect_outlet(client, "guardian", "https://guardian.ng", ["Olusosun"], "2026-01-01", "2026-12-31")
    assert len(recs) == 2


def test_lawma_hits_are_filtered() -> None:
    """LAWMA hits are filtered because the search also matches "lawmaker"."""
    lawmaker = [{"id": 9, "date": "2021-01-05T00:00:00", "link": "https://x/9/",
                 "title": {"rendered": "Lawmakers pass pension bill"}, "excerpt": {"rendered": "<p>Senate vote</p>"}}]
    client = FakeClient([FakeResponse(200, lawmaker, total_pages=1)])
    recs, log = news.collect_outlet(client, "nannews", "https://nannews.ng", ["LAWMA"], "2021-01-01", "2021-12-31")
    assert recs == [] and log[0]["found"] == 1


class ErrorResponse(FakeResponse):
    """Response whose body is not JSON."""

    def json(self):
        raise ValueError("not json")


def test_collect_outlet_retries_once_after_non_json() -> None:
    """A non-JSON reply is retried once before succeeding."""
    client = FakeClient([ErrorResponse(200, None), FakeResponse(200, PAYLOAD[:1])])
    recs, log = news.collect_outlet(
        client, "gazette", "https://gazettengr.com", ["LAWMA"], "2026-01-01", "2026-12-31", retry_wait=0
    )
    assert len(client.urls) == 2 and len(recs) == 1 and log[0]["status"] == "ok"


def test_collect_outlet_logs_after_second_failure() -> None:
    """Two non-JSON replies in a row are logged as a failure."""
    client = FakeClient([ErrorResponse(200, None), ErrorResponse(200, None)])
    _, log = news.collect_outlet(
        client, "gazette", "https://gazettengr.com", ["LAWMA"], "2026-01-01", "2026-12-31", retry_wait=0
    )
    assert log[0]["status"] == "response was not JSON"


def test_collect_outlet_respects_max_pages() -> None:
    """max_pages stops paging early."""
    client = FakeClient([FakeResponse(200, PAYLOAD, total_pages=5)])
    news.collect_outlet(client, "guardian", "https://guardian.ng", ["LAWMA"], "2026-01-01", "2026-12-31", max_pages=1)
    assert len(client.urls) == 1


def test_collect_outlet_logs_robots_block() -> None:
    """A robots.txt block is logged and no request is made."""
    client = FakeClient([], allow=False)
    recs, log = news.collect_outlet(client, "punch", "https://punchng.com", ["LAWMA"], "2026-01-01", "2026-12-31")
    assert recs == [] and client.urls == []
    assert log[0]["status"].startswith("blocked")


def test_collect_outlet_logs_http_error() -> None:
    """A failed first page is logged with its status code."""
    client = FakeClient([FakeResponse(403, None)])
    _, log = news.collect_outlet(client, "nannews", "https://nannews.ng", ["LAWMA"], "2026-01-01", "2026-12-31")
    assert log[0]["status"] == "http 403"


def test_robots_parser_disallow(monkeypatch: pytest.MonkeyPatch) -> None:
    """A robots.txt that disallows /wp-json/ blocks API URLs but not articles."""

    class RobotsResp:
        status_code = 200
        ok = True
        text = "User-agent: *\nDisallow: /wp-json/\n"

    client = news.PoliteClient(delay=0)
    monkeypatch.setattr(client.session, "get", lambda url, timeout: RobotsResp())
    assert not client.allowed("https://example.com/wp-json/wp/v2/posts?search=x")
    assert client.allowed("https://example.com/2026/06/article/")


def test_extract_text_returns_main_text() -> None:
    """trafilatura extracts the article body from a page."""
    body = " ".join(["Refuse has not been collected in Ikotun for three weeks, residents said."] * 8)
    page = f"<html><body><nav>Menu</nav><article><h1>Title</h1><p>{body}</p></article></body></html>"
    text = news.extract_text(page)
    assert text is not None and "Ikotun" in text


def test_write_csv_round_trip(tmp_path) -> None:
    """CSV output has the requested columns only."""
    path = tmp_path / "x.csv"
    scrape_news.write_csv(path, [{"a": 1, "b": 2, "c": 3}], ["a", "b"])
    assert path.read_text(encoding="utf-8").splitlines() == ["a,b", "1,2"]


def test_assess_relevance_uses_full_text(tmp_path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Saved full text decides relevance; otherwise the excerpt is used."""
    monkeypatch.setattr(scrape_news, "TEXT_DIR", tmp_path)
    (tmp_path / "nan-1.txt").write_text("Refuse has piled up in Ikorodu for weeks.", encoding="utf-8")
    recs = [
        {"article_id": "nan-1", "title": "Residents protest", "excerpt": "", "text_status": "saved"},
        {"article_id": "nan-2", "title": "Residents protest", "excerpt": "Pension reform", "text_status": "not fetched"},
    ]
    scrape_news.assess_relevance(recs)
    assert recs[0]["relevant"] is True and recs[0]["relevance_basis"] == "full text"
    assert recs[1]["relevant"] is False and recs[1]["relevance_basis"] == "excerpt"


def test_load_previous_renames_nan_outlet(tmp_path) -> None:
    """Rows saved under the old "nan" code are renamed, with their text file."""
    text_dir = tmp_path / "text"
    text_dir.mkdir()
    (text_dir / "nan-7.txt").write_text("x", encoding="utf-8")
    path = tmp_path / "articles.csv"
    scrape_news.write_csv(
        path,
        [{"article_id": "nan-7", "outlet": "nan", "date": "2026-01-01", "url": "u7", "title": "t",
          "excerpt": "e", "search_terms": "LAWMA", "relevant": True}],
        scrape_news.RAW_FIELDS,
    )
    rows = scrape_news.load_previous(path, text_dir)
    assert rows[0]["outlet"] == "nannews" and rows[0]["article_id"] == "nannews-7"
    assert (text_dir / "nannews-7.txt").exists() and not (text_dir / "nan-7.txt").exists()


def test_load_previous_missing_file(tmp_path) -> None:
    """No earlier run means no carried-over candidates."""
    assert scrape_news.load_previous(tmp_path / "none.csv", tmp_path) == []


def test_merge_keeps_union_of_runs() -> None:
    """Candidates from an earlier run are kept alongside new ones, merging search terms."""
    old = [{"article_id": "businessday-1", "url": "u1", "date": "2024-01-01", "search_terms": "waste Lagos"}]
    new = [{"article_id": "businessday-1", "url": "u1", "date": "2024-01-01", "search_terms": "LAWMA"},
           {"article_id": "businessday-2", "url": "u2", "date": "2025-01-01", "search_terms": "LAWMA"}]
    merged = news.deduplicate(new + old)
    assert len(merged) == 2 and merged[0]["search_terms"] == "LAWMA;waste Lagos"


def test_write_csv_append_adds_rows_without_second_header(tmp_path) -> None:
    """Appending to an existing CSV keeps one header."""
    path = tmp_path / "log.csv"
    scrape_news.write_csv(path, [{"a": 1}], ["a"])
    scrape_news.write_csv(path, [{"a": 2}], ["a"], append=True)
    assert path.read_text(encoding="utf-8").splitlines() == ["a", "1", "2"]


def test_write_csv_append_replaces_file_with_old_columns(tmp_path) -> None:
    """A log written with older columns is replaced rather than appended to."""
    path = tmp_path / "log.csv"
    path.write_text("a\n1\n", encoding="utf-8")
    scrape_news.write_csv(path, [{"run_at": "t", "a": 2}], ["run_at", "a"], append=True)
    assert path.read_text(encoding="utf-8").splitlines() == ["run_at,a", "t,2"]
