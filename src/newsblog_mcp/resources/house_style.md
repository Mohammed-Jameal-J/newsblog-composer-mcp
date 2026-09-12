# House style for the drafting step

The calling model writes the article body and FAQ. These are the rules that
step must follow. `build_schema` will reject output that breaks the structural
ones.

## Structure
- Intro: exactly 2 short paragraphs. First one states what happened; second one
  states why it matters, without editorialising.
- Body: 4-6 `<h2>` sections, 1-3 paragraphs each. Headings are statements, not
  questions.
- FAQ: 4-8 question/answer pairs. Every answer must be fully supported by the
  `fetch_article_facts` output. No speculative questions.
- References: an `<ol>` of real fetched URLs only, taken from `verify_news`
  sources. Never write a URL that was not returned by a tool.
- Close with a 2-3 sentence soft CTA tied to the publishing brand.

## Language

- Zero stock AI phrasing. `find_ai_words` must return clean before the post
  ships; it names the exact sentence to rewrite.
- No adjective that a subeditor would cut: if removing the word changes nothing,
  it was decoration.
- Attribute rather than gesture. "The regulator said" beats "experts say".

## Sourcing
- Paraphrase. Direct quotes stay under 15 words, one per source at most, always
  attributed.
- Never invent a statistic, date, name or quote. If it is not in
  `fetch_article_facts`, it does not go in the article.
- Anonymous-sourced reporting stays hedged: "reportedly", "according to people
  familiar with the matter". Do not state it as confirmed.
- If sources disagree, say so in the body rather than picking one silently.

## SEO

Run `seo_keywords` before drafting and write to what it returns.

- The primary keyword goes in the H1, in the first 100 words, in the meta title
  and in the slug. Once each is enough - `seo_audit` fails a draft above 2.5%
  keyword density as readily as one below 0.5%.
- Use at least three secondary keywords in the body, and put one of them in an
  H2. Headings still have to read as statements a human would write; a heading
  stuffed with keywords fails on both counts.
- Draw FAQ questions from `faq_query_candidates` - those come from real
  autocomplete data - but keep only the ones the researched facts can answer.
  A question you cannot answer from `fetch_article_facts` does not go in.
- Body copy of at least 600 words, 4-6 H2 sections.
- The banner alt text describes the image and mentions the topic. It is a
  description for someone who cannot see the image, not a keyword slot.
- Never repeat a keyword at the cost of a sentence reading naturally. The
  humanizer pass and the SEO pass pull against each other; when they conflict,
  the sentence wins and the keyword moves elsewhere.

## Description and headline
- `description` is one sentence, 110-155 characters, factual, no clickbait. It is
  the meta description, so it has to work as a search snippet on its own.
- `meta_title` is 30-60 characters and contains the primary keyword.
- The headline may be tightened from the input title but must not change its
  meaning or add a claim.
