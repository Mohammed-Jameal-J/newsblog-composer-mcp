"""Tool 9 - build_schema.

Deterministic templating only, no model call. Renders the house body format and
both JSON-LD blocks, then runs the "nothing should mismatch" checks: FAQ parity
between the HTML and the FAQPage schema, image parity between the <img> tag and
NewsArticle.image, and references that are real publisher URLs.
"""
from __future__ import annotations

import html as html_lib
import json
import re
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from jinja2 import Environment, FileSystemLoader, select_autoescape

from ..config import CONFIG, Config
from ..textutil import normalize, slugify

_AGGREGATOR_RE = re.compile(
    r"://(?:news\.google\.com|www\.bing\.com/news|news\.yahoo\.com|www\.msn\.com/[a-z-]+/news)")
_TEMPLATE_DIR = Path(__file__).resolve().parents[1] / "templates"
_ENV = Environment(
    loader=FileSystemLoader(str(_TEMPLATE_DIR)),
    autoescape=select_autoescape(["html", "xml"]),
    trim_blocks=True,
    lstrip_blocks=True,
)


def _tz(cfg: Config):
    try:
        return ZoneInfo(cfg.site_timezone)
    except (ZoneInfoNotFoundError, ValueError):
        return ZoneInfo("UTC")


def _now_iso(cfg: Config) -> str:
    return datetime.now(_tz(cfg)).replace(microsecond=0).isoformat()


def _localise(value: str, cfg: Config) -> str:
    """Render a timestamp in the site's timezone, so datePublished carries the
    offset a reader of the blog would expect rather than a bare Z."""
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return value
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=_tz(cfg))
    return parsed.astimezone(_tz(cfg)).replace(microsecond=0).isoformat()


def _display_date(iso: str) -> str:
    try:
        parsed = datetime.fromisoformat(iso.replace("Z", "+00:00"))
    except ValueError:
        return iso
    return f"{parsed.strftime('%B')} {parsed.day}, {parsed.year}"


def _permalink(cfg: Config, slug: str, published: str) -> str:
    try:
        parsed = datetime.fromisoformat(published.replace("Z", "+00:00"))
    except ValueError:
        parsed = datetime.now(_tz(cfg))
    return cfg.permalink_pattern.format(
        base=cfg.site_base_url.rstrip("/"), slug=slug,
        yyyy=f"{parsed.year:04d}", mm=f"{parsed.month:02d}", dd=f"{parsed.day:02d}",
    )


def _split_cta(text: str, link_text: str) -> tuple[str, str]:
    """The closing CTA carries one link. Split the sentence around the anchor
    text so the template can wrap exactly that phrase."""
    if link_text and link_text in text:
        before, _, after = text.partition(link_text)
        return before, after
    return text, ""


