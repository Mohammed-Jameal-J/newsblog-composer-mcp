"""Full pipeline on a GitHub Blog post, 12 September 2026.

    "Marketing ops as code: Automating events from planning to follow-up on GitHub"

Facts come from the GitHub Blog post by Tomoko Tanaka. Single-source story: the
verification note records that plainly rather than claiming corroboration.

Identity comes from profile.json, set at setup. This run uses a synthetic test
identity (Test User / Example Media) so nothing resembles a real publisher.
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
HEADLINE = "Marketing Ops as Code: How GitHub Runs Events from a Repository"

FACTS = [
    "Tomoko Tanaka, GitHub's regional marketing lead for Japan and Korea, published "
    "the approach on the GitHub Blog on September 11, 2026.",
    "The APAC marketing team runs its event lifecycle inside GitHub, from planning "
    "through post-event follow-up.",
    "The system uses issue forms for structured data capture, labels as workflow "
    "triggers, GitHub Actions for execution, GitHub Projects for tracking, and GitHub "
    "Copilot for planning.",
    "A team runbook written in Markdown as AGENTS.md tells Copilot how the team works.",
    "Individual procedures live in SKILL.md files that Copilot executes.",
    "Copilot drafts campaign details from the runbook, the author approves them, and an "
    "issue is filed with the event-setup label.",
    "Applying that single label triggers an Actions workflow that duplicates landing "
    "pages, generates UTM links, creates invitation emails, opens tracking issues and "
    "updates project boards.",
    "A daily cron-triggered workflow downloads and cleans registrant lists, and screens "
    "invitees against criteria for restricted events.",
    "Two slash commands, lead-upload and event-report, handle attendee export, CRM "
    "formatting and reporting after the event.",
    "A DRY_RUN variable lets the team rehearse a workflow without side effects.",
    "Changes to the skills go through code review like any other change in the "
    "repository.",
    "Event setup dropped from a couple of days to several minutes of automated "
    "processing.",
]

ARTICLE = {
    "headline": HEADLINE,
    "description": ("GitHub's APAC marketing team moved event operations into a "
                    "repository, cutting event setup from days to minutes using Actions "
                    "and Copilot."),
    "slug": "marketing-ops-as-code-github",
    "date_published": "2026-09-12T09:00:00-05:00",
    "section": "Engineering",
    "intro": [
        "GitHub's APAC marketing team has moved its event operations into a repository. "
        "Planning, landing pages, registrant screening, CRM upload and reporting all run "
        "through issues, labels and Actions. Tomoko Tanaka, the regional marketing lead "
        "for Japan and Korea, described the setup on the GitHub Blog on September 11.",
        "The reported result is that event setup dropped from a couple of days to "
        "several minutes of automated processing. The method is less about marketing "
        "than about what happens when a team writes its procedures down in a form a "
        "machine can run.",
    ],
    "sections": [
        {"heading": "The runbook is a file in the repository", "paragraphs": [
            "The team keeps its working practices in AGENTS.md, a Markdown runbook that "
            "tells Copilot how the team operates. Individual procedures live in "
            "SKILL.md files that Copilot executes directly.",
            "That choice is what makes the rest possible. Tanaka's summary of it: \"If "
            "you can write down how you do your work, you can automate it.\""]},
        {"heading": "One label starts the whole event", "paragraphs": [
            "Copilot drafts the campaign details from the runbook. A person approves "
            "them, and an issue is filed carrying the event-setup label.",
            "Applying that label triggers an Actions workflow that duplicates landing "
            "pages, generates UTM links, creates invitation emails, opens tracking "
            "issues and updates the project boards. The label is the button."]},
        {"heading": "The parts that run on their own", "paragraphs": [
            "A daily cron-triggered workflow downloads and cleans registrant lists. For "
            "restricted events it also screens invitees against the criteria for that "
            "event.",
            "After the event, two slash commands finish the job. One handles attendee "
            "export and CRM formatting, the other produces the report."]},
        {"heading": "The safety rails around it", "paragraphs": [
            "A DRY_RUN variable lets the team rehearse a workflow without side effects, "
            "which matters when the workflow sends invitation emails to a real list.",
            "Changes to the skills go through code review like any other change in the "
            "repository. A marketing procedure is now reviewed the way a function is."]},
        {"heading": "What transfers to other teams", "paragraphs": [
            "Nothing here depends on marketing. The pattern is a written runbook, "
            "structured intake, one trigger, and a rehearsal mode."],
         "bullets": [
             "Structured intake first. Issue forms give the automation clean fields "
             "instead of prose it has to interpret.",
             "One trigger, many effects. A single label is easier to teach than a "
             "six-step checklist, and easier to audit afterwards.",
             "A rehearsal mode is not optional once a workflow can email customers. "
             "DRY_RUN is the cheapest part of this system and the one that prevents the "
             "expensive mistake."]},
    ],
    "cta": (f"If your team has procedures that live in someone's head rather than in a "
            f"file, {COMPANY} can help you work out which ones are worth writing down "
            f"first."),
}

FAQ = [
    {"question": "What did GitHub's marketing team actually build?",
     "answer": "An event management system that runs inside GitHub, covering planning, "
               "landing pages, registrant screening, CRM upload and reporting, using "
               "issue forms, labels, Actions, Projects and Copilot."},
    {"question": "What are AGENTS.md and SKILL.md?",
     "answer": "AGENTS.md is the team runbook in Markdown, describing how the team "
               "works. SKILL.md files hold individual procedures that Copilot executes."},
    {"question": "What does applying the event-setup label do?",
     "answer": "It triggers an Actions workflow that duplicates landing pages, generates "
               "UTM links, creates invitation emails, opens tracking issues and updates "
               "the project boards."},
    {"question": "How are registrants handled?",
     "answer": "A daily cron-triggered workflow downloads and cleans registrant lists, "
               "and screens invitees against the criteria for restricted events."},
    {"question": "How much time does it save?",
     "answer": "Event setup dropped from a couple of days to several minutes of "
               "automated processing, according to the post."},
    {"question": "What stops a workflow from doing damage during testing?",
     "answer": "A DRY_RUN variable lets the team rehearse without side effects, and "
               "changes to the skills go through code review like any other change."},
]

IMAGE = {
    "url": f"{PROFILE['image_base_url']}/marketing-ops-as-code-github-banner.jpg",
    "alt": ("A single label on an issue card fanning out into landing pages, emails, "
            "tracking cards and a report, drawn as connected steps"),
}

REFERENCES = [
    {"title": "Marketing ops as code: Automating events from planning to follow-up on "
              "GitHub",
     "url": ("https://github.blog/ai-and-ml/github-copilot/"
             "marketing-ops-as-code-automating-events-from-planning-to-follow-up-on-"
             "github/"),
     "publisher": "The GitHub Blog"},
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

    audit = seo_audit(body, kw["primary_keyword"],
                      secondary_keywords=kw["secondary_keywords"][:4],
                      meta_title="Marketing ops as code: how GitHub runs events from a repo",
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
        image_concepts=("a single tag on a card fanning out into web pages, emails, "
                        "task cards and a chart, clean connected flow, technical "
                        "illustration"),
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
                  "independent_publishers": ["github.blog"],
                  "reasoning": "Single source: the vendor's own engineering blog, "
                               "written by the person who built the system. First-party "
                               "and detailed, but no independent publisher has verified "
                               "the time saving. Medium, not high."},
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
