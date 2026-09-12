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


# --------------------------------------------------------------------------- #
# Deriving a visual subject when the caller supplies none
#
# The old fallback used the headline, which is the wrong kind of text entirely:
# it names the story rather than describing a picture, and it carries figures and
# dates that collide with the prompt's own "no numbers in the image" rule. A
# derived subject is more generic than one a person would write, but it is at
# least a scene, and it never contradicts the constraints.
# --------------------------------------------------------------------------- #

# Ordered: the first match wins, so the more specific subjects come first.
_MOTIFS: tuple[tuple[tuple[str, ...], str], ...] = (
    (("breach", "attack", "malware", "exploit", "vulnerability", "hacked", "hacking",
      "ransomware", "phishing", "intrusion", "compromise", "spyware", "backdoor",
      "cyber", "espionage", "spying", "weapons", "misuse", "threat actor"),
     "a breached perimeter drawn as interlocking panels with one forced open, "
     "fragments drifting away from the gap"),
    (("robot", "robotic", "humanoid", "motion capture", "actuator", "gripper"),
     "a simplified humanoid figure mid-movement, its motion traced beside it as "
     "a clean skeleton of connected points"),
    (("data centre", "data center", "datacentre", "datacenter", "server rack",
      "cooling", "power grid", "electricity", "megawatt", "energy demand"),
     "rows of tall server cabinets seen in perspective, with power drawn as "
     "flowing lines feeding into them"),
    (("chip", "silicon", "semiconductor", "processor", "wafer", "fabrication",
      "foundry", "gpu", "npu", "accelerator"),
     "a stylised processor die viewed from above, concentric circuitry radiating "
     "outward from a bright centre"),
    (("funding", "valuation", "raise", "raised", "investment", "investor", "round",
      "venture", "series a", "series b", "ipo", "acquisition", "merger", "stake"),
     "abstract ascending forms suggesting capital gathering behind a young "
     "company, one shape rising clear of the rest"),
    (("regulator", "regulation", "policy", "legislation", "lawsuit", "inquiry",
      "compliance", "court", "ruling", "sanction", "antitrust", "ban"),
     "a balance scale built from flat geometric shapes, standing over a faint "
     "grid of documents"),
    (("privacy", "surveillance", "tracking", "personal data", "monitoring"),
     "a watching-eye motif dissolving at its edge into scattered data particles"),
    (("agent", "model", "training", "inference", "neural", "llm", "chatbot",
      "machine learning", "dataset"),
     "a branching network of nodes converging through layers into one clear "
     "output shape"),
    (("cloud", "platform", "infrastructure", "deployment", "api", "integration",
      "workflow", "automation", "pipeline"),
     "layered platform planes stacked in perspective, connected by clean lines "
     "running between them"),
    (("market", "revenue", "growth", "sales", "demand", "supply", "shipments",
      "forecast", "earnings"),
     "an ascending series of solid blocks with a single confident trend line "
     "crossing them"),
)

_GENERIC_MOTIF = ("an abstract editorial composition of layered geometric shapes "
                  "with one clear focal form")

# Words that are about reporting rather than about the thing being reported.
_NON_VISUAL = {"report", "reports", "reported", "says", "said", "according",
               "sources", "source", "statement", "announcement", "announced",
               "news", "story", "article", "week", "month", "year", "today",
               "company", "companies", "firm", "people", "plan", "plans"}


def _visual_themes(keywords: list[str], entities: list[str], limit: int = 3) -> list[str]:
    """Keyword phrases usable as picture subjects.

    Anything carrying a digit is dropped: the prompt forbids numbers in the
    image, so feeding '$500m valuation' to the subject line asks for exactly
    what the constraints rule out.
    """
    out: list[str] = []
    seen: set[str] = set()
    for raw in list(keywords) + list(entities):
        phrase = normalize(raw).lower()
        if not phrase or any(ch.isdigit() for ch in phrase):
            continue
        words = phrase.split()
        if len(words) > 4:
            continue
        if all(w in _NON_VISUAL or w in _LABEL_STOP for w in words):
            continue
        if phrase in seen or any(phrase in kept or kept in phrase for kept in out):
            continue
        seen.add(phrase)
        out.append(phrase)
        if len(out) >= limit:
            break
    return out


def _derive_subject(headline: str, keywords: list[str], entities: list[str]) -> str:
    """Build a describable scene from what the research already produced."""
    # Two passes. The keywords were mined from the body, so they describe what
    # the piece is actually about; the headline is one line chosen to be clicked.
    # Only fall back to it when nothing in the research matches.
    from_research = " ".join([k.lower() for k in keywords] + [e.lower() for e in entities])
    motif = ""
    for haystack in (from_research, headline.lower()):
        if not haystack.strip():
            continue
        for triggers, description in _MOTIFS:
            if any(trigger in haystack for trigger in triggers):
                motif = description
                break
        if motif:
            break
    motif = motif or _GENERIC_MOTIF

    themes = _visual_themes(keywords, entities)
    if not themes:
        return motif
    if len(themes) == 1:
        theme_text = themes[0]
    else:
        theme_text = ", ".join(themes[:-1]) + " and " + themes[-1]
    return f"{motif}, evoking {theme_text}"


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
    # stripped. A concept written by hand always wins; without one, a scene is
    # derived from the researched keywords rather than falling back to the
    # headline, which describes the story instead of the picture.
    concept_source = "supplied" if normalize(image_concepts) else "derived"
    subject_source = (normalize(image_concepts)
                      or _derive_subject(headline, keywords, entities))
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

    # Alt text describes the image for someone who cannot see it, so it takes the
    # scene and drops the ", evoking <themes>" tail, which is direction for the
    # illustrator rather than a description of the result.
    alt_source = safe_subject.split(", evoking ")[0]
    alt_text = normalize(f"Illustration: {alt_source}")
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
        "image_concept_source": concept_source,
        "image_concept_note": (
            "Concept written by the caller."
            if concept_source == "supplied" else
            "No image_concepts was passed, so the subject was derived from the "
            "researched keywords. It will produce a relevant but generic banner. "
            "For a better one, pass image_concepts describing a concrete scene "
            "drawn from the facts - what a reader would actually see - and call "
            "this tool again."),
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
