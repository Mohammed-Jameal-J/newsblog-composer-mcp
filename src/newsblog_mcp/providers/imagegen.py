"""Image generation providers plus the trademark filter that runs before any
prompt leaves the machine."""
from __future__ import annotations

import base64
import re
from pathlib import Path
from urllib.parse import quote

import httpx

from ..config import Config

# Seed list. Extend freely - the filter is a safety net, not a legal opinion.
TRADEMARKS = {
    "openai": "an AI research lab", "chatgpt": "a chat assistant interface",
    "anthropic": "an AI research lab", "claude": "an AI assistant",
    "gemini": "an AI assistant", "copilot": "a coding assistant",
    "nvidia": "a chipmaker", "geforce": "a graphics card", "cuda": "a compute platform",
    "intel": "a chipmaker", "amd": "a chipmaker", "ryzen": "a processor",
    "qualcomm": "a chipmaker", "snapdragon": "a mobile processor", "arm": "a chip designer",
    "apple": "a consumer electronics maker", "iphone": "a smartphone",
    "ipad": "a tablet", "macbook": "a laptop", "ios": "a mobile operating system",
    "google": "a search company", "android": "a mobile operating system",
    "youtube": "a video platform", "chrome": "a web browser",
    "microsoft": "a software company", "windows": "a desktop operating system",
    "azure": "a cloud platform", "xbox": "a games console",
    "meta": "a social media company", "facebook": "a social network",
    "instagram": "a photo sharing app", "whatsapp": "a messaging app",
    "amazon": "an online retailer", "aws": "a cloud platform", "alexa": "a voice assistant",
    "tesla": "an electric car maker", "spacex": "a rocket company",
    "starlink": "a satellite network", "twitter": "a social network", "tiktok": "a short video app",
    "samsung": "an electronics maker", "galaxy": "a smartphone", "sony": "an electronics maker",
    "playstation": "a games console", "netflix": "a streaming service",
    "disney": "an entertainment company", "spotify": "a music streaming service",
    "uber": "a ride hailing app", "airbnb": "a home rental platform",
    "reuters": "a news agency", "bloomberg": "a financial news outlet",
    "deepseek": "an AI lab", "mistral": "an AI lab", "huggingface": "an AI platform",
}
_BRAND_HINT = re.compile(r"\b(logo|logotype|wordmark|trademark|brand mark|branding)\b", re.I)


class ImageProviderError(RuntimeError):
    pass


# Brand names that are also ordinary English words. Replacing these on sight
# turned "a small robotic arm" into "a small robotic a chip designer", so they
# only count as brands when the word after them makes the company the subject.
_AMBIGUOUS = {
    "arm": re.compile(
        r"\barm\b(?=\s+(?:holdings|ltd|plc|cpus?|chips?|cores?|architecture|"
        r"processors?|designs?|licen\w+|neoverse|cortex|said|says|announced)\b)",
        re.I),
    "meta": re.compile(
        r"\bmeta\b(?=\s+(?:platforms|inc|ai|llama|quest|reality|oculus|said|"
        r"says|announced)\b)", re.I),
    "apple": re.compile(
        r"\bapple\b(?=\s+(?:inc|said|says|announced|confirmed|iphone|ipad|mac|"
        r"watch|tv|silicon|park|store|event)\b)", re.I),
}


def sanitize_prompt(prompt: str) -> tuple[str, list[str]]:
    """Strip brand names and logo requests. Returns (safe_prompt, removed)."""
    removed: list[str] = []
    safe = prompt
    for term, pattern in _AMBIGUOUS.items():
        replacement = TRADEMARKS.get(term)
        if replacement and pattern.search(safe):
            removed.append(term)
            safe = pattern.sub(replacement, safe)
    for term, replacement in TRADEMARKS.items():
        if term in _AMBIGUOUS:
            continue  # handled above, on a narrower pattern
        # Swallow any article in front of the brand so "the Nvidia logo" does not
        # become "the a chipmaker abstract symbol".
        pattern = re.compile(rf"\b(?:the|a|an)\s+{re.escape(term)}\b|\b{re.escape(term)}\b", re.I)
        if pattern.search(safe):
            removed.append(term)
            safe = pattern.sub(replacement, safe)
    if _BRAND_HINT.search(safe):
        removed.append("logo/brand-mark request")
        safe = _BRAND_HINT.sub("abstract symbol", safe)
    safe = re.sub(r"\s{2,}", " ", safe).strip().rstrip(".,;: ")
    safe += (". No text, no logos, no brand marks, no recognisable trademarks, "
             "no real people.")
    return safe, sorted(set(removed))


