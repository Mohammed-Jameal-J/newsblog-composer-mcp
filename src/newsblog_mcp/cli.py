"""A command line front door, so the pipeline works without an MCP client.

Every integration into Claude - extensions, connectors, skills - is gated
behind a paid plan. That leaves anyone on a free account with no way in, and no
packaging trick changes it. But look at what this server actually does:
verification, the two-publisher rule, wire and reshare detection, fact
extraction, keyword mining, both audits, the JSON-LD and the publishing pack
are all ordinary Python. Exactly one step needs a language model, and that is
writing the draft.

Everybody already has a free language model. So the model becomes the user's to
supply, by pasting:

    newsblog brief "<headline>"   ->  brief.md
    (paste brief.md into any chatbot, paste the answer back as draft.md)
    newsblog pack draft.md        ->  the finished package

That is the whole idea. No account, no key, no subscription, and - since the
bundled publisher feeds need no credentials - no API key either for technology,
AI and security stories.

`pack` has to turn prose back into structure, so `brief` asks for a shape it
can read: ## for sections, ### inside an FAQ section, two paragraphs before the
first ##. The parser says what it could not find rather than guessing, because
a silently mis-parsed post is worse than a refusal.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

from .config import CONFIG

EXIT_OK, EXIT_FAIL, EXIT_REFUSED = 0, 1, 2


def _out(text: str = "") -> None:
    print(text, flush=True)


def _write(path: Path, text: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


# --------------------------------------------------------------------------
# setup / doctor
# --------------------------------------------------------------------------

def cmd_setup(args) -> int:
    from .tools.profile import load_profile, save_profile, setup_questions

    existing = load_profile()
    if existing and not args.force:
        _out("Already set up:")
        for key in ("author_name", "company_name", "blog_base_url", "tone_label"):
            if existing.get(key):
                _out(f"  {key:16} {existing[key]}")
        _out("\nRun `newsblog setup --force` to change it.")
        return EXIT_OK

    _out("Four questions. These set the byline, the voice, the schema publisher")
    _out("and the canonical URL for every post.\n")
    answers = {}
    for question in setup_questions():
        key = question.get("key") or question.get("id") or ""
        prompt = question.get("question") or question.get("label") or key
        hint = question.get("placeholder") or question.get("why") or ""
        if hint:
            prompt = f"{prompt}\n  ({hint})"
        value = input(f"{prompt}\n> ").strip()
        if not value and question.get("required"):
            _out("That one is required.")
            return EXIT_FAIL
        answers[key] = value

    saved = save_profile(
        author_name=answers.get("author_name", ""),
        tone=answers.get("tone", "neutral"),
        company_name=answers.get("company_name", ""),
        site_url=answers.get("site_url", ""),
        company_url=answers.get("company_url", ""),
        logo_url=answers.get("logo_url", ""),
    )
    _out("\nSaved. " + json.dumps(saved, indent=2, ensure_ascii=False))
    return EXIT_OK


def cmd_doctor(args) -> int:
    report = CONFIG.capability_report()
    _out("Search providers")
    for name, ok in report["search"].items():
        if isinstance(ok, bool):
            _out(f"  {name:14} {'key present' if ok else '-'}")
    _out(f"  keyless      {', '.join(report['search']['keyless'])}")

    if args.probe:
        from .providers.search import probe_keys
        _out("\nProbing keys with a real request")
        for name, result in probe_keys(CONFIG).items():
            status = result.get("status")
            if status == "absent":
                continue
            _out(f"  {name:14} {status}" + (f"  {result.get('detail','')[:60]}"
                                            if status != "working" else ""))

    if args.feeds:
        from .providers.feeds import feed_health
        health = feed_health(CONFIG)
        _out(f"\nPublisher feeds: {health['feeds_alive']}/{health['feeds_total']} alive, "
             f"{health['articles_available']} articles available")
        for dead in health["feeds_dead"]:
            _out(f"  dead  {dead['publisher']:26} {dead['error'] or 'no entries'}")
    return EXIT_OK


# --------------------------------------------------------------------------
# find / verify
# --------------------------------------------------------------------------

def cmd_find(args) -> int:
    from .tools.stories import find_stories
    result = find_stories(args.topic, days=args.days, cfg=CONFIG)
    ready = result.get("ready_to_write") or []
    if not ready:
        _out(f"Nothing ready to write about '{args.topic}' in the last "
             f"{args.days} day(s).")
        _out("Widen the window with --days, or try a narrower event word "
             "('ransomware attack' beats 'cybersecurity').")
        return EXIT_REFUSED
    _out(f"{len(ready)} story(ies) with two or more publishers and a fetchable "
         f"source:\n")
    for i, story in enumerate(ready, 1):
        _out(f"{i}. {story['headline']}")
        _out(f"   {story['publisher_count']} publishers, "
             f"{story['age_hours']:.0f}h old")
    _out("\nNext:  newsblog brief \"<headline>\"")
    return EXIT_OK


def cmd_verify(args) -> int:
    from .tools.verify import verify_news
    result = verify_news(args.headline, cfg=CONFIG, days=args.days)
    _out(f"legit: {result['is_legit']}   confidence: {result['confidence']}")
    _out(f"publishers: {', '.join(result.get('independent_publishers') or []) or 'none'}")
    if result.get("wire_services_detected"):
        _out(f"wire copy: {', '.join(result['wire_services_detected'])}")
    if result.get("social_reposts_ignored"):
        _out(f"reshares ignored: {result['social_reposts_ignored']}")
    _out(f"\n{result.get('reasoning', '')}")
    return EXIT_OK if result["is_legit"] else EXIT_REFUSED


# --------------------------------------------------------------------------
# brief
# --------------------------------------------------------------------------

_SHAPE = """
---

