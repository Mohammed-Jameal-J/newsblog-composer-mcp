"""Server-side LLM calls, used only by humanize_text when a key is present."""
from __future__ import annotations

import httpx

from ..config import Config


class NoLLMConfigured(RuntimeError):
    pass


def complete(system: str, user: str, cfg: Config, max_tokens: int = 4000) -> tuple[str, str]:
    """Returns (text, model_label). Raises NoLLMConfigured if no key is set."""
    if cfg.anthropic_api_key:
        with httpx.Client(timeout=120.0) as client:
            r = client.post(
                "https://api.anthropic.com/v1/messages",
                headers={
                    "x-api-key": cfg.anthropic_api_key,
                    "anthropic-version": "2023-06-01",
                    "content-type": "application/json",
                },
                json={
                    "model": cfg.anthropic_model,
                    "max_tokens": max_tokens,
                    "system": system,
                    "messages": [{"role": "user", "content": user}],
                },
            )
            r.raise_for_status()
            data = r.json()
        text = "".join(block.get("text", "") for block in data.get("content", []))
        return text, f"anthropic:{cfg.anthropic_model}"

    if cfg.openai_api_key:
        with httpx.Client(timeout=120.0) as client:
            r = client.post(
                "https://api.openai.com/v1/chat/completions",
                headers={"Authorization": f"Bearer {cfg.openai_api_key}",
                         "Content-Type": "application/json"},
                json={
                    "model": cfg.openai_model,
                    "max_tokens": max_tokens,
                    "messages": [{"role": "system", "content": system},
                                 {"role": "user", "content": user}],
                },
            )
            r.raise_for_status()
            data = r.json()
        return data["choices"][0]["message"]["content"], f"openai:{cfg.openai_model}"

    raise NoLLMConfigured("No ANTHROPIC_API_KEY or OPENAI_API_KEY set.")