def build_schema(
    article: dict,
    faq: list[dict],
    image: dict,
    references: list[dict],
    keywords: list[str] | None = None,
    cfg: Config | None = None,
) -> dict:
    cfg = cfg or CONFIG
    headline = normalize(article.get("headline", ""))
    slug = article.get("slug") or slugify(headline)
    date_published = _localise(article.get("date_published") or _now_iso(cfg), cfg)
    date_modified = _localise(article.get("date_modified") or date_published, cfg)
    canonical = article.get("url") or _permalink(cfg, slug, date_published)
    image_url = normalize(image.get("url", ""))
    include_h1 = bool(article.get("include_h1", cfg.body_includes_h1))

    cta_text = normalize(article.get("cta", ""))
    cta_url = article.get("cta_url", cfg.cta_url)
    cta_link_text = article.get("cta_link_text", cfg.cta_link_text)
    cta_before, cta_after = _split_cta(cta_text, cta_link_text)

    ctx_article = {
        "headline": headline,
        "author": article.get("author") or cfg.author_name,
        "date_published": date_published,
        "date_display": _display_date(date_published),
        "include_h1": include_h1,
        "intro": [normalize(p) for p in article.get("intro", []) if normalize(p)],
        "sections": [
            {"heading": normalize(s.get("heading", "")),
             "paragraphs": [normalize(p) for p in s.get("paragraphs", []) if normalize(p)],
             "bullets": [normalize(b) for b in s.get("bullets", []) if normalize(b)]}
            for s in article.get("sections", [])
        ],
        "cta": cta_text,
        "cta_before": cta_before,
        "cta_after": cta_after,
        "cta_url": cta_url if (cta_url and cta_link_text and cta_link_text in cta_text) else "",
        "cta_link_text": cta_link_text,
    }
    ctx_faq = [
        {"question": normalize(i.get("question", "")), "answer": normalize(i.get("answer", ""))}
        for i in faq
    ]
    ctx_image = {
        "url": image_url,
        "alt": normalize(image.get("alt", "")) or headline,
        "title": normalize(image.get("title", "")) or headline,
    }
    ctx_refs = [
        {"title": normalize(r.get("title", "")) or r.get("url", ""),
         "url": r.get("url", ""),
         "publisher": normalize(r.get("publisher", ""))}
        for r in references
    ]

    html_body = _ENV.get_template("article.html.j2").render(
        article=ctx_article, faq=ctx_faq, image=ctx_image, references=ctx_refs
    )
    word_count = len(re.sub(r"<[^>]+>", " ", html_body).split())
    keywords = [normalize(k) for k in (keywords or []) if normalize(k)]

    publisher: dict = {
        "@type": "Organization",
        "name": cfg.publisher_name,
        "logo": {"@type": "ImageObject", "url": cfg.publisher_logo_url},
    }
    if cfg.publisher_url:
        publisher = {"@type": "Organization", "name": cfg.publisher_name,
                     "url": cfg.publisher_url,
                     "logo": {"@type": "ImageObject", "url": cfg.publisher_logo_url}}

    json_ld_article = {
        "@context": "https://schema.org",
        "@type": "NewsArticle",
        "headline": headline,
        "description": normalize(article.get("description", "")),
        "image": image_url,
        "datePublished": date_published,
        "dateModified": date_modified,
        "author": {"@type": "Person", "name": ctx_article["author"]},
        "publisher": publisher,
        "mainEntityOfPage": {"@type": "WebPage", "@id": canonical},
    }
    if keywords:
        json_ld_article["keywords"] = ", ".join(keywords)
    if article.get("section"):
        json_ld_article["articleSection"] = normalize(article["section"])
    json_ld_article["inLanguage"] = article.get("language") or cfg.default_language
    json_ld_article["wordCount"] = word_count

    json_ld_faq = {
        "@context": "https://schema.org",
        "@type": "FAQPage",
        "mainEntity": [
            {"@type": "Question", "name": i["question"],
             "acceptedAnswer": {"@type": "Answer", "text": i["answer"]}}
            for i in ctx_faq
        ],
    }

    issues = _validate(html_body, json_ld_article, json_ld_faq, ctx_article, ctx_faq,
                       ctx_image, ctx_refs, cfg, include_h1)

    return {
        "meta": {
            "title": normalize(article.get("meta_title", "")) or headline,
            "description": normalize(article.get("description", "")),
            "canonical": canonical,
            "image": image_url,
            "keywords": keywords,
            "slug": slug,
            "headline": headline,
            "date_published": date_published,
        },
        "word_count": word_count,
        "json_ld_article": json.dumps(json_ld_article, indent=2, ensure_ascii=False),
        "json_ld_faq": json.dumps(json_ld_faq, indent=2, ensure_ascii=False),
        "html_body": html_body,
        "paste_block": (
            f'<script type="application/ld+json">\n'
            f'{json.dumps(json_ld_article, indent=2, ensure_ascii=False)}\n'
            f'</script>\n\n'
            f'<script type="application/ld+json">\n'
            f'{json.dumps(json_ld_faq, indent=2, ensure_ascii=False)}\n'
            f'</script>\n\n'
            f'{html_body}'
        ),
        "canonical_url": canonical,
        "slug": slug,
        "validation": {"ok": not issues, "issues": issues},
    }


