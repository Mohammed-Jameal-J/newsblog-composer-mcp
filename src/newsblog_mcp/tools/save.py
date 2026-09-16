"""Tool 7 - save_and_present. Writes the assembled package to disk.

It also composes `display_verbatim`: the finished post as the user should see it
in the chat. Returning only file paths was not enough - a caller handed a folder
and a next_step writes a summary of the article instead of showing it, and the
person who asked for a blog post ends up reading four bullet points about the
blog post they cannot see. The article is the deliverable, so this tool now hands
back the article.
"""
from __future__ import annotations

import json
import shutil
from datetime import datetime, timezone
from html import unescape
from html.parser import HTMLParser
from pathlib import Path

from ..config import CONFIG, Config
from ..textutil import normalize, slugify

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


class _ToMarkdown(HTMLParser):
    """Render the house body format back to readable markdown.

    Only the tags the body template actually emits are handled - h1/h2/h3, p,
    ul/ol/li, strong/em, a, img. Anything else contributes its text and nothing
    else, which is the right failure mode: an unknown wrapper must never swallow
    a paragraph.

    The point is to show the person the article without asking the model to
    retype it. Retyping is where drift comes from - a model asked to "show the
    post" will paraphrase it, and then what is on screen is not what is in the
    file.
    """

    _BLOCK = {"p", "h1", "h2", "h3", "h4", "li", "div", "blockquote", "figcaption"}

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.blocks: list[str] = []
        self._kinds: list[str] = []
        self._buf: list[str] = []
        self._tag: str = ""
        self._list: list[str] = []
        self._index: list[int] = []
        self._skip = 0

    # -- helpers ---------------------------------------------------------
    def _flush(self) -> None:
        text = normalize("".join(self._buf))
        self._buf.clear()
        if not text:
            self._tag = ""
            return
        tag = self._tag
        kind = "block"
        if tag in ("h1", "h2"):
            block = f"## {text}"
        elif tag in ("h3", "h4"):
            block = f"### {text}"
        elif tag == "li":
            kind = "li"
            if self._list and self._list[-1] == "ol":
                self._index[-1] += 1
                block = f"{self._index[-1]}. {text}"
            else:
                block = f"- {text}"
        elif tag == "blockquote":
            block = f"> {text}"
        else:
            block = text
        self.blocks.append(block)
        self._kinds.append(kind)
        self._tag = ""

    # -- parser hooks ----------------------------------------------------
    def handle_starttag(self, tag: str, attrs: list) -> None:
        if tag in ("script", "style"):
            self._skip += 1
            return
        if self._skip:
            return
        a = dict(attrs)
        if tag == "img":
            alt = normalize(a.get("alt", ""))
            src = a.get("src", "")
            if src:
                self.blocks.append(f"![{alt}]({src})")
                self._kinds.append("block")
            return
        if tag == "br":
            self._buf.append(" ")
            return
        if tag in ("ul", "ol"):
            self._flush()
            self._list.append(tag)
            self._index.append(0)
            return
        if tag in ("strong", "b"):
            self._buf.append("**")
            return
        if tag in ("em", "i"):
            self._buf.append("*")
            return
        if tag == "a":
            self._buf.append("[")
            self._href = a.get("href", "")
            return
        if tag in self._BLOCK:
            self._flush()
            self._tag = tag

    def handle_endtag(self, tag: str) -> None:
        if tag in ("script", "style"):
            self._skip = max(0, self._skip - 1)
            return
        if self._skip:
            return
        if tag in ("ul", "ol"):
            self._flush()
            if self._list:
                self._list.pop()
                self._index.pop()
            return
        if tag in ("strong", "b"):
            self._buf.append("**")
            return
        if tag in ("em", "i"):
            self._buf.append("*")
            return
        if tag == "a":
            self._buf.append(f"]({getattr(self, '_href', '')})")
            return
        if tag in self._BLOCK:
            self._flush()

    def handle_data(self, data: str) -> None:
        if not self._skip:
            self._buf.append(data)

    def close(self) -> None:  # type: ignore[override]
        super().close()
        self._flush()

    @property
    def markdown(self) -> str:
        """Consecutive list items are joined with a single newline.

        Separating them by a blank line makes markdown render a loose list, with
        every bullet wrapped in its own paragraph and spaced apart. It reads as a
        formatting bug in the finished post.
        """
        out: list[str] = []
        previous = ""
        for block, kind in zip(self.blocks, self._kinds):
            if not block.strip():
                continue
            if out:
                out.append("\n" if kind == "li" and previous == "li" else "\n\n")
            out.append(block)
            previous = kind
        return "".join(out)


