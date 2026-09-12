"""Tool 4 - score_ai_text.

Uses a real detector API when a key is present. Otherwise falls back to a local
heuristic that measures the structural tells the rewrite rules target. The
fallback is clearly labelled: it is a writing-quality proxy, not an AI detector,
and no number from either path should be treated as proof of anything.
"""
from __future__ import annotations

import re
import statistics

from ..config import CONFIG, Config
from ..providers.detector import NoDetectorConfigured, detect
from ..textutil import sentences

CAVEAT = (
    "Treat this as directional only. Public AI detectors have real false-positive "
    "and false-negative rates, especially on short text and on non-native English "
    "phrasing, and no score here proves who or what wrote the text."
)

# Phrases that mark text as machine-written. The list is deliberately long and
# deliberately unforgiving: the brief is "no AI words in the content", so every
# hit is reported with its surrounding sentence rather than just counted.
_AI_PHRASES = [
    # openers and framings
    "in today's fast-paced", "in today's world", "in an era of", "in the ever-evolving",
    "as technology continues to evolve", "in the rapidly changing", "in recent years",
    "it's worth noting", "it is important to note", "it is worth mentioning",
    "needless to say", "at the end of the day", "when it comes to",
    "one thing is clear", "the reality is that", "let's dive in", "let's delve",
    # verbs and nouns
    "delve into", "delving into", "navigate the landscape", "navigating the complex",
    "harness the power", "unlock the potential", "leverage the power", "usher in",
    "revolutionize", "revolutionise", "spearhead", "underscore the importance",
    "underscores the importance", "serves as a testament", "stands as a testament",
    "a testament to", "at the forefront of", "paving the way for", "pave the way",
    "shed light on", "dive deeper", "explore the world of", "embark on a journey",
    "the landscape of", "the realm of", "in the realm of", "plays a vital role",
    "plays a crucial role", "plays a pivotal role", "a key player",
    # adjectives
    "game-changing", "game changer", "cutting-edge", "state-of-the-art", "seamless",
    "seamlessly", "robust", "revolutionary", "unprecedented", "pivotal", "crucial",
    "vital", "significant strides", "remarkable", "transformative", "groundbreaking",
    "innovative solutions", "holistic", "myriad", "plethora", "vast array",
    "ever-growing", "rapidly evolving", "dynamic landscape",
    # closers
    "in conclusion", "to sum up", "in summary", "ultimately", "all in all",
    "the bottom line is", "moving forward", "only time will tell",
    "as we look to the future", "the future looks bright", "exciting times ahead",
    # hedging stacks
    "may potentially", "could potentially", "it is possible that", "arguably one of",
    "some might argue", "experts say", "critics argue", "many believe",
]

_TRANSITION_STARTS = ("moreover", "furthermore", "additionally", "consequently",
                      "however", "nevertheless", "ultimately", "in conclusion")


def _locate(text: str, phrases: list[str], sents: list[str]) -> list[dict]:
    """Report each stock phrase with the sentence it sits in, so a rewrite can
    target the exact wording instead of guessing."""
    found: list[dict] = []
    lowered_sents = [(s, s.lower()) for s in sents]
    for phrase in phrases:
        for original, lowered in lowered_sents:
            if phrase in lowered:
                found.append({
                    "phrase": phrase,
                    "in_sentence": original.strip()[:180],
                    "fix": "Delete it or replace it with the specific fact it is standing in for.",
                })
                break
    return found


