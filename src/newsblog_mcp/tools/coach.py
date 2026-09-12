"""Tools for writers: draft_brief and review_draft.

These two exist because the pipeline's weakest link was that a model wrote the
prose. Detectors correctly flag that text as machine-written, and no amount of
cliche-removal changes it, because detectors measure how predictable the wording
is rather than how many stock phrases it contains.

So the split is: the server does research, verification, structure, keywords and
auditing. The person writes the sentences. `draft_brief` hands them everything
they need to start; `review_draft` reads what they wrote and tells them where it
is weak, without rewriting a word of it.

Nothing here generates prose. That is deliberate.
"""
from __future__ import annotations

import re
from collections import Counter

from ..config import CONFIG, Config
from ..textutil import normalize, sentences, tokens

# Openings that make a reader stop reading.
_WEAK_OPENERS = ("in this article", "this article", "this post", "today we",
                 "we will look", "let us", "let's look", "in this blog")
_HEDGE = ("perhaps", "arguably", "somewhat", "fairly", "rather", "quite",
          "relatively", "possibly", "maybe", "seems to", "appears to",
          "it could be argued", "some would say")
_PASSIVE = re.compile(
    r"\b(?:was|were|is|are|been|being|be)\s+\w+(?:ed|en)\b(?:\s+by\b)?", re.I)
_NUMBER = re.compile(r"\d")
_QUOTE = re.compile(r"[\"“]([^\"”]{10,})[\"”]")


# --------------------------------------------------------------------------- #
# draft_brief
# --------------------------------------------------------------------------- #

def draft_brief(
    headline: str,
    facts: list[dict] | None = None,
    keywords: dict | None = None,
    references: list[dict] | None = None,
    faq_candidates: list[str] | None = None,
    cfg: Config | None = None,
) -> dict:
    """Everything a writer needs in front of them before they start typing."""
    cfg = cfg or CONFIG
    facts = facts or []
    keywords = keywords or {}
    references = references or []

    by_source: dict[str, list[str]] = {}
    for fact in facts:
        by_source.setdefault(fact.get("publisher") or fact.get("source_url", "?"),
                             []).append(fact.get("text", ""))

    numeric = [f.get("text", "") for f in facts if _NUMBER.search(f.get("text", ""))]
    quoted = [f.get("text", "") for f in facts if _QUOTE.search(f.get("text", ""))]

    return {
        "headline": normalize(headline),
        "target_length": "600 to 900 words",
        "structure": [
            "Two short intro paragraphs. First says what happened. Second says why "
            "it matters, without editorialising.",
            "Four to six sections with statement headings, one to three paragraphs "
            "each.",
            "Four to eight FAQ questions, each answerable from the facts below.",
            "A closing call to action of two or three sentences.",
            "References as a numbered list of the real URLs below.",
        ],
        "facts_by_source": by_source,
        "facts_with_numbers": numeric,
        "facts_with_quotes": quoted,
        "references": references,
        "primary_keyword": keywords.get("primary_keyword", ""),
        "secondary_keywords": keywords.get("secondary_keywords", [])[:5],
        "keyword_placement": (
            "Primary keyword in the headline, the first 100 words and the meta "
            "title. Once each is enough. Three or more secondary keywords "
            "somewhere in the body, one of them in a section heading."),
        "faq_candidates": faq_candidates or keywords.get("faq_query_candidates", []),
        "what_only_you_can_add": [
            "What you would tell a client about this if they asked in a meeting.",
            "A comparable case you have seen, and how it turned out.",
            "The part of this story the coverage is getting wrong or skating over.",
            "What you would do differently if this were your company.",
            "A number from your own work that puts this one in proportion.",
        ],
        "rules": [
            "Every claim traces to a fact below. If it is not there, do not write it.",
            "Quotes stay under 15 words and keep their attribution.",
            "Anonymously sourced claims stay hedged: reportedly, according to.",
            "Write the sentences yourself. A model writing them is what a detector "
            "catches, and it is the part a byline actually claims.",
        ],
        "next_step": ("Write the draft, then run review_draft on it. It will tell you "
                      "what is weak without rewriting anything."),
    }


# --------------------------------------------------------------------------- #
# review_draft
# --------------------------------------------------------------------------- #

def _supported(sentence: str, fact_text: str) -> bool:
    """Does this fact plausibly back this sentence?"""
    s_tokens, f_tokens = tokens(sentence), tokens(fact_text)
    if not s_tokens:
        return False
    overlap = len(s_tokens & f_tokens) / len(s_tokens)
    s_nums = set(re.findall(r"\d[\d,.]*", sentence))
    f_nums = set(re.findall(r"\d[\d,.]*", fact_text))
    if s_nums and s_nums & f_nums:
        return True
    return overlap >= 0.4