def generate(prompt: str, style: str, cfg: Config, out_path: Path) -> dict:
    """Writes the image to out_path. Returns provider metadata."""
    width, height = (1200, 630) if style == "banner" else (1024, 1024)
    provider = (cfg.image_provider or "pollinations").lower()

    if provider == "openai":
        if not cfg.openai_api_key:
            raise ImageProviderError("IMAGE_PROVIDER=openai but OPENAI_API_KEY is unset.")
        size = "1792x1024" if style == "banner" else "1024x1024"
        with httpx.Client(timeout=180.0) as client:
            r = client.post(
                "https://api.openai.com/v1/images/generations",
                headers={"Authorization": f"Bearer {cfg.openai_api_key}"},
                json={"model": "gpt-image-1", "prompt": prompt, "size": size, "n": 1},
            )
            r.raise_for_status()
            data = r.json()["data"][0]
        if data.get("b64_json"):
            out_path.write_bytes(base64.b64decode(data["b64_json"]))
        else:
            with httpx.Client(timeout=180.0) as client:
                out_path.write_bytes(client.get(data["url"]).content)
        return {"provider": "openai", "size": size}

    if provider == "stability":
        if not cfg.stability_api_key:
            raise ImageProviderError("IMAGE_PROVIDER=stability but STABILITY_API_KEY is unset.")
        with httpx.Client(timeout=180.0) as client:
            r = client.post(
                "https://api.stability.ai/v2beta/stable-image/generate/core",
                headers={"Authorization": f"Bearer {cfg.stability_api_key}",
                         "Accept": "image/*"},
                files={"none": ""},
                data={"prompt": prompt, "output_format": "png",
                      "aspect_ratio": "16:9" if style == "banner" else "1:1"},
            )
            r.raise_for_status()
            out_path.write_bytes(r.content)
        return {"provider": "stability", "size": f"{width}x{height}"}

    if provider == "cloudflare":
        if not (cfg.cloudflare_account_id and cfg.cloudflare_api_token):
            raise ImageProviderError(
                "IMAGE_PROVIDER=cloudflare needs CLOUDFLARE_ACCOUNT_ID and "
                "CLOUDFLARE_API_TOKEN."
            )
        endpoint = (f"https://api.cloudflare.com/client/v4/accounts/"
                    f"{cfg.cloudflare_account_id}/ai/run/@cf/black-forest-labs/flux-1-schnell")
        with httpx.Client(timeout=180.0) as client:
            r = client.post(
                endpoint,
                headers={"Authorization": f"Bearer {cfg.cloudflare_api_token}"},
                json={"prompt": prompt[:2048], "steps": 6},
            )
            r.raise_for_status()
            payload = r.json()
        b64 = (payload.get("result") or {}).get("image") or payload.get("image")
        if not b64:
            raise ImageProviderError(f"Cloudflare returned no image: {str(payload)[:200]}")
        out_path.write_bytes(base64.b64decode(b64))
        return {"provider": "cloudflare", "model": "flux-1-schnell",
                "size": "1024x1024 (model fixed; crop to your banner ratio)"}

    # Keyless default. Anonymous access still works but is rate limited to about
    # one request every 15 seconds and may watermark the result. A free token
    # from auth.pollinations.ai lifts both.
    url = (f"https://image.pollinations.ai/prompt/{quote(prompt)}"
           f"?width={width}&height={height}&nologo=true")
    headers = {"User-Agent": cfg.user_agent}
    if cfg.pollinations_token:
        headers["Authorization"] = f"Bearer {cfg.pollinations_token}"
    with httpx.Client(timeout=180.0, follow_redirects=True) as client:
        r = client.get(url, headers=headers)
        r.raise_for_status()
        body = r.content
    if body[:1] == b"{" or b"<html" in body[:200].lower():
        raise ImageProviderError(
            "Pollinations returned a page rather than an image, which usually means "
            "the anonymous rate limit was hit or the endpoint now requires a token. "
            "Get a free one at auth.pollinations.ai and set POLLINATIONS_TOKEN, or "
            "switch IMAGE_PROVIDER to cloudflare/openai/stability."
        )
    out_path.write_bytes(body)
    return {
        "provider": "pollinations",
        "size": f"{width}x{height}",
        "authenticated": bool(cfg.pollinations_token),
        "note": ("Anonymous tier: about one request every 15 seconds, basic models, "
                 "and output may carry a watermark. A free token from "
                 "auth.pollinations.ai removes the watermark and raises the limit."),
    }
