"""Full pipeline, 12 September 2026.

    "Mecka AI nears $500M valuation in Sequoia-led deal amid rush for robot
     training data"

Facts come from TechCrunch (Marina Temkin, 11 September 2026). The round is
reported from two anonymous sources and the terms are not final, so every claim
about it stays hedged, per the house style.

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
HEADLINE = ("Mecka AI Nears $500M Valuation in Sequoia-Led Deal Amid Rush for Robot "
            "Training Data")

FACTS = [
    "TechCrunch reported on September 11, 2026 that Mecka AI is nearing a valuation of "
    "about $500 million in a round led by Sequoia Capital.",
    "The report is based on two people with knowledge of the deal, and TechCrunch says "
    "the terms are not final and could still change.",
    "The size of the round was not disclosed.",
    "Mecka AI collects and analyses human motion data used to train humanoid robots and "
    "other robotics.",
    "The company pays people to record themselves performing everyday tasks such as "
    "making coffee or fixing cars, using body sensors and smartphones.",
    "The approach is described as egocentric data capture, recording real-world physical "
    "interaction from the perspective of the person doing the task.",
    "Mecka AI announced a $60 million Series A in June 2026, three months before this "
    "report.",
    "The Series A was led by Framework Ventures, with Menlo Ventures, SV Angel and "
    "Kindred Ventures participating.",
    "The company was founded in 2024.",
    "The co-founders are Josh Gao and Mogen Cheng, both Canadians who previously ran a "
    "restaurant fintech startup, Jason Chong, formerly of Coinbase, and Duy Nguyen, who "
    "handles operations.",
    "Co-founder Josh Gao told Fortune the company is projecting a $100 million annual "
    "run rate by the end of 2026.",
    "Mecka AI's customers have not been publicly disclosed.",
    "TechCrunch notes that many robotics companies and AI labs rely on similar data "
    "collection methods.",
]

ARTICLE = {
    "headline": HEADLINE,
    "description": ("Mecka AI is reportedly nearing a $500 million valuation in a "
                    "Sequoia-led round, three months after closing a $60 million "
                    "Series A."),
    "slug": "mecka-ai-sequoia-valuation",
    "date_published": "2026-09-12T09:00:00-05:00",
    "section": "Artificial Intelligence",
    "intro": [
        "Mecka AI is nearing a valuation of about $500 million in a round led by Sequoia "
        "Capital, according to a TechCrunch report published on September 11. The report "
        "cites two people with knowledge of the deal. TechCrunch says the terms are not "
        "final and could still change, and the size of the round was not disclosed.",
        "The company sells training data for robots. It pays people to record themselves "
        "doing everyday tasks, then turns those recordings into data used to train "
        "humanoid robots and other robotics systems.",
    ],
    "sections": [
        {"heading": "What Mecka AI sells", "paragraphs": [
            "The company collects and analyses human motion data. People are paid to "
            "record themselves performing ordinary tasks, such as making coffee or "
            "fixing cars, wearing body sensors and using smartphones.",
            "The method is described as egocentric capture: the recording is made from "
            "the perspective of the person doing the task, rather than from a camera "
            "watching them. TechCrunch notes that many robotics companies and AI labs "
            "rely on similar collection methods."]},
        {"heading": "What is reported, and what is not confirmed", "paragraphs": [
            "The $500 million figure and Sequoia's role both come from two anonymous "
            "sources. Neither party has confirmed the round on the record in the "
            "report.",
            "The round size is unknown. TechCrunch states directly that terms are not "
            "final. A deal at this stage can change in size, price or lead investor "
            "before it closes."]},
        {"heading": "How the company got here", "paragraphs": [
            "Mecka AI was founded in 2024 and announced a $60 million Series A in June "
            "2026, three months before this report. Framework Ventures led that round, "
            "with Menlo Ventures, SV Angel and Kindred Ventures participating.",
            "The co-founders are Josh Gao and Mogen Cheng, both Canadians who previously "
            "ran a restaurant fintech startup, Jason Chong, formerly of Coinbase, and "
            "Duy Nguyen, who handles operations. Gao told Fortune the company is "
            "projecting a $100 million annual run rate by the end of 2026."]},
        {"heading": "Why robot training data is being bid up", "paragraphs": [
            "Robotics models need examples of physical action, and those examples cannot "
            "be scraped from the web the way text and images were. They have to be "
            "recorded by someone performing the task.",
            "That makes collection a supply problem rather than a compute problem. A "
            "company that can record at volume holds something the labs cannot generate "
            "for themselves, which is the position Mecka AI is being valued on."]},
        {"heading": "What to watch next", "paragraphs": [
            "Three things would move this story from reported to established, and none "
            "of them has happened yet."],
         "bullets": [
             "A confirmed round. Until the company or Sequoia says so on the record, "
             "the valuation is two sources and an unfinished term sheet.",
             "Disclosed customers. The company has not named who buys the data, which "
             "is the number that would support a $100 million run rate projection.",
             "Competing collectors. If the method transfers easily, the advantage sits "
             "in operations and scale rather than in technology."]},
    ],
    "cta": (f"Teams weighing where their own training data will come from can talk it "
            f"through with {COMPANY}."),
}

FAQ = [
    {"question": "What is Mecka AI reportedly raising at?",
     "answer": "A valuation of about $500 million, in a round led by Sequoia Capital, "
               "according to TechCrunch. The round size was not disclosed."},
    {"question": "How solid is the report?",
     "answer": "It rests on two people with knowledge of the deal, and TechCrunch says "
               "the terms are not final and could still change. Neither company "
               "confirmed it on the record."},
    {"question": "What does the company actually do?",
     "answer": "It collects and analyses human motion data to train humanoid robots and "
               "other robotics, paying people to record themselves performing everyday "
               "tasks using body sensors and smartphones."},
    {"question": "What is egocentric data capture?",
     "answer": "Recording a task from the perspective of the person performing it, "
               "rather than from a camera observing them."},
    {"question": "What funding has Mecka AI raised before?",
     "answer": "A $60 million Series A announced in June 2026, led by Framework "
               "Ventures, with Menlo Ventures, SV Angel and Kindred Ventures "
               "participating. The company was founded in 2024."},
    {"question": "Who runs the company?",
     "answer": "Co-founders Josh Gao and Mogen Cheng, who previously ran a restaurant "
               "fintech startup, Jason Chong, formerly of Coinbase, and Duy Nguyen, who "
               "handles operations."},
]

IMAGE = {
    "url": f"{PROFILE['image_base_url']}/mecka-ai-sequoia-valuation-banner.jpg",
    "alt": ("A person wearing motion sensors performing an everyday kitchen task while "
            "the movement is captured as data points"),
}

REFERENCES = [
    {"title": "Mecka AI nears $500M valuation in Sequoia-led deal amid rush for robot "
              "training data",
     "url": ("https://techcrunch.com/2026/09/11/"
             "mecka-ai-nears-500m-valuation-in-sequoia-led-deal-amid-rush-for-robot-"
             "training-data/"),
     "publisher": "TechCrunch"},
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
    print("style score     :", score["style_score"],
          "/100  (NOT an AI-detection reading - no detector key set)")

    hedges = sum(body.lower().count(w) for w in
                 ("reportedly", "according to", "not final", "not disclosed",
                  "techcrunch says", "two people"))
    print("hedging markers :", hedges)

    audit = seo_audit(body, kw["primary_keyword"],
                      secondary_keywords=kw["secondary_keywords"][:4],
                      meta_title="Mecka AI nears $500M valuation in Sequoia-led deal",
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
        image_concepts=("a person wearing small motion sensors performing an everyday "
                        "kitchen task, their movement rendered beside them as a clean "
                        "skeleton of data points, technical and restrained"),
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
                  "independent_publishers": ["techcrunch.com"],
                  "reasoning": "One originating newsroom (TechCrunch). The many other "
                               "domains carrying this headline are syndications and "
                               "rewrites of that report, not independent confirmation. "
                               "The underlying sourcing is two anonymous people and the "
                               "terms are not final."},
              "human_score": {"after": score["style_score"],
                              "detector_used": score["detector_used"],
                              "is_real_detector": score.get("is_real_detector", False),
                              "clean_of_ai_words": words["clean"],
                              "ai_word_count": words["count"]},
              "seo": {**audit, "primary_keyword": kw["primary_keyword"],
                      "secondary_keywords": kw["secondary_keywords"][:4]},
              "references": REFERENCES},
        pack=pack, cfg=cfg)
    print("\nwritten to:", saved["folder"])
