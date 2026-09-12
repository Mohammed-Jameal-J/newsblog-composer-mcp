"""NewsBlog Composer MCP server.

Seven tools, exposed separately so the calling model chains them itself and any
step can be debugged in isolation. The server does the deterministic work -
search, fetch, extract, template, generate, score, write files. The reasoning
(does this corroborate, what should the article say, which FAQ questions) stays
in the calling model, guided by the two resources this server exposes.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any, Literal

try:  # mcp >= 2.0
    from mcp.server.mcpserver import MCPServer as _Server
except ImportError:  # mcp 1.x, where the same class was called FastMCP
    from mcp.server.fastmcp import FastMCP as _Server

from . import __version__
from dataclasses import replace

from .config import CONFIG, Config
from .tools.coach import draft_brief as _draft_brief
from .tools.coach import review_draft as _review_draft
from .tools.facts import fetch_article_facts as _fetch_article_facts
from .tools.humanize import humanize_text as _humanize_text
from .tools.humanize import rules_text
from .tools.image import generate_image as _generate_image
from .tools.pack import build_publishing_pack as _build_publishing_pack
from .tools.profile import (TONES, answer_template, clear_profile, load_profile,
                            require_profile, save_profile, setup_questions,
                            setup_required_response, tone_guidance)
from .tools.save import save_and_present as _save_and_present
from .tools.schema import build_schema as _build_schema
from .tools.seo import seo_audit as _seo_audit
from .tools.seo import seo_keywords as _seo_keywords
from .tools.stories import find_stories as _find_stories
from .tools.score import find_ai_words as _find_ai_words
from .tools.score import score_ai_text as _score_ai_text
from .tools.verify import verify_news as _verify_news

_INSTRUCTIONS = """\
Before using any tool in this server, check whether it is set up: call
`get_profile`. If it returns `configured: false`, ask the user these two
questions, in the chat, and wait for their answers:

  1. What name should appear on the byline?
  2. What voice should the posts be written in? (neutral, witty, upbeat,
     heartfelt, sombre - `get_profile` lists them with descriptions)
  3. What is your company or publication called?
  4. The domain where posts are published.

Ask all of it in ONE interaction, not one question at a time. Render the voice
as clickable options; give the three text fields as a form, or as the
`answer_template` block the refusal returns, for the user to overwrite. Do NOT
offer guessed answers for the name, company or domain: those belong to the
user, and any option you invent will get clicked and published. Never make the
user compose a prose reply to set up.

Then call `set_profile` with the answers. Every content tool refuses to run
until that is done, including when the user opens with a headline - a post
written before the questions are answered carries the wrong byline, an unchosen
voice, and someone else's company and canonical URL.

