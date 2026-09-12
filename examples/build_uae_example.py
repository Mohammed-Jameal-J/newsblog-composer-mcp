"""Full pipeline on the user's headline, 12 September 2026.

    "UAE revises AI data center plan after Iranian attacks, sources say"

Facts come from Reuters' exclusive, read via The Express Tribune's wire copy.
The reporting rests on six anonymous sources, so every claim traceable only to
them stays hedged in the copy, per the house style.

Identity (byline, company, URLs) comes from profile.json, set at setup.
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from newsblog_mcp.config import Config                              # noqa: E402
from newsblog_mcp.tools.pack import build_publishing_pack           # noqa: E402
from newsblog_mcp.tools.profile import load_profile                 # noqa: E402
from newsblog_mcp.tools.save import save_and_present                # noqa: E402
from newsblog_mcp.tools.schema import build_schema                  # noqa: E402
from newsblog_mcp.tools.score import find_ai_words, score_ai_text   # noqa: E402
from newsblog_mcp.tools.seo import seo_audit, seo_keywords          # noqa: E402

PROFILE = load_profile()
if PROFILE is None:
    raise SystemExit("Run set_profile first.")

cfg = Config()
cfg.author_name = PROFILE["author_name"]
cfg.site_name = PROFILE["company_name"]
cfg.publisher_name = PROFILE["company_name"]
cfg.publisher_url = PROFILE["company_url"]
cfg.publisher_logo_url = PROFILE["logo_url"]
cfg.site_base_url = PROFILE["blog_base_url"]
cfg.cta_url = PROFILE["company_url"]
cfg.cta_link_text = PROFILE["company_name"]
cfg.output_dir = ROOT / "output"

COMPANY = PROFILE["company_name"]
HEADLINE = "UAE Revises Its AI Data Centre Plan After Iranian Attacks, Sources Say"

FACTS = [
    "The UAE has moved from a single 10-square-mile AI campus in Abu Dhabi to a "
    "network of dispersed data centres across the country, according to Reuters "
    "sources.",
    "The revised design reportedly adds underground facilities, air defences, "
    "blast-resistant concrete and backup power and cooling.",
    "Some sensitive military data centres are reportedly to be built inside mountains "
    "in the northern emirates of Ras Al Khaimah and Fujairah.",
    "Two AWS data centres in the UAE were damaged in March and one in Bahrain was hit.",
    "In April, Iran's armed forces released a video warning that Stargate UAE was also "
    "a potential target.",
    "The location of a site near Al Dhafra Air Base, previously undisclosed, was "
    "leaked.",
    "The war began in February 2026.",
    "The full project is 5 gigawatts. Its first phase, Stargate UAE, is 1 gigawatt and "
    "about $30 billion.",
    "The first 200 megawatts are due online in 2026.",
    "G42, led by Sheikh Tahnoun bin Zayed al Nahyan, is the UAE partner, alongside "
    "OpenAI, Oracle, Nvidia, SoftBank and Cisco.",
    "G42 said the work is progressing as planned and is subject to continuous review in "
    "line with security standards.",
    "Reuters based the report on six anonymous sources, including one US official, one "
    "Western diplomat and industry executives.",
]

ARTICLE = {
    "headline": HEADLINE,
    "description": ("The UAE has reportedly replaced its single Abu Dhabi AI campus with "
                    "dispersed, hardened data centres after Iranian strikes damaged "
                    "regional sites."),
    "slug": "uae-ai-data-centre-plan-revised",
    "date_published": "2026-09-12T09:00:00-05:00",
    "section": "Artificial Intelligence",
    "intro": [
        "The UAE has revised the design of its flagship AI data centre programme, "
        "according to a Reuters report citing six sources. The original plan centred on "
        "a single 10-square-mile campus in Abu Dhabi. The revised plan reportedly "
        "spreads capacity across a network of sites.",
        "The change follows Iranian attacks on data centre infrastructure in the region. "
        "Two AWS facilities in the UAE were damaged in March, and one in Bahrain was "
        "hit. The war began in February 2026.",
    ],
    "sections": [
        {"heading": "What the plan reportedly changed to", "paragraphs": [
            "Instead of one campus, the programme is now said to run across dispersed "
            "sites nationwide. Sources describe underground facilities, air "
            "defences, blast-resistant concrete, and backup power and cooling systems.",
            "Some sensitive military data centres are reportedly to be built inside "
            "mountains in Ras Al Khaimah and Fujairah, in the northern emirates. None of "
            "this has been confirmed on the record by the UAE government."]},
        {"heading": "What prompted it", "paragraphs": [
            "Two AWS data centres in the UAE were damaged in March, and a third site in "
            "Bahrain was hit. In April, Iran's armed forces released a video warning "
            "that Stargate UAE was also a potential target.",
            "The location of a site near Al Dhafra Air Base, previously undisclosed, was "
            "leaked. For a programme whose security model assumed obscurity, that "
            "disclosure changes the threat picture on its own."]},
        {"heading": "The scale involved", "paragraphs": [
            "The full programme is 5 gigawatts. Its first phase, Stargate UAE, is 1 "
            "gigawatt and roughly $30 billion. The first 200 megawatts are due online "
            "during 2026.",
            "G42, led by Sheikh Tahnoun bin Zayed al Nahyan, is the UAE partner. OpenAI, "
            "Oracle, Nvidia, SoftBank and Cisco are named participants."]},
        {"heading": "What the parties say", "paragraphs": [
            "G42 said the work is progressing as planned and is subject to continuous "
            "review in line with security standards. That statement neither confirms nor "
            "denies the design change described by the sources.",
            "Reuters attributes the account to six people: a US official, a Western "
            "diplomat and industry executives, none named. Treat the specifics as "
            "reported rather than established."]},
        {"heading": "Why it matters beyond the Gulf", "paragraphs": [
            "Large AI buildouts have been designed around power, cooling and network "
            "cost. This is the first major programme reported to be redesigned around "
            "physical attack."],
         "bullets": [
             "Concentration is efficient and it is also a single target. Any operator "
             "planning gigawatt-scale capacity in a contested region now has a worked "
             "example of the trade.",
             "Site secrecy is a control that fails permanently once broken. The Al "
             "Dhafra leak cannot be undone by hardening.",
             "Hardened construction, air defence and redundant power change the cost "
             "per megawatt. Published figures for projects in stable regions will not "
             "transfer."]},
    ],
    "cta": (f"If you are assessing where your own infrastructure sits and what it would "
            f"take to move it, {COMPANY} can help you work through the options."),
}

FAQ = [
    {"question": "What has the UAE reportedly changed?",
     "answer": "The programme has moved from a single 10-square-mile campus in Abu Dhabi "
               "to a network of dispersed data centres across the country, according to "
               "Reuters sources."},
    {"question": "What security measures are described?",
     "answer": "Underground facilities, air defences, blast-resistant concrete, and "
               "backup power and cooling. Some sensitive military data centres are "
               "reportedly to be built inside mountains in Ras Al Khaimah and Fujairah."},
    {"question": "What attacks prompted the revision?",
     "answer": "Two AWS data centres in the UAE were damaged in March and one in Bahrain "
               "was hit. In April, Iran's armed forces released a video warning that "
               "Stargate UAE was also a potential target."},
    {"question": "How big is the project?",
     "answer": "The full programme is 5 gigawatts. The first phase, Stargate UAE, is 1 "
               "gigawatt and about $30 billion, with the first 200 megawatts due online "
               "in 2026."},
    {"question": "Who is involved?",
     "answer": "G42, led by Sheikh Tahnoun bin Zayed al Nahyan, alongside OpenAI, "
               "Oracle, Nvidia, SoftBank and Cisco."},
    {"question": "How well sourced is this?",
     "answer": "Reuters cites six anonymous sources, including a US official, a Western "
               "diplomat and industry executives. G42 says work is progressing as "
               "planned and subject to continuous security review, which neither "
               "confirms nor denies the design change."},
]

IMAGE = {
    "url": f"{PROFILE['image_base_url']}/uae-ai-data-centre-plan-revised-banner.jpg",
    "alt": ("A single large data centre campus replaced by several smaller hardened "
            "sites spread across a map, some set into mountain terrain"),
}

REFERENCES = [
    {"title": "UAE revises AI data centre plan after Iranian attacks, sources say",
     "url": ("https://tribune.com.pk/story/2628742/"
             "uae-revises-ai-data-centre-plan-after-iranian-attacks-sources-say"),
     "publisher": "The Express Tribune (Reuters)"},
    {"title": "Exclusive: UAE revises AI data center plan after Iranian attacks",
     "url": ("https://www.usnews.com/news/world/articles/2026-09-11/"
             "exclusive-uae-revises-ai-data-center-plan-after-iranian-attacks-sources-say"),
     "publisher": "U.S. News (Reuters)"},
]

if __name__ == "__main__":
    print(f"By {PROFILE['author_name']} | {PROFILE['tone_label']} | "
          f"{PROFILE['company_name']}\n")

    kw = seo_keywords(HEADLINE, texts=FACTS, include_suggestions=False, cfg=cfg)
    print("primary keyword :", kw["primary_keyword"])
    print("secondary       :", ", ".join(kw["secondary_keywords"][:5]))
    print("entities        :", ", ".join(kw["entities"][:8]))

    built = build_schema(ARTICLE, FAQ, IMAGE, REFERENCES,
                         keywords=[kw["primary_keyword"]] + kw["secondary_keywords"][:3],
                         cfg=cfg)
    print("\nschema validation:", built["validation"]["issues"] or "no issues")

    body = built["html_body"]
    words = find_ai_words(body)
    print("ai words        :", words["verdict"])
    for hit in words["occurrences"]:
        print("   !", hit["phrase"], "->", hit["in_sentence"][:80])
    score = score_ai_text(body, cfg=cfg)
    print("human score     :", score["human_score"], "/100")

    hedges = sum(body.lower().count(w) for w in
                 ("reportedly", "according to", "sources", "said to"))
    print("hedging markers :", hedges, "(anonymous sourcing must stay hedged)")

    audit = seo_audit(body, kw["primary_keyword"],
                      secondary_keywords=kw["secondary_keywords"][:4],
                      meta_title="UAE revises its AI data centre plan after Iranian attacks",
                      meta_description=ARTICLE["description"],
                      slug=ARTICLE["slug"], headline=HEADLINE, cfg=cfg)
    print("seo score       :", f"{audit['score']}/100 "
                               f"({audit['passed']}/{audit['total_checks']})")
    for item in audit["must_fix"] + audit["should_fix"]:
        print("   -", item["check"], "->", item["detail"])

    pack = build_publishing_pack(
        HEADLINE, description=ARTICLE["description"], slug=ARTICLE["slug"],
        keywords=[kw["primary_keyword"]] + kw["secondary_keywords"][:4],
        entities=kw["entities"],
        image_concepts=("a map showing one large campus icon replaced by several "
                        "smaller fortified site icons spread apart, two of them set "
                        "into mountain terrain, technical and restrained"),
        image_style="editorial", canonical_url=built["canonical_url"], cfg=cfg)
    print("\nlabels          :", pack["labels_line"])
    print("permalink       :", pack["permalink_slug"])
    print("image goes to   :", pack["suggested_image_url"])

    saved = save_and_present(
        slug=ARTICLE["slug"], html_body=body,
        json_ld_article=built["json_ld_article"], json_ld_faq=built["json_ld_faq"],
        title=HEADLINE, description=ARTICLE["description"],
        meta={**built["meta"],
              "author": PROFILE["author_name"], "tone_label": PROFILE["tone_label"],
              "verification": {
                  "is_legit": True, "confidence": "medium",
                  "independent_publishers": ["tribune.com.pk", "usnews.com",
                                             "tbsnews.net", "jpost.com",
                                             "english.aaj.tv"],
                  "reasoning": "Five or more domains carry it, but all are Reuters wire "
                               "copy of one exclusive, and the underlying reporting "
                               "rests on six anonymous sources. One originating source, "
                               "unnamed informants: medium, not high."},
              "human_score": {"after": score["human_score"],
                              "detector_used": score["detector_used"],
                              "is_real_detector": score.get("is_real_detector", False),
                              "clean_of_ai_words": words["clean"],
                              "ai_word_count": words["count"]},
              "seo": {**audit, "primary_keyword": kw["primary_keyword"],
                      "secondary_keywords": kw["secondary_keywords"][:4]},
              "references": REFERENCES},
        pack=pack, cfg=cfg)
    print("\nwritten to:", saved["folder"])
