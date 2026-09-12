"""Tool 2 - fetch_article_facts.

Downloads each URL, extracts clean article text, and pulls out candidate facts,
short attributed quotes and figures. Every item carries its source_url so the
finished post can be traced back line by line. Nothing is invented: a URL that
fails extraction is reported as a failure, not filled in.
"""
from __future__ import annotations

import re

import httpx

from ..config import CONFIG, Config
from ..textutil import normalize, registrable_domain, sentences

_BOILERPLATE = re.compile(
    r"cookie|subscribe|sign up|newsletter|all rights reserved|©|advertisement|"
    r"read more|follow us|terms of service|privacy policy|share this",
    re.I,
)
_QUOTE_RE = re.compile(r"[\"“]([^\"”]{15,200})[\"”]")
_ATTRIB_RE = re.compile(
    r"(?:said|says|told|according to|added|wrote)\s+([A-Z][\w.'-]+(?:\s+[A-Z][\w.'-]+){0,3})"
)
_FIGURE_RE = re.compile(
    r"((?:US\$|\$|€|£|₹)\s?\d[\d,.]*\s?(?:billion|million|trillion|bn|mn)?"
    r"|\d[\d,.]*\s?(?:percent|%)"
    r"|\d[\d,.]*\s?(?:billion|million|trillion)"
    r"|\d[\d,.]*\s?(?:GW|MW|TWh|GB|TB|km|miles|users|jobs|employees|customers|devices))",
    re.I,
)
_PROPER_RE = re.compile(r"\b[A-Z][a-z]{2,}\b")


def _looks_like_fact(sentence: str) -> bool:
    if not (45 <= len(sentence) <= 320):
        return False
    if _BOILERPLATE.search(sentence):
        return False
    if sentence.endswith("?"):
        return False
    has_number = bool(re.search(r"\d", sentence))
    has_proper = len(_PROPER_RE.findall(sentence)) >= 1
    return has_number or has_proper


def _extract_quotes(text: str, fallback_attrib: str) -> list[dict]:
    out = []
    for match in _QUOTE_RE.finditer(text):
        quote = normalize(match.group(1))
        words = quote.split()
        if not (4 <= len(words) <= 15):
            continue
        window = text[match.end(): match.end() + 120]
        before = text[max(0, match.start() - 120): match.start()]
        attrib_match = _ATTRIB_RE.search(window) or _ATTRIB_RE.search(before)
        out.append({
            "text": quote,
            "attribution": normalize(attrib_match.group(1)) if attrib_match else fallback_attrib,
            "attribution_confident": bool(attrib_match),
        })
    return out


def _extract_figures(text: str) -> list[dict]:
    out, seen = [], set()
    for match in _FIGURE_RE.finditer(text):
        value = normalize(match.group(1))
        if value.lower() in seen:
            continue
        seen.add(value.lower())
        start = max(0, match.start() - 70)
        label = normalize(text[start:match.start()]).split(". ")[-1]
        out.append({"label": label[-70:], "value": value})
    return out


def fetch_article_facts(
    urls: list[str],
    cfg: Config | None = None,
    max_facts_per_url: int = 12,
) -> dict:
    cfg = cfg or CONFIG
    try:
        import trafilatura
    except ImportError as exc:  # pragma: no cover
        return {"error": f"trafilatura is not installed: {exc}", "facts": [],
                "quotes": [], "figures": [], "per_url": []}

    facts: list[dict] = []
    quotes: list[dict] = []
    figures: list[dict] = []
    per_url: list[dict] = []

    headers = {"User-Agent": cfg.user_agent, "Accept-Language": "en-US,en;q=0.9"}
    with httpx.Client(timeout=cfg.http_timeout, follow_redirects=True, headers=headers) as client:
        for url in urls:
            record = {"url": url, "ok": False, "error": None, "chars": 0,
                      "title": "", "author": "", "date": ""}
            try:
                response = client.get(url)
                response.raise_for_status()
                html = response.text
            except Exception as exc:
                record["error"] = f"fetch failed: {type(exc).__name__}: {exc}"
                per_url.append(record)
                continue

            text = trafilatura.extract(
                html, include_comments=False, include_tables=False,
                favor_precision=True, url=url,
            )
            if not text or len(text) < 200:
                record["error"] = "extraction produced no usable article text"
                per_url.append(record)
                continue

            try:
                meta = trafilatura.extract_metadata(html, default_url=url)
                record["title"] = normalize(getattr(meta, "title", "") or "")
                record["author"] = normalize(getattr(meta, "author", "") or "")
                record["date"] = normalize(getattr(meta, "date", "") or "")
            except Exception:
                pass

            publisher = registrable_domain(url)
            record.update(ok=True, chars=len(text))
            per_url.append(record)

            picked = 0
            for sentence in sentences(text):
                sentence = normalize(sentence)
                if _looks_like_fact(sentence):
                    facts.append({"text": sentence, "source_url": url, "publisher": publisher})
                    picked += 1
                    if picked >= max_facts_per_url:
                        break

            for quote in _extract_quotes(text, fallback_attrib=publisher)[:4]:
                quotes.append({**quote, "source_url": url, "publisher": publisher})
            for figure in _extract_figures(text)[:8]:
                figures.append({**figure, "source_url": url, "publisher": publisher})

    ok_count = sum(1 for r in per_url if r["ok"])
    return {
        "facts": facts,
        "quotes": quotes,
        "figures": figures,
        "per_url": per_url,
        "summary": {
            "urls_requested": len(urls),
            "urls_extracted": ok_count,
            "urls_failed": len(urls) - ok_count,
            "fact_count": len(facts),
        },
        "usage_note": (
            "Every fact, quote and figure above carries source_url. Do not write any "
            "claim into the article that is not traceable to one of these entries. "
            "Quotes are capped at 15 words and must stay attributed."
        ),
    }