def review_draft(
    draft: str,
    facts: list[dict] | None = None,
    cfg: Config | None = None,
) -> dict:
    """Read a human's draft and say where it is weak. Never rewrites it."""
    from .score import find_ai_words  # local import keeps the module standalone

    cfg = cfg or CONFIG
    facts = facts or []
    draft = draft or ""
    sents = sentences(draft)
    words = draft.split()
    fact_texts = [f.get("text", "") for f in facts]

    notes: list[dict] = []

    def note(kind: str, severity: str, message: str, where: str = "") -> None:
        notes.append({"type": kind, "severity": severity, "note": message,
                      "sentence": where[:180]})

    # 1. Claims the supplied facts do not support.
    if fact_texts:
        for sentence in sents:
            if not _NUMBER.search(sentence) and not _QUOTE.search(sentence):
                continue
            if not any(_supported(sentence, f) for f in fact_texts):
                note("unsupported", "high",
                     "This carries a figure or a quote that none of the researched "
                     "facts back up. Check it, or cut it.", sentence)

    # 2. Quotes that ran long or lost their attribution.
    for match in _QUOTE.finditer(draft):
        quote = match.group(1)
        if len(quote.split()) > 15:
            note("long_quote", "medium",
                 f"Quote runs to {len(quote.split())} words. House limit is 15. "
                 f"Paraphrase the middle and keep the sharp part.", quote)
        window = draft[max(0, match.start() - 120): match.end() + 120]
        if not re.search(r"\b(said|says|told|according to|wrote|added)\b", window, re.I):
            note("unattributed_quote", "high",
                 "This quote has no attribution nearby. Name who said it.", quote)

    # 3. Stock AI phrasing and em dashes.
    ai = find_ai_words(draft)
    for hit in ai["occurrences"]:
        note("stock_phrase", "medium",
             f"{hit['phrase']!r}: {hit['fix']}", hit["in_sentence"])

    # 4. Openings that waste the reader's first sentence.
    opening = " ".join(words[:25]).lower()
    for weak in _WEAK_OPENERS:
        if weak in opening:
            note("weak_opening", "high",
                 f"The draft opens with {weak!r}. Open on the thing that happened "
                 f"instead; the reader already knows they are reading an article.",
                 " ".join(words[:25]))
            break

    # 5. Hedging stacks.
    hedges = [h for h in _HEDGE if h in draft.lower()]
    if len(hedges) >= 3:
        note("hedging", "medium",
             f"{len(hedges)} soft qualifiers ({', '.join(hedges[:5])}). Each one "
             f"asks the reader to discount the sentence. Keep the ones where the "
             f"sourcing is genuinely thin and cut the rest.")

    # 6. Passive constructions, reported not condemned.
    passive_hits = _PASSIVE.findall(draft)
    passive_rate = len(passive_hits) / max(len(sents), 1)
    if passive_rate > 0.35:
        note("passive", "low",
             f"About {passive_rate:.0%} of sentences use a passive construction. "
             f"Some are right for reporting; check whether each one is hiding who "
             f"did the thing.")

    # 7. Rhythm. Uniform sentence length is the loudest tell in either direction.
    lengths = [len(s.split()) for s in sents if s.split()]
    if len(lengths) > 4:
        mean = sum(lengths) / len(lengths)
        spread = (sum((n - mean) ** 2 for n in lengths) / len(lengths)) ** 0.5
        if mean and spread / mean < 0.35:
            note("rhythm", "medium",
                 f"Sentence length barely varies (average {mean:.0f} words, spread "
                 f"{spread:.0f}). Break one long sentence in each section, and let "
                 f"one run short.")
        longest = max(lengths)
        if longest > 45:
            worst = max(sents, key=lambda s: len(s.split()))
            note("long_sentence", "low",
                 f"One sentence runs to {longest} words. Split it.", worst)

    # 8. Concrete detail, which is what separates a draft worth reading.
    with_numbers = sum(1 for s in sents if _NUMBER.search(s))
    named = len(set(re.findall(r"\b[A-Z][a-z]{2,}(?:\s+[A-Z][a-z]{2,})?\b", draft)))

    strengths: list[str] = []
    if with_numbers >= max(3, len(sents) // 6):
        strengths.append(f"{with_numbers} sentences carry a concrete figure. That is "
                         f"what makes a piece feel reported rather than summarised.")
    if named >= 6:
        strengths.append(f"{named} distinct named entities. Specific beats general.")
    if ai["clean"]:
        strengths.append("No stock AI phrasing and no em dashes.")
    if lengths and len(lengths) > 4:
        mean = sum(lengths) / len(lengths)
        spread = (sum((n - mean) ** 2 for n in lengths) / len(lengths)) ** 0.5
        if mean and spread / mean >= 0.5:
            strengths.append("Sentence rhythm varies well.")

    by_severity = Counter(n["severity"] for n in notes)
    return {
        "word_count": len(words),
        "sentence_count": len(sents),
        "must_fix": [n for n in notes if n["severity"] == "high"],
        "worth_fixing": [n for n in notes if n["severity"] == "medium"],
        "consider": [n for n in notes if n["severity"] == "low"],
        "strengths": strengths,
        "counts": dict(by_severity),
        "verdict": (
            "Nothing blocking. Read it once more for rhythm and ship it."
            if not by_severity.get("high") else
            f"{by_severity['high']} thing(s) to fix before this goes out, starting "
            f"with anything marked unsupported."),
        "note": ("This is feedback on your writing, not a rewrite. Nothing here was "
                 "generated for you, and nothing in your draft was changed."),
    }
