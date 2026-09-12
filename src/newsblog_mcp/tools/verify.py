"""Tool 1 - verify_news.

Decides nothing about the *story*; it decides whether independent publishers
are actually reporting it, and hands the reasoning back so the calling model
can judge. A title with no corroboration is rejected here so the rest of the
pipeline can never run on an invented headline.
"""
from __future__ import annotations

import re
from datetime import datetime, timezone
from urllib.parse import urlparse

from ..config import CONFIG, Config
from ..providers.search import SearchHit, gather
from ..textutil import normalize, overlap, registrable_domain, tokens

RELEVANCE_THRESHOLD = 0.45
# Above this, two headlines are the same sentence rather than two newsrooms
# independently describing one event.
SYNDICATION_THRESHOLD = 0.85
_PRIMARY_SUBDOMAINS = ("blog.", "news.", "newsroom.", "press.", "investor.", "about.", "ir.")
_PRIMARY_PATH_HINTS = ("/press-release", "/press/", "/newsroom", "/blog/", "/investor")
_PRIMARY_TLDS = (".gov", ".gov.uk", ".europa.eu", ".int", ".mil")
# Registrable domains, because that is what registrable_domain() returns:
# news.google.com reduces to google.com.
_AGGREGATORS = {"google.com", "bing.com", "msn.com", "yahoo.com", "flipboard.com",
                "news.com", "smartnews.com"}


def _parse_date(value: str):
    if not value:
        return None
    value = value.strip()
    for fmt in ("%Y-%m-%dT%H:%M:%S%z", "%Y-%m-%dT%H:%M:%SZ", "%Y-%m-%d",
                "%a, %d %b %Y %H:%M:%S %z", "%a, %d %b %Y %H:%M:%S %Z"):
        try:
            dt = datetime.strptime(value, fmt)
            return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
        except ValueError:
            continue
    try:
        dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
        return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
    except ValueError:
        return None


def _is_primary(hit: SearchHit, title: str) -> bool:
    parsed = urlparse(hit.url)
    host = (parsed.hostname or "").lower()
    path = (parsed.path or "").lower()
    if any(host.endswith(t) for t in _PRIMARY_TLDS):
        return True
    if any(host.startswith(s) for s in _PRIMARY_SUBDOMAINS) and any(
        p in path for p in _PRIMARY_PATH_HINTS
    ):
        return True
    # A company reporting its own news: the registrable domain's brand word
    # appears in the headline itself (e.g. nvidia.com for an Nvidia headline).
    brand = registrable_domain(hit.url).split(".")[0]
    return bool(brand) and len(brand) > 3 and brand in tokens(title)


def _publisher_key(hit: SearchHit) -> str:
    """Identity of the outlet behind a hit.

    Aggregator links (Google News redirects) all share one domain, so keying on
    the URL would collapse twenty different outlets into "google.com" and make
    corroboration counting meaningless. For those, the feed's own publisher name
    is the real identity. Both forms reduce to a bare brand token so that
    "reuters.com" and "Reuters" count as one publisher, not two.
    """
    name = re.sub(r"[^a-z0-9]", "", (hit.publisher or "").lower())
    domain = registrable_domain(hit.url)
    if not hit.fetchable or domain in _AGGREGATORS:
        return name or "unknown"
    return (domain.split(".")[0].lower() if domain else "") or name or "unknown"


def _publisher_label(hit: SearchHit) -> str:
    domain = registrable_domain(hit.url)
    if not hit.fetchable or domain in _AGGREGATORS:
        return hit.publisher or "unknown"
    return domain or hit.publisher or "unknown"


def _dedupe(hits: list[SearchHit]) -> list[SearchHit]:
    seen: dict[tuple[str, str], SearchHit] = {}
    for hit in hits:
        if not hit.url:
            continue
        key = (_publisher_key(hit), re.sub(r"[^a-z0-9]", "", hit.title.lower())[:60])
        current = seen.get(key)
        # Prefer a fetchable URL over a redirect for the same story.
        if current is None or (hit.fetchable and not current.fetchable):
            seen[key] = hit
    return list(seen.values())


def _syndication(publishers: dict) -> dict:
    """Detect wire copy masquerading as independent corroboration.

    A Reuters or AP story runs verbatim on dozens of sites. Counting those as
    dozens of publishers is the single easiest way to conclude a story is
    well-corroborated when in fact exactly one newsroom reported it.
    """
    hits = list(publishers.values())
    if len(hits) < 2:
        return {"likely_syndicated": False, "clusters": []}

    groups: list[list] = []
    for hit in hits:
        for group in groups:
            if max(overlap(hit.title, group[0].title),
                   overlap(group[0].title, hit.title)) >= SYNDICATION_THRESHOLD:
                group.append(hit)
                break
        else:
            groups.append([hit])

    largest = max(groups, key=len)
    return {
        "likely_syndicated": len(largest) >= 2 and len(largest) >= len(hits) * 0.6,
        "distinct_wordings": len(groups),
        "largest_identical_group": len(largest),
        "shared_headline": largest[0].title if len(largest) > 1 else "",
        "clusters": [[h.publisher or registrable_domain(h.url) for h in g]
                     for g in groups],
    }


