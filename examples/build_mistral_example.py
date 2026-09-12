"""Rebuild a known-good post through build_schema to confirm the house format.

The content here is the Mistral post as it was written by hand. Running it back
through the tool shows what the pipeline would have produced for the same story,
so the output format can be compared against the real thing.

    python examples/build_mistral_example.py
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from newsblog_mcp.config import Config          # noqa: E402
from newsblog_mcp.tools.save import save_and_present   # noqa: E402
from newsblog_mcp.tools.schema import build_schema     # noqa: E402
from newsblog_mcp.tools.seo import seo_audit           # noqa: E402

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

ARTICLE = {
    "headline": ("Mistral's EUR 3B Raise Shows Sovereign AI Is Becoming a Default "
                 "Enterprise Requirement"),
    "description": ("Mistral's EUR 3B round highlights the rise of sovereign AI, with "
                    "enterprises prioritising regional inference and control."),
    "slug": "mistral-eur3b-sovereign-ai-enterprise-requirement",
    "date_published": "2026-09-09T09:00:00-05:00",
    "section": "Artificial Intelligence",
    "intro": [
        "The dominant story in frontier AI used to be \"bigger models win.\" That's "
        "still true, but it's no longer the whole picture. Reporting on Mistral's new "
        "3 billion euro round at a valuation above 21 billion euros points to a "
        "different center of gravity: not just model capability, but where the compute "
        "runs, who controls it, and how organizations avoid depending on one country's "
        "platforms and policies.",
        "What matters is what comes attached to the capital. Mistral isn't pitching "
        "itself as \"the European ChatGPT.\" Instead, it's leaning into a sovereign AI "
        "posture: scaling compute, expanding internationally, and building products "
        "that let customers choose which regions process their AI queries.",
    ],
    "sections": [
        {"heading": "What Happened", "paragraphs": [
            "Mistral raised 3 billion euros in a Series D at a post-money valuation of "
            "more than 21 billion euros, with Samsung Electronics leading and the "
            "EQT-managed Scaleup Europe Fund plus existing investor PSG Equity as "
            "co-leads.",
            "The operational strategy matters as much as the fundraising headline. "
            "Mistral has built tools that let customers pick which regions process "
            "their AI queries, and has started hosting third-party open-weight models."]},
        {"heading": "Why This Is Happening Now: Sovereign AI Moved From Politics Into Procurement",
         "paragraphs": [
             "This shift is a response to growing concerns, especially in Europe but "
             "not limited to it, about depending too heavily on the United States for "
             "critical tech, at a time when AI regulation and AI product politics are "
             "both intensifying.",
             "That is also why the investor mix matters. The round carries geopolitical "
             "undertones while still being international in composition, with American "
             "backers alongside European ones."]},
        {"heading": "The Deeper Bet: An Infrastructure and Control Story", "paragraphs": [
            "The goal isn't to win by building a single consumer product that dominates "
            "attention; it's to become the trusted layer for governments and regulated "
            "enterprises that want frontier-grade AI with bounded dependence.",
            "If customers can mandate where inference happens, and can choose among "
            "open-weight models hosted in controlled regions, you get a menu of "
            "deployment patterns that looks like a traditional infrastructure decision."]},
        {"heading": "What This Means for Enterprises Watching AI Risk and Cost",
         "paragraphs": [
             "This matters even if you're not in government or a heavily regulated "
             "industry, because sovereign patterns tend to become defaults once large "
             "buyers normalize them.",
             "It also changes the cost conversation. The biggest cost drivers become "
             "operations, compliance overhead, and the ability to standardize "
             "deployments across geographies, not just token pricing."]},
        {"heading": "Practical Takeaways", "paragraphs": [
            "If you're planning AI adoption for 2026 and beyond, the useful question is "
            "what operating constraints are becoming normal, and which vendors can meet "
            "them without you building an entire governance layer yourself."],
         "bullets": [
             "If a regulator or internal policy requires inference residency, can your "
             "stack prove where requests are processed, and enforce it by design?",
             "Are you selecting an AI vendor, or an AI operating model: multi-model, "
             "open-weight, region-scoped, auditable?",
             "If you need optionality, what's your escape hatch: model portability, "
             "eval portability, or only contractual promises?"]},
    ],
    "cta": ("If your team is evaluating AI vendors against data residency, inference "
            "location, or regional compliance requirements, Example Media can help you "
            "turn \"sovereign AI\" from a checkbox into an actual architecture decision."),
}

FAQ = [
    {"question": "What happened, in one sentence?",
     "answer": "Mistral raised 3 billion euros at a valuation above 21 billion to scale "
               "compute and infrastructure while doubling down on a sovereign AI "
               "strategy focused on controlling where AI workloads are processed."},
    {"question": "Who led the round?",
     "answer": "The Series D was led by Samsung Electronics, with the EQT-managed "
               "Scaleup Europe Fund and PSG Equity as co-leads."},
    {"question": "What is \"sovereign AI\" in practical enterprise terms?",
     "answer": "It maps to controllable deployment constraints, especially where "
               "inference runs, and reduced strategic dependency on a single foreign "
               "tech stack."},
    {"question": "What's the one product move worth paying attention to?",
     "answer": "Mistral's tools that let customers choose which regions process their AI "
               "queries, plus its move to host third-party open-weight models."},
    {"question": "Is Mistral positioning as a consumer ChatGPT competitor?",
     "answer": "No. Mistral says its goal is not to build a \"European ChatGPT.\""},
    {"question": "Is this only relevant to European companies?",
     "answer": "No. Sovereignty is a broader concern in Europe and elsewhere, tied to "
               "rising dependence concerns and intensifying AI regulation politics."},
]

IMAGE = {
    "url": "https://blog.example.com/images/mistral-eur3b-sovereign-ai-banner.jpg",
    "alt": ("Illustration of Mistral's EUR 3B sovereign AI strategy across Europe, "
            "showing regional data centers, connected infrastructure, and protected "
            "AI workloads"),
}

REFERENCES = [{
    "title": "Mistral raises EUR 3B as sovereign AI becomes big business",
    "url": ("https://techcrunch.com/2026/09/08/"
            "mistral-raises-e3b-as-sovereign-ai-becomes-big-business/"),
    "publisher": "TechCrunch",
}]

KEYWORDS = ["sovereign ai", "mistral funding", "regional inference",
            "enterprise ai infrastructure"]

if __name__ == "__main__":
    built = build_schema(ARTICLE, FAQ, IMAGE, REFERENCES, keywords=KEYWORDS, cfg=cfg)
    print("validation issues:", built["validation"]["issues"] or "none")

    audit = seo_audit(built["html_body"], "sovereign ai",
                      secondary_keywords=KEYWORDS[1:],
                      meta_title="Mistral's EUR 3B Raise Shows Sovereign AI Is Default",
                      meta_description=ARTICLE["description"],
                      slug=ARTICLE["slug"], headline=ARTICLE["headline"], cfg=cfg)
    print(f"seo score: {audit['score']}/100 "
          f"({audit['passed']}/{audit['total_checks']} checks)")
    for item in audit["must_fix"]:
        print("  MUST FIX:", item["check"], "-", item["detail"])

    saved = save_and_present(
        slug=ARTICLE["slug"], html_body=built["html_body"],
        json_ld_article=built["json_ld_article"], json_ld_faq=built["json_ld_faq"],
        title=ARTICLE["headline"], description=ARTICLE["description"],
        meta={**built["meta"], "seo": {**audit, "primary_keyword": "sovereign ai",
                                       "secondary_keywords": KEYWORDS[1:]},
              "references": REFERENCES},
        cfg=cfg)
    print("written to:", saved["folder"])