def _heuristic(text: str) -> dict:
    words = re.findall(r"[A-Za-z']+", text)
    n_words = max(len(words), 1)
    sents = sentences(text) or [text]
    lengths = [len(s.split()) for s in sents if s.split()]
    paragraphs = [p for p in text.split("\n") if p.strip()]
    para_lengths = [len(p.split()) for p in paragraphs] or [n_words]

    mean_len = statistics.fmean(lengths) if lengths else 0.0
    sd_len = statistics.pstdev(lengths) if len(lengths) > 1 else 0.0
    burstiness = (sd_len / mean_len) if mean_len else 0.0
    ttr = len({w.lower() for w in words}) / n_words
    em_dashes = text.count("—") / n_words * 1000
    lowered = text.lower()
    phrase_hits = [p for p in _AI_PHRASES if p in lowered]
    occurrences = _locate(text, phrase_hits, sents)
    not_just = len(re.findall(r"not (just|only)\b[^.]{0,80}\bbut\b", lowered))
    transition_starts = sum(
        1 for s in sents if s.lower().lstrip("\"'“").startswith(_TRANSITION_STARTS)
    )
    transition_ratio = transition_starts / max(len(sents), 1)
    para_cv = (statistics.pstdev(para_lengths) / statistics.fmean(para_lengths)
               if len(para_lengths) > 1 and statistics.fmean(para_lengths) else 0.0)

    score = 100.0
    flags: list[str] = []

    penalty = min(len(phrase_hits) * 4.0, 35.0)
    if penalty:
        flags.append(f"{len(phrase_hits)} stock AI phrase(s): {', '.join(phrase_hits[:6])}")
    score -= penalty

    if burstiness < 0.35:
        p = (0.35 - burstiness) / 0.35 * 25.0
        score -= p
        flags.append(f"uniform sentence length (burstiness {burstiness:.2f}, want >0.35)")

    if em_dashes > 4:
        p = min((em_dashes - 4) * 2.0, 10.0)
        score -= p
        flags.append(f"em dash overuse ({em_dashes:.1f} per 1000 words)")

    if transition_ratio > 0.08:
        p = min((transition_ratio - 0.08) * 100.0, 12.0)
        score -= p
        flags.append(f"{transition_starts} sentences open with a filler transition")

    if ttr < 0.35:
        p = min((0.35 - ttr) * 60.0, 15.0)
        score -= p
        flags.append(f"low lexical variety (type-token ratio {ttr:.2f})")

    if para_cv < 0.30 and len(para_lengths) > 2:
        score -= 8.0
        flags.append("every paragraph is roughly the same length")

    if not_just:
        p = min(not_just * 5.0, 10.0)
        score -= p
        flags.append(f'{not_just} "not just X but Y" construction(s)')

    return {
        # NOT a human_score. This measures cliche density and sentence rhythm.
        # A real detector measures token predictability, which is a different
        # thing entirely: text can score 95 here and 100% AI at GPTZero, because
        # removing stock phrases does not make an LLM's word choices less
        # predictable. Naming this "human_score" invited exactly that confusion.
        "style_score": round(max(5.0, min(97.0, score)), 1),
        "human_score": None,
        "what_this_measures": (
            "Cliche density, sentence-length variation, lexical variety and em "
            "dash use. It does NOT estimate whether a detector will call this "
            "AI-written. No AI-detection reading was taken because no detector "
            "key is configured."),
        "ai_words_found": occurrences,
        "ai_word_count": len(occurrences),
        "clean_of_ai_words": not occurrences,
        "flagged_patterns": flags,
        "detector_used": "heuristic:local-v1",
        "is_real_detector": False,
        "metrics": {
            "words": n_words, "sentences": len(sents),
            "mean_sentence_words": round(mean_len, 1),
            "burstiness": round(burstiness, 3),
            "type_token_ratio": round(ttr, 3),
            "em_dashes_per_1k": round(em_dashes, 2),
            "paragraph_length_cv": round(para_cv, 3),
        },
        "caveat": CAVEAT + (
            " This particular score came from a LOCAL HEURISTIC, not an AI detector: "
            "it measures the structural tells the humanizer rules target and nothing "
            "more. Set GPTZERO_API_KEY or SAPLING_API_KEY for a real detector."
        ),
    }


def find_ai_words(text: str) -> dict:
    """Banned-phrase and em-dash check, with locations. Cheap enough to run after
    every rewrite pass until it comes back clean.

    Em dashes count as a tell here by house choice. They are legitimate English,
    but a long dash where a comma or a full stop would do is one of the most
    reliable signals a reader uses to spot machine-written prose.
    """
    sents = sentences(text) or [text]
    lowered = (text or "").lower()
    hits = [p for p in _AI_PHRASES if p in lowered]
    occurrences = _locate(text, hits, sents)

    dashes = [
        {"phrase": "— (em dash)", "in_sentence": s.strip()[:180],
         "fix": "Replace with a comma, a full stop, a colon, or a plain hyphen."}
        for s in sents if "—" in s or "&mdash;" in s
    ]
    total = len(occurrences) + len(dashes)
    if not total:
        verdict = "No stock AI phrasing or em dashes detected."
    else:
        parts = []
        if occurrences:
            parts.append(f"{len(occurrences)} stock AI phrase(s)")
        if dashes:
            parts.append(f"{len(dashes)} sentence(s) with an em dash")
        verdict = (f"{' and '.join(parts)} still present. Rewrite each sentence listed "
                   f"below, keeping every fact, then run this again.")
    return {
        "clean": not total,
        "count": total,
        "phrase_count": len(occurrences),
        "em_dash_count": len(dashes),
        "occurrences": occurrences + dashes,
        "verdict": verdict,
    }


def score_ai_text(text: str, cfg: Config | None = None) -> dict:
    cfg = cfg or CONFIG
    if not (text or "").strip():
        return {"error": "empty text", "human_score": None}
    try:
        result = detect(text, cfg)
        words = find_ai_words(text)
        result.update(is_real_detector=True, flagged_patterns=[], caveat=CAVEAT,
                      what_this_measures="A real AI-detection API reading.",
                      ai_words_found=words["occurrences"],
                      ai_word_count=words["count"],
                      clean_of_ai_words=words["clean"])
        return result
    except NoDetectorConfigured:
        return _heuristic(text)
    except Exception as exc:
        fallback = _heuristic(text)
        fallback["detector_error"] = f"{type(exc).__name__}: {exc}"
        fallback["caveat"] = ("The configured detector failed, so this is the local "
                              "heuristic score instead. ") + fallback["caveat"]
        return fallback
