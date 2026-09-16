"""Tools 9 and 10 - seo_keywords and seo_audit.

Keywords are mined from the text of the sources that were actually fetched, not
invented, so the terms the post targets are the terms the reporting uses. The
audit then checks a finished draft against on-page rules and returns a list of
concrete fixes.

Neither tool has search-volume data - that needs a paid keyword API. What these
give you is relevance and structure, which is most of on-page SEO.
"""
from __future__ import annotations

import re
from collections import Counter
from html.parser import HTMLParser

from ..config import CONFIG, Config
from ..providers.suggest import expand
from ..textutil import normalize, sentences, slugify, tokens

_STOP = {
    # Core function words. These were only partly covered, which let phrases like
    # "led by" through as keywords: "by" was never in the list.
    "a", "an", "of", "in", "on", "to", "is", "it", "as", "at", "be", "or", "by",
    "do", "did", "if", "so", "up", "we", "us", "my", "me", "he", "she", "no",
    "yes", "via", "off", "led", "lead", "leads", "am", "im", "ive", "id",
    "the", "and", "for", "that", "this", "with", "from", "have", "has", "had",
    "was", "were", "will", "would", "could", "should", "been", "being", "are",
    "its", "his", "her", "their", "they", "them", "there", "these", "those",
    "than", "then", "when", "what", "which", "who", "whom", "how", "why", "all",
    "any", "but", "not", "you", "your", "our", "out", "own", "can", "may",
    "more", "most", "some", "such", "only", "also", "into", "over", "after",
    "before", "about", "said", "says", "say", "told", "according", "new", "one",
    "two", "first", "last", "year", "years", "day", "days", "time", "made",
    "make", "just", "like", "now", "still", "back", "way", "per", "cent",
    # Common verbs and connectives. Without these a headline phrase like
    # "amazon took qualcomm" scores as a keyword, which it plainly is not.
    "took", "take", "takes", "taken", "taking", "become", "becomes", "becoming",
    "shows", "show", "showed", "gets", "get", "got", "put", "puts", "use", "uses",
    "used", "using", "see", "sees", "seen", "come", "comes", "came", "going",
    "goes", "went", "want", "wants", "need", "needs", "know", "knows", "think",
    "thinks", "look", "looks", "find", "finds", "give", "gives", "given", "keep",
    "keeps", "hold", "holds", "held", "set", "sets", "run", "runs", "call",
    "calls", "called", "ask", "asks", "asked", "try", "tries", "seem", "seems",
    "leave", "leaves", "left", "mean", "means", "turn", "turns", "start",
    "starts", "started", "help", "helps", "move", "moves", "bring", "brings",
    "happen", "happens", "write", "writes", "provide", "include", "includes",
    "continue", "add", "adds", "added", "change", "changes", "lead", "leads",
    "follow", "follows", "stop", "create", "creates", "allow", "allows", "spend",
    "grow", "grows", "open", "opens", "win", "wins", "won", "offer", "offers",
    "consider", "appear", "appears", "buy", "buys", "bought", "wait", "send",
    "sends", "expect", "expects", "build", "builds", "stay", "fall", "falls",
    "cut", "cuts", "reach", "reaches", "remain", "remains", "rise", "rises",
    "rose", "jump", "jumps", "goes", "does", "did", "done", "being", "having",
    "must", "might", "every", "each", "both", "here", "very", "much", "many",
    "well", "even", "already", "yet", "now", "next", "same", "other", "another",
    "normal", "actually", "really",
    # Reporting and action verbs. A keyword should name a subject, not an event:
    # "anthropic banned" is a sentence fragment, "threat report" is a keyword.
    "banned", "blocked", "removed", "targeted", "targeting", "published",
    "reported", "reporting", "described", "describes", "documenting", "tried",
    "ran", "runs", "assigned", "covering", "monitored", "affected", "using",
    "named", "names", "found", "finds", "identified", "disrupted", "released",
    "carried", "handled", "linked", "tied", "aimed", "worked", "working",
    "according", "claims", "claimed", "stated", "states",
    # Prepositions and connectives: they join two phrases, they are not part of
    # either one.
    "across", "among", "amongst", "between", "within", "through", "throughout",
    "during", "against", "toward", "towards", "beyond", "alongside", "including",
    "plus", "onto", "upon", "under", "above", "below", "behind", "beside",
    "since", "until", "unless", "while", "whilst", "whether", "because",
    # Units and comparison words. On a benchmark-heavy story these outscored the
    # actual subject and produced keywords like "percent against".
    "percent", "pct", "versus", "against", "scored", "scores", "compared",
    "reached", "rate", "rates", "times", "points", "figure", "figures",
    "total", "average", "roughly", "about", "around", "approximately",
}
_STRUCTURAL_H2 = {"frequently asked questions", "faq", "faqs", "references",
                  "sources", "further reading"}
