"""Publisher feeds: the keyless provider that returns URLs you can actually open.

Every other keyless provider has the same defect. Google News RSS names the
publisher correctly and then hands over a `news.google.com/rss/articles/CBMi...`
redirect; the payload inside it is an opaque Google id, not a URL, so there is
nothing to decode. GDELT returns real links and rate-limits hard because it is
free and shared. Bing returns real links and frequently returns nothing at all.

Measured on a live run with no search key: 44 articles found, 35 inside the
window, 29 distinct stories - and exactly one with a URL the server could open.
The free tier was never short of news. It was short of addresses.

So this provider skips the middlemen and reads the publishers directly. An RSS
feed is a publisher stating, in public and in a fixed format, what it just
published and where it lives. No key, no quota, no redirect, and the `<link>`
is the article itself.

The cost is that a feed carries only that outlet's own stories, so a headline is
only found if one of the listed outlets covered it - which is why the list is
chosen for a beat (technology, AI and security) rather than being a general news
sample. Within that beat it is better than any keyed provider; outside it, it
returns nothing and the other providers answer instead.

Two rules keep it honest:

  * **Matching is on distinctive tokens, not substrings.** A feed is a firehose
    of everything an outlet published today. Loose matching would hand back a
    story about a different company that happened to share the word "launch",
    and a confidently wrong source is worse than no source.
  * **A dead feed is silent, never fatal.** Publishers move their feeds without
    warning. Any feed that errors, times out or returns nothing is skipped; the
    rest still answer. `feed_health()` reports what responded so the list can be
    pruned against reality instead of guesswork.
"""
from __future__ import annotations

import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

import httpx

from ..config import CONFIG, Config
from ..httpfetch import fetch_html
from ..textutil import normalize, overlap, registrable_domain, strip_html, tokens

# (publisher name as it should be credited, feed url, beat)
#
# Every URL here answered a real request. Seven that looked obvious were
# removed after they did not: BleepingComputer, Engadget, CISA and SC Media
# return 403 to any automated client, Digital Trends 405, Sophos 404. Run
# capabilities(check_feeds=True) after editing this list - a plausible feed
# URL is not a working one, and a dead entry silently narrows the only
# keyless path that returns openable links.
#
# The publisher name is written here rather than derived from the domain because
# "arstechnica.com" is not how Ars Technica is cited, and these strings end up
# in a reference list a reader sees.
FEEDS: list[tuple[str, str, str]] = [
    # --- technology, general ---
    ("TechCrunch", "https://techcrunch.com/feed/", "tech"),
    ("The Verge", "https://www.theverge.com/rss/index.xml", "tech"),
    ("Ars Technica", "https://feeds.arstechnica.com/arstechnica/index", "tech"),
    ("Wired", "https://www.wired.com/feed/rss", "tech"),
    ("The Register", "https://www.theregister.com/headlines.atom", "tech"),
    ("ZDNET", "https://www.zdnet.com/news/rss.xml", "tech"),
    ("VentureBeat", "https://venturebeat.com/feed/", "tech"),
    ("The Next Web", "https://thenextweb.com/feed", "tech"),
    ("SiliconANGLE", "https://siliconangle.com/feed/", "tech"),
    ("TechRadar", "https://www.techradar.com/feeds/articletype/news", "tech"),
    ("Tom's Hardware", "https://www.tomshardware.com/feeds/all", "tech"),
    ("CNET", "https://www.cnet.com/rss/news/", "tech"),
    ("TechSpot", "https://www.techspot.com/backend.xml", "tech"),
    ("Axios", "https://www.axios.com/feeds/feed.rss", "tech"),
    ("Gizmodo", "https://gizmodo.com/feed", "tech"),
    ("MIT Technology Review", "https://www.technologyreview.com/feed/", "tech"),
    ("IEEE Spectrum", "https://spectrum.ieee.org/feeds/feed.rss", "tech"),
    ("BBC News", "https://feeds.bbci.co.uk/news/technology/rss.xml", "tech"),
    ("The Guardian", "https://www.theguardian.com/uk/technology/rss", "tech"),
    ("CNBC", "https://www.cnbc.com/id/19854910/device/rss/rss.html", "tech"),
    ("NPR", "https://feeds.npr.org/1019/rss.xml", "tech"),

    # --- artificial intelligence ---
    ("VentureBeat AI", "https://venturebeat.com/category/ai/feed/", "ai"),
    ("The Decoder", "https://the-decoder.com/feed/", "ai"),
    ("MarkTechPost", "https://www.marktechpost.com/feed/", "ai"),
    ("Google", "https://blog.google/rss/", "ai"),
    ("OpenAI", "https://openai.com/news/rss.xml", "ai"),
    ("Google DeepMind", "https://deepmind.google/blog/rss.xml", "ai"),
    ("NVIDIA", "https://blogs.nvidia.com/feed/", "ai"),
    ("Microsoft", "https://blogs.microsoft.com/feed/", "ai"),
    ("Hugging Face", "https://huggingface.co/blog/feed.xml", "ai"),

    # --- security ---
    ("The Hacker News", "https://feeds.feedburner.com/TheHackersNews", "security"),
    ("Krebs on Security", "https://krebsonsecurity.com/feed/", "security"),
    ("Dark Reading", "https://www.darkreading.com/rss.xml", "security"),
    ("SecurityWeek", "https://www.securityweek.com/feed/", "security"),
    ("CyberScoop", "https://cyberscoop.com/feed/", "security"),
    ("The Record", "https://therecord.media/feed", "security"),
    ("Help Net Security", "https://www.helpnetsecurity.com/feed/", "security"),
    ("Infosecurity Magazine", "https://www.infosecurity-magazine.com/rss/news/", "security"),
    ("Schneier on Security", "https://www.schneier.com/feed/atom/", "security"),
    ("Graham Cluley", "https://grahamcluley.com/feed/", "security"),
    ("Malwarebytes", "https://www.malwarebytes.com/blog/feed/index.xml", "security"),
    ("Unit 42", "https://unit42.paloaltonetworks.com/feed/", "security"),
    ("Security Affairs", "https://securityaffairs.com/feed", "security"),
    ("HackRead", "https://hackread.com/feed/", "security"),
    ("ESET WeLiveSecurity", "https://www.welivesecurity.com/en/rss/feed/", "security"),
    ("Cisco Talos", "https://blog.talosintelligence.com/rss/", "security"),
    ("SANS Internet Storm Center", "https://isc.sans.edu/rssfeed_full.xml", "security"),
    ("Check Point Research", "https://research.checkpoint.com/feed/", "security"),
]

