"""Full pipeline on a real story from 08-09 September 2026.

Facts came from The Next Web's report on the Qualcomm/AWS deal. Every figure
below appears in that reporting; nothing here is invented. This is what the MCP
produces end to end once verify_news and fetch_article_facts have run.

    python examples/build_today_example.py
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from newsblog_mcp.config import Config                      # noqa: E402
from newsblog_mcp.tools.pack import build_publishing_pack   # noqa: E402
from newsblog_mcp.tools.save import save_and_present        # noqa: E402
from newsblog_mcp.tools.schema import build_schema          # noqa: E402
from newsblog_mcp.tools.score import find_ai_words, score_ai_text  # noqa: E402
from newsblog_mcp.tools.seo import seo_audit, seo_keywords  # noqa: E402

cfg = Config()
cfg.site_name = "Example Media"
cfg.site_base_url = "https://blog.example.com"
cfg.author_name = "Test Author"
cfg.publisher_name = "Example Media"
cfg.publisher_url = "https://example.com"
cfg.publisher_logo_url = "https://example.com/logo.png"
cfg.site_timezone = "America/Chicago"
cfg.cta_url = "https://example.com"
cfg.cta_link_text = "Example Media"
cfg.output_dir = ROOT / "output"

HEADLINE = ("Amazon Took $4B in Qualcomm Warrants to Become a Customer, and That Is "
            "Now Normal")

# What fetch_article_facts would have returned, each traceable to the source.
FACTS = [
    "Qualcomm issued Amazon warrants covering 25 million shares, valued at about "
    "$4 billion, at a strike price of $161.26 per share.",
    "The warrants expire on September 3, 2036, giving Amazon a ten-year window.",
    "Vesting is tied to commercial milestones and to Amazon buying up to $60 billion "
    "of Qualcomm server chips.",
    "The custom silicon covers AI inference and optical connectivity up to 1.6T, using "
    "Qualcomm's SerDes and optical DSP.",
    "Qualcomm will run chip design workloads on Amazon Bedrock.",
    "Qualcomm shares rose 4 percent on the announcement.",
    "Qualcomm is one of three chipmakers, alongside Nvidia and AMD, supplying the EU's "
    "AI gigafactories programme, which earmarks roughly 30 billion euros across seven "
    "possible sites with about 1 billion euros committed so far.",
]

ARTICLE = {
    "headline": HEADLINE,
    "description": ("Qualcomm gave Amazon $4B in warrants to win AWS as a custom silicon "
                    "customer, tying vesting to $60B of chip purchases."),
    "slug": "qualcomm-amazon-warrants-custom-ai-silicon",
    "date_published": "2026-09-09T09:00:00-05:00",
    "section": "Artificial Intelligence",
    "intro": [
        "Qualcomm has issued Amazon warrants covering 25 million of its own shares, "
        "worth about $4 billion at a strike price of $161.26. The warrants run until "
        "September 3, 2036, and they vest against commercial milestones and up to $60 "
        "billion of Qualcomm server chip purchases by Amazon.",
        "Read the structure rather than the headline number. Qualcomm is not selling "
        "chips to a hyperscaler here so much as paying one to adopt them, and the "
        "payment is equity rather than a discount.",
    ],
    "sections": [
        {"heading": "What Qualcomm actually gave away", "paragraphs": [
            "The warrant covers 25 million shares at $161.26, expiring September 3, "
            "2036. Vesting is conditional: Amazon has to hit commercial milestones and "
            "work up toward $60 billion in Qualcomm server chip purchases before the "
            "full position is earned.",
            "Qualcomm shares rose 4 percent on the news, so the market read a ten-year "
            "dilution risk as cheaper than staying outside the hyperscaler market."]},
        {"heading": "What the silicon does", "paragraphs": [
            "The work covers AI inference and optical connectivity up to 1.6T, built on "
            "Qualcomm's SerDes and optical DSP. That is the interconnect layer, not the "
            "training accelerator, which places Qualcomm in the part of the data centre "
            "where inference volume, not model training, drives the spend.",
            "The deal runs both directions. Qualcomm will run its own chip design "
            "workloads on Amazon Bedrock, so the customer relationship is mutual."]},
        {"heading": "Equity as a customer acquisition cost", "paragraphs": [
            "The Next Web described the pattern plainly: \"Amazon is being paid in "
            "equity to become a customer.\" For a chipmaker without a Western "
            "hyperscaler on its books, that is the price of entry.",
            "Whether it works depends on the $60 billion figure. If Amazon buys "
            "anywhere near it, the warrant is cheap. If purchases stall at the first "
            "milestone, Qualcomm has bought a press release."]},
        {"heading": "Where this sits against the EU build-out", "paragraphs": [
            "Qualcomm is also one of three chipmakers, with Nvidia and AMD, supplying "
            "the EU's AI gigafactories programme. That programme earmarks roughly 30 "
            "billion euros across seven possible sites, though only about 1 billion "
            "euros has actually been committed from Brussels.",
            "Two very different funding models, then: an American hyperscaler paying "
            "with equity and moving now, and a European programme with a large headline "
            "number and a small committed one."]},
        {"heading": "What to take from it if you buy infrastructure", "paragraphs": [
            "The useful question is not who won. It is what the terms tell you about "
            "where inference silicon pricing is heading over the next few years."],
         "bullets": [
             "If suppliers are paying for adoption, expect inference cost per token to "
             "keep falling faster than list prices suggest.",
             "Interconnect at 1.6T is becoming the constraint worth asking vendors "
             "about, ahead of raw accelerator throughput.",
             "A ten-year warrant signals how long the supplier expects the lock-in to "
             "last. Match your own contract terms to that, not to a one-year budget."]},
    ],
    "cta": ("If you are sizing inference costs or picking silicon for a workload that "
            "has to run for years, Example Media can help you model the terms rather "
            "than the headlines."),
}

FAQ = [
    {"question": "What did Qualcomm actually give Amazon?",
     "answer": "Warrants covering 25 million Qualcomm shares, worth roughly $4 billion, "
               "at a strike price of $161.26, expiring September 3, 2036."},
    {"question": "What does Amazon have to do to earn them?",
     "answer": "Hit commercial milestones and buy up to $60 billion of Qualcomm server "
               "chips. The warrants vest against those conditions rather than "
               "immediately."},
    {"question": "What are the chips for?",
     "answer": "AI inference and optical connectivity up to 1.6T, using Qualcomm's "
               "SerDes and optical DSP."},
    {"question": "Does anything flow back to Qualcomm?",
     "answer": "Yes. Qualcomm will run its own chip design workloads on Amazon Bedrock."},
    {"question": "How did the market react?",
     "answer": "Qualcomm shares rose 4 percent on the announcement."},
    {"question": "How does this compare with Europe's chip spending?",
     "answer": "Qualcomm is one of three suppliers, with Nvidia and AMD, to the EU AI "
               "gigafactories programme, which earmarks about 30 billion euros across "
               "seven possible sites but has committed around 1 billion so far."},
]

REFERENCES = [
    {"title": "Qualcomm hands Amazon $4B of warrants to build custom silicon for AWS",
     "url": "https://thenextweb.com/news/qualcomm-amazon-4bn-warrants",
     "publisher": "The Next Web"},
    {"title": "Qualcomm issues Amazon warrants to acquire 25 million shares",
     "url": "https://www.cnbc.com/2026/09/08/qualcomm-amazon-data-center-infrastructure-deal.html",
     "publisher": "CNBC"},
]

if __name__ == "__main__":
    print("=" * 70)
    kw = seo_keywords(HEADLINE, texts=FACTS, include_suggestions=False, cfg=cfg)
    print("primary keyword :", kw["primary_keyword"])
    print("secondary       :", ", ".join(kw["secondary_keywords"][:5]))
    print("entities        :", ", ".join(kw["entities"][:6]))

    built = build_schema(ARTICLE, FAQ,
                         {"url": "https://blog.example.com/images/qualcomm-aws-warrants-banner.jpg",
                          "alt": "Custom inference silicon and optical interconnect "
                                 "linking a chipmaker to a cloud provider's data centre"},
                         REFERENCES,
                         keywords=[kw["primary_keyword"]] + kw["secondary_keywords"][:3],
                         cfg=cfg)
    print("\nschema validation:", built["validation"]["issues"] or "no issues")

    body_text = built["html_body"]
    words = find_ai_words(body_text)
    print("ai words        :", words["verdict"])
    score = score_ai_text(body_text, cfg=cfg)
    print("human score     :", score["human_score"], "/100  (", score["detector_used"], ")")

    audit = seo_audit(body_text, kw["primary_keyword"],
                      secondary_keywords=kw["secondary_keywords"][:4],
                      meta_title="Amazon Took $4B in Qualcomm Warrants to Become a Customer",
                      meta_description=ARTICLE["description"],
                      slug=ARTICLE["slug"], headline=HEADLINE, cfg=cfg)
    print("seo score       :", f"{audit['score']}/100 ({audit['passed']}/{audit['total_checks']})")
    for item in audit["must_fix"] + audit["should_fix"]:
        print("   -", item["check"], "->", item["detail"])

    pack = build_publishing_pack(
        HEADLINE, description=ARTICLE["description"], slug=ARTICLE["slug"],
        keywords=[kw["primary_keyword"]] + kw["secondary_keywords"][:4],
        entities=kw["entities"],
        image_concepts=("a custom inference chip package connected by glowing optical "
                        "fibre links to a row of data centre racks, with a stylised "
                        "share certificate motif flowing back the other way"),
        canonical_url=built["canonical_url"], cfg=cfg)
    print("\nlabels          :", pack["labels_line"])
    print("permalink       :", pack["permalink_slug"])

    saved = save_and_present(
        slug=ARTICLE["slug"], html_body=body_text,
        json_ld_article=built["json_ld_article"], json_ld_faq=built["json_ld_faq"],
        title=HEADLINE, description=ARTICLE["description"],
        meta={**built["meta"],
              "verification": {"is_legit": True, "confidence": "high",
                               "independent_publishers": ["thenextweb.com", "cnbc.com"],
                               "reasoning": "Two independent publishers carried the deal terms."},
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
    for path in saved["paths"]:
        print("  ", Path(path).name)