_CALENDAR = {
    "monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday",
    "january", "february", "march", "april", "may", "june", "july", "august",
    "september", "october", "november", "december",
}
# N-grams must not cross a punctuation boundary. Without this, "weapons, cyber,
# influence" yields the phrase "weapons cyber", which appears nowhere in the
# text and reads as nonsense when it wins as the primary keyword.
_SEGMENT_RE = re.compile(r"[.,;:!?()\[\]{}\"\u201c\u201d\u2018\u2019\u2026/|]+|\s[-\u2013\u2014]\s|\n+")
_WORD_RE = re.compile(r"[a-z0-9][a-z0-9'\-]*")
# No dot inside the pattern: allowing one made "DSP. Qualcomm" match as a single
# entity across a sentence boundary. Entities are extracted per sentence too.
_ENTITY_RE = re.compile(r"\b([A-Z][a-zA-Z0-9&'-]+(?:\s+[A-Z][a-zA-Z0-9&'-]+){0,3})\b")


# --------------------------------------------------------------------------- #
# seo_keywords
# --------------------------------------------------------------------------- #

def _ngrams(words: list[str], n: int) -> list[str]:
    return [" ".join(words[i:i + n]) for i in range(len(words) - n + 1)]


def _usable(phrase: str) -> bool:
    """A keyword phrase is a run of content words.

    Checking only the first and last word let "anthropic published threat"
    through, with the verb buried in the middle. A phrase containing a stopword
    anywhere is two phrases with filler between them, not one keyword.
    """
    parts = phrase.split()
    if any(p in _STOP for p in parts):
        return False
    # A phrase of nothing but very short tokens is noise, but "mecka ai" is not.
    if all(len(p) < 3 for p in parts):
        return False
    return not any(p.isdigit() for p in parts)


def _score_phrases(body: str, title: str) -> Counter:
    """Score candidate phrases found in the SOURCE BODY.

    The headline boosts a phrase but can no longer invent one: a phrase that
    appears only in the headline and never in the reporting is not what the
    story is about, it is just how one sub-editor worded it.
    """
    segments = [[w for w in _WORD_RE.findall(seg.lower()) if len(w) > 1]
                for seg in _SEGMENT_RE.split(body)]
    segments = [seg for seg in segments if seg]
    title_words = set(_WORD_RE.findall(title.lower()))
    scores: Counter = Counter()
    for n, weight in ((1, 1.0), (2, 2.4), (3, 2.8)):
        counts: Counter = Counter()
        for seg in segments:
            counts.update(p for p in _ngrams(seg, n) if _usable(p))
        for phrase, count in counts.items():
            # A single mention of one word is noise; phrases earn their place.
            if n == 1 and count < 2:
                continue
            bonus = 2.5 if set(phrase.split()) <= title_words else 1.0
            scores[phrase] += weight * bonus * count
    return scores


def _dedupe_phrases(ranked: list[str], limit: int) -> list[str]:
    """Drop phrases wholly contained in a higher-ranked one."""
    kept: list[str] = []
    for phrase in ranked:
        if any(phrase in k or k in phrase for k in kept):
            continue
        kept.append(phrase)
        if len(kept) >= limit:
            break
    return kept


