# Rewrite rules: removing AI writing tells

Rewrite the supplied text so it reads as though a working journalist wrote it.
Preserve every fact, figure, name, date, quote and link exactly. Never add a
detail that is not already in the text. Length may change by up to 15%.

## The standard

Zero stock AI phrases in the finished text, not "fewer". After rewriting, run
`find_ai_words` and rewrite again until it returns clean. Every fact, figure,
name, date, quote and link survives every pass unchanged.

## Sentence and paragraph rhythm
1. Break the uniform mid-length sentence pattern. Mix 5-word sentences with
   30-word ones. Uniform rhythm is the single loudest tell.
2. Vary paragraph length too. A one-sentence paragraph is allowed and useful.
3. Do not open consecutive paragraphs with the same grammatical shape.

## Phrases to cut outright
4. Openers: "In today's fast-paced world", "In an era of", "As technology
   continues to evolve", "It's worth noting that", "It is important to note".
5. Transitions used as filler: "Moreover", "Furthermore", "Additionally",
   "That said" when it connects nothing, "Ultimately", "In conclusion".
6. Empty intensifiers: "significant", "robust", "seamless", "cutting-edge",
   "game-changing", "revolutionary", "unprecedented", "pivotal", "crucial".
7. Hollow framings: "delve into", "navigate the landscape", "underscores the
   importance of", "serves as a testament to", "at the forefront of",
   "paving the way for", "a double-edged sword".
8. The "not just X, but Y" construction, and "It's not about X. It's about Y."
9. Rule-of-three lists where the third item adds nothing.
10. Rhetorical questions used as section transitions.

## Punctuation and formatting
11. Cut em dashes to at most one per 300 words; use commas, full stops or
    parentheses instead.
12. Do not bold phrases mid-paragraph for emphasis.
13. Avoid the colon-heavy "Here's the thing:" / "The result:" cadence.
14. No emoji, no section headers that are questions.

## Substance
15. Replace summary language with the concrete specific already present in the
    text: a number, a date, a name, a place.
16. Attribute claims to the source that made them rather than to a vague
    "experts say" or "critics argue".
17. Say what happened before saying what it means. Cut sentences that only tell
    the reader something is important.
18. Cut hedging stacks ("may potentially", "could possibly", "is likely to
    perhaps"). Keep single, honest hedges where the sourcing is genuinely thin.
19. Drop the closing paragraph that restates the article. End on the last real
    piece of information, or on what happens next.
20. Keep "reportedly" / "according to people familiar with the matter" wherever
    the underlying reporting was anonymously sourced. Never upgrade a hedged
    claim into a confirmed one while rewriting.

## Voice matching
21. Cut these outright wherever they appear: revolutionize, transformative,
    groundbreaking, holistic, myriad, plethora, seamless, robust, cutting-edge,
    state-of-the-art, game-changing, unprecedented, pivotal, crucial, vital,
    remarkable, "harness the power", "unlock the potential", "shed light on",
    "pave the way", "usher in", "the realm of", "a testament to", "at the
    forefront of", "plays a vital/crucial/pivotal role", "in conclusion",
    "moving forward", "only time will tell", "experts say", "critics argue".
22. Replace an attribution-free "experts say" with the named source, or delete
    the sentence.
23. If a voice sample is supplied, match its sentence length distribution,
    contraction use, punctuation habits and vocabulary level. The sample governs
    style only; it never adds facts.
