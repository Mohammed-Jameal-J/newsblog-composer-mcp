"""Pluggable news-search providers.

Every provider returns the same SearchHit shape so verify_news does not care
which one answered. Keyed providers are preferred when their key is present;
the keyless RSS providers keep the server useful with no credentials at all.
"""
from __future__ import annotations

import time
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from typing import Iterable
from urllib.parse import parse_qs, quote_plus, unquote, urlparse

import httpx

from ..config import CONFIG, Config
from ..textutil import normalize, registrable_domain, strip_html


@dataclass
class SearchHit:
    title: str
    url: str
    publisher: str
    published_date: str
    snippet: str
    provider: str
    fetchable: bool = True

    def to_dict(self) -> dict:
        return asdict(self)


def _gdelt_date(value: str) -> str:
    """GDELT stamps look like 20260908T121500Z."""
    if not value or len(value) < 15:
        return value or ""
    try:
        return datetime.strptime(value, "%Y%m%dT%H%M%SZ").replace(
            tzinfo=timezone.utc).isoformat()
    except ValueError:
        return value


def _iso(value) -> str:
    if not value:
        return ""
    if isinstance(value, str):
        return value
    try:
        return datetime(*value[:6], tzinfo=timezone.utc).isoformat()
    except Exception:
        return ""


_LAST_CALL: dict[str, float] = {}


def _client(cfg: Config, timeout: float | None = None) -> httpx.Client:
    return httpx.Client(
        timeout=timeout or cfg.search_timeout,
        follow_redirects=True,
        headers={"User-Agent": cfg.user_agent, "Accept-Language": "en-US,en;q=0.9"},
    )


class SearchProvider:
    name = "base"
    keyless = False
    #: how many of the query variants this provider is worth running
    max_queries = 2
    #: minimum seconds between two calls to this provider
    min_interval = 0.0
    #: per-provider timeout override, for providers that are simply slow
    timeout: float | None = None

    def __init__(self, cfg: Config) -> None:
        self.cfg = cfg

    def available(self) -> bool:
        return False

    def search(self, query: str, limit: int = 10,
               days: int | None = None) -> list[SearchHit]:
        """`days` limits results to the last N days where the provider supports
        it; providers that cannot filter simply ignore it."""
        raise NotImplementedError


class BraveNews(SearchProvider):
    name = "brave"

    def available(self) -> bool:
        return bool(self.cfg.brave_api_key)

    def search(self, query: str, limit: int = 10, days: int | None = None) -> list[SearchHit]:
        with _client(self.cfg) as c:
            r = c.get(
                "https://api.search.brave.com/res/v1/news/search",
                params={"q": query, "count": limit, "spellcheck": 0},
                headers={"X-Subscription-Token": self.cfg.brave_api_key,
                         "Accept": "application/json"},
            )
            r.raise_for_status()
            data = r.json()
        hits = []
        for item in data.get("results", [])[:limit]:
            url = item.get("url", "")
            hits.append(SearchHit(
                title=normalize(item.get("title", "")),
                url=url,
                publisher=(item.get("meta_url", {}) or {}).get("hostname") or registrable_domain(url),
                published_date=item.get("page_age") or item.get("age") or "",
                snippet=strip_html(item.get("description", "")),
                provider=self.name,
            ))
        return hits


class SerperNews(SearchProvider):
    name = "serper"

    def available(self) -> bool:
        return bool(self.cfg.serper_api_key)

    def search(self, query: str, limit: int = 10, days: int | None = None) -> list[SearchHit]:
        with _client(self.cfg) as c:
            r = c.post(
                "https://google.serper.dev/news",
                json={"q": query, "num": limit},
                headers={"X-API-KEY": self.cfg.serper_api_key,
                         "Content-Type": "application/json"},
            )
            r.raise_for_status()
            data = r.json()
        hits = []
        for item in data.get("news", [])[:limit]:
            url = item.get("link", "")
            hits.append(SearchHit(
                title=normalize(item.get("title", "")),
                url=url,
                publisher=item.get("source") or registrable_domain(url),
                published_date=item.get("date", ""),
                snippet=normalize(item.get("snippet", "")),
                provider=self.name,
            ))
        return hits


class NewsApiOrg(SearchProvider):
    name = "newsapi"

    def available(self) -> bool:
        return bool(self.cfg.newsapi_key)

    def search(self, query: str, limit: int = 10, days: int | None = None) -> list[SearchHit]:
        with _client(self.cfg) as c:
            r = c.get(
                "https://newsapi.org/v2/everything",
                params={"q": query, "pageSize": limit, "language": "en",
                        "sortBy": "relevancy"},
                headers={"X-Api-Key": self.cfg.newsapi_key},
            )
            r.raise_for_status()
            data = r.json()
        hits = []
        for item in data.get("articles", [])[:limit]:
            url = item.get("url", "")
            hits.append(SearchHit(
                title=normalize(item.get("title", "")),
                url=url,
                publisher=(item.get("source", {}) or {}).get("name") or registrable_domain(url),
                published_date=item.get("publishedAt", ""),
                snippet=normalize(item.get("description") or ""),
                provider=self.name,
            ))
        return hits


