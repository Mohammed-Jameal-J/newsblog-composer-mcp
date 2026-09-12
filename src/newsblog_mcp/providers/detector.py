"""AI-detection providers for score_ai_text. Optional; keyless fallback lives
in tools/score.py."""
from __future__ import annotations

import httpx

from ..config import Config


class NoDetectorConfigured(RuntimeError):
    pass


def detect(text: str, cfg: Config) -> dict:
    """Returns {human_score 0-100, detector_used, raw}."""
    if cfg.gptzero_api_key:
        with httpx.Client(timeout=60.0) as client:
            r = client.post(
                "https://api.gptzero.me/v2/predict/text",
                headers={"x-api-key": cfg.gptzero_api_key, "Content-Type": "application/json"},
                json={"document": text},
            )
            r.raise_for_status()
            data = r.json()
        doc = (data.get("documents") or [{}])[0]
        probs = doc.get("class_probabilities") or {}
        human = probs.get("human")
        if human is None:
            generated = doc.get("completely_generated_prob")
            human = (1.0 - generated) if generated is not None else None
        if human is None:
            raise RuntimeError(f"Unexpected GPTZero response shape: {list(doc)}")
        return {"human_score": round(float(human) * 100, 1),
                "detector_used": "gptzero", "raw": doc}

    if cfg.sapling_api_key:
        with httpx.Client(timeout=60.0) as client:
            r = client.post(
                "https://api.sapling.ai/api/v1/aidetect",
                json={"key": cfg.sapling_api_key, "text": text},
            )
            r.raise_for_status()
            data = r.json()
        ai_score = float(data.get("score", 0.0))  # 1.0 == fully AI
        return {"human_score": round((1.0 - ai_score) * 100, 1),
                "detector_used": "sapling", "raw": data}

    raise NoDetectorConfigured("No GPTZERO_API_KEY or SAPLING_API_KEY set.")