# A headline only matches when this share of its distinctive tokens appear in
# the feed entry's title. Tuned by what it must reject: "Google releases a new
# local-first Granola competitor" against an unrelated Google story shares only
# "google", which is 0.2 - well under the floor.
MIN_MATCH = 0.55

# Feeds are polled once and reused. verify_news and find_stories each run
# several query variants, and without this the same forty feeds get fetched
# a dozen times for one headline.
CACHE_TTL = 300.0

_CACHE: dict[str, tuple[float, list]] = {}
_LOCK = threading.Lock()


def _parse(body: bytes):
    import feedparser
    return feedparser.parse(body)


def _load_one(client: httpx.Client, name: str, url: str) -> tuple[str, list, str]:
    """Return (publisher, entries, error). A failure is data, not an exception."""
    now = time.monotonic()
    with _LOCK:
        cached = _CACHE.get(url)
        if cached and now - cached[0] < CACHE_TTL:
            return name, cached[1], ""
    body, error = fetch_html(client, url)
    if error:
        # Strip the article-oriented advice off the end; for a feed the status
        # code is the whole story.
        return name, [], error.replace("fetch failed: ", "").split(" - ")[0]
    try:
        entries = list(_parse(body).entries)
    except Exception as exc:
        return name, [], f"{type(exc).__name__}: {exc}"
    with _LOCK:
        _CACHE[url] = (now, entries)
    return name, entries, ""


def _gather(cfg: Config, beats: tuple[str, ...] | None = None,
            timeout: float = 6.0) -> tuple[list[tuple[str, list]], list[dict]]:
    feeds = [(n, u) for n, u, beat in FEEDS if not beats or beat in beats]
    loaded: list[tuple[str, list]] = []
    report: list[dict] = []
    with httpx.Client(timeout=timeout, follow_redirects=True) as client:
        with ThreadPoolExecutor(max_workers=16) as pool:
            futures = {pool.submit(_load_one, client, n, u): (n, u)
                       for n, u in feeds}
            for future in as_completed(futures):
                name, entries, error = future.result()
                url = futures[future][1]
                report.append({"publisher": name, "url": url,
                               "entries": len(entries), "error": error})
                if entries:
                    loaded.append((name, entries))
    return loaded, report


