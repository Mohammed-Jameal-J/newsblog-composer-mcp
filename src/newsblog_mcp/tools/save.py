"""Tool 7 - save_and_present. Writes the assembled package to disk."""
from __future__ import annotations

import json
import shutil
from datetime import datetime, timezone
from pathlib import Path

from ..config import CONFIG, Config
from ..textutil import slugify

_PAGE = """<!doctype html>
<html lang="{lang}">
<head>
<meta charset="utf-8" />
<meta name="viewport" content="width=device-width, initial-scale=1" />
<title>{title}</title>
<meta name="description" content="{description}" />
{canonical_tag}
<meta name="robots" content="index, follow, max-image-preview:large" />
<meta property="og:type" content="article" />
<meta property="og:title" content="{title}" />
<meta property="og:description" content="{description}" />
{og_url_tag}
{og_image_tag}
<meta name="twitter:card" content="summary_large_image" />
<meta name="twitter:title" content="{title}" />
<meta name="twitter:description" content="{description}" />
{twitter_image_tag}
<script type="application/ld+json">
{ld_article}
</script>
<script type="application/ld+json">
{ld_faq}
</script>
</head>
<body>
{body}
</body>
</html>
"""


def _attr(value: str) -> str:
    return (value or "").replace("&", "&amp;").replace('"', "&quot;").replace("<", "&lt;")


def save_and_present(
    slug: str,
    html_body: str,
    json_ld_article: str = "",
    json_ld_faq: str = "",
    image_path: str = "",
    meta: dict | None = None,
    pack: dict | None = None,
    title: str = "",
    description: str = "",
    canonical_url: str = "",
    image_url: str = "",
    language: str = "",
    cfg: Config | None = None,
) -> dict:
    cfg = cfg or CONFIG
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    folder = cfg.output_dir / f"{slugify(slug or title)}-{stamp}"
    folder.mkdir(parents=True, exist_ok=True)
    written: list[str] = []

    canonical = canonical_url or (meta or {}).get("canonical", "")
    social_image = image_url or (meta or {}).get("image", "")
    page = _PAGE.format(
        lang=_attr(language or cfg.default_language),
        title=_attr(title or slug),
        description=_attr(description),
        canonical_tag=(f'<link rel="canonical" href="{_attr(canonical)}" />'
                       if canonical else "<!-- no canonical URL supplied -->"),
        og_url_tag=(f'<meta property="og:url" content="{_attr(canonical)}" />'
                    if canonical else ""),
        og_image_tag=(f'<meta property="og:image" content="{_attr(social_image)}" />'
                      if social_image else ""),
        twitter_image_tag=(f'<meta name="twitter:image" content="{_attr(social_image)}" />'
                           if social_image else ""),
        ld_article=json_ld_article or "{}",
        ld_faq=json_ld_faq or "{}",
        body=html_body,
    )
    # The block to paste straight into Blogger: both JSON-LD scripts followed by
    # the styled body, exactly as the house format expects it.
    paste_block = "\n\n".join(part for part in (
        f'<script type="application/ld+json">\n{json_ld_article}\n</script>'
        if json_ld_article else "",
        f'<script type="application/ld+json">\n{json_ld_faq}\n</script>'
        if json_ld_faq else "",
        html_body,
    ) if part)

    for name, content in (
        ("index.html", page),
        ("paste-into-blogger.html", paste_block),
        ("body.html", html_body),
        ("newsarticle.jsonld", json_ld_article),
        ("faqpage.jsonld", json_ld_faq),
    ):
        if content:
            path = folder / name
            path.write_text(content, encoding="utf-8")
            written.append(str(path))

    if image_path:
        source = Path(image_path)
        if source.exists():
            target = folder / source.name
            shutil.copy2(source, target)
            written.append(str(target))
        else:
            written.append(f"MISSING image_path: {image_path}")

    if pack:
        from .pack import render_pack_markdown
        pack_path = folder / "publish-pack.md"
        pack_path.write_text(render_pack_markdown(pack), encoding="utf-8")
        written.append(str(pack_path))

    if meta:
        path = folder / "meta.json"
        path.write_text(json.dumps(meta, indent=2, ensure_ascii=False), encoding="utf-8")
        written.append(str(path))

        report = _report(title or slug, meta)
        report_path = folder / "report.md"
        report_path.write_text(report, encoding="utf-8")
        written.append(str(report_path))

    return {
        "folder": str(folder),
        "paths": written,
        "paste_file": str(folder / "paste-into-blogger.html"),
        "next_step": (
            "Open publish-pack.md first: it has the title, labels, permalink and the "
            "Gemini image prompt. Generate and upload the banner, then paste "
            "paste-into-blogger.html into the post's HTML view - it carries both "
            "JSON-LD blocks and the styled body. report.md summarises the "
            "verification, human score and SEO score."
        ),
    }


