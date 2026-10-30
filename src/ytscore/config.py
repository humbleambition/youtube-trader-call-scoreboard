"""Load channels.yaml and exclusions.yaml."""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import yaml


@dataclass
class Exclusions:
    channels: set[str] = field(default_factory=set)
    videos: set[str] = field(default_factory=set)
    calls: set[tuple[str, str]] = field(default_factory=set)  # (video_id, TICKER)


def load_exclusions(path: str | Path | None) -> Exclusions:
    if not path or not Path(path).exists():
        return Exclusions()
    d = yaml.safe_load(Path(path).read_text()) or {}
    return Exclusions(
        channels={c["name"].strip() for c in d.get("channels") or []},
        videos={v["id"] for v in d.get("videos") or []},
        calls={(c["video_id"], c["ticker"].upper().strip()) for c in d.get("calls") or []},
    )


def load_channels(path: str | Path) -> list[dict]:
    return (yaml.safe_load(Path(path).read_text()) or {}).get("channels") or []