def body_to_markdown(html_body: str) -> str:
    """The article as readable markdown, for showing in the chat."""
    parser = _ToMarkdown()
    parser.feed(unescape(html_body or ""))
    parser.close()
    return parser.markdown


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

    # Refuse rather than warn. Accepting a missing pack meant a caller could skip
    # build_publishing_pack entirely and still get a finished-looking package -
    # and since the banner question lives in that tool, skipping it also skipped
    # the question. One omission, four things missing from what the user sees:
    # permalink, tags, banner URL and the image prompt, plus a banner style they
    # were never asked about. A warning did not stop it; a refusal does.
    if pack and not pack.get("ready_for_save", True):
        return {
            "error": "banner_style_not_chosen",
            "message": (
                "The user has not been asked which banner style they want, so the "
                "pack carries no image prompt and nothing has been written to "
                "disk. Show them the styles in the pack's "
                "ask_the_user_about_the_image.options, wait for their answer, then "
                "call build_publishing_pack again with image_style set to what "
                "they picked. Do not choose a style yourself - the banner is the "
                "first thing a reader sees and it is the user's call."
            ),
            "options": (pack.get("ask_the_user_about_the_image") or {}).get("options"),
            "next_tool": "build_publishing_pack",
        }

    if not pack:
        return {
            "error": "pack_required",
            "message": (
                "Call build_publishing_pack first and pass its result as `pack`. "
                "Without it there is no permalink, no tags, no banner URL and no "
                "image prompt to show the user, and they have not been asked what "
                "the banner should look like. Nothing has been written to disk."
            ),
            "next_tool": "build_publishing_pack",
            "then": "Call save_and_present again with pack set.",
        }

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

    pack = pack or {}
    article_markdown = body_to_markdown(html_body)
    display = _display_block(
        folder=folder,
        article_markdown=article_markdown,
        title=title or pack.get("title") or slug,
        description=description or pack.get("meta_description", ""),
        pack=pack,
        meta={**(meta or {}), "_banner_style": pack.get("image_style_used")
              if pack.get("image_style_chosen_by_user") else None},
    )

    result = {
        "SHOW_THIS_TO_THE_USER": display,
        "how_to_present": (
            "Two things, in this order.\n\n"
            "1. Create an artifact of type text/html - an HTML FILE, not markdown "
            "- whose entire content is `preview_html`, copied byte for byte, "
            "titled with the post's headline. Do NOT build a markdown artifact "
            "out of `article_markdown`: markdown renders read-only, so the user "
            "loses the code view, and what they see stops matching the file on "
            "disk. An HTML artifact gives both views behind one toggle - the "
            "laid-out post for the writer, the markup and JSON-LD for the "
            "developer - and it is the same bytes as index.html.\n\n"
            "2. Print SHOW_THIS_TO_THE_USER in your reply exactly as it is. It "
            "carries the title, permalink, meta description, tags, banner URL, "
            "where the files were saved, the article and the image prompt, in the "
            "order the user wants them. Do not summarise it, do not drop lines "
            "from it, do not shorten the article, and do not replace it with a "
            "list of what the post covers. Add your own notes after it, never "
            "instead of it."
        ),
        "preview_html": page,
        "preview_note": (
            "A complete standalone page: meta description, canonical, Open Graph "
            "and Twitter tags, both JSON-LD blocks, and the styled body. Safe to "
            "put straight into an artifact."
        ),
        "folder": str(folder),
        "paths": written,
        "paste_file": str(folder / "paste-into-blogger.html"),
        "article_markdown": article_markdown,
        "word_count": len(article_markdown.split()),
        "next_step": (
            "After showing the post: paste-into-blogger.html goes into the post's "
            "HTML view - it carries both JSON-LD blocks and the styled body. "
            "publish-pack.md has the same title, labels and permalink in a file, "
            "and report.md summarises the verification, human score and SEO score."
        ),
    }

    warnings = _unfinished(pack, meta or {}, result["word_count"])
    if warnings:
        result["before_the_user_publishes"] = warnings
    return result


