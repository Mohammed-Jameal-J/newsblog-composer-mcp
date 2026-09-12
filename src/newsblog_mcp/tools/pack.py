"""Tool - build_publishing_pack.

The last mile. Everything a person needs to paste the post into Blogger and get
the banner made, in one block: title, labels, permalink, meta description, alt
text, and an image prompt written for Gemini.

The image prompt is text, not an API call. You paste it into Gemini, save the
image it returns, upload it, and put that URL into build_schema. That is the
route worth taking when no image key is configured, and it produces better
banners than the keyless generators anyway.
"""
from __future__ import annotations

import re

from ..config import CONFIG, Config
from ..providers.imagegen import sanitize_prompt
from ..textutil import normalize, slugify

_LABEL_STOP = {"the", "a", "an", "of", "for", "and", "in", "on", "to", "is", "are",
               "why", "what", "how", "this", "that", "its", "it", "as", "with"}

# Keyword extraction lowercases everything, so a label built from it comes out
# "Iphone". These are the casings that matter when the label is published.
_CASING = {
    "iphone": "iPhone", "ipad": "iPad", "ipados": "iPadOS", "ios": "iOS",
    "macos": "macOS", "macbook": "MacBook", "imac": "iMac", "airpods": "AirPods",
    "airtag": "AirTag", "watchos": "watchOS", "tvos": "tvOS", "siri": "Siri",
    "ai": "AI", "agi": "AGI", "api": "API", "apis": "APIs", "llm": "LLM",
    "llms": "LLMs", "gpu": "GPU", "gpus": "GPUs", "cpu": "CPU", "npu": "NPU",
    "ceo": "CEO", "cto": "CTO", "cfo": "CFO", "ui": "UI", "ux": "UX",
    "saas": "SaaS", "paas": "PaaS", "iaas": "IaaS", "aws": "AWS", "gcp": "GCP",
    "eu": "EU", "us": "US", "uk": "UK", "usa": "USA", "gdpr": "GDPR",
    "seo": "SEO", "sdk": "SDK", "ide": "IDE", "ml": "ML", "nlp": "NLP",
    "rag": "RAG", "ocr": "OCR", "vpn": "VPN", "sso": "SSO", "iot": "IoT",
    "5g": "5G", "6g": "6G", "3d": "3D", "hd": "HD", "4k": "4K", "8k": "8K",
    "openai": "OpenAI", "chatgpt": "ChatGPT", "deepseek": "DeepSeek",
    "youtube": "YouTube", "tiktok": "TikTok", "github": "GitHub",
    "linkedin": "LinkedIn", "whatsapp": "WhatsApp", "paypal": "PayPal",
    "nvidia": "Nvidia", "amd": "AMD", "arm": "Arm", "tsmc": "TSMC", "ibm": "IBM",
    "gpt": "GPT", "sol": "Sol", "astra": "Astra",
}

# A label naming a unit or a comparison is noise, not a topic.
_LABEL_NOISE = {"percent", "million", "billion", "trillion", "against", "scored",
                "versus", "compared", "rate", "times", "device", "company",
                "thing", "things", "part", "way", "today", "year",
                "series", "round", "report", "data", "news", "update"}


def _cased(word: str) -> str:
    """Correct casing for a single label word."""
    if "-" in word:  # gpt-6 -> GPT-6, not Gpt-6
        return "-".join(_cased(part) for part in word.split("-"))
    mapped = _CASING.get(word.lower())
    if mapped:
        return mapped
    # A token mixing letters and digits is an identifier, not a word: GPT6, 5G.
    if any(c.isdigit() for c in word) and any(c.isalpha() for c in word):
        return word.upper()
    # Already carries capitals (EU's, AWS, iPhone): leave it alone.
    return word if word[:1].isupper() else word.capitalize()

_STYLES = {
    "editorial": ("modern editorial tech illustration, flat vector shapes with subtle "
                  "gradients and soft depth, restrained palette of slate blue, teal and "
                  "warm grey on a light background, generous negative space"),
    "photographic": ("cinematic photographic style, shallow depth of field, natural "
                     "directional light, muted colour grade, no people's faces in focus"),
    "abstract": ("abstract geometric composition, layered translucent planes, isometric "
                 "grid motifs, cool blue and graphite palette with one warm accent"),
}


