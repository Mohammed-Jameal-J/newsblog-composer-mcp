"""Tool 3 - humanize_text.

With an LLM key set, the rewrite happens server-side so it behaves identically
in every MCP client. Without one, the tool returns the rule set and the text and
asks the calling model to do the rewrite itself - which keeps the server useful
with zero credentials, at the cost of client-to-client variation.
"""
from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from ..config import CONFIG, Config
from ..providers.llm import NoLLMConfigured, complete

_RULES_PATH = Path(__file__).resolve().parents[1] / "resources" / "humanizer_patterns.md"


@lru_cache(maxsize=1)
def rules_text() -> str:
    """Read once and cache. Resource files are static, and re-reading them on
    every call is a needless I/O hit on network or virtualised filesystems."""
    return _RULES_PATH.read_text(encoding="utf-8")


def humanize_text(text: str, voice_sample: str = "", cfg: Config | None = None) -> dict:
    cfg = cfg or CONFIG
    rules = rules_text()

    system = (
        "You are a rewriting editor. Apply the rules below to the supplied text. "
        "Preserve every fact, figure, name, date, quote and URL exactly as given; "
        "never invent detail to sound more natural. Return only the rewritten "
        "text, no preamble and no commentary.\n\n" + rules
    )
    user = text if not voice_sample else (
        f"VOICE SAMPLE (style only, contains no facts to use):\n{voice_sample}\n\n"
        f"TEXT TO REWRITE:\n{text}"
    )

    try:
        rewritten, model = complete(system, user, cfg)
    except NoLLMConfigured:
        return {
            "mode": "delegated_to_caller",
            "rewritten_text": "",
            "instructions": rules,
            "text_to_rewrite": text,
            "voice_sample": voice_sample,
            "patterns_removed": [],
            "critique": "",
            "note": (
                "No ANTHROPIC_API_KEY or OPENAI_API_KEY is configured, so this tool "
                "did not rewrite anything. Apply `instructions` to `text_to_rewrite` "
                "yourself, preserving every fact, figure, name, date, quote and URL, "
                "then pass the result to score_ai_text and build_schema. Set an LLM "
                "key if you want this to happen server-side instead."
            ),
        }
    except Exception as exc:
        return {"mode": "error", "rewritten_text": "",
                "error": f"{type(exc).__name__}: {exc}", "patterns_removed": [],
                "critique": ""}

    return {
        "mode": "server_side",
        "rewritten_text": rewritten.strip(),
        "model_used": model,
        "patterns_removed": [],
        "critique": ("Rewritten server-side against the house rule set. Diff it against "
                     "the original before publishing; the rules forbid new facts but the "
                     "model is not infallible."),
    }
