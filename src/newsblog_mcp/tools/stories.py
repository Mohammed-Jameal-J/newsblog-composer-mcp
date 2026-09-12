"""Tool 2 - find_stories.

verify_news answers "is this exact headline real". That is the wrong first step
when the input is a topic rather than a headline: "AI today" is not a claim to
verify, it is a request for what happened.

This tool takes a topic, pulls recent coverage, groups articles that are
reporting the same event, and ranks the resulting stories by how many
independent publishers carried them and how recent they are. The calling model
picks one, and only then does verify_news run on that story's headline.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from ..config import CONFIG, Config
from ..providers.search import SearchHit, gather
from ..textutil import normalize, overlap, registrable_domain
from .verify import _parse_date, _publisher_key, _publisher_label

CLUSTER_THRESHOLD = 0.5


def _cluster(hits: list[SearchHit]) -> list[list[SearchHit]]:
    """Group hits whose headlines describe the same event."""
    clusters: list[list[SearchHit]] = []
    for hit in sorted(hits, key=lambda h: len(h.title), reverse=True):
        for cluster in clusters:
            if any(max(overlap(hit.title, other.title),
                       overlap(other.title, hit.title)) >= CLUSTER_THRESHOLD
                   for other in cluster[:4]):
                cluster.append(hit)
                break
        else:
            clusters.append([hit])
    return clusters


def _representative(cluster: list[SearchHit]) -> str:
    """The headline most typical of the cluster, not just the first one."""
    if len(cluster) == 1:
        return cluster[0].title
    best, best_score = cluster[0], -1.0
    for candidate in cluster:
        score = sum(overlap(candidate.title, other.title)
                    for other in cluster if other is not candidate)
        if score > best_score:
            best, best_score = candidate, score
    return best.title


def find_stories(
    topic: str,
    days: int = 2,
    limit: int = 30,
    cfg: Config | None = None,
) -> dict:
    cfg = cfg or CONFIG
    topic = normalize(topic)
    if not topic:
        return {"stories": [], "error": "empty topic"}

    cutoff = datetime.now(timezone.utc) - timedelta(days=days)
    raw_hits, provider_log = gather([topic], cfg=cfg, limit=limit, days=days)

    fresh, undated, stale = [], 0, 0
    for hit in raw_hits:
        if _publisher_key(hit) == "unknown" or not hit.title:
            continue
        published = _parse_date(hit.published_date)
        if published is None:
            undated += 1
            fresh.append(hit)  # keep, but it cannot be ranked on recency
        elif published >= cutoff:
            fresh.append(hit)
        else:
            stale += 1

    stories = []
    for cluster in _cluster(fresh):
        publishers: dict[str, SearchHit] = {}
        for hit in cluster:
            publishers.setdefault(_publisher_key(hit), hit)
        dates = [d for d in (_parse_date(h.published_date) for h in cluster) if d]
        latest = max(dates) if dates else None
        age_hours = ((datetime.now(timezone.utc) - latest).total_seconds() / 3600
                     if latest else None)
        stories.append({
            "headline": _representative(cluster),
            "publisher_count": len(publishers),
            "publishers": sorted({_publisher_label(h) for h in publishers.values()}),
            "earliest_date": min(dates).isoformat() if dates else "",
            "latest_date": latest.isoformat() if latest else "",
            "age_hours": round(age_hours, 1) if age_hours is not None else None,
            "fetchable_urls": [h.url for h in cluster if h.fetchable][:6],
            "article_count": len(cluster),
            "sample_titles": [h.title for h in cluster[:4]],
        })

    # Corroboration first, then freshness. A story two publishers carried an hour
    # ago beats one publisher shouting yesterday.
    stories.sort(key=lambda s: (s["publisher_count"],
                                -(s["age_hours"] if s["age_hours"] is not None else 9999)),
                 reverse=True)

    usable = [s for s in stories if s["publisher_count"] >= 2 and s["fetchable_urls"]]
    return {
        "topic": topic,
        "window_days": days,
        "stories": stories[:12],
        "ready_to_write": usable[:5],
        "counts": {"articles_seen": len(raw_hits), "in_window": len(fresh),
                   "too_old": stale, "undated": undated, "stories_found": len(stories)},
        "provider_log": provider_log,
        "usage_note": (
            "Pick a story from `ready_to_write` - those already have two or more "
            "independent publishers and at least one fetchable URL. Pass its "
            "`headline` to verify_news, then its `fetchable_urls` to "
            "fetch_article_facts. If ready_to_write is empty, either the topic is "
            "too narrow, the window is too short, or nothing much happened; widen "
            "`days` before giving up. `age_hours` is how old the newest article in "
            "the story is - use it to pick something actually current."
        ),
    }
