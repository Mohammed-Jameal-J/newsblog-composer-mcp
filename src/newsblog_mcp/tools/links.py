"""Internal links: the only links on a page you actually control.

A backlink is a link on somebody else's site pointing at yours. Nothing in this
file makes one, and nothing can - that decision belongs to a person who does not
work for you. What this does is the half that was missing: linking a new post to
the posts you have already published.

That matters for three reasons. It passes authority between your own pages, it
keeps a reader moving through the site instead of leaving it, and it is how a
crawler learns that twelve of your posts are about the same subject - which is
also what builds the topical depth an answer engine looks for.

Every post this server writes already carries its slug, title, keywords and
entities. Until now nothing read them back. This keeps a small index beside
`profile.json` and matches a new draft against it.

**Matching is deliberately strict.** The obvious design - link whenever a word
repeats - produces links between posts that merely share the word "model", and
an irrelevant internal link is worse than no link: readers ignore it and search
engines read it as low quality. A shared *entity* is evidence; a shared common
word is not. Below the floor, this returns nothing, and returning nothing is a
correct answer.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from ..paths import data_dir
from ..textutil import normalize, tokens

INDEX_NAME = "post_index.json"

# Keep the index from growing without bound. A blog that has published 500 posts
# has enough history for any match worth making.
MAX_ENTRIES = 500

# What a match is worth. An entity both posts name is the strong signal; a shared
# secondary keyword is weak corroboration on its own.
_W_PRIMARY = 4.0      # the other post's primary keyword appears in this draft
_W_ENTITY = 3.0       # per shared entity
_W_KEYWORD = 1.0      # per shared secondary keyword

# Below this, link nothing. One shared entity clears it; three shared common
# keywords do not.
MIN_SCORE = 3.0


def index_path() -> Path:
    return data_dir() / INDEX_NAME


def load_index() -> list[dict]:
    """Every post recorded so far. Never raises - a broken index is not a reason
    to stop the server, and an empty list degrades to "no suggestions"."""
    try:
        raw = index_path().read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return []
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return []
    return [row for row in data if isinstance(row, dict)] if isinstance(data, list) else []


def record_post(slug: str, title: str, url: str,
                primary_keyword: str = "",
                keywords: list[str] | None = None,
                entities: list[str] | None = None,
                published: str = "") -> dict:
    """Add one post to the index, or update it if the slug is already there.

    Best effort by design: called from save_and_present, where a failure must not
    cost the user the post that was just written.
    """
    entry = {
        "slug": normalize(slug),
        "title": normalize(title),
        "url": normalize(url),
        "primary_keyword": normalize(primary_keyword).lower(),
        "keywords": [normalize(k).lower() for k in (keywords or []) if normalize(k)][:12],
        "entities": [normalize(e) for e in (entities or []) if normalize(e)][:12],
        "published": published or datetime.now(timezone.utc).strftime("%Y-%m-%d"),
    }
    if not entry["slug"]:
        return {"ok": False, "reason": "no slug"}

    rows = [r for r in load_index() if r.get("slug") != entry["slug"]]
    rows.append(entry)
    rows = rows[-MAX_ENTRIES:]
    try:
        path = index_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(rows, indent=2, ensure_ascii=False), encoding="utf-8")
    except OSError as exc:
        return {"ok": False, "reason": str(exc)}
    return {"ok": True, "indexed": len(rows), "path": str(index_path())}


def _lower_set(values) -> set[str]:
    return {normalize(v).lower() for v in (values or []) if normalize(v)}


def suggest_internal_links(headline: str,
                           primary_keyword: str = "",
                           keywords: list[str] | None = None,
                           entities: list[str] | None = None,
                           exclude_slug: str = "",
                           limit: int = 4,
                           min_score: float = MIN_SCORE) -> dict:
    """Past posts worth linking to from this draft, with anchor text."""
    index = load_index()
    if not index:
        return {
            "suggestions": [],
            "indexed_posts": 0,
            "note": ("No posts are indexed yet. The index fills as save_and_present "
                     "writes each post, so this starts being useful from the second "
                     "post onward and matters from about thirty."),
        }

    here_entities = _lower_set(entities)
    here_keywords = _lower_set(keywords) | ({normalize(primary_keyword).lower()}
                                            if primary_keyword else set())
    here_text = tokens(f"{headline} {' '.join(keywords or [])}")

    scored = []
    for row in index:
        if row.get("slug") == normalize(exclude_slug):
            continue
        if not row.get("url"):
            continue

        reasons = []
        score = 0.0

        shared_entities = sorted(_lower_set(row.get("entities")) & here_entities)
        if shared_entities:
            score += _W_ENTITY * len(shared_entities)
            reasons.append("shares " + ", ".join(shared_entities[:3]))

        their_primary = normalize(row.get("primary_keyword", "")).lower()
        if their_primary and (their_primary in here_keywords
                              or tokens(their_primary) <= here_text):
            score += _W_PRIMARY
            reasons.append(f"that post is about {their_primary}")

        shared_keywords = sorted(_lower_set(row.get("keywords")) & here_keywords)
        if shared_keywords:
            score += _W_KEYWORD * len(shared_keywords)
            reasons.append("both cover " + ", ".join(shared_keywords[:2]))

        if score < min_score:
            continue

        # The anchor describes the destination. "Click here" and "read more" tell
        # a crawler nothing and tell a reader nothing either.
        anchor = their_primary or normalize(row.get("title", ""))
        scored.append({
            "url": row["url"],
            "title": row.get("title", ""),
            "slug": row.get("slug", ""),
            "published": row.get("published", ""),
            "anchor_text": anchor,
            "score": round(score, 1),
            "why": "; ".join(reasons),
        })

    scored.sort(key=lambda s: (-s["score"], s["published"]))
    picked = scored[:max(0, limit)]

    return {
        "suggestions": picked,
        "indexed_posts": len(index),
        "considered": len(index),
        "min_score": min_score,
        "how_to_use": (
            "Work these into sentences as you write, not into a 'Related posts' "
            "list at the end - those are skipped by readers and discounted by "
            "crawlers. Use anchor_text, or a phrase that reads naturally and still "
            "describes the destination. Never 'click here' or 'read more'."
        ),
        "note": ("Nothing cleared the relevance floor, so link nothing. A post with "
                 "no internal links is fine; one with four irrelevant links is not."
                 if not picked else
                 f"{len(picked)} of {len(index)} indexed posts are relevant enough."),
    }
