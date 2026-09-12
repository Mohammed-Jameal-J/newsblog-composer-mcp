"""Environment-driven configuration. Every credential is optional."""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

from dotenv import load_dotenv

from .paths import data_dir, default_output_dir, dotenv_path

load_dotenv(dotenv_path())


def _env(name: str, default: str = "") -> str:
    return (os.getenv(name) or default).strip()


@dataclass
class Config:
    brave_api_key: str = field(default_factory=lambda: _env("BRAVE_API_KEY"))
    serper_api_key: str = field(default_factory=lambda: _env("SERPER_API_KEY"))
    newsapi_key: str = field(default_factory=lambda: _env("NEWSAPI_KEY"))
    tavily_api_key: str = field(default_factory=lambda: _env("TAVILY_API_KEY"))
    google_cse_key: str = field(default_factory=lambda: _env("GOOGLE_CSE_KEY"))
    google_cse_id: str = field(default_factory=lambda: _env("GOOGLE_CSE_ID"))
    gdelt_timespan: str = field(default_factory=lambda: _env("GDELT_TIMESPAN", "14d"))
    search_provider: str = field(default_factory=lambda: _env("SEARCH_PROVIDER"))

    anthropic_api_key: str = field(default_factory=lambda: _env("ANTHROPIC_API_KEY"))
    anthropic_model: str = field(default_factory=lambda: _env("ANTHROPIC_MODEL", "claude-sonnet-4-5"))
    openai_api_key: str = field(default_factory=lambda: _env("OPENAI_API_KEY"))
    openai_model: str = field(default_factory=lambda: _env("OPENAI_MODEL", "gpt-4o-mini"))

    gptzero_api_key: str = field(default_factory=lambda: _env("GPTZERO_API_KEY"))
    sapling_api_key: str = field(default_factory=lambda: _env("SAPLING_API_KEY"))

    image_provider: str = field(default_factory=lambda: _env("IMAGE_PROVIDER", "pollinations"))
    stability_api_key: str = field(default_factory=lambda: _env("STABILITY_API_KEY"))
    pollinations_token: str = field(default_factory=lambda: _env("POLLINATIONS_TOKEN"))
    cloudflare_account_id: str = field(default_factory=lambda: _env("CLOUDFLARE_ACCOUNT_ID"))
    cloudflare_api_token: str = field(default_factory=lambda: _env("CLOUDFLARE_API_TOKEN"))

    default_language: str = field(default_factory=lambda: _env("SITE_LANGUAGE", "en"))
    site_name: str = field(default_factory=lambda: _env("SITE_NAME", "Your Blog"))
    site_base_url: str = field(default_factory=lambda: _env("SITE_BASE_URL", "https://example.com"))
    author_name: str = field(default_factory=lambda: _env("AUTHOR_NAME", "Staff Writer"))
    publisher_name: str = field(default_factory=lambda: _env("PUBLISHER_NAME", ""))
    publisher_logo_url: str = field(default_factory=lambda: _env("PUBLISHER_LOGO_URL", ""))
    publisher_url: str = field(default_factory=lambda: _env("PUBLISHER_URL", ""))
    site_timezone: str = field(default_factory=lambda: _env("SITE_TIMEZONE", "UTC"))
    # {base}/{yyyy}/{mm}/{slug}.html matches Blogger; use {base}/{slug} for most CMSes.
    permalink_pattern: str = field(
        default_factory=lambda: _env("PERMALINK_PATTERN", "{base}/{yyyy}/{mm}/{slug}.html"))
    # Blogger and most themes render the post title as the page H1 themselves, so
    # the body must not contain a second one.
    body_includes_h1: bool = field(
        default_factory=lambda: _env("BODY_INCLUDES_H1", "false").lower() == "true")
    cta_url: str = field(default_factory=lambda: _env("CTA_URL", ""))
    cta_link_text: str = field(default_factory=lambda: _env("CTA_LINK_TEXT", ""))

    output_dir: Path = field(
        default_factory=lambda: (Path(_env("OUTPUT_DIR")).expanduser()
                                 if _env("OUTPUT_DIR") else default_output_dir()))
    user_agent: str = field(
        default_factory=lambda: _env(
            "HTTP_USER_AGENT", "Mozilla/5.0 (compatible; NewsBlogMCP/0.1)"
        )
    )
    http_timeout: float = 25.0
    # Search providers get a shorter leash: six calls at 25s each is a two-minute
    # wait before anything is printed, which reads as a hang.
    search_timeout: float = 12.0

    def __post_init__(self) -> None:
        if not self.publisher_name:
            self.publisher_name = self.site_name
        if not self.output_dir.is_absolute():
            # A relative OUTPUT_DIR is relative to the data directory, not to
            # whatever directory the MCP client happened to launch us from.
            self.output_dir = (data_dir() / self.output_dir).resolve()

    @property
    def has_llm(self) -> bool:
        return bool(self.anthropic_api_key or self.openai_api_key)

    @property
    def has_detector(self) -> bool:
        return bool(self.gptzero_api_key or self.sapling_api_key)

    def capability_report(self) -> dict:
        return {
            "search": {
                "tavily": bool(self.tavily_api_key),
                "brave": bool(self.brave_api_key),
                "serper": bool(self.serper_api_key),
                "google_cse": bool(self.google_cse_key and self.google_cse_id),
                "newsapi": bool(self.newsapi_key),
                "keyless": ["gdelt", "bing_rss", "google_rss"],
                "forced_provider": self.search_provider or None,
            },
            "humanize_llm": {
                "anthropic": bool(self.anthropic_api_key),
                "openai": bool(self.openai_api_key),
                "fallback": "instructions returned to the calling LLM",
            },
            "ai_detector": {
                "gptzero": bool(self.gptzero_api_key),
                "sapling": bool(self.sapling_api_key),
                "fallback": "local heuristic scorer (not a real detector)",
            },
            "image": {
                "provider": self.image_provider,
                "stability_key": bool(self.stability_api_key),
                "cloudflare": bool(self.cloudflare_account_id and self.cloudflare_api_token),
                "pollinations_token": bool(self.pollinations_token),
                "note": ("Anonymous Pollinations is rate limited to roughly one request "
                         "every 15 seconds and may watermark output. A free token from "
                         "auth.pollinations.ai removes the watermark."),
            },
            "output_dir": str(self.output_dir),
            "publishing": {
                "site": self.site_name, "author": self.author_name,
                "timezone": self.site_timezone, "permalink": self.permalink_pattern,
                "body_includes_h1": self.body_includes_h1,
            },
        }


CONFIG = Config()