def _validate(html_body, ld_article, ld_faq, article, faq, image, refs, cfg,
              include_h1) -> list[str]:
    issues: list[str] = []
    plain = html_lib.unescape(html_body)

    if not article["headline"]:
        issues.append("headline is empty")
    if not ld_article["description"]:
        issues.append("description is empty (needed for the NewsArticle schema)")
    elif not 110 <= len(ld_article["description"]) <= 160:
        issues.append(
            f"description is {len(ld_article['description'])} characters; it is used as "
            f"the meta description, so aim for 110-160")

    if not image["url"]:
        issues.append("no image URL supplied; NewsArticle.image would be empty")
    else:
        srcs = re.findall(r'<img[^>]+src="([^"]+)"', html_body)
        if image["url"] not in srcs:
            issues.append("the <img> src does not match the image passed in")
        if ld_article["image"] != image["url"]:
            issues.append("NewsArticle.image does not match the <img> src")
        if not image["alt"]:
            issues.append("banner has no alt text")

    if include_h1 and len(re.findall(r"<h1[^>]*>", html_body)) != 1:
        issues.append("BODY_INCLUDES_H1 is set but the body does not contain exactly one H1")
    if not include_h1 and re.search(r"<h1[^>]*>", html_body):
        issues.append("body contains an H1 but the platform is expected to render one")

    if not faq:
        issues.append("no FAQ entries supplied")
    elif not 4 <= len(faq) <= 8:
        issues.append(f"{len(faq)} FAQ entries; the house style calls for 4-8")
    if len(ld_faq["mainEntity"]) != len(faq):
        issues.append("FAQPage entry count does not match the FAQ list")

    rendered_questions = [normalize(html_lib.unescape(q))
                          for q in re.findall(r"<h3[^>]*>(.*?)</h3>", html_body, re.S)]
    for item in faq:
        if not item["question"] or not item["answer"]:
            issues.append(f"FAQ entry is missing a question or answer: {item}")
        elif item["question"] not in rendered_questions:
            issues.append(f"FAQ question missing from rendered HTML: {item['question'][:60]!r}")
    for entry in ld_faq["mainEntity"]:
        if entry["name"] not in rendered_questions:
            issues.append(f"FAQPage question not present in HTML: {entry['name'][:60]!r}")

    if not refs:
        issues.append("no references supplied; the References section would be empty")
    for ref in refs:
        if not ref["url"].startswith("http"):
            issues.append(f"reference is not a real fetched URL: {ref['url']!r}")
        elif _AGGREGATOR_RE.search(ref["url"]):
            issues.append(
                f"reference points at an aggregator redirect, not the publisher: "
                f"{ref['url'][:70]}... Use verify_news reference_candidates, which "
                f"only contains real publisher URLs.")
        elif ref["url"] not in plain:
            issues.append(f"reference missing from rendered HTML: {ref['url']}")

    sections = article["sections"]
    if not sections:
        issues.append("no <h2> sections supplied")
    elif not 2 <= len(sections) <= 4:
        issues.append(f"{len(sections)} body sections; the house style calls for 2-3")
    else:
        # Length is checked per section, not just in total. Six paragraphs under
        # one heading reads as a wall however good the sentences are, and two
        # under one heading means the heading is doing the work.
        heavy = [s.get("heading", "?") for s in sections
                 if len(s.get("paragraphs") or []) > 4]
        thin = [s.get("heading", "?") for s in sections
                if len(s.get("paragraphs") or []) < 2 and not s.get("bullets")]
        if heavy:
            issues.append("section(s) running over 4 paragraphs; split them: "
                          + ", ".join(heavy[:3]))
        if thin:
            issues.append("section(s) under 2 paragraphs: " + ", ".join(thin[:3]))
    if len(article["intro"]) != 2:
        issues.append(f"{len(article['intro'])} intro paragraphs; the house style calls for 2")
    if not article["cta"]:
        issues.append("no closing CTA paragraph")
    elif cfg.cta_link_text and not article["cta_url"]:
        issues.append(
            f"the CTA does not contain the link text {cfg.cta_link_text!r}, so it "
            f"rendered without a link to {cfg.cta_url}")

    if not cfg.publisher_logo_url:
        issues.append("PUBLISHER_LOGO_URL is unset, so publisher.logo.url is empty")
    return issues