def seo_keywords(
    title: str,
    texts: list[str] | None = None,
    include_suggestions: bool = True,
    cfg: Config | None = None,
) -> dict:
    cfg = cfg or CONFIG
    title = normalize(title)
    body = "\n".join(normalize(t) for t in (texts or []) if t)
    scores = _score_phrases(body or title, title)
    ranked = [phrase for phrase, _ in scores.most_common(300)]
    multiword = [p for p in ranked if " " in p]

    title_tokens = tokens(title)
    # Prefer a multi-word phrase, but only one that is actually carrying the
    # article. Taking any multi-word phrase over a much stronger single word
    # picked "different claude instances" on a piece whose subject was Claude.
    top_score = scores[ranked[0]] if ranked else 0.0
    primary = ranked[0] if ranked else title.lower()
    for phrase in multiword:
        if set(phrase.split()) & title_tokens and scores[phrase] >= top_score * 0.45:
            primary = phrase
            break
    secondary = _dedupe_phrases([p for p in ranked if p != primary], 10)

    entities = Counter()
    for sentence in (sentences(body) or [title]):
        # Skip the first word of each sentence: it is capitalised by grammar, not
        # because it names anything.
        for match in _ENTITY_RE.findall(" " + sentence.split(" ", 1)[-1]):
            cleaned = match.strip(" .,;:'\"")
            if len(cleaned) > 3 and cleaned.lower() not in _STOP | _CALENDAR:
                entities[cleaned] += 1
    # Sentence openers are already skipped above, so a single mention is real
    # evidence now. Filtering on count here was dropping every proper noun that
    # appeared once - which is most of them in a short news piece.

    long_tail, questions, suggest_errors = ([], [], [])
    if include_suggestions:
        long_tail, questions, suggest_errors = expand(primary, cfg)

    meta_title = title if len(title) <= 60 else title[:57].rsplit(" ", 1)[0] + "..."
    first_sentence = re.split(r"(?<=[.!?])\s", body.strip())[0] if body.strip() else title
    meta_description = normalize(first_sentence)
    if primary.lower() not in meta_description.lower():
        meta_description = f"{primary.capitalize()}: {meta_description}"
    if len(meta_description) > 155:
        meta_description = meta_description[:152].rsplit(" ", 1)[0] + "..."

    return {
        "primary_keyword": primary,
        "secondary_keywords": secondary,
        "entities": [name for name, _ in entities.most_common(12)],
        "long_tail_queries": long_tail,
        "faq_query_candidates": questions,
        "suggested_slug": slugify(f"{primary} {title}" if primary not in title.lower() else title),
        "suggested_meta_title": meta_title,
        "suggested_meta_description": meta_description,
        "suggestion_errors": suggest_errors,
        "usage_note": (
            "Keywords are mined from the source text you fetched, so they reflect the "
            "reporting rather than a guess. faq_query_candidates come from real "
            "autocomplete data - prefer those for FAQ questions, but only keep the ones "
            "your facts can actually answer. There is no search-volume data here; that "
            "needs a paid keyword API."
        ),
    }


# --------------------------------------------------------------------------- #
# seo_audit
# --------------------------------------------------------------------------- #

