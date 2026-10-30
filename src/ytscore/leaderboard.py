"""Per-channel leaderboard from scored calls."""
from __future__ import annotations

from .stats import summarize

MIN_N = 15  # minimum next-session scored calls to appear on the public leaderboard


def build(scored: list[dict], since: str = "0000", until: str = "9999", min_n: int = MIN_N) -> list[dict]:
    d = [x for x in scored if since <= x["date"] <= until]
    rows = []
    for ch in sorted({x["channel"].strip() for x in d}):
        mine = [x for x in d if x["channel"].strip() == ch]
        rows.append(dict(channel=ch, calls=len(mine),
                         day=summarize(mine, "next_day_ok", "next_day_pct"),
                         week=summarize(mine, "week_ok", "week_pct")))
    rows = [r for r in rows if r["day"]["n"] >= min_n]
    rows.sort(key=lambda r: (-(r["day"]["hit"] or 0), -r["day"]["n"]))
    for i, r in enumerate(rows, 1):
        r["rank"] = i
    return rows


def _pct(x):
    return "–" if x is None else f"{100 * x:.0f}%"


def to_markdown(rows: list[dict]) -> str:
    out = ["| # | Channel | Next-session hit rate | Scored calls | Always-long baseline | Edge vs long | p (vs coin flip) | 1-week hit rate (n) |",
           "|---|---|---|---|---|---|---|---|"]
    for r in rows:
        a, b = r["day"], r["week"]
        edge = "–" if a["edge"] is None else f"{100 * a['edge']:+.0f} pts"
        out.append(f"| {r['rank']} | {r['channel']} | {_pct(a['hit'])} | {a['n']} | {_pct(a['long'])} | {edge} | "
                   f"{a['p']:.3f} | {_pct(b['hit'])} ({b['n']}) |")
    return "\n".join(out)
