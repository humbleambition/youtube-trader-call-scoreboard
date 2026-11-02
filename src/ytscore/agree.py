"""Extraction agreement: do two independent extraction passes over the same videos find the same calls?

Pass A is the published extraction (data/calls). Pass B is a second, independent pass over a random sample of
the same transcripts, made from the same public prompt without seeing pass A. For videos present in both:

- call recall: share of A's scorable short-term calls (bullish / bearish / neutral) that B also found on the
  same ticker with any bias, and the reverse (B's calls found by A);
- bias agreement: among calls both passes found, share where the short-term bias is the same;
- scored outcome agreement: among calls both passes scored, share where the hit / miss verdict is the same.

Low agreement means the host's words are ambiguous enough that two careful readers disagree, which limits how
much any single hit rate can mean.
"""
from __future__ import annotations

from pathlib import Path

from .schema import VideoCalls

SCORABLE = ("bullish", "bearish", "neutral")


def _calls(v: VideoCalls) -> dict[str, str]:
    """{TICKER: short-term bias} for scorable short-term calls (first mention wins)."""
    out: dict[str, str] = {}
    for c in v.calls:
        b = c.short_term.bias
        if b in SCORABLE:
            out.setdefault(c.ticker.upper().strip(), b)
    return out


def compare(a_dir: str | Path, b_dir: str | Path) -> dict:
    b_files = {f.stem: f for f in Path(b_dir).glob("*.json")}
    per_video, a_n, b_n, both, same = [], 0, 0, 0, 0
    for vid, fb in sorted(b_files.items()):
        fa = Path(a_dir) / f"{vid}.json"
        if not fa.exists():
            continue
        a = _calls(VideoCalls.model_validate_json(fa.read_text()))
        b = _calls(VideoCalls.model_validate_json(fb.read_text()))
        common = set(a) & set(b)
        agree = sum(a[t] == b[t] for t in common)
        a_n, b_n, both, same = a_n + len(a), b_n + len(b), both + len(common), same + agree
        per_video.append(dict(video_id=vid, a=len(a), b=len(b), both=len(common), same_bias=agree,
                              only_a=sorted(set(a) - set(b)), only_b=sorted(set(b) - set(a)),
                              differ={t: [a[t], b[t]] for t in sorted(common) if a[t] != b[t]}))
    return dict(videos=len(per_video), a_calls=a_n, b_calls=b_n, matched=both, same_bias=same,
                recall_a_in_b=round(both / a_n, 4) if a_n else None,
                recall_b_in_a=round(both / b_n, 4) if b_n else None,
                bias_agreement=round(same / both, 4) if both else None,
                per_video=per_video)
