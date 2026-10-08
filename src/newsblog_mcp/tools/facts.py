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
from ..httpfetch import fetch_html
from ..providers.feeds import cached_article
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


def _fact_key(sentence: str) -> str:
    """Identity of a fact, ignoring punctuation and case.

    Two outlets running the same wire copy differ by a curly quote or a dateline
    prefix, not by content.
    """
    return re.sub(r"[^a-z0-9 ]", "", (sentence or "").lower()).strip()


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


# Section labels used by newsrooms that write in blocks. Text captured between
# quote marks around them is page furniture, not something a person said.
_SECTION_LABELS = (
    "why it matters", "what they're saying", "what they are saying",
    "zoom out", "zoom in", "yes, but", "the big picture", "go deeper",
    "what we're watching", "what we are watching", "driving the news",
    "by the numbers", "between the lines", "the bottom line", "catch up quick",
)


def _is_quotable(quote: str) -> bool:
    """Whether this looks like something a person actually said.

    The regex matches anything between quote marks, and on a page that uses
    typographic quotes for emphasis that produced fragments like
    "- even as the White House continues using the term", attributed to the
    publisher's domain. A fragment handed to a writer as a quote is an invitation
    to print it, so these are dropped rather than passed along hedged.
    """
    low = quote.lower()
    if any(label in low for label in _SECTION_LABELS):
        return False
    # A real quote opens on a word, not on punctuation or a dangling conjunction.
    if not quote[:1].isalnum() and quote[:1] not in "'\u2018":
        return False
    if low.split(" ", 1)[0] in {"and", "but", "or", "so", "because", "which",
                                "that", "even", "though", "while"}:
        return False
    return True


def _extract_quotes(text: str, fallback_attrib: str) -> list[dict]:
    out = []
    for match in _QUOTE_RE.finditer(text):
        quote = normalize(match.group(1))
        words = quote.split()
        if not (4 <= len(words) <= 15):
            continue
        if not _is_quotable(quote):
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
        # Cut to the last whole word. A flat [-70:] slice produced labels like
        # "ss-NORC Center for Public Affairs Research finds that most Americans,"
        # where the source said "AP-NORC" - a figure whose label starts mid-word
        # reads as a typo in the source rather than a crop.
        if len(label) > 70:
            label = label[-70:]
            label = label.split(" ", 1)[1] if " " in label else label
        out.append({"label": label.strip(), "value": value})
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
    seen_facts: dict[str, dict] = {}
    quotes: list[dict] = []
    figures: list[dict] = []
    per_url: list[dict] = []

    with httpx.Client(timeout=cfg.http_timeout, follow_redirects=True) as client:
        for url in urls:
            record = {"url": url, "ok": False, "error": None, "chars": 0,
                      "title": "", "author": "", "date": ""}
            # Headers live in httpfetch because being refused by a publisher is
            # a policy answer, not a transport failure, and the retry that gets
            # past it is the same for every caller.
            html, error = fetch_html(client, url, cfg.user_agent)
            if error:
                # The page said no. Ask the publisher's own feed, which is the
                # same article published in a format meant for machines.
                html = cached_article(url)
                if html:
                    record["source"] = "publisher feed (article page refused the fetch)"
                    error = ""
            if error:
                record["error"] = error
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
                    # Syndication means two outlets often carry identical wire
                    # text. Listing it twice inflated fact_count - 24 facts that
                    # were really 12 - and invited the writer to treat one wire
                    # report as two independent confirmations. The duplicate is
                    # recorded as another publisher on the SAME fact instead.
                    key = _fact_key(sentence)
                    if key in seen_facts:
                        other = seen_facts[key]
                        if publisher not in other["also_reported_by"]:
                            other["also_reported_by"].append(publisher)
                        continue
                    entry = {"text": sentence, "source_url": url,
                             "publisher": publisher, "also_reported_by": []}
                    seen_facts[key] = entry
                    facts.append(entry)
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