## How to use this file

Paste everything above into any chatbot - Claude, ChatGPT, Gemini, whichever you
have - and ask it to write the article to the brief. Then save what it gives you
as `draft.md` and run:

    newsblog pack draft.md

### The shape `newsblog pack` can read

Ask for exactly this, or the packer cannot turn the prose back into a post:

    Two paragraphs, no heading, before anything else. These are the intro.

    ## A section heading phrased as a question
    Two to four paragraphs.

    ## Another section heading phrased as a question
    Two to four paragraphs.

    ## Frequently Asked Questions
    ### A question
    The answer in one short paragraph.
    ### Another question
    The answer.

    ## Call to action
    One closing sentence.

Nothing else: no title line, no references section, no commentary. The packer
adds the banner, the byline, the references and both JSON-LD blocks itself.
"""


def cmd_brief(args) -> int:
    from .tools.verify import verify_news
    from .tools.facts import fetch_article_facts
    from .tools.seo import seo_keywords
    from .tools.coach import draft_brief
    from .tools.profile import load_profile
    from .tools.pack import render_pack_markdown  # noqa: F401  (import check)

    if not load_profile():
        _out("Not set up yet. Run `newsblog setup` first.")
        return EXIT_FAIL

    _out(f"Verifying: {args.headline}")
    verified = verify_news(args.headline, cfg=CONFIG, days=args.days)
    if not verified["is_legit"]:
        _out(f"\nREFUSED. {verified.get('reasoning', '')}")
        _out("\nThis is the gate working, not a failure. A story one outlet is "
             "carrying is not corroborated, and this tool does not write from "
             "a single unverified claim.")
        return EXIT_REFUSED
    _out(f"  {verified['confidence']} confidence, "
         f"{len(verified.get('independent_publishers') or [])} publishers")

    urls = verified.get("fetchable_urls") or []
    if not urls:
        _out("\nREFUSED. Verified, but every source is behind a redirect or a "
             "block, so there are no facts to write from.")
        return EXIT_REFUSED

    _out(f"Fetching {len(urls)} source(s)")
    facts = fetch_article_facts(urls[:5], cfg=CONFIG)
    if not facts.get("facts"):
        _out("\nREFUSED. Nothing could be extracted from any source:")
        for row in facts.get("per_url", []):
            if not row.get("ok"):
                _out(f"  {row['url'][:70]}\n    {row.get('error')}")
        return EXIT_REFUSED
    _out(f"  {len(facts['facts'])} facts from "
         f"{facts['summary']['urls_extracted']} source(s)")

    keywords = seo_keywords(args.headline,
                            texts=[f["text"] for f in facts["facts"]], cfg=CONFIG)
    _out(f"  primary keyword: {keywords['primary_keyword']}")

    brief = draft_brief(args.headline, facts=facts["facts"], keywords=keywords,
                        references=verified.get("reference_candidates"),
                        faq_candidates=keywords.get("faq_query_candidates"),
                        cfg=CONFIG)

    lines = [f"# Write this article: {args.headline}", "",
             f"Target length: {brief.get('target_length', '1000-1300 words')}", ""]
    lines += ["## Open with a direct answer", "", brief.get("answer_first", ""), ""]
    lines += ["## Headings", "", brief.get("heading_shape", ""), ""]
    lines += ["## Structure", ""] + [f"- {s}" for s in brief.get("structure", [])] + [""]
    lines += ["## Rules", ""] + [f"- {r}" for r in brief.get("rules", [])] + [""]
    lines += ["## The facts you may use", "",
              "Every reported claim must trace to one of these. If it is not "
              "here, it does not go in the post.", ""]
    for source, items in (brief.get("facts_by_source") or {}).items():
        lines += [f"### {source}", ""] + [f"- {t}" for t in items] + [""]
    if brief.get("faq_candidates"):
        lines += ["## Questions worth answering", ""]
        lines += [f"- {q}" for q in brief["faq_candidates"]] + [""]
    lines += ["## Keywords", "",
              f"- primary: {brief.get('primary_keyword', '')}",
              f"- secondary: {', '.join(brief.get('secondary_keywords') or [])}",
              f"- placement: {brief.get('keyword_placement', '')}", ""]
    lines += [_SHAPE]

    path = _write(Path(args.out), "\n".join(lines))
    state = {"headline": args.headline, "verified": verified,
             "facts": facts["facts"], "keywords": keywords}
    _write(path.with_suffix(".state.json"),
           json.dumps(state, indent=2, ensure_ascii=False))

    _out(f"\nWrote {path}")
    _out(f"      {path.with_suffix('.state.json')}  (keep this, pack reads it)")
    _out("\nPaste the brief into any chatbot, save the answer as draft.md, then:")
    _out("  newsblog pack draft.md")
    return EXIT_OK


# --------------------------------------------------------------------------
# pack
# --------------------------------------------------------------------------

def parse_draft(markdown: str) -> dict:
    """Prose back into structure. Says what is missing instead of guessing."""
    text = markdown.replace("\r\n", "\n").strip()
    text = re.sub(r"^#\s+.*\n", "", text, count=1)  # a title line, if one slipped in

    blocks = re.split(r"\n(?=##\s)", text)
    intro_block, section_blocks = blocks[0], blocks[1:]

    intro = [p.strip() for p in re.split(r"\n\s*\n", intro_block) if p.strip()]

    sections, faq, cta = [], [], ""
    for block in section_blocks:
        head, _, body = block.partition("\n")
        heading = head.lstrip("#").strip()
        low = heading.lower()
        if "frequently asked" in low or low in {"faq", "faqs", "questions"}:
            for pair in re.split(r"\n(?=###\s)", body):
                q_line, _, answer = pair.partition("\n")
                question = q_line.lstrip("#").strip()
                answer = " ".join(a.strip() for a in answer.split("\n") if a.strip())
                if question and answer:
                    faq.append({"question": question, "answer": answer})
            continue
        if "call to action" in low or low in {"cta", "closing"}:
            cta = " ".join(p.strip() for p in body.split("\n") if p.strip())
            continue
        paragraphs = [p.strip().replace("\n", " ")
                      for p in re.split(r"\n\s*\n", body) if p.strip()]
        if paragraphs:
            sections.append({"heading": heading, "paragraphs": paragraphs})

    problems = []
    if len(intro) < 2:
        problems.append(f"found {len(intro)} intro paragraph(s) before the first "
                        f"'##'; exactly two are needed")
    if not 2 <= len(sections) <= 3:
        problems.append(f"found {len(sections)} '##' section(s) outside the FAQ; "
                        f"two or three are needed")
    if not 4 <= len(faq) <= 8:
        problems.append(f"found {len(faq)} FAQ entries under '## Frequently Asked "
                        f"Questions' with '###' questions; four to eight are needed")
    if not cta:
        problems.append("no '## Call to action' section found")

    return {"intro": intro[:2], "sections": sections, "faq": faq, "cta": cta,
            "problems": problems}


def cmd_pack(args) -> int:
    from .tools.seo import seo_audit
    from .tools.score import score_ai_text
    from .tools.schema import build_schema
    from .tools.pack import build_publishing_pack
    from .tools.save import save_and_present

    draft_path = Path(args.draft)
    if not draft_path.exists():
        _out(f"No such file: {draft_path}")
        return EXIT_FAIL
    state_path = Path(args.state) if args.state else draft_path.with_name("brief.state.json")
    if not state_path.exists():
        _out(f"Cannot find {state_path}. That file is written by `newsblog brief` "
             f"and carries the verification and the facts. Point at it with --state.")
        return EXIT_FAIL

    state = json.loads(state_path.read_text(encoding="utf-8"))
    parsed = parse_draft(draft_path.read_text(encoding="utf-8"))
    if parsed["problems"]:
        _out("The draft is not in a shape this can read:\n")
        for problem in parsed["problems"]:
            _out(f"  - {problem}")
        _out("\nThe required shape is at the bottom of brief.md. Ask the chatbot "
             "to redo it to that shape rather than editing by hand.")
        return EXIT_FAIL

    headline = state["headline"]
    keywords = state["keywords"]
    body_text = "\n\n".join(
        parsed["intro"]
        + [p for s in parsed["sections"] for p in s["paragraphs"]]
        + [f"{q['question']} {q['answer']}" for q in parsed["faq"]])

    human = score_ai_text(body_text, cfg=CONFIG)
    _out(f"style score {human.get('style_score', '?')}/100, "
         f"{human.get('ai_word_count', '?')} stock phrase(s)")

    pack = build_publishing_pack(
        headline=headline, slug=keywords.get("suggested_slug", ""),
        description=keywords.get("suggested_meta_description", ""),
        keywords=[keywords["primary_keyword"]] + keywords.get("secondary_keywords", [])[:4],
        entities=keywords.get("entities"), image_style=args.banner,
        image_concepts=args.concept or "", cfg=CONFIG)
    if not pack.get("ready_for_save"):
        _out("\nPick a banner style with --banner. Choices:")
        for option in (pack.get("ask_the_user_about_the_image") or {}).get("options", []):
            _out(f"  {option['value']:22} {option['summary']}")
        return EXIT_FAIL

    built = build_schema(
        article={"headline": headline,
                 "description": keywords.get("suggested_meta_description", "")[:155],
                 "meta_title": keywords.get("suggested_meta_title", headline),
                 "slug": pack["permalink_slug"], "intro": parsed["intro"],
                 "sections": parsed["sections"], "cta": parsed["cta"]},
        faq=parsed["faq"],
        image={"url": pack["suggested_image_url"], "alt": pack["image_alt_text"]},
        references=state["verified"].get("reference_candidates", [])[:3],
        keywords=[keywords["primary_keyword"]], cfg=CONFIG)

    audit = seo_audit(html_body=built["html_body"], headline=headline,
                      primary_keyword=keywords["primary_keyword"],
                      secondary_keywords=keywords.get("secondary_keywords"),
                      meta_title=built["meta"]["title"],
                      meta_description=built["meta"]["description"],
                      slug=built["slug"], cfg=CONFIG)
    _out(f"SEO {audit['score']}/100, AEO {audit.get('aeo', {}).get('score', '?')}/100")
    for item in audit.get("must_fix", []):
        _out(f"  MUST FIX  {item['check']}: {item.get('detail', '')}")

    saved = save_and_present(
        slug=built["slug"], html_body=built["html_body"], title=headline,
        description=built["meta"]["description"],
        canonical_url=built["canonical_url"], image_url=built["meta"]["image"],
        json_ld_article=built["json_ld_article"], json_ld_faq=built["json_ld_faq"],
        pack=pack,
        meta={"verification": state["verified"], "seo": audit, "human_score": human,
              "references": state["verified"].get("reference_candidates", [])[:3]},
        cfg=CONFIG)

    _out("\n" + saved["SHOW_THIS_TO_THE_USER"])
    _out(f"\nFiles: {saved['folder']}")
    _out(f"Paste into Blogger's HTML view: {saved['paste_file']}")
    return EXIT_OK


# --------------------------------------------------------------------------

def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="newsblog",
        description="Turn a news headline into a verified, publication-ready blog "
                    "package. Bring your own chatbot for the writing step.")
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("setup", help="record the byline, voice and blog URL")
    p.add_argument("--force", action="store_true", help="overwrite an existing profile")
    p.set_defaults(func=cmd_setup)

    p = sub.add_parser("doctor", help="what is configured and what is reachable")
    p.add_argument("--probe", action="store_true", help="test each API key for real")
    p.add_argument("--feeds", action="store_true", help="check every bundled feed")
    p.set_defaults(func=cmd_doctor)

    p = sub.add_parser("find", help="find stories worth writing about")
    p.add_argument("topic")
    p.add_argument("--days", type=int, default=2)
    p.set_defaults(func=cmd_find)

    p = sub.add_parser("verify", help="check one headline is real and corroborated")
    p.add_argument("headline")
    p.add_argument("--days", type=int, default=7)
    p.set_defaults(func=cmd_verify)

    p = sub.add_parser("brief", help="verify, fetch, and write the brief to paste")
    p.add_argument("headline")
    p.add_argument("--days", type=int, default=7)
    p.add_argument("--out", default="brief.md")
    p.set_defaults(func=cmd_brief)

    p = sub.add_parser("pack", help="audit a draft and build the publishing package")
    p.add_argument("draft")
    p.add_argument("--state", default="", help="brief.state.json from the brief step")
    p.add_argument("--banner", default="", help="banner style, see the list on error")
    p.add_argument("--concept", default="", help="what the banner should show")
    p.set_defaults(func=cmd_pack)

    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        return args.func(args)
    except KeyboardInterrupt:
        _out("\nStopped.")
        return EXIT_FAIL


if __name__ == "__main__":
    sys.exit(main())
