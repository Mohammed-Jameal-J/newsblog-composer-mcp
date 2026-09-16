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
{panel}
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

    # The audit numbers are required for the same reason the pack is: a caller
    # that can finish without them does finish without them, and the user gets a
    # table with the two numbers they asked for missing. Refusing is what makes
    # seo_audit and score_ai_text actually run.
    _m = meta if isinstance(meta, dict) else {}
    missing_audits = [
        name for name, key in (("seo_audit", "seo"), ("score_ai_text", "human_score"))
        if not isinstance(_m.get(key), dict) or not _m.get(key)
    ]
    if pack and missing_audits:
        return {
            "error": "audit_required",
            "message": (
                f"Run {' and '.join(missing_audits)} on the finished body and pass "
                f"the result(s) in meta, then call this again. Without them the "
                f"user's Checks table has no SEO score and no AI-detection "
                f"reading - the two numbers they look at first. Nothing has been "
                f"written to disk."
            ),
            "meta_keys_needed": [k for n, k in
                                 (("seo_audit", "seo"),
                                  ("score_ai_text", "human_score"))
                                 if n in missing_audits],
            "example": {
                "seo": "the whole dict seo_audit returned",
                "human_score": ("the whole dict score_ai_text returned, including "
                                "is_real_detector and clean_of_ai_words"),
            },
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

    pack = pack or {}
    article_markdown = body_to_markdown(html_body)
    checks_meta = {**(meta or {}), "_banner_style": pack.get("image_style_used")
                   if pack.get("image_style_chosen_by_user") else None}
    checks_rows = _checks_table(checks_meta, article_markdown)

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
        # Nothing but the post. The publishing details and the image prompt were
        # briefly rendered here as insurance against a caller compressing the
        # chat block - but the artifact is what the user reads as the article,
        # and a "Publishing details" section at the bottom of it is clutter in
        # the one place that should look exactly like the finished page. Those
        # details live in the chat block, in publish-pack.md and in report.md.
        panel="",
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

    # Same details as a standalone page on disk, for anyone who wants them in a
    # browser rather than in the chat. Deliberately a separate file so it can
    # never be mistaken for the post.
    if pack:
        try:
            details = folder / "publishing-details.html"
            details.write_text(
                "<!doctype html><meta charset=\"utf-8\">"
                + _panel_html(pack, meta or {}, folder, checks_rows),
                encoding="utf-8")
            written.append(str(details))
        except Exception as exc:  # noqa: BLE001
            written.append(f"publishing-details.html SKIPPED: {exc}")

    if pack:
        from .pack import render_pack_markdown
        pack_path = folder / "publish-pack.md"
        try:
            pack_path.write_text(render_pack_markdown(pack), encoding="utf-8")
            written.append(str(pack_path))
        except Exception as exc:  # noqa: BLE001 - see below
            # A caller handing back a reshaped pack used to raise here and take
            # the whole tool down, losing the article, the schema and every
            # other file with it. The post is what matters; say what went wrong
            # and keep the package.
            written.append(f"publish-pack.md SKIPPED: {type(exc).__name__}: {exc}")

    if meta:
        path = folder / "meta.json"
        path.write_text(json.dumps(meta, indent=2, ensure_ascii=False), encoding="utf-8")
        written.append(str(path))

        report = _report(title or slug, meta)
        report_path = folder / "report.md"
        report_path.write_text(report, encoding="utf-8")
        written.append(str(report_path))

    display = _display_block(
        folder=folder,
        article_markdown=article_markdown,
        title=title or pack.get("title") or slug,
        description=description or pack.get("meta_description", ""),
        pack=pack,
        meta=checks_meta,
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
            "2. Print SHOW_THIS_TO_THE_USER in your reply exactly as it is, "
            "including the Checks table as a TABLE and the image prompt in its "
            "code block. It is deliberately short - the article is in the "
            "artifact, not in here - so there is nothing to condense. Do not "
            "turn the table into a sentence and do not drop the image prompt. It "
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
    def as_dict(value) -> dict:
        """A caller that retypes `meta` by hand can put a string here."""
        return value if isinstance(value, dict) else {}

    verification = as_dict(meta.get("verification"))
    seo = as_dict(meta.get("seo"))
    scores = as_dict(meta.get("human_score"))
    words = len(article_markdown.split())

    publishers = [str(x) for x in (verification.get("independent_publishers") or [])
                  if str(x).strip()]
    if verification:
        verdict = ("corroborated" if verification.get("is_legit") else "NOT corroborated")
        sources = (f"**{verdict}** - {len(publishers)} independent "
                   f"publisher{'s' if len(publishers) != 1 else ''}"
                   + (f" ({', '.join(publishers[:4])})" if publishers else ""))
    else:
        sources = "_not recorded - pass the verify_news result in `meta.verification`_"

    if seo:
        must = seo.get("must_fix") or []
        must = must if isinstance(must, list) else []
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
        f"| Banner style | **{banner_style}**, chosen by you |" if banner_style
        else "| Banner style | _not confirmed - ask which style they want_ |",
        f"| Length | {length} |",
        f"| SEO | {seo_line} |",
        f"| Stock AI phrasing | {stock} |",
        f"| AI detection | {human} |",
    ]



def _panel_html(pack: dict, meta: dict, folder: Path, checks: list[str]) -> str:
    """The publishing details, rendered into the preview page itself.

    The chat block is text a model can compress, and it did: a Checks table came
    back as one prose sentence with the SEO score dropped, and the image prompt
    vanished. The artifact is a file - whatever is in it is what the user sees.
    So everything that must not go missing goes in here as well.
    """
    def esc(value) -> str:
        return _attr("" if value is None else str(value))

    rows = []
    for raw in checks:
        cells = [c.strip() for c in raw.strip().strip("|").split("|")]
        if len(cells) != 2 or set("".join(cells)) <= set("-"):
            continue
        label, value = cells
        # Strip markdown emphasis without touching underscores inside
        # identifiers - a blanket replace turned newspaper_front into
        # newspaperfront, which is not a style anyone can pass back.
        value = value.replace("**", "").strip()
        if value.startswith("_") and value.endswith("_"):
            value = value[1:-1]
        value = value.replace("`", "")
        rows.append(
            f'<tr><td style="padding:6px 14px 6px 0;color:#666;'
            f'white-space:nowrap;vertical-align:top">{esc(label)}</td>'
            f'<td style="padding:6px 0">{esc(value)}</td></tr>')

    prompt = pack.get("gemini_image_prompt")
    prompt_block = (
        f'<pre style="white-space:pre-wrap;background:#f6f6f6;padding:14px;'
        f'border-radius:6px;font-size:13px;line-height:1.6;overflow-x:auto">'
        f'{esc(prompt)}</pre>'
        if prompt else
        '<p style="font-size:14px;color:#666">Not generated - the banner style '
        'was never chosen.</p>')

    fields = [
        ("Permalink", pack.get("permalink_slug") or meta.get("slug", "")),
        ("Full URL", pack.get("full_url") or meta.get("canonical", "")),
        ("Meta description", pack.get("meta_description", "")),
        ("Tags", pack.get("labels_line")
         or ", ".join(pack.get("labels") or []) or "(none)"),
        ("Banner goes to", pack.get("suggested_image_url") or meta.get("image", "")),
        ("Saved to", str(folder)),
    ]
    field_rows = "".join(
        f'<tr><td style="padding:6px 14px 6px 0;color:#666;white-space:nowrap;'
        f'vertical-align:top">{esc(label)}</td>'
        f'<td style="padding:6px 0;word-break:break-word">{esc(value)}</td></tr>'
        for label, value in fields if str(value or "").strip())

    return f"""
<div style="max-width:720px;margin:48px auto 0;padding:24px 0 8px;
  border-top:3px solid #1a1a1a;font-family:Arial,Helvetica,sans-serif;
  color:#1a1a1a">
<h2 style="font-size:18px;margin:0 0 4px">Publishing details</h2>
<p style="font-size:13px;color:#777;margin:0 0 18px">Not part of the post. Do not paste this section into your blog.</p>
<table style="border-collapse:collapse;font-size:14px;width:100%">{field_rows}</table>
<h3 style="font-size:16px;margin:26px 0 8px">Checks</h3>
<table style="border-collapse:collapse;font-size:14px;width:100%">{"".join(rows)}</table>
<h3 style="font-size:16px;margin:26px 0 8px">Image prompt</h3>
{prompt_block}
</div>"""


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
        "The full post is in the artifact above - readable, with the code view "
        "for the markup and JSON-LD." if article_markdown
        else "_(no body was passed to save_and_present)_",
        "", "---", "",
    ]
    if prompt:
        lines += ["### Image prompt", "",
                  "Paste this into Gemini, then upload the result to the banner "
                  "URL above.", "",
                  "```", prompt, "```", ""]
    else:
        lines += ["### Image prompt", "",
                  "_Not generated - the banner style was never chosen._", ""]
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
    seo = meta.get("seo")
    seo = seo if isinstance(seo, dict) else {}
    must = seo.get("must_fix")
    for issue in (must if isinstance(must, list) else []):
        if isinstance(issue, dict):
            out.append(f"SEO must-fix: {issue.get('check')} - {issue.get('detail', '')}")
    return out