def verify_news(title: str, cfg: Config | None = None, limit: int = 10,
                days: int | None = None) -> dict:
    cfg = cfg or CONFIG
    title = normalize(title)
    if not title:
        return {"is_legit": False, "confidence": "low", "sources": [], "publish_date": "",
                "reasoning": "Empty title supplied.", "provider_log": []}

    queries = [f'"{title}"', title]
    raw_hits, provider_log = gather(queries, cfg=cfg, limit=limit, days=days)

    if not raw_hits and all(not entry.get("ok") for entry in provider_log):
        return {
            "is_legit": False, "confidence": "low", "sources": [], "publish_date": "",
            "reasoning": "No search provider responded, so the headline could not be "
                         "checked at all. This is a tooling failure, not evidence that "
                         "the story is fake. See provider_log.",
            "provider_log": provider_log,
        }

    hits = _dedupe(raw_hits)
    relevant, rejected = [], []
    for hit in hits:
        if _publisher_key(hit) == "unknown":
            continue  # an aggregator link with no named outlet proves nothing
        score = max(overlap(title, hit.title), overlap(title, hit.snippet))
        if score >= RELEVANCE_THRESHOLD:
            relevant.append((score, hit))
        else:
            rejected.append((score, hit))
    relevant.sort(key=lambda pair: pair[0], reverse=True)

    publishers: dict[str, SearchHit] = {}
    for _, hit in relevant:
        publishers.setdefault(_publisher_key(hit), hit)
    publisher_labels = sorted({_publisher_label(h) for h in publishers.values()})

    dates = [d for d in (_parse_date(h.published_date) for _, h in relevant) if d]
    publish_date = min(dates).isoformat() if dates else ""
    date_spread_days = (max(dates) - min(dates)).days if len(dates) >= 2 else 0

    primary = [h for _, h in relevant if _is_primary(h, title)]
    n_pub = len(publishers)

    if n_pub == 0:
        verdict, confidence = False, "low"
        reasoning = (
            f"{len(hits)} search result(s) came back but none matched the headline "
            f"closely enough (best token overlap "
            f"{max([s for s, _ in rejected], default=0.0):.2f} vs threshold "
            f"{RELEVANCE_THRESHOLD}). Treat this headline as unverified."
        )
    elif n_pub == 1 and primary:
        verdict, confidence = True, "high"
        reasoning = (
            f"Single source, but it is the primary/official one "
            f"({registrable_domain(primary[0].url)}) reporting its own news, which the "
            f"brief accepts as high confidence."
        )
    elif n_pub == 1:
        verdict, confidence = False, "low"
        reasoning = (
            f"Only one publisher ({publisher_labels[0]}) is carrying this and it is not "
            f"a primary/official source. Two independent publishers are required before "
            f"this pipeline will generate content."
        )
    else:
        verdict = True
        confidence = "high" if n_pub >= 3 else "medium"
        reasoning = (f"{n_pub} independent publishers are reporting this: "
                     f"{', '.join(publisher_labels[:6])}.")
        if primary:
            confidence = "high"
            reasoning += f" One of them is a primary/official source ({registrable_domain(primary[0].url)})."

    syndication = _syndication(publishers)
    if verdict and syndication["likely_syndicated"]:
        confidence = "medium" if confidence == "high" else confidence
        reasoning += (
            f" CAUTION: {syndication['largest_identical_group']} of these carry a "
            f"near-identical headline, so this is most likely one wire story "
            f"(Reuters, AP, AFP) republished rather than {n_pub} newsrooms reporting "
            f"independently. Only {syndication['distinct_wordings']} distinct wording(s) "
            f"appear. Treat it as {syndication['distinct_wordings']} source(s), find the "
            f"originating outlet, and cite that."
        )

    if verdict and date_spread_days > 30:
        confidence = "low"
        reasoning += (
            f" CONFLICT: matched reports span {date_spread_days} days, so these may be "
            f"separate events or recycled coverage rather than one story. Check the "
            f"dates before writing anything."
        )

    return {
        "is_legit": verdict,
        "confidence": confidence,
        "sources": [
            {**hit.to_dict(), "relevance": round(score, 2),
             "is_primary_source": _is_primary(hit, title)}
            for score, hit in relevant[:12]
        ],
        "publish_date": publish_date,
        "reasoning": reasoning,
        "fetchable_urls": [h.url for _, h in relevant if h.fetchable][:8],
        "reference_candidates": [
            {"title": h.title, "url": h.url, "publisher": _publisher_label(h)}
            for _, h in relevant if h.fetchable
        ][:10],
        "independent_publishers": publisher_labels,
        "syndication": syndication,
        "provider_log": provider_log,
    }
