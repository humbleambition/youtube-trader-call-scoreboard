"""LLM extraction of calls from a transcript via any OpenAI-compatible chat endpoint (e.g. OpenRouter).

Environment:
  YTSCORE_LLM_API_KEY   API key (falls back to OPENROUTER_API_KEY, then OPENAI_API_KEY)
  YTSCORE_LLM_MODEL     model id, e.g. 'anthropic/claude-sonnet-4.5' (required)
  YTSCORE_LLM_BASE_URL  default https://openrouter.ai/api/v1
"""
from __future__ import annotations

import json
import os
import re
from importlib import resources
from pathlib import Path

from .schema import VideoCalls

DEFAULT_BASE_URL = "https://openrouter.ai/api/v1"


def load_prompt() -> str:
    return resources.files("ytscore").joinpath("prompts/extract.md").read_text()


def _settings() -> tuple[str, str, str]:
    key = os.getenv("YTSCORE_LLM_API_KEY") or os.getenv("OPENROUTER_API_KEY") or os.getenv("OPENAI_API_KEY")
    model = os.getenv("YTSCORE_LLM_MODEL")
    if not key or not model:
        raise RuntimeError("Set YTSCORE_LLM_API_KEY and YTSCORE_LLM_MODEL (see .env.example).")
    return key, model, os.getenv("YTSCORE_LLM_BASE_URL", DEFAULT_BASE_URL).rstrip("/")


def parse_json(text: str) -> dict:
    """Parse the model's reply, tolerating a ```json fence."""
    m = re.search(r"\{.*\}", text, re.S)
    if not m:
        raise ValueError("no JSON object in model reply")
    return json.loads(m.group(0))


def extract(transcript: str, meta: dict, timeout: int = 300) -> VideoCalls:
    """meta: {'video_id', 'channel', 'title', 'approx_date'}. Returns validated calls."""
    import requests

    key, model, base = _settings()
    user = (f"Metadata:\n{json.dumps(meta, ensure_ascii=False)}\n\nTranscript:\n{transcript}")
    r = requests.post(f"{base}/chat/completions", timeout=timeout,
                      headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
                      json={"model": model, "temperature": 0,
                            "response_format": {"type": "json_object"},
                            "messages": [{"role": "system", "content": load_prompt()},
                                         {"role": "user", "content": user}]})
    r.raise_for_status()
    data = parse_json(r.json()["choices"][0]["message"]["content"])
    data.setdefault("video_id", meta["video_id"])
    data.setdefault("channel", meta["channel"])
    return VideoCalls.model_validate(data)


def extract_file(transcript_path: str | Path, meta: dict, out_dir: str | Path) -> Path:
    vc = extract(Path(transcript_path).read_text(), meta)
    out = Path(out_dir) / f"{vc.video_id}.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(vc.model_dump_json(indent=1))
    return out
