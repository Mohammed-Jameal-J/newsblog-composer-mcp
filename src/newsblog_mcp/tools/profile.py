"""Session profile: who is publishing, where, and in what voice.

The pipeline refuses to produce content until these are answered. Without them
every post carries whatever happens to be in .env - which means a second person
installing this server would publish under the first person's byline, link their
call to action to the first person's company, and point every canonical URL at
the first person's domain.

The answers persist to profile.json in the project root, so the questions are
asked once per install rather than once per conversation.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

PROFILE_PATH = Path(__file__).resolve().parents[3] / "profile.json"


TONES: dict[str, dict] = {
    "neutral": {
        "label": "Neutral newsroom",
        "summary": "Straight reporting voice. No colour, no jokes.",
        "guidance": [
            "Report what happened and what it means. Nothing else.",
            "No jokes, no exclamation marks, no direct address to the reader.",
            "Short declarative sentences carry the facts; analysis stays measured.",
        ],
    },
    "witty": {
        "label": "Funny / wry",
        "summary": "Dry humour and light asides, facts still straight.",
        "guidance": [
            "Allow dry observational humour, understatement and a wry aside once "
            "every couple of sections. Never more than one joke per section.",
            "The humour comes from the situation, never from mocking a named person, "
            "a company's staff, or anyone's misfortune.",
            "Punchlines go at the end of a paragraph, not mid-sentence.",
            "Every factual sentence stays literal. A joke may never alter a figure, "
            "a date or a quote, and must be obviously a joke.",
        ],
    },
    "upbeat": {
        "label": "Happy / optimistic",
        "summary": "Energetic and forward-looking, without hype.",
        "guidance": [
            "Lead with what this makes possible. Emphasise momentum and opportunity.",
            "Warm, energetic sentences; contractions are fine.",
            "Optimism comes from the specifics, not from adjectives. No 'exciting', "
            "'amazing', 'incredible' or exclamation marks.",
            "Do not overstate a result or bury a downside to keep the mood up. If "
            "something in the story is bad, say so plainly and move on.",
        ],
    },
    "heartfelt": {
        "label": "Emotional / human",
        "summary": "Warm and personal, focused on who is affected.",
        "guidance": [
            "Lead with the people in the story and what changes for them.",
            "Speak to the reader directly where it helps. 'You' is allowed.",
            "Use concrete human detail already present in the sources; never invent "
            "a person, a feeling or a scene to make it land.",
            "Restraint over sentimentality. One sentence of feeling beats a paragraph.",
        ],
    },
    "sombre": {
        "label": "Sad / serious",
        "summary": "Measured and respectful, for difficult news.",
        "guidance": [
            "Plain language, short sentences, no rhetorical flourish.",
            "No humour, no silver linings, no calls to action dressed as comfort.",
            "Name the harm and who it falls on, without dwelling on detail for effect.",
            "The closing CTA stays quiet and practical, or is dropped entirely.",
        ],
    },
}


def setup_questions() -> list[dict]:
    """The questions a client must put to the user, verbatim.

    Every text question is the user's own to answer. Clients must NOT offer
    guessed options - not a name from the account, not a company from an earlier
    post, not a domain inferred from anything. Suggesting answers here produces
    posts published under the wrong byline by someone who just clicked the first
    option.
    """
    return [
        {
            "id": "author_name",
            "question": "What name should appear on the byline?",
            "type": "text",
            "required": True,
            "placeholder": "Your name",
            "offer_options": False,
            "why": "Used as the author name: printed as 'By <name>' on the post and "
                   "written into the NewsArticle author field.",
        },
        {
            "id": "tone",
            "question": "What voice should the posts be written in?",
            "type": "choice",
            "required": True,
            "offer_options": True,
            "options": [{"value": key, "label": t["label"], "summary": t["summary"]}
                        for key, t in TONES.items()],
            "why": "Shapes how the article is written. It never changes the facts.",
        },
        {
            "id": "company_name",
            "question": "What is your company or publication called?",
            "type": "text",
            "required": True,
            "placeholder": "Your company name",
            "offer_options": False,
            "why": "Used as the publisher in the schema, and as the linked text in "
                   "the closing call to action.",
        },
        {
            "id": "site_url",
            "question": "Enter the domain where your blog posts are published.",
            "type": "text",
            "required": True,
            "placeholder": "https://yourdomain.com",
            "offer_options": False,
            "why": "Used to build the canonical link and the banner image link on "
                   "every post, and the call-to-action link. A main domain or a "
                   "subdomain both work - enter whichever one your posts live on.",
        },
        {
            "id": "company_url",
            "question": "Different company website for the call-to-action link? "
                        "Leave blank to use the same domain.",
            "type": "text",
            "required": False,
            "placeholder": "",
            "offer_options": False,
            "why": "Only needed when the blog sits on a subdomain and the call to "
                   "action should point at the main company site instead.",
        },
        {
            "id": "logo_url",
            "question": "Logo image URL? Leave blank to use <site>/logo.png.",
            "type": "text",
            "required": False,
            "placeholder": "",
            "offer_options": False,
            "why": "Goes into publisher.logo.url.",
        },
    ]


REQUIRED_KEYS = ("author_name", "tone", "company_name", "company_url")


def load_profile() -> dict | None:
    try:
        data = json.loads(PROFILE_PATH.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    if all(data.get(k) for k in REQUIRED_KEYS) and data.get("tone") in TONES:
        return data
    return None  # an older or half-written profile re-asks the questions


def _clean_url(value: str, field: str, required: bool = True) -> str:
    value = (value or "").strip().rstrip("/")
    if not value:
        if required:
            raise ValueError(f"{field} is required.")
        return ""
    if not value.startswith(("http://", "https://")):
        value = "https://" + value
    if "." not in value.split("//", 1)[-1]:
        raise ValueError(f"{field} does not look like a URL: {value!r}")
    return value


def save_profile(author_name: str, tone: str, company_name: str, site_url: str,
                 company_url: str = "", logo_url: str = "") -> dict:
    """site_url is the one domain that matters: where posts are published.

    Everything else derives from it. company_url is only for the case where the
    blog sits on a subdomain and the call to action should point somewhere else.
    """
    author_name = (author_name or "").strip()
    tone = (tone or "").strip().lower()
    company_name = (company_name or "").strip()
    if not author_name:
        raise ValueError("author_name is required.")
    if tone not in TONES:
        raise ValueError(f"tone must be one of {sorted(TONES)}, got {tone!r}.")
    if not company_name:
        raise ValueError("company_name is required.")

    blog_base_url = _clean_url(site_url, "site_url")
    company_url = _clean_url(company_url, "company_url", required=False) or blog_base_url
    logo_url = _clean_url(logo_url, "logo_url", required=False) or f"{company_url}/logo.png"

    data = {
        "author_name": author_name,
        "tone": tone,
        "tone_label": TONES[tone]["label"],
        "company_name": company_name,
        "company_url": company_url,
        "blog_base_url": blog_base_url,
        "logo_url": logo_url,
        "image_base_url": f"{blog_base_url}/images",
        "set_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
    }
    PROFILE_PATH.write_text(json.dumps(data, indent=2), encoding="utf-8")
    return data


def clear_profile() -> bool:
    try:
        PROFILE_PATH.unlink()
        return True
    except OSError:
        return False


def tone_guidance(tone: str) -> str:
    entry = TONES.get(tone)
    if not entry:
        return ""
    lines = [f"## Voice: {entry['label']}", "", entry["summary"], ""]
    lines += [f"- {rule}" for rule in entry["guidance"]]
    lines += [
        "",
        "Tone governs wording only. It never changes a fact, a figure, a date, a "
        "quote or a link, and it never decides which story is worth covering. If the "
        "chosen voice would misrepresent the subject - a joke about a death, "
        "cheerfulness about job losses - drop the voice for that post, write it "
        "straight, and say so when you hand the draft over.",
    ]
    return "\n".join(lines)


def answer_template() -> str:
    """A block the user can overwrite in one go.

    Reading six questions and composing a prose reply is friction nobody spends
    on setup. Filling three blanks and clicking a voice is not.
    """
    lines = [
        'Name:          <- your name. Printed as "By <name>" on the post and set as',
        '                  the schema author.',
        "Company name:  <- your company or publication. Becomes the publisher in the",
        "                  schema and the linked text in the closing call to action.",
        "Blog domain:   <- where your posts are published. Builds every canonical URL",
        "                  and banner image link. Main domain or subdomain, either is",
        "                  fine.",
        "Voice:         <- pick one:",
    ]
    width = max(len(key) for key in TONES)
    for key, tone in TONES.items():
        lines.append(f"                  {key.ljust(width)}  {tone['summary']}")
    return "\n".join(lines) + "\n"


def setup_required_response() -> dict:
    """What every gated tool returns while the profile is unset."""
    return {
        "error": "setup_required",
        "message": (
            "This server has not been set up yet. Ask the user the questions below "
            "(the four marked required, plus the optional two if they want to set "
            "them), wait for their answers, then call set_profile. Do not draft, "
            "research or build anything before that - a post written now would carry "
            "the wrong byline, an unchosen voice, and someone else's company and "
            "canonical URL."
        ),
        "questions": setup_questions(),
        "ask_as": ("Ask in ONE interaction, not six. Render the voice question as "
                   "clickable options, and the three text fields as a form or as the "
                   "answer_template block below for the user to overwrite. Do NOT "
                   "present guessed answers for the name, company or domain - those "
                   "are the user's to type, and anything you suggest will get clicked "
                   "and published. Never make the user compose a prose reply."),
        "answer_template": answer_template(),
        "next_tool": ("set_profile(author_name='...', tone='...', company_name='...', "
                      "site_url='...')"),
    }


def require_profile() -> tuple[dict | None, dict | None]:
    """Returns (profile, blocked_response). Exactly one is not None."""
    profile = load_profile()
    if profile is None:
        return None, setup_required_response()
    return profile, None