def _checks_table(meta: dict, article_markdown: str) -> list[str]:
    """Verification, SEO and AI-detection numbers, where the user can see them.

    These were being written to report.md and nowhere else, so a person reading
    the chat had no idea whether the post had been audited at all. A missing
    number is shown as missing rather than omitted - a blank row is a prompt to
    go and run the step; a row that simply is not there reads as "fine".
    """
    verification = meta.get("verification") or {}
    seo = meta.get("seo") or {}
    scores = meta.get("human_score") or {}
    words = len(article_markdown.split())

    publishers = verification.get("independent_publishers") or []
    if verification:
        verdict = ("corroborated" if verification.get("is_legit") else "NOT corroborated")
        sources = (f"**{verdict}** - {len(publishers)} independent "
                   f"publisher{'s' if len(publishers) != 1 else ''}"
                   + (f" ({', '.join(publishers[:4])})" if publishers else ""))
    else:
        sources = "_not recorded - pass the verify_news result in `meta.verification`_"

    if seo:
        must = seo.get("must_fix") or []
        seo_line = (f"**{seo.get('score', '?')}/100** "
                    f"({seo.get('passed', '?')}/{seo.get('total_checks', '?')} checks"
                    + (f", {len(must)} must-fix" if must else ", nothing must-fix") + ")")
    else:
        seo_line = "_not audited - run seo_audit and pass it in `meta.seo`_"

    if scores.get("is_real_detector"):
        after = scores.get("after")
        human = (f"**{after}/100 human** "
                 f"(detector: {scores.get('detector_used', 'unknown')})")
    elif scores:
        human = (f"**Not measured.** No detector key is set, so no detector has read "
                 f"this. Local style score {scores.get('after', '?')}/100 - that is "
                 f"cliche density and sentence rhythm, not a prediction of what a "
                 f"detector will say.")
    else:
        human = ("**Not measured.** Set GPTZERO_API_KEY or SAPLING_API_KEY for a real "
                 "reading.")

    ai_words = scores.get("clean_of_ai_words")
    if ai_words is None:
        stock = "_not checked - run find_ai_words_"
    elif ai_words:
        stock = "**none found**"
    else:
        stock = f"**{scores.get('ai_word_count', '?')} still present**"

    banner_style = meta.get("_banner_style")
    length = f"**{words} words**" + ("" if 1000 <= words <= 1300
                                     else " - house target is 1000-1300")

    return [
        "| | |", "|---|---|",
        f"| Sources | {sources} |",
        *([f"| Banner style | **{banner_style}**, chosen by you |"]
          if banner_style else []),
        f"| Length | {length} |",
        f"| SEO | {seo_line} |",
        f"| Stock AI phrasing | {stock} |",
        f"| AI detection | {human} |",
    ]


def _display_block(folder: Path, article_markdown: str, title: str,
                   description: str, pack: dict, meta: dict) -> str:
    """The seven things, in the order the user asked for them, every time."""
    labels = pack.get("labels_line") or ", ".join(pack.get("labels") or []) or "(none)"
    permalink = pack.get("permalink_slug") or meta.get("slug", "")
    full_url = pack.get("full_url") or meta.get("canonical", "")
    banner = pack.get("suggested_image_url") or meta.get("image", "")
    prompt = pack.get("gemini_image_prompt", "")

    lines = [
        f"## {title}", "",
        f"**Permalink:** `{permalink}`" + (f"  \n**Full URL:** {full_url}" if full_url else ""),
        "",
        f"**Meta description:** {description}"
        + (f" _({len(description)} characters)_" if description else ""),
        "",
        f"**Tags:** {labels}",
        "",
        f"**Banner goes to:** `{banner}`" if banner else "**Banner:** not set yet",
        "",
        f"**Saved to:** `{folder}`",
        "",
        "---", "",
        "### Checks", "",
        *_checks_table(meta, article_markdown),
        "",
        "---", "",
        "### Blog content", "",
        article_markdown or "_(no body was passed to save_and_present)_",
        "", "---", "",
    ]
    if prompt:
        lines += ["### Image prompt", "",
                  "```", prompt, "```", ""]
    return "\n".join(lines)


def _unfinished(pack: dict, meta: dict, word_count: int) -> list[str]:
    """Things that are wrong but do not stop the file being written.

    Returned rather than raised: the package on disk is still useful, and a user
    who wanted a draft should get the draft plus the truth about it.
    """
    out: list[str] = []
    if not pack:
        out.append(
            "No pack was passed, so the title, permalink, tags and image prompt "
            "are missing from what the user sees. Call build_publishing_pack and "
            "pass its result as `pack`.")
    elif pack.get("image_direction_required"):
        missing = pack.get("image_still_needs") or ["style", "scene"]
        out.append(
            f"The banner {' and '.join(missing)} "
            f"{'were' if len(missing) > 1 else 'was'} never chosen by the user - "
            f"{'the style is a placeholder default' if 'style' in missing else 'the scene was derived from keywords'}. "
            f"Ask them before they publish, then call build_publishing_pack again "
            f"with image_style{' and image_concepts' if 'scene' in missing else ''} set.")
    if word_count and word_count < 1000:
        out.append(
            f"The body is {word_count} words. The house target is 1000-1300, so "
            f"this is short - say so rather than presenting it as finished.")
    seo = meta.get("seo") or {}
    for issue in seo.get("must_fix", []):
        out.append(f"SEO must-fix: {issue.get('check')} - {issue.get('detail', '')}")
    return out


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