def _entry_url(entry) -> str:
    link = entry.get("link", "") or ""
    if link:
        return link
    for alt in entry.get("links", []) or []:
        href = alt.get("href", "")
        if href:
            return href
    return ""


def _norm_url(url: str) -> str:
    """Compare URLs the way a human would: ignoring scheme, www and trailing /."""
    url = (url or "").strip().lower()
    for prefix in ("https://", "http://"):
        if url.startswith(prefix):
            url = url[len(prefix):]
    if url.startswith("www."):
        url = url[4:]
    return url.split("?")[0].split("#")[0].rstrip("/")


def _entry_content(entry) -> str:
    """The fullest text a feed entry carries. Many feeds ship the whole article."""
    for block in entry.get("content", []) or []:
        value = block.get("value", "") if isinstance(block, dict) else ""
        if value:
            return value
    return entry.get("summary", "") or ""


def cached_article(url: str) -> str:
    """Article HTML for a URL already seen in a bundled feed, else "".

    SecurityWeek, BleepingComputer and Associated Press all return 403 to any
    automated fetch of an article page. No header set changes that; it is a
    decision about who may read, not a technical obstacle. But a publisher that
    refuses the page often still broadcasts the same article in its own feed,
    which is a document it publishes specifically to be read by machines.

    So when the page is refused, the feed is asked instead. Only a substantial
    body counts: feeds that carry a two line teaser are skipped rather than
    passed off as the article, because half a story extracted cleanly is worse
    than an honest failure.
    """
    target = _norm_url(url)
    if not target:
        return ""
    with _LOCK:
        snapshot = [entries for _ts, entries in _CACHE.values()]
    for entries in snapshot:
        for entry in entries:
            if _norm_url(_entry_url(entry)) != target:
                continue
            body = _entry_content(entry)
            if len(body) >= 600:
                return body
    return ""


def search_feeds(query: str, limit: int = 10, cfg: Config | None = None,
                 beats: tuple[str, ...] | None = None) -> tuple[list[dict], list[dict]]:
    """Articles from the bundled publishers whose titles match `query`.

    Returns (hits, feed_report). Hits are plain dicts in SearchHit field order
    so this module stays importable without the provider machinery.
    """
    cfg = cfg or CONFIG
    loaded, report = _gather(cfg, beats)

    # A full headline must really match. A two word topic like "ransomware
    # attack" must not: requiring 55% of two tokens means requiring both, so
    # every headline that said "ransomware" without "attack" was discarded and
    # this provider returned nothing on a query it should own. Short queries get
    # the looser bar, with the long-word rule below guarding against junk.
    query_tokens = tokens(query)
    threshold = 0.5 if len(query_tokens) <= 4 else MIN_MATCH

    scored: list[tuple[float, dict]] = []
    for publisher, entries in loaded:
        for entry in entries:
            title = normalize(entry.get("title", ""))
            if not title:
                continue
            score = overlap(query, title)
            shared = query_tokens & tokens(title)
            # One long shared word is real evidence; "attack" or "data" is not.
            strong = any(len(word) >= 6 for word in shared)
            if score < threshold or not strong:
                continue
            url = _entry_url(entry)
            if not url.startswith("http"):
                continue
            scored.append((score, {
                "title": title,
                "url": url,
                # Credit the outlet by name, falling back to the domain only if
                # the feed came from somewhere unexpected after a redirect.
                "publisher": publisher or registrable_domain(url),
                "published_date": entry.get("published", "") or entry.get("updated", ""),
                "snippet": strip_html(entry.get("summary", ""))[:400],
                "provider": "publisher_feeds",
                "fetchable": True,
            }))

    scored.sort(key=lambda s: -s[0])
    return [hit for _, hit in scored[:limit]], report


def feed_health(cfg: Config | None = None) -> dict:
    """Which bundled feeds actually answer. Run this before trusting the list."""
    _CACHE.clear()
    loaded, report = _gather(cfg or CONFIG)
    report.sort(key=lambda r: (r["error"] == "", r["publisher"]))
    alive = [r for r in report if not r["error"] and r["entries"]]
    return {
        "feeds_total": len(report),
        "feeds_alive": len(alive),
        "feeds_dead": [r for r in report if r["error"] or not r["entries"]],
        "articles_available": sum(r["entries"] for r in report),
        "report": report,
    }
