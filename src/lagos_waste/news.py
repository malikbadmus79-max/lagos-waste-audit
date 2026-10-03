"""Collection of news articles on waste collection in Lagos from WordPress-based outlets.

Articles are found through each outlet's public WordPress REST API search
(`/wp-json/wp/v2/posts`). Requests carry a descriptive User-Agent, wait at
least two seconds between calls to the same outlet and respect robots.txt.
Full article text is stored only under `data/raw/news/` (not version-controlled).
"""

from __future__ import annotations

import html
import re
import time
from dataclasses import dataclass, field
from urllib.parse import urlencode, urlparse
from urllib.robotparser import RobotFileParser

import requests
from bs4 import BeautifulSoup

USER_AGENT = (
    "lagos-waste-audit/0.1 (independent research on household waste collection in Lagos; "
    "https://github.com/malikbadmus79-max/lagos-waste-audit)"
)
REQUEST_DELAY_SECONDS = 2.0
EXCERPT_CHARS = 400

OUTLETS: dict[str, str] = {
    "guardian": "https://guardian.ng",
    "punch": "https://punchng.com",
    "vanguard": "https://www.vanguardngr.com",
    "businessday": "https://businessday.ng",
    "gazette": "https://gazettengr.com",
    "nannews": "https://nannews.ng",
}

SEARCH_TERMS: list[str] = [
    "LAWMA",
    "Lagos Waste Management Authority",
    "PSP operators",
    "refuse Lagos",
    "waste Lagos",
    "dumpsite Lagos",
    "Olusosun",
    "Solous",
]

# Terms specific to Lagos waste management: every search hit is kept as a candidate.
# Hits for other terms are kept only when the title or excerpt is relevant.
# "LAWMA" is not precise: WordPress search matches substrings, so it also returns
# every article containing "lawmaker".
PRECISE_TERMS: set[str] = {"Olusosun", "Solous"}
RETRY_WAIT_SECONDS = 10.0

LGAS: list[str] = [
    "Agege", "Ajeromi-Ifelodun", "Alimosho", "Amuwo-Odofin", "Apapa", "Badagry", "Epe",
    "Eti-Osa", "Ibeju-Lekki", "Ifako-Ijaiye", "Ikeja", "Ikorodu", "Kosofe", "Lagos Island",
    "Lagos Mainland", "Mushin", "Ojo", "Oshodi-Isolo", "Shomolu", "Surulere",
]

WASTE_PATTERN = re.compile(
    r"\b(waste|refuse|garbage|rubbish|trash|dumpsites?|dump\s?sites?|landfills?|LAWMA|PSP|sanitation)\b",
    re.IGNORECASE,
)
LAGOS_PATTERN = re.compile(
    r"\b(Lagos|LAWMA|" + "|".join(re.escape(lga) for lga in LGAS) + r")\b",
    re.IGNORECASE,
)


def clean_html(raw: str) -> str:
    """Convert an HTML fragment to plain text with single spaces."""
    text = BeautifulSoup(raw or "", "html.parser").get_text(" ")
    text = html.unescape(text)
    return re.sub(r"\s+", " ", text).strip()


def search_url(base: str, term: str, after: str, before: str, page: int, per_page: int = 100) -> str:
    """Build a WordPress REST API search URL for one page of results.

    `after` and `before` are ISO dates (YYYY-MM-DD).
    """
    params = {
        "search": term,
        "after": f"{after}T00:00:00",
        "before": f"{before}T23:59:59",
        "per_page": per_page,
        "page": page,
        "orderby": "date",
        "order": "asc",
        "_fields": "id,date,link,title,excerpt",
    }
    return f"{base.rstrip('/')}/wp-json/wp/v2/posts?{urlencode(params)}"


def parse_posts(payload: list[dict], outlet: str, term: str) -> list[dict]:
    """Convert a WordPress posts payload into article records."""
    records = []
    for post in payload:
        title = clean_html(post.get("title", {}).get("rendered", ""))
        excerpt = clean_html(post.get("excerpt", {}).get("rendered", ""))[:EXCERPT_CHARS]
        records.append(
            {
                "article_id": f"{outlet}-{post['id']}",
                "outlet": outlet,
                "date": str(post.get("date", ""))[:10],
                "url": post.get("link", ""),
                "title": title,
                "excerpt": excerpt,
                "search_terms": term,
            }
        )
    return records


def is_relevant(title: str, excerpt: str) -> bool:
    """True when the title and excerpt mention both waste and Lagos (or a Lagos LGA)."""
    text = f"{title} {excerpt}"
    return bool(WASTE_PATTERN.search(text)) and bool(LAGOS_PATTERN.search(text))


