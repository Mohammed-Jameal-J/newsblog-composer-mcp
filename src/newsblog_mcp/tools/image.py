"""Tool 5 - generate_image.

The trademark filter runs before the prompt reaches any API, so a story about a
named company still produces a concept banner rather than an attempt at that
company's branding.
"""
from __future__ import annotations

from datetime import datetime, timezone

from ..config import CONFIG, Config
from ..providers.imagegen import ImageProviderError, generate, sanitize_prompt
from ..textutil import slugify


def generate_image(
    prompt: str,
    style: str = "banner",
    slug: str = "",
    cfg: Config | None = None,
) -> dict:
    cfg = cfg or CONFIG
    if style not in ("banner", "square"):
        return {"error": f"style must be 'banner' or 'square', got {style!r}"}
    if not (prompt or "").strip():
        return {"error": "empty prompt"}

    safe_prompt, removed = sanitize_prompt(prompt)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    name = f"{slugify(slug or prompt, 40)}-{style}-{stamp}.png"
    target_dir = cfg.output_dir / "images"
    target_dir.mkdir(parents=True, exist_ok=True)
    out_path = target_dir / name

    try:
        meta = generate(safe_prompt, style, cfg, out_path)
    except ImageProviderError as exc:
        return {"error": str(exc), "prompt_used": safe_prompt, "terms_removed": removed}
    except Exception as exc:
        return {"error": f"{type(exc).__name__}: {exc}", "prompt_used": safe_prompt,
                "terms_removed": removed}

    return {
        "image_path": str(out_path),
        "image_url_or_base64": out_path.as_uri(),
        "alt_text_suggestion": (
            "Illustration: " + safe_prompt.split(". No text")[0][:120]
        ),
        "prompt_used": safe_prompt,
        "original_prompt": prompt,
        "terms_removed": removed,
        "bytes": out_path.stat().st_size,
        **meta,
        "publish_note": (
            "image_url_or_base64 is a local file URI. Upload the file to your CDN or "
            "media library and pass the resulting public https URL into build_schema, "
            "otherwise NewsArticle.image will point at a path no crawler can reach."
        ),
    }
