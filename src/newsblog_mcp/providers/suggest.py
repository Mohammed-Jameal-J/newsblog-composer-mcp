"""Keyless query-suggestion source.

Google's autocomplete endpoint needs no key and returns what people actually
type, which makes it a better source of long-tail phrases and FAQ questions than
anything a model invents. It is undocumented, so every failure is swallowed and
reported rather than raised - the SEO tool stays useful without it.
"""
from __future__ import annotations

import json

import httpx

from ..config import Config

_ENDPOINT = "https://suggestqueries.google.com/complete/search"
_QUESTION_PREFIXES = ("what is", "how does", "why", "when will", "who", "is", "will")


def suggest(seed: str, cfg: Config, hl: str = "en") -> list[str]:
    with httpx.Client(timeout=12.0, follow_redirects=True,
                      headers={"User-Agent": cfg.user_agent}) as client:
        r = client.get(_ENDPOINT, params={"client": "firefox", "hl": hl, "q": seed})
        r.raise_for_status()
        payload = json.loads(r.text)
    if isinstance(payload, list) and len(payload) > 1 and isinstance(payload[1], list):
        return [s for s in payload[1] if isinstance(s, str)]
    return []


def expand(seed: str, cfg: Config, include_questions: bool = True) -> tuple[list[str], list[str], list[str]]:
    """Returns (long_tail, questions, errors)."""
    long_tail: list[str] = []
    questions: list[str] = []
    errors: list[str] = []

    seeds = [seed]
    if include_questions:
        seeds += [f"{prefix} {seed}" for prefix in _QUESTION_PREFIXES]

    for item in seeds:
        try:
            for phrase in suggest(item, cfg):
                bucket = questions if phrase.split(" ", 1)[0].lower() in {
                    "what", "how", "why", "when", "who", "is", "will", "does", "can"
                } else long_tail
                if phrase.lower() != seed.lower() and phrase not in bucket:
                    bucket.append(phrase)
        except Exception as exc:
            errors.append(f"{item!r}: {type(exc).__name__}: {exc}")
            break  # one failure means the endpoint is unreachable; stop hammering it

    return long_tail[:20], questions[:20], errors
