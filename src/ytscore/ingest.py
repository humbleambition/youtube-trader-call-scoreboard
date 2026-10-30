"""Fetch captions and turn them into timestamped plain text for extraction.

Auto-generated YouTube captions "roll": each cue repeats the tail of the previous one.
`dedupe_cues` removes that overlap so every spoken word appears once, and inserts a
`[M:SS]` marker at the first cue of each new minute so extracted calls can carry a
timestamp a viewer can jump to.

Transcripts are copyrighted full text: they are written to a local `transcripts/`
directory that is git-ignored and must never be committed.
"""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Iterable

Cue = tuple[float, str]  # (start time in seconds, caption text)


def parse_srt(text: str) -> list[Cue]:
    """Parse SRT content into (start_seconds, text) cues."""
    cues: list[Cue] = []
    for block in re.split(r"\n\s*\n", text.strip()):
        lines = [l.strip() for l in block.strip().splitlines()]
        if len(lines) < 3 or "-->" not in lines[1]:
            continue
        h, m, s = lines[1].split("-->")[0].strip().replace(",", ".").split(":")
        cues.append((int(h) * 3600 + int(m) * 60 + float(s), " ".join(lines[2:])))
    return cues


def fmt_ts(seconds: float) -> str:
    """Elapsed time as M:SS (minutes may exceed 59), e.g. 3725 -> '62:05'."""
    s = int(seconds)
    return f"{s // 60}:{s % 60:02d}"


def dedupe_cues(cues: Iterable[Cue], lookback: int = 60) -> str:
    """Join cues into text, dropping words a cue repeats from the end of what came before.

    For each cue, find the longest prefix of its words that equals a suffix of the last
    `lookback` words already kept, and keep only the remainder (same rule as the pilot tracker).
    """
    words: list[str] = []
    marks: dict[int, float] = {}  # word index -> start seconds of first new cue in that minute
    seen_minutes: set[int] = set()
    for start, text in cues:
        w = text.split()
        if not w:
            continue
        tail = words[-lookback:]
        k = 0
        for n in range(min(len(w), len(tail)), 0, -1):
            if tail[-n:] == w[:n]:
                k = n
                break
        new = w[k:]
        if not new:
            continue
        minute = int(start // 60)
        if minute not in seen_minutes:
            seen_minutes.add(minute)
            marks[len(words)] = start
        words += new
    out: list[str] = []
    for i, wd in enumerate(words):
        if i in marks:
            out.append(f"\n[{fmt_ts(marks[i])}]")
        out.append(wd)
    return " ".join(out).strip()


def srt_to_text(text: str) -> str:
    return dedupe_cues(parse_srt(text))


def fetch_transcript(video_id: str, languages: tuple[str, ...] = ("en",)) -> str:
    """Download captions with youtube-transcript-api and return deduplicated text."""
    from youtube_transcript_api import YouTubeTranscriptApi

    fetched = YouTubeTranscriptApi().fetch(video_id, languages=list(languages))
    return dedupe_cues((s.start, s.text.replace("\n", " ")) for s in fetched)


def ingest(video_ids: Iterable[str], out_dir: str | Path, force: bool = False) -> dict[str, str]:
    """Fetch each video's captions into out_dir/<id>.txt. Returns {id: 'ok'|'skipped'|error}."""
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    status: dict[str, str] = {}
    for vid in video_ids:
        dst = out / f"{vid}.txt"
        if dst.exists() and not force:
            status[vid] = "skipped"
            continue
        try:
            dst.write_text(fetch_transcript(vid))
            status[vid] = "ok"
        except Exception as e:  # captions disabled, members-only, rate limited ...
            status[vid] = f"error: {type(e).__name__}"
    return status


# ---- channel listing (YouTube's /videos and /streams tabs; no API key) ----

_UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/120",
       "Cookie": "CONSENT=YES+1; SOCS=CAI", "Accept-Language": "en-US"}
_AGO_DAYS = {"second": 0, "minute": 0, "hour": 0, "day": 1, "week": 7, "month": 30, "year": 365}


def ago_to_days(s: str | None) -> int:
    m = re.search(r"(\d+) (second|minute|hour|day|week|month|year)", s or "")
    return int(m.group(1)) * _AGO_DAYS[m.group(2)] if m else 999


def _walk(o, acc):
    if isinstance(o, dict):
        if "lockupViewModel" in o:
            acc.append(o["lockupViewModel"])
        for v in o.values():
            _walk(v, acc)
    elif isinstance(o, list):
        for v in o:
            _walk(v, acc)


def list_channel_videos(channel: dict, max_days: int = 14) -> list[dict]:
    """Recent uploads and streams for a channels.yaml entry. Dates are YouTube's 'N days ago'
    and can be off by a day; extraction prefers a date the host states."""
    import requests

    res = []
    for tab in ("videos", "streams"):
        html = requests.get(f"{channel['url']}/{tab}", headers=_UA, timeout=25).text
        m = re.search(r"var ytInitialData = (\{.*?\});</script>", html)
        if not m:
            continue
        acc: list = []
        _walk(json.loads(m.group(1)), acc)
        for l in acc:
            try:
                title = l["metadata"]["lockupMetadataViewModel"]["title"]["content"]
            except (KeyError, TypeError):
                continue
            s = json.dumps(l)
            ago = re.search(r'"accessibilityLabel": "([^"]*ago)"', s)
            dur = re.search(r'"text": "(\d+:\d\d(?::\d\d)?)"', s)
            d = ago_to_days(ago.group(1) if ago else None)
            if d <= max_days:
                res.append(dict(channel=channel["name"], id=l.get("contentId"), title=title, tab=tab,
                                days_ago=d, duration=dur.group(1) if dur else None))
    return res