def deduplicate(records: list[dict]) -> list[dict]:
    """Keep one record per URL, merging the search terms that found it."""
    by_url: dict[str, dict] = {}
    for rec in records:
        key = rec["url"]
        if key in by_url:
            terms = set(by_url[key]["search_terms"].split(";")) | set(rec["search_terms"].split(";"))
            by_url[key]["search_terms"] = ";".join(sorted(terms))
        else:
            by_url[key] = dict(rec)
    return sorted(by_url.values(), key=lambda r: (r["date"], r["article_id"]))


@dataclass
class PoliteClient:
    """HTTP client with a fixed User-Agent, per-host delay and robots.txt checks."""

    delay: float = REQUEST_DELAY_SECONDS
    session: requests.Session = field(default_factory=requests.Session)
    _robots: dict[str, RobotFileParser | None] = field(default_factory=dict)
    _last_call: dict[str, float] = field(default_factory=dict)

    def __post_init__(self) -> None:
        self.session.headers.update({"User-Agent": USER_AGENT})

    def _wait(self, host: str) -> None:
        elapsed = time.monotonic() - self._last_call.get(host, 0.0)
        if elapsed < self.delay:
            time.sleep(self.delay - elapsed)
        self._last_call[host] = time.monotonic()

    def _robots_for(self, url: str) -> RobotFileParser | None:
        parts = urlparse(url)
        host = parts.netloc
        if host not in self._robots:
            parser = RobotFileParser()
            self._wait(host)
            try:
                resp = self.session.get(f"{parts.scheme}://{host}/robots.txt", timeout=30)
            except requests.RequestException:
                self._robots[host] = None
                return None
            if resp.status_code == 404:
                parser.parse([])
            elif resp.ok:
                parser.parse(resp.text.splitlines())
            else:
                self._robots[host] = None
                return None
            self._robots[host] = parser
        return self._robots[host]

    def allowed(self, url: str) -> bool:
        """True when robots.txt could be read and permits the URL for this User-Agent."""
        parser = self._robots_for(url)
        return parser is not None and parser.can_fetch(USER_AGENT, url)

    def get(self, url: str) -> requests.Response:
        """GET a URL after waiting for the per-host delay."""
        self._wait(urlparse(url).netloc)
        return self.session.get(url, timeout=60)


def _get_json(client: PoliteClient, url: str, retry_wait: float) -> tuple[object, object, str | None]:
    """GET a JSON page, retrying once after a dropped connection or a non-JSON reply.

    Returns (response, payload, error); error is None on success.
    """
    error: str | None = None
    for attempt in range(2):
        if attempt:
            time.sleep(retry_wait)
        try:
            resp = client.get(url)
        except requests.RequestException as exc:
            error = f"request error: {type(exc).__name__}"
            continue
        if resp.status_code == 400:
            return resp, None, "past last page"
        if not resp.ok:
            return resp, None, f"http {resp.status_code}"
        try:
            return resp, resp.json(), None
        except ValueError:
            error = "response was not JSON"
    return None, None, error


def collect_outlet(
    client: PoliteClient,
    outlet: str,
    base: str,
    terms: list[str],
    after: str,
    before: str,
    max_pages: int | None = None,
    retry_wait: float = RETRY_WAIT_SECONDS,
) -> tuple[list[dict], list[dict]]:
    """Search one outlet for every term; return (candidate records, log rows).

    Hits for PRECISE_TERMS are all kept; hits for other terms are kept when the
    title or excerpt mentions both waste and Lagos.
    """
    records: list[dict] = []
    log: list[dict] = []
    for term in terms:
        page, found, kept, status = 1, 0, 0, "ok"
        while True:
            url = search_url(base, term, after, before, page)
            if not client.allowed(url):
                status = "blocked by robots.txt or robots.txt unreadable"
                break
            resp, payload, error = _get_json(client, url, retry_wait)
            if error == "past last page" and page > 1:
                break
            if error:
                status = error
                break
            if not payload:
                break
            batch = parse_posts(payload, outlet, term)
            found += len(batch)
            relevant = [r for r in batch if term in PRECISE_TERMS or is_relevant(r["title"], r["excerpt"])]
            kept += len(relevant)
            records.extend(relevant)
            total_pages = int(resp.headers.get("X-WP-TotalPages", page))
            if page >= total_pages or (max_pages is not None and page >= max_pages):
                break
            page += 1
        log.append({"outlet": outlet, "search_term": term, "pages": page, "found": found,
                    "relevant": kept, "status": status})
    return records, log


def extract_text(html_doc: str) -> str | None:
    """Extract the main article text from a page with trafilatura."""
    import trafilatura

    return trafilatura.extract(html_doc, include_comments=False, include_tables=False)
