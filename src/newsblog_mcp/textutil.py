"""Small text helpers shared by several tools. No external deps."""
from __future__ import annotations

import re
import unicodedata
from urllib.parse import urlparse

_STOPWORDS = {
    "a", "an", "and", "are", "as", "at", "be", "but", "by", "for", "from", "has",
    "have", "how", "in", "into", "is", "it", "its", "of", "on", "or", "over",
    "that", "the", "their", "there", "this", "to", "was", "were", "will", "with",
    "after", "before", "amid", "says", "say", "said", "new", "more", "than",
}

_CC_SLD = {
    "co.uk", "co.in", "co.jp", "com.au", "co.nz", "com.br", "co.za", "com.sg",
    "com.hk", "co.kr", "com.mx", "or.jp", "ne.jp", "gov.uk", "ac.uk",
}

_SENTENCE_RE = re.compile(r"(?<=[.!?])\s+(?=[A-Z\"'“])")


def normalize(text: str) -> str:
    text = unicodedata.normalize("NFKC", text or "")
    return re.sub(r"\s+", " ", text).strip()


def tokens(text: str) -> set[str]:
    words = re.findall(r"[a-z0-9]+", (text or "").lower())
    return {w for w in words if len(w) > 2 and w not in _STOPWORDS}


def overlap(a: str, b: str) -> float:
    """Fraction of the query's distinctive tokens present in the candidate."""
    ta, tb = tokens(a), tokens(b)
    if not ta:
        return 0.0
    return len(ta & tb) / len(ta)


def registrable_domain(url: str) -> str:
    host = (urlparse(url).hostname or "").lower()
    if host.startswith("www."):
        host = host[4:]
    parts = host.split(".")
    if len(parts) >= 3 and ".".join(parts[-2:]) in _CC_SLD:
        return ".".join(parts[-3:])
    return ".".join(parts[-2:]) if len(parts) >= 2 else host


def sentences(text: str) -> list[str]:
    out: list[str] = []
    for block in (text or "").split("\n"):
        block = block.strip()
        if not block:
            continue
        out.extend(s.strip() for s in _SENTENCE_RE.split(block) if s.strip())
    return out


def slugify(text: str, max_len: int = 70) -> str:
    text = unicodedata.normalize("NFKD", text or "").encode("ascii", "ignore").decode()
    text = re.sub(r"[^a-zA-Z0-9]+", "-", text).strip("-").lower()
    return (text[:max_len].rstrip("-")) or "post"


def strip_html(text: str) -> str:
    return normalize(re.sub(r"<[^>]+>", " ", text or ""))