def _report(title: str, meta: dict) -> str:
    """A one-page summary of how the post was produced, for the person who has
    to decide whether to publish it."""
    def as_dict(value) -> dict:
        return value if isinstance(value, dict) else {}

    lines = [f"# {title}", ""]
    if meta.get("author") or meta.get("tone_label"):
        lines += [f"By **{meta.get('author', '')}** · voice: "
                  f"**{meta.get('tone_label', meta.get('tone', 'unset'))}**", ""]

    verification = as_dict(meta.get("verification"))
    if verification:
        lines += [
            "## Verification", "",
            f"- Verdict: **{'corroborated' if verification.get('is_legit') else 'NOT corroborated'}**",
            f"- Confidence: {verification.get('confidence', 'unknown')}",
            f"- Independent publishers: {', '.join(verification.get('independent_publishers', [])) or 'none'}",
            f"- Reasoning: {verification.get('reasoning', '')}", "",
        ]

    scores = as_dict(meta.get("human_score"))
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

    seo = as_dict(meta.get("seo"))
    if seo:
        lines += [
            "## SEO", "",
            f"- Score: **{seo.get('score', '?')}** / 100 "
            f"({seo.get('passed', '?')}/{seo.get('total_checks', '?')} checks)",
            f"- Primary keyword: {seo.get('primary_keyword', '')}",
            f"- Secondary: {', '.join(seo.get('secondary_keywords', []))}",
        ]
        for issue in (seo.get("must_fix") if isinstance(seo.get("must_fix"), list)
                      else []):
            lines.append(f"- MUST FIX: {issue.get('check')}: {issue.get('detail', '')}")
        lines.append("")

    lines += ["## Publishing", "",
              f"- Canonical: {meta.get('canonical', '')}",
              f"- Slug: {meta.get('slug', '')}",
              f"- Published: {meta.get('date_published', '')}",
              f"- Image: {meta.get('image', '')}", ""]

    references = meta.get("references") or []
    references = [r for r in references if isinstance(r, dict)] \
        if isinstance(references, list) else []
    if references:
        lines += ["## References", ""]
        lines += [f"{n}. [{r.get('title', r.get('url'))}]({r.get('url')})"
                  for n, r in enumerate(references, 1)]
        lines.append("")

    return "\n".join(lines)