def _labels(keywords: list[str], entities: list[str], limit: int = 6) -> list[str]:
    """Blogger labels: short, title-cased, deduplicated, no filler words."""
    seen: set[str] = set()
    out: list[str] = []
    # Primary keyword leads; named entities are cleaner than the remaining
    # n-grams, so they come next.
    keywords = list(keywords)
    ordered = keywords[:1] + list(entities) + keywords[1:]
    for raw in ordered:
        phrase = normalize(raw)
        words = [w for w in phrase.split() if w.lower() not in _LABEL_STOP]
        if not words or len(words) > 3:
            continue
        if any(w.lower() in _LABEL_NOISE for w in words):
            continue
        label = " ".join(_cased(w) for w in words)
        low = label.lower()
        if len(label) > 24 or low in seen:
            continue
        # "Qualcomm" and "Qualcomm Warrants" are one label, not two.
        if any(low in kept.lower() or kept.lower() in low for kept in out):
            continue
        seen.add(low)
        out.append(label)
        if len(out) >= limit:
            break
    return out


def build_publishing_pack(
    headline: str,
    description: str = "",
    slug: str = "",
    keywords: list[str] | None = None,
    entities: list[str] | None = None,
    image_concepts: str = "",
    image_style: str = "editorial",
    canonical_url: str = "",
    cfg: Config | None = None,
) -> dict:
    cfg = cfg or CONFIG
    headline = normalize(headline)
    keywords = [normalize(k) for k in (keywords or []) if normalize(k)]
    entities = [normalize(e) for e in (entities or []) if normalize(e)]
    slug = slug or slugify(headline)
    labels = _labels(keywords, entities)

    # The visual subject: what the story is about, with brand names already
    # stripped. Falls back to the headline when no concepts were supplied.
    subject_source = image_concepts or headline
    safe_subject, removed = sanitize_prompt(subject_source)
    safe_subject = safe_subject.split(". No text")[0].strip()
    style = _STYLES.get(image_style, _STYLES["editorial"])

    gemini_prompt = (
        f"Create a wide banner illustration for a news article, 1200x630 pixels, "
        f"16:9 landscape.\n\n"
        f"Subject: {safe_subject}.\n\n"
        f"Style: {style}.\n\n"
        f"Composition: single clear focal idea, uncluttered, readable as a thumbnail "
        f"at small size, with space on one side where a headline could sit.\n\n"
        f"Hard constraints: no text, no words, no letters or numbers anywhere in the "
        f"image; no logos, wordmarks, brand marks or trademarked designs; no "
        f"recognisable real people; no watermarks; no borders or frames."
    )

    alt_text = normalize(f"Illustration: {safe_subject}")
    if len(alt_text) > 150:  # trim on a word boundary, not mid-word
        alt_text = alt_text[:147].rsplit(" ", 1)[0].rstrip(",;:") + "..."

    suggested_image_url = f"{cfg.site_base_url.rstrip('/')}/images/{slug}-banner.jpg"

    return {
        "title": headline,
        "meta_description": normalize(description),
        "permalink_slug": slug,
        "suggested_image_url": suggested_image_url,
        "full_url": canonical_url or f"{cfg.site_base_url.rstrip('/')}/{slug}",
        "labels": labels,
        "labels_line": ", ".join(labels),
        "gemini_image_prompt": gemini_prompt,
        "image_alt_text": alt_text,
        "trademarks_removed": removed,
        "how_to_use": (
            "1. Paste gemini_image_prompt into Gemini and save the image it returns.\n"
            f"2. Upload it as {suggested_image_url} (or anywhere public) and copy the "
            "URL.\n"
            "3. Pass that URL plus image_alt_text into build_schema.\n"
            "4. In Blogger: paste the body, put `title` in the post title, "
            "`labels_line` in Labels, and `permalink_slug` in Permalink > Custom.\n"
            "5. Put meta_description in Search Description."
        ),
    }


def render_pack_markdown(pack: dict) -> str:
    lines = [
        "# Publishing pack", "",
        "## Title", "", pack["title"], "",
        "## Search description", "", pack["meta_description"], "",
        f"({len(pack['meta_description'])} characters)", "",
        "## Labels / tags", "", pack["labels_line"] or "(none generated)", "",
        "## Permalink", "",
        f"Custom permalink: `{pack['permalink_slug']}`", "",
        f"Full URL: {pack['full_url']}", "",
        "## Banner image goes here", "",
        f"`{pack.get('suggested_image_url', '')}`", "",
        "## Image prompt for Gemini", "",
        "Paste this into Gemini, save the image, upload it, then put the public URL "
        "into build_schema.", "",
        "```", pack["gemini_image_prompt"], "```", "",
        "## Image alt text", "", pack["image_alt_text"], "",
    ]
    if pack["trademarks_removed"]:
        lines += ["## Brand terms stripped from the image prompt", "",
                  ", ".join(pack["trademarks_removed"]),
                  "", "These were replaced with generic descriptors so the generated "
                  "image cannot reproduce a real trademark.", ""]
    return "\n".join(lines)