Once set up, read the `newsblog://house-style` resource before drafting. It
carries the structure rules and the chosen voice."""

mcp = _Server("newsblog-composer", version=__version__,
              instructions=_INSTRUCTIONS)


def _gate() -> dict | None:
    """Pipeline tools call this first. Returns a refusal while unconfigured."""
    _, blocked = require_profile()
    return blocked


def _cfg() -> Config:
    """CONFIG with the setup answers applied over it.

    Identity comes from profile.json, not .env, so a second person installing
    this server publishes under their own byline, company and domain rather than
    inheriting whatever was in the first person's environment file.
    """
    cfg = replace(CONFIG)
    profile = load_profile()
    if not profile:
        return cfg
    cfg.author_name = profile["author_name"]
    cfg.site_name = profile["company_name"]
    cfg.publisher_name = profile["company_name"]
    cfg.publisher_url = profile["company_url"]
    cfg.publisher_logo_url = profile["logo_url"]
    cfg.site_base_url = profile["blog_base_url"]
    cfg.cta_url = profile["company_url"]
    cfg.cta_link_text = profile["company_name"]
    return cfg

_RESOURCES = Path(__file__).resolve().parent / "resources"
# Loaded once at import. These files never change at runtime, and serving them
# from memory keeps resources/read off the filesystem entirely.
_HOUSE_STYLE = (_RESOURCES / "house_style.md").read_text(encoding="utf-8")
_HUMANIZER_RULES = rules_text()


@mcp.resource("newsblog://house-style")
def house_style() -> str:
    """Structure, sourcing and voice rules the drafting step must follow."""
    profile = load_profile()
    if not profile:
        return (_HOUSE_STYLE + "\n\n## Voice\n\nNot chosen yet. Call get_profile, "
                "ask the user the setup questions, then set_profile.\n")
    return (f"{_HOUSE_STYLE}\n\n{tone_guidance(profile['tone'])}\n\n"
            f"Byline: {profile['author_name']}\n")


@mcp.resource("newsblog://humanizer-rules")
def humanizer_rules() -> str:
    """The AI-writing-tell rules used by humanize_text."""
    return _HUMANIZER_RULES


@mcp.tool()
def get_profile() -> dict:
    """Check whether this server has been set up, and with what.

    CALL THIS FIRST, before anything else. If `configured` is false, ask the user
    the returned questions in the chat, wait for their answers, then call
    set_profile. Every content tool refuses to run until then.

    The answers decide the byline, the voice, the schema publisher, where the
    call to action links, and the canonical URL for every post. Nothing here is
    inferred from the environment.
    """
    profile = load_profile()
    if profile:
        return {"configured": True, **profile,
                "note": "Call set_profile again to change any of these."}
    # Reuse the gate's payload verbatim. get_profile is the tool clients are told
    # to call first, so it must not drift from what the refusal says - it had its
    # own stale copy claiming "these two questions" and carrying no template.
    return {"configured": False, **setup_required_response()}


@mcp.tool()
def set_profile(author_name: str, tone: str, company_name: str = "",
                site_url: str = "", company_url: str = "",
                logo_url: str = "") -> dict:
    """Record who is publishing, where, and in what voice. Run once, after asking.

    author_name: the person's real name. Prints as "By <name>" and goes into the
      NewsArticle author field.
    tone: neutral | witty | upbeat | heartfelt | sombre. Shapes how posts are
      written; it never changes a fact, a figure, a quote or a link.
    company_name: the publisher. Becomes the schema publisher and the linked text
      in the closing call to action.
    site_url: the domain where posts are published. Canonical URLs, image paths
      and the call-to-action link are all built from it. A main domain or a
      subdomain both work.
    company_url: only when the blog is on a subdomain and the call to action
      should point at a different company site. Defaults to site_url.
    logo_url: defaults to <company_url>/logo.png.

    Only pass values the user actually typed. Ask the name, company and domain
    as free-text questions - do not offer guessed options, do not take a name
    from the account or folder path, do not pick a tone for them, and do not
    carry over a company or domain from an earlier post or example.
    """
    try:
        saved = save_profile(author_name, tone, company_name, site_url,
                             company_url=company_url, logo_url=logo_url)
    except ValueError as exc:
        return {"error": str(exc), "valid_tones": sorted(TONES),
                "questions": setup_questions()}
    return {
        "configured": True,
        **saved,
        "voice_rules": tone_guidance(saved["tone"]),
        "applies_to": {
            "byline": f"By {saved['author_name']}",
            "canonical_urls": f"{saved['blog_base_url']}/YYYY/MM/<slug>.html",
            "call_to_action_links_to": saved["company_url"],
            "schema_publisher": saved["company_name"],
            "banner_images_go_under": saved["image_base_url"],
        },
        "next_step": ("Setup is done. For a topic start with find_stories; for a "
                      "specific headline start with verify_news."),
    }


@mcp.tool()
def reset_profile() -> dict:
    """Forget the byline and voice, so the setup questions are asked again."""
    return {"cleared": clear_profile(),
            "next_tool": "get_profile, then ask the user the two questions again"}


@mcp.tool()
def capabilities() -> dict:
    """Report which providers are configured and which keyless fallbacks are in use.

    Call this first when something behaves unexpectedly - it shows whether
    verify_news has a real search key, whether humanize_text can rewrite
    server-side, and whether score_ai_text is using a real detector or the local
    heuristic.
    """
    return _cfg().capability_report()


@mcp.tool()
def find_stories(topic: str, days: int = 2, limit: int = 30) -> dict:
    """Step 1 when the input is a TOPIC rather than a specific headline.

    "AI today", "electric vehicles", "Indian fintech" are topics: there is no
    claim to verify yet, you first have to find out what actually happened.
    This searches recent coverage, groups articles reporting the same event into
    stories, and ranks them by independent publisher count and freshness.

    Use `ready_to_write` - those stories already clear the two-publisher bar and
    have fetchable URLs. Check `age_hours` to pick something current. Then pass
    the chosen story's `headline` to verify_news and its `fetchable_urls` to
    fetch_article_facts.

    `days` is the recency window and defaults to 2. Widen it if nothing comes
    back; narrow it to 1 for same-day news only.
    """
    blocked = _gate()
    if blocked:
        return blocked
    return _find_stories(topic, days=days, limit=limit, cfg=_cfg())


@mcp.tool()
def verify_news(title: str, limit: int = 10, days: int | None = None) -> dict:
    """Step 2 - confirm a SPECIFIC headline is real and corroborated. Check that a headline describes a real, corroborated story.

    Searches every configured news provider, keeps only results that actually
    match the headline, and counts how many INDEPENDENT publishers are carrying
    it. Returns is_legit=false unless at least two independent publishers match,
    or a single primary/official source does.

    This verifies a headline; it does not find one. If the user gave you a topic
    ("today's AI news") rather than a headline, call find_stories first. Note
    that an old headline will correctly return old sources - `days` limits how
    far back to look.

    Do not draft anything if is_legit is false. Feed `fetchable_urls` to
    fetch_article_facts, and use `reference_candidates` as the reference list -
    those are real publisher URLs. Some providers return aggregator redirects
    that still name the outlet; they count toward corroboration but are not
    usable as links, and build_schema rejects them.
    """
    blocked = _gate()
    if blocked:
        return blocked
    return _verify_news(title, cfg=_cfg(), limit=limit, days=days)


@mcp.tool()
def fetch_article_facts(urls: list[str], max_facts_per_url: int = 12) -> dict:
    """Step 3. Download the verified sources and extract usable material.

    Returns facts, short attributed quotes (<=15 words) and figures, each tagged
    with the source_url it came from. URLs that fail to fetch or extract are
    reported in per_url with the reason - they are never filled in with guesses.

    Everything you write in the article must trace back to an entry returned
    here. If a claim is not in this output, it does not go in the post.
    """
    blocked = _gate()
    if blocked:
        return blocked
    return _fetch_article_facts(urls, cfg=_cfg(), max_facts_per_url=max_facts_per_url)


@mcp.tool()
def draft_brief(headline: str, facts: list[dict] | None = None,
                keywords: dict | None = None,
                references: list[dict] | None = None,
                faq_candidates: list[str] | None = None) -> dict:
    """Step 5. Hand the writer everything they need, then get out of the way.

    Takes the verified facts and the keywords and returns a brief: the structure
    to follow, the facts grouped by source with the numbers and quotes separated
    out, the keywords and where to place them, FAQ candidates, and a list of the
    things only this writer can add.

    It does not write prose, and it should not be asked to. The person writes the
    sentences; that is the part a byline claims, and it is the part a detector
    catches when a model does it instead.
    """
    blocked = _gate()
    if blocked:
        return blocked
    return _draft_brief(headline, facts=facts, keywords=keywords,
                        references=references, faq_candidates=faq_candidates,
                        cfg=_cfg())


@mcp.tool()
def review_draft(draft: str, facts: list[dict] | None = None) -> dict:
    """Step 6. Read the writer's draft and say where it is weak. Never rewrite it.

    Pass the human-written draft and the facts from fetch_article_facts. Returns
    must_fix / worth_fixing / consider, each note naming the sentence and what to
    do about it, plus what the draft already does well.

    Checks claims against the researched facts and flags figures or quotes
    nothing supports, quotes over 15 words or missing attribution, stock AI
    phrasing, weak openings, hedging stacks, passive density, and flat sentence
    rhythm.

    Returning a rewritten draft defeats the purpose. Give the writer the notes.
    """
    blocked = _gate()
    if blocked:
        return blocked
    return _review_draft(draft, facts=facts, cfg=_cfg())


@mcp.tool()
def humanize_text(text: str, voice_sample: str = "") -> dict:
    """Optional. Rewrite a draft to strip AI writing tells, keeping facts intact.

    Prefer review_draft. This rewrites the text for the writer, which produces
    machine-written prose again; a detector will read it as such, because
    detectors measure how predictable the wording is rather than how many stock
    phrases it contains. Use this only to edit text the writer already wrote, and
    tell them it was used.


    With an LLM key configured, the rewrite happens server-side and comes back in
    rewritten_text. Without one, mode='delegated_to_caller' and you must apply the
    returned `instructions` to `text_to_rewrite` yourself, preserving every fact,
    figure, name, date, quote and URL exactly.

    Optionally pass voice_sample to match a specific writer's rhythm. The sample
    governs style only and never contributes facts.
    """
    blocked = _gate()
    if blocked:
        return blocked
    return _humanize_text(text, voice_sample=voice_sample, cfg=_cfg())


@mcp.tool()
def score_ai_text(text: str) -> dict:
    """Step 7. Score how human the text reads, 0-100 (higher = more human).

    Uses a real detector API if one is configured, otherwise a local heuristic
    that measures structural tells (sentence-length burstiness, stock phrases,
    em dash density, lexical variety). Check is_real_detector before presenting
    the number, and always surface the caveat: no detector score proves
    authorship. Run it before and after humanize_text to show the improvement.
    """
    return _score_ai_text(text, cfg=_cfg())


@mcp.tool()
def find_ai_words(text: str) -> dict:
    """Check a draft for stock AI phrasing and report exactly where it appears.

    Returns `clean` (boolean), a count, and every occurrence with the sentence it
    sits in. Run it after humanize_text and rewrite each flagged sentence,
    keeping every fact, figure, name and link. Repeat until `clean` is true - the
    house standard is zero, not "fewer".

    Cheaper and more precise than score_ai_text for this one job; score_ai_text
    also measures rhythm and gives you the number.
    """
    return _find_ai_words(text)


@mcp.tool()
def build_publishing_pack(headline: str, description: str = "", slug: str = "",
                          keywords: list[str] | None = None,
                          entities: list[str] | None = None,
                          image_concepts: str = "",
                          image_style: str = "editorial",
                          canonical_url: str = "") -> dict:
    """Final step. Everything needed to publish, in one block.

    Returns the title, the Blogger labels line, the custom permalink slug, the
    search description, the image alt text, and `gemini_image_prompt` - a
    paste-ready prompt for Gemini with brand names already stripped, so the
    banner cannot reproduce a real trademark.

    `image_concepts`: describe what the banner should show in plain words (the
    objects and ideas, not the company names). Leave it empty and the headline is
    used. `image_style` is editorial, photographic or abstract.

    Pass the result to save_and_present as `pack` and it is written to
    publish-pack.md alongside the post.
    """
    blocked = _gate()
    if blocked:
        return blocked
    return _build_publishing_pack(
        headline, description=description, slug=slug, keywords=keywords,
        entities=entities, image_concepts=image_concepts, image_style=image_style,
        canonical_url=canonical_url, cfg=_cfg())


@mcp.tool()
def generate_image(prompt: str, style: Literal["banner", "square"] = "banner",
                   slug: str = "") -> dict:
    """Step 8. Generate a banner image for the article and save it locally.

    Build the prompt from the article's visual concepts, not its brand names. A
    trademark filter runs anyway and rewrites brand terms into generic
    descriptors before the prompt leaves this machine; check terms_removed to see
    what it changed.

    The returned path is local. Upload the file and pass a public https URL to
    build_schema, or NewsArticle.image will point somewhere no crawler can reach.
    """
    blocked = _gate()
    if blocked:
        return blocked
    return _generate_image(prompt, style=style, slug=slug, cfg=_cfg())


@mcp.tool()
def seo_keywords(title: str, texts: list[str] | None = None,
                 include_suggestions: bool = True) -> dict:
    """Step 4. Mine the keywords this post should target, before drafting.

    Pass the headline plus the `text` of the facts returned by
    fetch_article_facts. Keywords come out of the source material you actually
    fetched, so they reflect the reporting rather than a guess.

    Returns primary_keyword, secondary_keywords, entities, and - from real Google
    autocomplete data - long_tail_queries and faq_query_candidates. Draft the FAQ
    from faq_query_candidates wherever your facts can answer them: those are
    questions people actually type. Also returns a suggested slug, meta title and
    meta description to feed into build_schema and seo_audit.

    No search-volume or competition data; that needs a paid keyword API.
    """
    blocked = _gate()
    if blocked:
        return blocked
    return _seo_keywords(title, texts=texts, include_suggestions=include_suggestions,
                         cfg=_cfg())


@mcp.tool()
def seo_audit(html_body: str, primary_keyword: str,
              secondary_keywords: list[str] | None = None, meta_title: str = "",
              meta_description: str = "", slug: str = "",
              headline: str = "") -> dict:
    """Step 10. Score the finished body against on-page SEO rules before publishing.

    Checks H1 uniqueness and keyword placement, keyword density, H2 structure,
    word count, meta title and description lengths, slug shape, image alt text,
    and external source links. Returns a score plus must_fix / should_fix /
    nice_to_have lists.

    Pass `headline` when the body has no H1 because the blog platform renders the
    title itself - the H1 checks then run against that headline instead of
    failing a correctly-built post.

    Fix everything in must_fix and call again. On-page structure only - it says
    nothing about search volume, competition or backlinks.
    """
    return _seo_audit(html_body, primary_keyword,
                      secondary_keywords=secondary_keywords, meta_title=meta_title,
                      meta_description=meta_description, slug=slug,
                      headline=headline, cfg=_cfg())


@mcp.tool()
def build_schema(article: dict, faq: list[dict], image: dict,
                 references: list[dict], keywords: list[str] | None = None) -> dict:
    """Step 9. Render the HTML body and both JSON-LD blocks, then check them.

    article: {headline, description (110-160 chars, used as the meta
      description), intro:[str,str] (exactly two), sections:[{heading,
      paragraphs:[str], bullets?:[str]}] (4-6), cta (one closing sentence that
      must contain CTA_LINK_TEXT verbatim so it renders as a link),
      date_published?, author?, slug?, url?, meta_title?, section?, language?,
      include_h1?}
    faq: [{question, answer}] - 4 to 8 entries
    image: {url, alt, title?, caption?} - url must be the public https URL
    references: [{title, url, publisher?}] - real fetched URLs only
    keywords: the primary and secondary keywords from seo_keywords; they go into
      NewsArticle.keywords and come back in `meta` for save_and_present

    Pure templating, no model call. Renders the house body format: 720px
    container, inline styles, banner, byline, hr-separated H2 sections, FAQ as
    H3/P pairs, references as an ordered list. By default the body carries NO H1
    because Blogger renders the post title itself - set BODY_INCLUDES_H1=true if
    your platform does not.

    Returns `paste_block`, which is both JSON-LD scripts followed by the body,
    ready to paste into the post editor, and `meta` - pass that straight to
    save_and_present so the head, the schema and the body cannot drift apart. Returns validation.issues listing every
    mismatch found: FAQ questions that differ between the HTML and the FAQPage
    schema, an image URL that differs between the <img> tag and NewsArticle.image,
    references missing from the body. Fix the issues and call again rather than
    publishing output with a non-empty issues list.
    """
    profile, blocked = require_profile()
    if blocked:
        return blocked
    # The byline is the profile's unless the caller deliberately overrode it.
    article = {**article, "author": article.get("author") or profile["author_name"]}
    result = _build_schema(article, faq, image, references, keywords=keywords,
                           cfg=_cfg())
    result["meta"]["author"] = article["author"]
    result["meta"]["tone"] = profile["tone"]
    result["meta"]["tone_label"] = profile["tone_label"]
    return result


@mcp.tool()
def save_and_present(slug: str, html_body: str, json_ld_article: str = "",
                     json_ld_faq: str = "", image_path: str = "",
                     title: str = "", description: str = "",
                     canonical_url: str = "", image_url: str = "",
                     language: str = "", meta: dict[str, Any] | None = None,
                     pack: dict[str, Any] | None = None) -> dict:
    """Step 11. Write the finished package to disk and return the paths.

    Produces a timestamped folder containing paste-into-blogger.html (both
    JSON-LD blocks plus the styled body - the file to paste into the post
    editor), index.html (a standalone preview page with meta, canonical, Open
    Graph and Twitter tags in the head), body.html, newsarticle.jsonld,
    faqpage.jsonld, a copy of the image, meta.json, report.md, and - when `pack`
    from build_publishing_pack is supplied - publish-pack.md with the title,
    labels, permalink and Gemini image prompt.

    report.md is the human-readable summary: verification verdict and
    publishers, human score before and after humanising, SEO score with any
    must-fix items, and the reference list. Populate `meta` with keys
    `verification`, `human_score` ({before, after, detector_used,
    is_real_detector}), `seo` and `references` and they all appear in it.

    Pass the `meta` dict that build_schema returned - canonical_url, image_url and
    the rest are read from it when not given explicitly. Put the verification
    result, both human scores, the SEO audit and the reference list in meta so the
    post stays auditable later.
    """
    blocked = _gate()
    if blocked:
        return blocked
    return _save_and_present(
        slug=slug, html_body=html_body, json_ld_article=json_ld_article,
        json_ld_faq=json_ld_faq, image_path=image_path, meta=meta,
        title=title, description=description, canonical_url=canonical_url,
        image_url=image_url, language=language, pack=pack, cfg=_cfg(),
    )


def main() -> None:
    """stdio by default; --http for ChatGPT and other remote clients.

    ChatGPT cannot spawn a local process, so a stdio-only server can never reach
    it. Running with --http exposes a streamable HTTP endpoint that can be
    deployed behind HTTPS and added as a custom connector.

        newsblog-mcp              # Claude Desktop, Claude Code, any stdio client
        newsblog-mcp --http       # serve on 0.0.0.0:8000 for a remote client
    """
    import argparse

    parser = argparse.ArgumentParser(prog="newsblog-mcp")
    parser.add_argument("--http", action="store_true",
                        help="serve over streamable HTTP instead of stdio")
    parser.add_argument("--host", default="0.0.0.0")
    parser.add_argument("--port", type=int, default=8000)
    args = parser.parse_args()

    if args.http:
        # mcp 2.x takes host/port as run() kwargs, not on Settings.
        mcp.run(transport="streamable-http", host=args.host, port=args.port)
    else:
        mcp.run()


if __name__ == "__main__":
    main()
