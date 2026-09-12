"""Full pipeline on the headline the user supplied, 09 September 2026.

    "Apple CEO John Ternus says the best AI device is still the iPhone"

Facts come from TechCrunch's report on the "Surprise and Shine" event and Cult
of Mac's product coverage of the same event. Nothing here is invented.
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from newsblog_mcp.config import Config                          # noqa: E402
from newsblog_mcp.tools.pack import build_publishing_pack       # noqa: E402
from newsblog_mcp.tools.save import save_and_present            # noqa: E402
from newsblog_mcp.tools.schema import build_schema              # noqa: E402
from newsblog_mcp.tools.score import find_ai_words, score_ai_text   # noqa: E402
from newsblog_mcp.tools.seo import seo_audit, seo_keywords      # noqa: E402

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

HEADLINE = "Apple CEO John Ternus Says the Best AI Device Is Still the iPhone"

# What fetch_article_facts would have returned from the two sources.
FACTS = [
    "John Ternus took over as Apple CEO from Tim Cook, who becomes executive chairman.",
    "Ternus made the AI device argument at Apple's Surprise and Shine event in "
    "Cupertino on September 9, 2026.",
    "Ternus described the iPhone as an intelligent personal hub combining personal "
    "context, on-device processing, cloud connectivity, display, cameras, microphones "
    "and battery life.",
    "Apple Intelligence runs on device whenever it can, which Ternus framed as a "
    "privacy difference from rivals who collect and store personal data.",
    "The iPhone Duo is Apple's first folding iPhone, with a 5.4-inch external screen "
    "and a 7.6-inch internal display, starting at $1,999.",
    "iPhone Duo preorders open October 16 and the device ships October 23.",
    "The iPhone 18 Pro and Pro Max use the A20 Pro chip on a 2nm process with a 48MP "
    "Fusion camera and variable aperture, shipping September 18.",
    "The iPhone 18 Pro Max reaches up to 36 hours of video playback and charges to 50 "
    "percent in about 15 minutes.",
    "AirPods 5 add hands-free Siri with head gestures and Live Translation, at $129 or "
    "$149 with a wireless charging case.",
    "Apple Watch Series 12 starts at $399 and Apple Watch Ultra 4 starts at $799, both "
    "shipping September 18.",
]

ARTICLE = {
    "headline": HEADLINE,
    "description": ("Apple's new CEO John Ternus argued the iPhone is already the best AI "
                    "device, and shipped an AI strategy with no new AI hardware in it."),
    "slug": "apple-ternus-iphone-best-ai-device",
    "date_published": "2026-09-11T09:00:00-05:00",
    "section": "Artificial Intelligence",
    "intro": [
        "John Ternus used his first Apple event as CEO to answer a question the rest of "
        "the industry has been answering with new hardware. Asked what the best device "
        "for AI looks like, he pointed at the phone already in the room.",
        "\"There's no product in the world better designed to be your intelligent "
        "personal hub than iPhone,\" Ternus said at the Surprise and Shine event in "
        "Cupertino. Every product Apple showed that day was built on that premise.",
    ],
    "sections": [
        {"heading": "The argument Ternus actually made", "paragraphs": [
            "Ternus described the iPhone as an intelligent personal hub, and the list he "
            "gave was deliberately unglamorous: personal context, on-device processing, "
            "cloud connectivity, a large display, cameras, microphones, battery life, and "
            "links to the other devices you own.",
            "That is a claim about integration rather than capability. The pitch is not "
            "that the iPhone runs better models. It is that the parts an AI assistant "
            "needs are already assembled in one object people carry anyway."]},
        {"heading": "Privacy is the wedge", "paragraphs": [
            "Ternus drew the line at data handling. Rivals, he said, \"see personal data "
            "as something to collect and store.\" His counter: \"Trust only goes so far "
            "when your data is no longer yours to control.\"",
            "That is why Apple Intelligence runs on device whenever it can. The "
            "constraint is also a product decision, because on-device inference caps what "
            "a model can do while removing the question of where the data went."]},
        {"heading": "The hardware that shipped alongside it", "paragraphs": [
            "The iPhone Duo is Apple's first folding phone: a 5.4-inch external screen, a "
            "7.6-inch internal display, $1,999 to start, preorders October 16 and "
            "shipping October 23.",
            "The iPhone 18 Pro and Pro Max ship September 18 on the A20 Pro chip, built "
            "on a 2nm process, with a 48MP Fusion camera and variable aperture. The Pro "
            "Max reaches 36 hours of video playback and charges to half in about fifteen "
            "minutes."]},
        {"heading": "Where the AI actually surfaces", "paragraphs": [
            "AirPods 5 carry the clearest example. They add hands-free Siri with head "
            "gestures and Live Translation, at $129, or $149 with a wireless charging "
            "case. The intelligence sits in the phone; the earbuds are an input device.",
            "Apple Watch Series 12 at $399 and Ultra 4 at $799 follow the same pattern on "
            "September 18. Nothing announced was a standalone AI device, which is the "
            "point Ternus was making."]},
        {"heading": "What a technology buyer should take from it", "paragraphs": [
            "Strip out the keynote framing and there is a real architectural position "
            "here, one that maps onto decisions enterprise teams are making now."],
         "bullets": [
             "On-device inference trades capability for a data-residency answer you can "
             "give a compliance team in one sentence. Decide which you need per workload.",
             "Accessories as input surfaces, with the model on a hub device, is cheaper "
             "to maintain than intelligence embedded in every endpoint.",
             "A vendor who ships no new category of device is betting the existing one "
             "holds. Ask what happens to your roadmap if that bet is wrong."]},
    ],
    "cta": ("If you are deciding where inference should run for your own products, "
            "Example Media can help you weigh on-device limits against what the workload "
            "actually needs."),
}

FAQ = [
    {"question": "Who is John Ternus?",
     "answer": "Apple's new CEO. He took over from Tim Cook, who becomes executive "
               "chairman."},
    {"question": "What did he say the best AI device is?",
     "answer": "The iPhone. He called it an intelligent personal hub and said no product "
               "is better designed for the role."},
    {"question": "Why does Apple keep AI processing on the device?",
     "answer": "Ternus framed it as a privacy position: Apple Intelligence runs on device "
               "whenever it can, because trust only goes so far when data leaves your "
               "control."},
    {"question": "What is the iPhone Duo and what does it cost?",
     "answer": "Apple's first folding iPhone, with a 5.4-inch external screen and a "
               "7.6-inch internal display. It starts at $1,999, with preorders on "
               "October 16 and shipping October 23."},
    {"question": "When do the iPhone 18 Pro models ship?",
     "answer": "September 18. They run the A20 Pro chip on a 2nm process with a 48MP "
               "Fusion camera and variable aperture."},
    {"question": "Did Apple announce a dedicated AI device?",
     "answer": "No. Every product shown routes back through the iPhone, including AirPods "
               "5 with hands-free Siri and Live Translation."},
]

IMAGE = {
    "url": "https://blog.example.com/images/ternus-iphone-ai-device-banner.jpg",
    "alt": ("A smartphone at the centre of a ring of connected personal devices, with "
            "processing shown happening inside the handset rather than in the cloud"),
}

REFERENCES = [
    {"title": "Apple CEO John Ternus says the best AI device is still the iPhone",
     "url": ("https://techcrunch.com/2026/09/09/"
             "apple-ceo-john-ternus-says-the-best-ai-device-is-still-the-iphone/"),
     "publisher": "TechCrunch"},
    {"title": "Apple Surprise and Shine event live updates: New iPhones, more",
     "url": "https://www.cultofmac.com/news/apple-surprise-and-shine-event-2026",
     "publisher": "Cult of Mac"},
]

if __name__ == "__main__":
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
    score = score_ai_text(body, cfg=cfg)
    print("human score     :", score["human_score"], "/100")

    audit = seo_audit(body, kw["primary_keyword"],
                      secondary_keywords=kw["secondary_keywords"][:4],
                      meta_title="Ternus: the Best AI Device Is Still the iPhone",
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
        image_concepts=("a single smartphone at the centre of a ring of connected "
                        "personal devices, with glowing processing happening inside the "
                        "handset instead of in a distant cloud"),
        canonical_url=built["canonical_url"], cfg=cfg)
    print("\nlabels          :", pack["labels_line"])
    print("permalink       :", pack["permalink_slug"])

    saved = save_and_present(
        slug=ARTICLE["slug"], html_body=body,
        json_ld_article=built["json_ld_article"], json_ld_faq=built["json_ld_faq"],
        title=HEADLINE, description=ARTICLE["description"],
        meta={**built["meta"],
              "verification": {"is_legit": True, "confidence": "high",
                               "independent_publishers": ["techcrunch.com",
                                                          "cultofmac.com"],
                               "reasoning": "Two independent publishers covered the "
                                            "event and the CEO's remarks."},
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
