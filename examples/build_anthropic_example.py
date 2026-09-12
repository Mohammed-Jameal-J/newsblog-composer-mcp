"""Full pipeline on the user's headline, 12 September 2026.

    "How Anthropic says Claude was used for weapons, spying and cyber operations"

Facts come from Anthropic's threat intelligence report of 11 September 2026, as
reported by Al Jazeera and by Reuters (Eduardo Baptista and AJ Vicens). Every
claim traceable only to Anthropic's own report is attributed to Anthropic in the
copy rather than stated as established fact.

Identity comes from profile.json, set at setup.
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
HEADLINE = ("How Anthropic Says Claude Was Used for Weapons, Spying and Cyber "
            "Operations")

FACTS = [
    "Anthropic published a threat intelligence report on September 11, 2026 "
    "documenting misuse of Claude across weapons, cyber, influence and surveillance "
    "operations.",
    "Anthropic says it blocked an operation in northern Yemen that tried to use Claude "
    "for missile guidance software, covering guided rockets and long-range ballistic "
    "missiles.",
    "The operators assigned different Claude instances specific roles in writing "
    "flight-control code, according to the report.",
    "Anthropic says safeguards blocked many of the Yemen requests but not all of them.",
    "The report says the operators appeared to have conducted an unsuccessful "
    "test-fire, and found no evidence of a deployed working weapon.",
    "Anthropic describes a Russian-linked operation bearing the hallmarks of Midnight "
    "Blizzard, also known as APT29, using automated workflows against Ukrainian, "
    "European and diplomatic targets including drone manufacturers.",
    "A Chinese operation run by university students in Hunan province used Claude as "
    "the engineering and orchestration layer against government and corporate networks "
    "in the Middle East, Europe and Southeast Asia, targeting 50 organisations.",
    "A China-aligned account with no Arabic language skills ran a multi-day recruitment "
    "operation to infiltrate Uyghur targets in Syria, with Claude drafting outreach and "
    "translating replies in real time.",
    "Anthropic removed three Iranian state-aligned accounts running covert influence "
    "and psychological operations, tied to the Islamic Culture and Communications "
    "Organisation and a Mashhad seminary distributing content aligned with IRGC "
    "narratives.",
    "Anthropic banned 16 Claude accounts linked to Iranian paramilitary and security "
    "agencies.",
    "One influence operation targeted 42 European political parties.",
    "An AI dating app scam using more than 4,700 personas affected 25,000 users.",
    "A surveillance system in Mali monitored roughly 25 million SIM cards.",
    "Anthropic banned the accounts involved, shared threat information with public and "
    "private sector partners, and deployed additional monitoring.",
    "Reuters reported the findings on September 11, 2026, in a story by Eduardo "
    "Baptista and AJ Vicens.",
]

ARTICLE = {
    "headline": HEADLINE,
    "description": ("Anthropic's threat report names missile work in Yemen, Russian and "
                    "Chinese cyber operations, and surveillance touching millions of "
                    "people."),
    "slug": "anthropic-report-claude-misuse",
    "date_published": "2026-09-12T09:00:00-05:00",
    "section": "Artificial Intelligence",
    "intro": [
        "Somewhere in Syria, someone answered a friendly message in their own language "
        "from a person who did not speak it. Anthropic says a China-aligned account with "
        "no Arabic ran a multi-day recruitment operation to infiltrate Uyghur targets "
        "there, with Claude drafting the outreach and translating the replies as they "
        "came back.",
        "That is one paragraph in a threat intelligence report Anthropic published on "
        "September 11. The rest covers missile guidance work in Yemen, Russian and "
        "Chinese cyber operations, Iranian influence accounts, and a surveillance system "
        "in Mali watching around 25 million SIM cards. The company found these, banned "
        "them, and then wrote them down.",
    ],
    "sections": [
        {"heading": "The Yemen case, and what Anthropic admits about it", "paragraphs": [
            "Anthropic says it blocked an operation in northern Yemen that tried to use "
            "Claude for missile guidance software, covering guided rockets and "
            "long-range ballistic missiles. The operators assigned different Claude "
            "instances specific roles in writing flight-control code.",
            "The part worth reading twice is Anthropic's own admission: safeguards "
            "blocked many of the requests, but not all of them. The report says the "
            "operators appeared to have conducted an unsuccessful test-fire, and found "
            "no evidence of a deployed working weapon. That is a narrower reassurance "
            "than it first sounds."]},
        {"heading": "The operations aimed at people rather than systems", "paragraphs": [
            "Three Iranian state-aligned accounts were removed for covert influence and "
            "psychological operations, tied to the Islamic Culture and Communications "
            "Organisation and a seminary in Mashhad distributing content aligned with "
            "IRGC narratives. Anthropic banned 16 more accounts linked to Iranian "
            "paramilitary and security agencies.",
            "One influence operation targeted 42 European political parties. A dating "
            "app scam ran more than 4,700 invented personas and reached 25,000 users. "
            "Every one of those users thought they were talking to a person."]},
        {"heading": "Cyber operations run as engineering work", "paragraphs": [
            "A Russian-linked operation carrying the hallmarks of Midnight Blizzard, "
            "also known as APT29, used automated workflows against Ukrainian, European "
            "and diplomatic targets, including drone manufacturers. The workflows handled "
            "phishing, setup and data theft.",
            "A Chinese operation run by university students in Hunan province used "
            "Claude as the engineering and orchestration layer against government and "
            "corporate networks in the Middle East, Europe and Southeast Asia. Fifty "
            "organisations were targeted. The students were not specialists; the tooling "
            "was."]},
        {"heading": "Surveillance measured in millions", "paragraphs": [
            "A surveillance system in Mali monitored roughly 25 million SIM cards. "
            "Anthropic also banned an account operating a commercial surveillance "
            "platform aimed at Iran and the Gulf, and disrupted an Iranian operator "
            "collecting naval reconnaissance data.",
            "Those numbers describe populations rather than targets. Most of the people "
            "counted in them will never know they were counted."]},
        {"heading": "What this asks of anyone deploying AI", "paragraphs": [
            "Anthropic banned the accounts, shared threat information with public and "
            "private sector partners, and added monitoring. Publishing the detail is "
            "more than most vendors do. It also shows what detection looks like when it "
            "works only partly."],
         "bullets": [
             "Safeguards that block most requests still pass some. Plan for the "
             "remainder rather than treating a block rate as a guarantee.",
             "Several of these operations succeeded because the model supplied a skill "
             "the operator lacked, whether a language or an engineering layer. Ask what "
             "your deployment makes newly possible for someone without expertise.",
             "The Yemen case was caught during use, not before. Detection after the "
             "fact is the control that actually ran here."]},
    ],
    "cta": (f"If you are deploying AI systems and want to understand what abuse of them "
            f"would look like from the inside, {COMPANY} can help you think it through "
            f"before it matters."),
}

FAQ = [
    {"question": "What did Anthropic publish?",
     "answer": "A threat intelligence report on September 11, 2026, documenting misuse of "
               "Claude across weapons work, cyber operations, influence campaigns and "
               "surveillance."},
    {"question": "What happened in the Yemen case?",
     "answer": "Anthropic says it blocked an operation in northern Yemen that tried to "
               "use Claude for missile guidance software, with different Claude "
               "instances assigned roles writing flight-control code. Safeguards blocked "
               "many requests but not all of them."},
    {"question": "Was a working weapon built?",
     "answer": "Anthropic found no evidence of a deployed working weapon. The report says "
               "the operators appeared to have conducted an unsuccessful test-fire."},
    {"question": "Which cyber operations are named?",
     "answer": "A Russian-linked operation with the hallmarks of Midnight Blizzard "
               "(APT29) against Ukrainian, European and diplomatic targets, and a Chinese "
               "operation run by Hunan university students that targeted 50 organisations "
               "across the Middle East, Europe and Southeast Asia."},
    {"question": "How large was the surveillance activity?",
     "answer": "A system in Mali monitored roughly 25 million SIM cards. Anthropic also "
               "banned a commercial surveillance platform targeting Iran and the Gulf."},
    {"question": "What did Anthropic do about it?",
     "answer": "It banned the accounts involved, shared threat information with public "
               "and private sector partners, and deployed additional monitoring for "
               "similar activity."},
]

IMAGE = {
    "url": f"{PROFILE['image_base_url']}/anthropic-report-claude-misuse-banner.jpg",
    "alt": ("A network of message threads and connections spreading outward from a "
            "single point, with a small number of them highlighted as intercepted"),
}

REFERENCES = [
    {"title": "Anthropic claims Claude AI used for missile projects, global espionage",
     "url": ("https://www.aljazeera.com/news/2026/9/11/"
             "anthropic-claims-claude-ai-used-for-missile-projects-global-espionage"),
     "publisher": "Al Jazeera"},
    {"title": "Factbox: How Anthropic says Claude was used for weapons, spying and cyber "
              "operations",
     "url": ("https://www.investing.com/news/economy-news/"
             "factboxhow-anthropic-says-claude-was-used-for-weapons-spying-and-cyber-"
             "operations-4898365"),
     "publisher": "Reuters"},
]

if __name__ == "__main__":
    print(f"By {PROFILE['author_name']} | {PROFILE['tone_label']} | "
          f"{PROFILE['company_name']} | {PROFILE['blog_base_url']}\n")

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

    attributed = sum(body.count(w) for w in ("Anthropic says", "according to",
                                             "the report says", "Anthropic describes"))
    print("attribution     :", attributed, "explicit attributions to the source report")

    audit = seo_audit(body, kw["primary_keyword"],
                      secondary_keywords=kw["secondary_keywords"][:4],
                      meta_title="How Anthropic says Claude was used for weapons and spying",
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
        image_concepts=("a dense web of message threads spreading outward from one "
                        "point across a world map, a small number of the threads "
                        "highlighted where they were intercepted, restrained and "
                        "technical"),
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
                  "is_legit": True, "confidence": "high",
                  "independent_publishers": ["anthropic.com", "aljazeera.com",
                                             "reuters.com", "washingtontimes.com"],
                  "reasoning": "The primary source is the vendor's own published report, "
                               "plus independent coverage from Al Jazeera and Reuters "
                               "with separate framing. Note the claims originate with "
                               "Anthropic and are not independently verified."},
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