def _report(title: str, meta: dict) -> str:
    """A one-page summary of how the post was produced, for the person who has
    to decide whether to publish it."""
    lines = [f"# {title}", ""]
    if meta.get("author") or meta.get("tone_label"):
        lines += [f"By **{meta.get('author', '')}** · voice: "
                  f"**{meta.get('tone_label', meta.get('tone', 'unset'))}**", ""]

    verification = meta.get("verification") or {}
    if verification:
        lines += [
            "## Verification", "",
            f"- Verdict: **{'corroborated' if verification.get('is_legit') else 'NOT corroborated'}**",
            f"- Confidence: {verification.get('confidence', 'unknown')}",
            f"- Independent publishers: {', '.join(verification.get('independent_publishers', [])) or 'none'}",
            f"- Reasoning: {verification.get('reasoning', '')}", "",
        ]

    scores = meta.get("human_score") or {}
    if scores:
        real = scores.get("is_real_detector")
        lines += ["## AI detection", ""]
        if real:
            before, after = scores.get("before"), scores.get("after")
            if before is not None and after is not None:
                lines.append(f"- Before humanising: **{before}** / 100 human")
                lines.append(f"- After humanising: **{after}** / 100 human "
                             f"({after - before:+.1f})")
            elif after is not None:
                lines.append(f"- Human score: **{after}** / 100")
            lines.append(f"- Detector: {scores.get('detector_used', 'unknown')}")
        else:
            lines += [
                "- **Not measured.** No AI-detection key is configured, so no "
                "detector has read this text.",
                f"- Style score (cliche density and sentence rhythm only): "
                f"**{scores.get('after', '?')}** / 100. This is NOT an estimate of "
                f"what a detector will say. Text can score high here and still be "
                f"flagged as AI-generated, because detectors measure how "
                f"predictable the wording is, not how many stock phrases it "
                f"contains.",
                "- Set GPTZERO_API_KEY or SAPLING_API_KEY for a real reading.",
            ]
        clean = scores.get("clean_of_ai_words")
        if clean is not None:
            lines.append(f"- Stock AI phrasing: "
                         f"**{'none found' if clean else str(scores.get('ai_word_count', 0)) + ' still present'}**")
        lines += ["", "> No detector score proves who wrote a text, in either "
                      "direction. Treat any number here as directional.", ""]

    seo = meta.get("seo") or {}
    if seo:
        lines += [
            "## SEO", "",
            f"- Score: **{seo.get('score', '?')}** / 100 "
            f"({seo.get('passed', '?')}/{seo.get('total_checks', '?')} checks)",
            f"- Primary keyword: {seo.get('primary_keyword', '')}",
            f"- Secondary: {', '.join(seo.get('secondary_keywords', []))}",
        ]
        for issue in seo.get("must_fix", []):
            lines.append(f"- MUST FIX: {issue.get('check')}: {issue.get('detail', '')}")
        lines.append("")

    lines += ["## Publishing", "",
              f"- Canonical: {meta.get('canonical', '')}",
              f"- Slug: {meta.get('slug', '')}",
              f"- Published: {meta.get('date_published', '')}",
              f"- Image: {meta.get('image', '')}", ""]

    references = meta.get("references") or []
    if references:
        lines += ["## References", ""]
        lines += [f"{n}. [{r.get('title', r.get('url'))}]({r.get('url')})"
                  for n, r in enumerate(references, 1)]
        lines.append("")

    return "\n".join(lines)