class _Doc(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.text_parts: list[str] = []
        self.headings: list[tuple[str, str]] = []
        self.images: list[dict] = []
        self.links: list[dict] = []
        self._tag: str | None = None
        self._buf: list[str] = []

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if tag in ("h1", "h2", "h3"):
            self._tag, self._buf = tag, []
        elif tag == "img":
            self.images.append({"src": a.get("src", ""), "alt": a.get("alt", ""),
                                "title": a.get("title", "")})
        elif tag == "a":
            self.links.append({"href": a.get("href", ""), "rel": a.get("rel", "")})

    def handle_endtag(self, tag):
        if tag == self._tag:
            self.headings.append((tag, normalize("".join(self._buf))))
            self._tag = None

    def handle_data(self, data):
        self.text_parts.append(data)
        if self._tag:
            self._buf.append(data)

    @property
    def text(self) -> str:
        return normalize(" ".join(self.text_parts))


def _phrase_pattern(phrase: str) -> str:
    """Match a phrase tolerantly of a trailing plural on its last word.

    "data centres" as the target keyword and "data centre plan" in the headline
    are the same keyword to a search engine, and failing the H1 check over one
    letter sends the writer to fix something that was never wrong.
    """
    words = phrase.split()
    if not words:
        return r"(?!x)x"  # matches nothing
    head = [re.escape(w) for w in words[:-1]]
    last = words[-1]
    base = last[:-1] if len(last) > 3 and last.endswith("s") else last
    return r"\b" + r"\s+".join(head + [re.escape(base) + "s?"]) + r"\b"


def _phrase_count(text: str, phrase: str) -> int:
    return len(re.findall(_phrase_pattern(phrase), text, re.I))


def _contains(text: str, phrase: str) -> bool:
    return bool(re.search(_phrase_pattern(phrase), text or "", re.I))


def seo_audit(
    html_body: str,
    primary_keyword: str,
    secondary_keywords: list[str] | None = None,
    meta_title: str = "",
    meta_description: str = "",
    slug: str = "",
    headline: str = "",
    cfg: Config | None = None,
) -> dict:
    secondary_keywords = secondary_keywords or []
    doc = _Doc()
    doc.feed(html_body or "")
    text = doc.text
    words = text.split()
    word_count = len(words)
    primary = normalize(primary_keyword).lower()

    checks: list[dict] = []

    def check(name: str, ok: bool, severity: str, detail: str = "") -> None:
        checks.append({"check": name, "ok": bool(ok), "severity": severity, "detail": detail})

    h1s = [t for tag, t in doc.headings if tag == "h1"]
    # Blogger and most themes render the post title as the page H1 outside the
    # body you paste in. When there is no H1 in the body, audit the headline that
    # the platform will render instead of failing a correctly-built post.
    h1_source = "body"
    if not h1s and headline:
        h1s = [normalize(headline)]
        h1_source = "platform (from the supplied headline)"
    # "Frequently Asked Questions" and "References" are structural headings, not
    # content sections - counting them made a correct 5-section post look like 7.
    h2s = [t for tag, t in doc.headings
           if tag == "h2" and t.strip().lower() not in _STRUCTURAL_H2]
    h3s = [t for tag, t in doc.headings if tag == "h3"]

    check("exactly one H1", len(h1s) == 1, "high",
          f"found {len(h1s)} in {h1_source}")
    check("primary keyword in H1", bool(h1s) and _contains(h1s[0], primary), "high",
          h1s[0] if h1s else "no H1 and no headline supplied")
    intro = " ".join(words[:100])
    check("primary keyword in first 100 words", _contains(intro, primary), "high")
    # Two developed sections read better at 1000-1300 words than six stubs, so
    # the floor is 2. The FAQ and References headings count toward this total.
    check("2-8 H2 sections", 2 <= len(h2s) <= 8, "medium", f"found {len(h2s)}")

    hits = _phrase_count(text, primary) if primary else 0
    density = (hits * len(primary.split()) / word_count * 100) if word_count else 0.0
    check("keyword density between 0.5% and 2.5%", 0.5 <= density <= 2.5, "medium",
          f"{density:.2f}% ({hits} occurrences in {word_count} words)")

    used_secondary = [k for k in secondary_keywords if _phrase_count(text, k)]
    check("at least 3 secondary keywords used", len(used_secondary) >= 3, "medium",
          f"used: {used_secondary[:6]}")
    check("a secondary keyword appears in an H2",
          any(any(_contains(h, k) for k in secondary_keywords) for h in h2s),
          "low")

    # The house target is 1000-1300 words. A 600-word floor at medium severity let
    # a 719-word post score 93/100, which is how a draft 280 words short of the
    # brief reached the user looking finished.
    check("word count at least 1000", word_count >= 1000, "high",
          f"{word_count} words; the house target is 1000-1300")
    check("word count not over 1300", word_count <= 1300, "low",
          f"{word_count} words")

    check("meta title 30-60 characters", 30 <= len(meta_title) <= 60, "high",
          f"{len(meta_title)} chars")
    check("primary keyword in meta title", _contains(meta_title, primary), "high")
    check("meta description 110-155 characters", 110 <= len(meta_description) <= 155,
          "high", f"{len(meta_description)} chars")
    check("primary keyword in meta description", _contains(meta_description, primary),
          "medium")

    if slug:
        check("slug is 3-8 words, hyphenated, no stopwords",
              3 <= len(slug.split("-")) <= 8 and not set(slug.split("-")) & _STOP,
              "medium", slug)
        check("primary keyword words in slug",
              bool(set(primary.split()) & set(slug.split("-"))), "medium", slug)

    check("every image has alt text", all(i["alt"].strip() for i in doc.images), "high",
          f"{len(doc.images)} image(s)")
    check("banner alt text mentions the topic",
          any(set(primary.split()) & set(i["alt"].lower().split()) for i in doc.images),
          "low")

    external = [l for l in doc.links if l["href"].startswith("http")]
    check("at least 2 external source links", len(external) >= 2, "high",
          f"{len(external)} link(s)")
    check("external links carry rel attributes",
          all(l["rel"] for l in external), "low")

    check("FAQ section present", len(h3s) >= 3, "medium", f"{len(h3s)} H3 question(s)")

    weights = {"high": 3, "medium": 2, "low": 1}
    earned = sum(weights[c["severity"]] for c in checks if c["ok"])
    total = sum(weights[c["severity"]] for c in checks)
    failed = [c for c in checks if not c["ok"]]

    return {
        "score": round(earned / total * 100) if total else 0,
        "passed": len(checks) - len(failed),
        "total_checks": len(checks),
        "must_fix": [c for c in failed if c["severity"] == "high"],
        "should_fix": [c for c in failed if c["severity"] == "medium"],
        "nice_to_have": [c for c in failed if c["severity"] == "low"],
        "all_checks": checks,
        "stats": {
            "h1_source": h1_source,
            "word_count": word_count, "h2_count": len(h2s), "h3_count": len(h3s),
            "keyword_hits": hits, "keyword_density_pct": round(density, 2),
            "images": len(doc.images), "external_links": len(external),
        },
        "caveat": (
            "On-page structure only. It says nothing about search volume, competition, "
            "backlinks or whether the topic is worth targeting."
        ),
    }
