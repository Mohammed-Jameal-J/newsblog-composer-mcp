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

# Banner styles keyed to what a news blog actually publishes. Each one says what
# the picture IS, not just how it is rendered, because "flat vector shapes" with
# no subject produces the same abstract blob every time.
_STYLES = {
    "product_hero": (
        "studio product photograph, the object lit softly on a clean surface with "
        "a bright airy background, shallow depth of field, generous empty space on "
        "the left for text"),
    "explainer_diagram": (
        "flat vector infographic, three or four labelled stages connected by "
        "arrows across the middle, navy and soft teal on white, simple icons, the "
        "kind of diagram that explains a process at a glance"),
    "scene_with_display": (
        "wide photographic street or interior scene at eye level, a large screen "
        "or display board in the frame carrying the headline, cinematic natural "
        "light, real depth and atmosphere"),
    "hardware_macro": (
        "close photographic detail of the hardware itself, hands working on it, "
        "shallow depth of field, cool technical lighting"),
    "whiteboard_sketch": (
        "a whiteboard in a working office photographed slightly off-centre, the "
        "point of the story drawn on it by hand in marker, blurred desks behind"),
    "newspaper_front": (
        "front page of a printed newspaper photographed flat, cream stock, heavy "
        "serif masthead across the top, the headline set large beneath it in bold "
        "serif, columns of small body text, a photograph boxed into the layout"),
    "editorial_illustration": (
        "editorial illustration in the style of a broadsheet opinion page, flat "
        "shapes with restrained texture, two or three colours plus a neutral "
        "ground, confident simple forms"),
    "newsletter_header": (
        "clean newsletter header, one large simple subject on a plain light "
        "ground, minimal detail, flat colour, generous empty space"),
    # Older keys, kept so existing calls still resolve.
    "editorial": ("editorial illustration in the style of a broadsheet opinion page, "
                  "flat shapes with restrained texture, two or three colours"),
    "photographic": ("photojournalistic press photograph, natural directional light, "
                     "shallow depth of field, documentary framing"),
    "abstract": ("abstract conceptual composition, layered geometric planes and soft "
                 "gradients, cool palette with one warm accent"),
    "news_photo": ("photojournalistic press photograph, natural directional light, "
                   "shallow depth of field, documentary framing"),
    "flat_infographic": ("flat vector infographic, labelled stages connected by "
                         "arrows, limited palette, simple icons"),
    "conceptual_abstract": ("abstract conceptual composition, layered geometric "
                            "planes and soft gradients"),
}

# Where the headline sits, per style. A banner with text floating over the busiest
# part of the picture is the commonest way these come out unusable.
_TEXT_ZONE = {
    "product_hero": "in the left third, over the empty background beside the object",
    "explainer_diagram": "across the lower third, below the diagram",
    "scene_with_display": "on the display board inside the scene, as if it were "
                          "really printed there",
    "hardware_macro": "in the upper left, over the darker out-of-focus area",
    "whiteboard_sketch": "written on the whiteboard in the same marker hand",
    "newspaper_front": "as the main front-page headline beneath the masthead",
    "editorial_illustration": "in the left third, over flat empty ground",
    "newsletter_header": "centred beneath the subject",
}

_STYLE_CHOICES = [
    {"value": "product_hero", "label": "Product hero",
     "summary": "The device or object photographed on a clean bright surface, headline beside it."},
    {"value": "explainer_diagram", "label": "Explainer diagram",
     "summary": "Labelled stages with arrows, big title underneath. For how-it-works stories."},
    {"value": "scene_with_display", "label": "Real scene with a display",
     "summary": "A street or office photo with the headline on a screen inside the shot."},
    {"value": "hardware_macro", "label": "Hardware close-up",
     "summary": "Hands on the actual hardware, shallow focus. For chips, servers, devices."},
    {"value": "whiteboard_sketch", "label": "Office whiteboard",
     "summary": "The point drawn by hand on a whiteboard. For numbers, decisions, tradeoffs."},
    {"value": "newspaper_front", "label": "Newspaper front page",
     "summary": "Printed broadsheet layout with your masthead and the headline set large."},
    {"value": "editorial_illustration", "label": "Editorial illustration",
     "summary": "Drawn, flat colour, like an opinion page. When nothing concrete fits."},
    {"value": "newsletter_header", "label": "Newsletter header",
     "summary": "One simple subject, lots of space. Reads well small."},
]


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
    image_style: str = "editorial_illustration",
    banner_text: str = "",
    banner_kicker: str = "",
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
    # Only the SCENE is run through the trademark filter. The headline printed on
    # the banner is the post's own title and has to be spelled exactly, brand
    # names included: writing "Apple" on a banner about Apple is reporting, and
    # mangling it is the one thing a reader will notice immediately.
    safe_subject, removed = sanitize_prompt(subject_source)
    safe_subject = safe_subject.split(". No text")[0].strip()
    style_key = image_style if image_style in _STYLES else "editorial_illustration"
    style = _STYLES[style_key]
    zone = _TEXT_ZONE.get(style_key, "in the left third, over a clear area")

    # The headline goes ON the banner. Every reference blog banner does this, and
    # a generator told "no text" produces a picture the post cannot use.
    on_image = normalize(banner_text) or headline
    kicker = normalize(banner_kicker)

    text_block = (f'Text to render on the image, spelled exactly as written:\n'
                  f'  Headline: "{on_image}"\n')
    if kicker:
        text_block += f'  Smaller line beneath it: "{kicker}"\n'
    text_block += (f"Set the headline {zone}. Keep it large, high contrast and "
                   f"clear of the busy part of the picture. Do not add any other "
                   f"words.")

    gemini_prompt = (
        f"A 1200x630 landscape banner for a blog post.\n\n"
        f"Scene: {safe_subject}.\n\n"
        f"Style: {style}.\n\n"
        f"{text_block}\n\n"
        f"No real company logos or wordmarks. No recognisable real people."
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
        "image_style_used": style_key,
        "image_concept_source": concept_source,
        "image_direction_required": concept_source == "derived",
        "ask_the_user_about_the_image": None if concept_source == "supplied" else {
            "question": "What should the banner look like?",
            "options": _STYLE_CHOICES,
            "also_ask": ("If they have a picture in mind, take it in their own words "
                         "and pass it as image_concepts. Otherwise offer the suggested "
                         "subject below and let them change it."),
            "suggested_subject": safe_subject,
            "note_on_text": ("The post headline is printed on the banner by "
                             "default. Pass banner_text to shorten it for the "
                             "image, and banner_kicker for a smaller second line."),
            "how_to_apply": ("Call build_publishing_pack again with image_style set to "
                             "their choice and image_concepts describing one concrete "
                             "scene from the facts, then hand over the new prompt."),
        },
        "image_concept_note": (
            "Concept written by the caller."
            if concept_source == "supplied" else
            "No image_concepts was passed, so the subject was derived from the "
            "researched keywords. It will produce a relevant but generic banner. "
            "For a better one, pass image_concepts describing a concrete scene "
            "drawn from the facts - what a reader would actually see - and call "
            "this tool again."),
        "present_in_this_order": [
            "Title", "Permalink", "Meta description", "Tags",
            "Banner goes to", "Blog content", "Gemini image prompt",
        ],
        "hand_over_note": (
            "Give the user exactly those seven, in that order, every time. The blog "
            "content is the rendered body from build_schema, not a summary of it."),
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