class Tavily(SearchProvider):
    """Free tier is 1,000 credits/month with no card, which makes it the best
    keyed option for this pipeline as of 2026."""

    name = "tavily"

    def available(self) -> bool:
        return bool(self.cfg.tavily_api_key)

    def search(self, query: str, limit: int = 10, days: int | None = None) -> list[SearchHit]:
        with _client(self.cfg) as c:
            r = c.post(
                "https://api.tavily.com/search",
                headers={"Authorization": f"Bearer {self.cfg.tavily_api_key}",
                         "Content-Type": "application/json"},
                json={"query": query, "topic": "news", "max_results": min(limit, 20),
                      **({"days": days} if days else {})},
            )
            r.raise_for_status()
            data = r.json()
        hits = []
        for item in data.get("results", [])[:limit]:
            url = item.get("url", "")
            hits.append(SearchHit(
                title=normalize(item.get("title", "")),
                url=url,
                publisher=registrable_domain(url),
                published_date=item.get("published_date", "") or "",
                snippet=normalize(item.get("content", ""))[:400],
                provider=self.name,
            ))
        return hits


class GoogleCustomSearch(SearchProvider):
    """100 queries/day free, no card. Needs both an API key and a search engine
    id (cx) from programmablesearchengine.google.com."""

    name = "google_cse"

    def available(self) -> bool:
        return bool(self.cfg.google_cse_key and self.cfg.google_cse_id)

    def search(self, query: str, limit: int = 10, days: int | None = None) -> list[SearchHit]:
        with _client(self.cfg) as c:
            r = c.get(
                "https://www.googleapis.com/customsearch/v1",
                params={"key": self.cfg.google_cse_key, "cx": self.cfg.google_cse_id,
                        "q": query, "num": min(limit, 10)},
            )
            r.raise_for_status()
            data = r.json()
        hits = []
        for item in data.get("items", [])[:limit]:
            url = item.get("link", "")
            meta = ((item.get("pagemap") or {}).get("metatags") or [{}])[0]
            hits.append(SearchHit(
                title=normalize(item.get("title", "")),
                url=url,
                publisher=item.get("displayLink") or registrable_domain(url),
                published_date=meta.get("article:published_time", "") or "",
                snippet=normalize(item.get("snippet", "")),
                provider=self.name,
            ))
        return hits


class Gdelt(SearchProvider):
    """GDELT DOC 2.0. Free, official, no key, no signup, and news-specific -
    which is why it is the default keyless provider rather than an RSS scrape."""

    name = "gdelt"
    keyless = True
    # GDELT rate limits aggressively and answers slowly - one query, spaced out,
    # with a longer leash. Firing two variants back to back earns a 429.
    max_queries = 1
    min_interval = 5.0
    timeout = 30.0

    def available(self) -> bool:
        return True

    def search(self, query: str, limit: int = 10, days: int | None = None) -> list[SearchHit]:
        params = {"query": f"{query} sourcelang:english", "mode": "ArtList",
                  "maxrecords": min(max(limit, 10), 75), "format": "json",
                  "sort": "DateDesc",
                  "timespan": f"{days}d" if days else self.cfg.gdelt_timespan}
        with _client(self.cfg, self.timeout) as c:
            r = c.get("https://api.gdeltproject.org/api/v2/doc/doc", params=params)
            if r.status_code == 429:
                time.sleep(6)
                r = c.get("https://api.gdeltproject.org/api/v2/doc/doc", params=params)
            r.raise_for_status()
            try:
                data = r.json()
            except Exception as exc:  # GDELT returns plain-text errors on bad queries
                raise RuntimeError(f"GDELT did not return JSON: {r.text[:160]}") from exc
        hits = []
        for item in data.get("articles", [])[:limit]:
            url = item.get("url", "")
            hits.append(SearchHit(
                title=normalize(item.get("title", "")),
                url=url,
                publisher=item.get("domain") or registrable_domain(url),
                published_date=_gdelt_date(item.get("seendate", "")),
                snippet="",
                provider=self.name,
            ))
        return hits


class _RssProvider(SearchProvider):
    keyless = True
    url_template = ""

    def available(self) -> bool:
        return True

    def _feed(self, query: str):
        import feedparser  # imported lazily so import errors surface per-provider
        url = self.url_template.format(q=quote_plus(query))
        with _client(self.cfg) as c:
            r = c.get(url)
            r.raise_for_status()
            body = r.content
        return feedparser.parse(body)


class GoogleNewsRss(_RssProvider):
    """Keyless. Links are Google redirect URLs, so hits are marked unfetchable;
    they still carry the real publisher, which is what cross-checking needs."""

    name = "google_rss"
    url_template = "https://news.google.com/rss/search?q={q}&hl=en-US&gl=US&ceid=US:en"

    def search(self, query: str, limit: int = 10, days: int | None = None) -> list[SearchHit]:
        feed = self._feed(query)
        hits = []
        for entry in feed.entries[:limit]:
            source = getattr(entry, "source", None)
            publisher = ""
            source_url = ""
            if source is not None:
                publisher = normalize(getattr(source, "title", "") or "")
                source_url = getattr(source, "href", "") or ""
            title = normalize(entry.get("title", ""))
            if not publisher and " - " in title:
                title, publisher = title.rsplit(" - ", 1)
            hits.append(SearchHit(
                title=normalize(title),
                url=entry.get("link", ""),
                publisher=publisher or registrable_domain(source_url),
                published_date=_iso(entry.get("published_parsed") or entry.get("published")),
                snippet=strip_html(entry.get("summary", "")),
                provider=self.name,
                fetchable=False,
            ))
        return hits


def _unwrap_bing(url: str) -> str:
    """Bing feeds wrap every link in /news/apiclick.aspx?...&url=<escaped real url>.

    Left wrapped, every result looks like it was published by bing.com, which
    poisons publisher counting and produces reference links that point at a
    redirector instead of the source. The real URL is right there in the query
    string, so unwrap it.
    """
    parsed = urlparse(url)
    if "bing.com" not in (parsed.hostname or "") or "apiclick" not in (parsed.path or ""):
        return url
    target = parse_qs(parsed.query).get("url", [""])[0]
    target = unquote(target)
    return target if target.startswith("http") else url


class BingNewsRss(_RssProvider):
    """Keyless. Links arrive wrapped in a Bing redirector and are unwrapped back
    to the publisher URL, which makes them usable as references."""

    name = "bing_rss"
    url_template = "https://www.bing.com/news/search?q={q}&format=rss&count=20"

    def search(self, query: str, limit: int = 10, days: int | None = None) -> list[SearchHit]:
        feed = self._feed(query)
        hits = []
        for entry in feed.entries[:limit]:
            url = _unwrap_bing(entry.get("link", ""))
            unwrapped = "bing.com" not in (urlparse(url).hostname or "")
            hits.append(SearchHit(
                title=normalize(entry.get("title", "")),
                url=url,
                publisher=registrable_domain(url),
                published_date=_iso(entry.get("published_parsed") or entry.get("published")),
                snippet=strip_html(entry.get("summary", "")),
                provider=self.name,
                fetchable=unwrapped,
            ))
        return hits


# Order matters: keyed providers first (more reliable, higher limits), then the
# keyless ones. GDELT leads the keyless group because it is an official API
# rather than an RSS endpoint that can change shape without notice.
# GDELT leads the keyless group: it is an official API and the only keyless
# provider that returns fetchable publisher URLs. Google News RSS follows
# because it reliably names the real publisher even though its links are
# redirects, which is what corroboration counting needs. Bing RSS is last; it
# frequently returns nothing.
_ALL = [Tavily, BraveNews, SerperNews, GoogleCustomSearch, NewsApiOrg,
        Gdelt, GoogleNewsRss, BingNewsRss]
_BY_NAME = {cls.name: cls for cls in _ALL}


def build_providers(cfg: Config | None = None) -> list[SearchProvider]:
    cfg = cfg or CONFIG
    if cfg.search_provider:
        cls = _BY_NAME.get(cfg.search_provider)
        if not cls:
            raise ValueError(
                f"SEARCH_PROVIDER={cfg.search_provider!r} is not one of {sorted(_BY_NAME)}"
            )
        return [cls(cfg)]
    return [p for p in (cls(cfg) for cls in _ALL) if p.available()]


def gather(queries: Iterable[str], cfg: Config | None = None, limit: int = 10,
           days: int | None = None) -> tuple[list[SearchHit], list[dict]]:
    """Run every available provider over every query. Returns (hits, provider_log)."""
    cfg = cfg or CONFIG
    providers = build_providers(cfg)
    hits: list[SearchHit] = []
    log: list[dict] = []
    query_list = list(queries)
    for provider in providers:
        for query in query_list[:provider.max_queries]:
            if provider.min_interval:
                since = time.time() - _LAST_CALL.get(provider.name, 0.0)
                if since < provider.min_interval:
                    time.sleep(provider.min_interval - since)
            _LAST_CALL[provider.name] = time.time()
            started = time.time()
            try:
                found = provider.search(query, limit=limit, days=days)
                hits.extend(found)
                log.append({"provider": provider.name, "query": query, "ok": True,
                            "count": len(found), "ms": int((time.time() - started) * 1000)})
            except Exception as exc:  # a dead provider must not kill the call
                log.append({"provider": provider.name, "query": query, "ok": False,
                            "error": f"{type(exc).__name__}: {exc}"})
    return hits, log
