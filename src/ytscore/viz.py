"""Charts: channels x sessions hit-rate heatmap, and the leaderboard bar chart."""
from __future__ import annotations

import datetime as dt
from collections import defaultdict
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.colors as mc  # noqa: E402
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.patches import FancyBboxPatch  # noqa: E402

INK, BG, MUTE, EMPTY = "#1d1d1f", "#f4f4f5", "#7a7a7e", "#e2e2e5"
RED, MID, GREEN = "#b0605a", "#e9dfcf", "#4f7a5d"
CMAP = mc.LinearSegmentedColormap.from_list("rg", [RED, MID, GREEN])
plt.rcParams.update({"font.family": "DejaVu Sans", "text.color": INK})


def _short(d: str) -> str:
    return dt.date.fromisoformat(d).strftime("%b %-d")


def _cell(ax, x, y, color):
    ax.add_patch(FancyBboxPatch((x + 0.04, y + 0.06), 0.86, 0.78,
                                boxstyle="round,pad=0,rounding_size=0.07", color=color, lw=0))


def session_heatmap(scored: list[dict], out: str | Path, min_session_calls: int = 1, min_channel_calls: int = 15):
    """Each column is one session (same close-to-close window for every channel); cell = right/scored."""
    cnt = defaultdict(int)
    for x in scored:
        if x.get("next_day_ok") is not None:
            cnt[x["next_date"]] += 1
    sess = sorted(d for d, n in cnt.items() if n >= min_session_calls)
    hit = defaultdict(lambda: defaultdict(list))
    for x in scored:
        if x.get("next_date") in sess and x.get("next_day_ok") is not None:
            hit[x["channel"].strip()][x["next_date"]].append(bool(x["next_day_ok"]))

    def rate(c):
        v = [b for l in hit[c].values() for b in l]
        return sum(v) / len(v), len(v)

    chs = sorted([c for c in hit if rate(c)[1] >= min_channel_calls], key=lambda c: -rate(c)[0])
    W, H = len(sess), len(chs)
    fig, ax = plt.subplots(figsize=(3.6 + W * 0.66, 1.9 + H * 0.4), dpi=150)
    fig.patch.set_facecolor(BG)
    ax.set_facecolor(BG)
    for i, d in enumerate(sess):
        day = dt.date.fromisoformat(d)
        ax.text(i + 0.47, -0.25, day.strftime("%a\n%b %-d"), ha="center", va="bottom", fontsize=7.5,
                fontweight="bold", linespacing=1.1)
    for j, c in enumerate(chs):
        for i, d in enumerate(sess):
            v = hit[c].get(d)
            if not v:
                _cell(ax, i, j, EMPTY)
                continue
            r = sum(v) / len(v)
            _cell(ax, i, j, CMAP(r))
            ax.text(i + 0.47, j + 0.45, f"{sum(v)}/{len(v)}", ha="center", va="center", fontsize=6.5,
                    family="DejaVu Sans Mono", color=INK if 0.25 < r < 0.75 else "white")
        r, n = rate(c)
        ax.text(-0.15, j + 0.45, c, ha="right", va="center", fontsize=9)
        ax.text(W + 0.15, j + 0.45, f"{round(100 * r)}%  n={n}", ha="left", va="center", fontsize=8,
                family="DejaVu Sans Mono", color=MUTE)
    ax.text(W + 0.15, -0.25, "overall", ha="left", va="bottom", fontsize=7.5, color=MUTE)
    ax.set_xlim(-0.05, W + 1.9)
    ax.set_ylim(H, -0.95)
    ax.axis("off")
    fig.suptitle("Next-session hit rate by session", x=0.01, y=0.995, ha="left", va="top", fontsize=13, fontweight="bold")
    fig.text(0.01, 1 - 0.36 / (1.9 + H * 0.4),
             f"Right calls / scored calls per channel, all markets combined. Each column is one session "
             f"({_short(sess[0])} to {_short(sess[-1])}), the same close-to-close move for every channel.",
             ha="left", va="top", fontsize=8.5, color=MUTE)
    fig.text(0.01, 0.008, f"Green = mostly right, red = mostly wrong, grey = no scored call. Channels with at least "
             f"{min_channel_calls} scored calls, best overall first. Weekend columns are crypto.",
             fontsize=7.5, color=MUTE)
    plt.tight_layout(rect=(0, 0.015, 1, 1 - 0.55 / (1.9 + H * 0.4)))
    plt.savefig(out, facecolor=BG)
    plt.close(fig)
    return sess, chs


def leaderboard_chart(rows: list[dict], out: str | Path, window: str = ""):
    """Horizontal bars of next-session hit rate, with the always-long baseline and the 50% coin-flip line."""
    H = len(rows)
    fig, ax = plt.subplots(figsize=(10, 1.5 + H * 0.38), dpi=150)
    fig.patch.set_facecolor(BG)
    ax.set_facecolor(BG)
    for j, r in enumerate(rows):
        a = r["day"]
        ax.barh(j, a["hit"] * 100, height=0.62, color=CMAP(min(max((a["hit"] - 0.3) / 0.4, 0), 1)), lw=0)
        ax.plot([a["long"] * 100] * 2, [j - 0.36, j + 0.36], color=INK, lw=1.6)
        ax.text(max(a["hit"], a["long"]) * 100 + 1.5, j, f"{100 * a['hit']:.0f}%  n={a['n']}", va="center", fontsize=8.5,
                family="DejaVu Sans Mono", zorder=3, bbox=dict(boxstyle="square,pad=0.15", fc=BG, ec="none"))
    ax.axvline(50, color=MUTE, lw=1, ls=(0, (3, 3)), zorder=1)
    ax.set_yticks(range(H), [r["channel"] for r in rows], fontsize=9)
    ax.set_ylim(H - 0.4, -0.6)
    ax.set_xlim(0, 100)
    ax.set_xticks([0, 25, 50, 75, 100], ["0%", "25%", "50%", "75%", "100%"], fontsize=8, color=MUTE)
    for s in ("top", "right", "left"):
        ax.spines[s].set_visible(False)
    ax.spines["bottom"].set_color(MUTE)
    ax.tick_params(axis="y", length=0)
    fig.suptitle("Short-term call leaderboard", x=0.01, y=0.995, ha="left", va="top", fontsize=13, fontweight="bold")
    fig.text(0.01, 1 - 0.36 / (1.5 + H * 0.38),
             f"Share of next-session calls that were right{(' · ' + window) if window else ''}. "
             "Black tick = always-long baseline on the same calls; dashed line = coin flip.",
             ha="left", va="top", fontsize=8.5, color=MUTE)
    plt.tight_layout(rect=(0, 0, 1, 1 - 0.55 / (1.5 + H * 0.38)))
    plt.savefig(out, facecolor=BG)
    plt.close(fig)


CALL_GROUPS = [("Indices", ["ES", "NQ", "RTY"]), ("Metals", ["GC", "SI"]), ("Crypto", ["BTC"]),
               ("Rates / oil / dollar", ["TNX", "CL", "DXY"])]
CALL_NAMES = {"ES": "S&P 500", "NQ": "Nasdaq", "RTY": "Russell", "GC": "Gold", "SI": "Silver", "BTC": "Bitcoin",
              "TNX": "10y yield", "CL": "Crude", "DXY": "Dollar"}
BIAS_COL = {"bullish": "#9cc2a6", "bearish": "#dba59e", "neutral": "#cfcfd3"}
_WHEN = {"weekend": 0, "premarket": 1, "unknown": 1, "intraday": 2, "after_close": 3}


def calls_heatmap(scored: list[dict], session: str, out: str | Path, horizon: str = "short"):
    """What each channel called on each market, all scored over ONE shared window.

    horizon="short": calls whose next session is `session` (close before -> session close).
    horizon="week":  medium-term calls whose reference close is `session`, scored one week later.
    The actual move is printed once per column, so every cell is judged against the same number."""
    tick = [t for _, ts in CALL_GROUPS for t in ts]
    key_b, key_ok, key_pct = ("st", "next_day_ok", "next_day_pct") if horizon == "short" else ("mt", "mt_early_ok", "week_pct")
    rows = sorted(scored, key=lambda x: (x.get("date") or "", _WHEN.get(x.get("when"), 1)))
    cells, moves, end = defaultdict(dict), {}, None
    for x in rows:
        t = x.get("ticker")
        if t not in tick or x.get(key_b) in (None, "none"):
            continue
        if horizon == "short" and x.get("next_date") != session:
            continue
        if horizon == "week" and (x.get("ref_date") != session or not x.get("week_to")):
            continue
        cells[x["channel"].strip()][t] = (x[key_b], x.get(key_ok))  # latest call wins
        if x.get(key_pct) is not None:
            moves[t] = x[key_pct]
        if horizon == "week":
            end = max(end or "", x["week_to"])
    if not cells:
        raise ValueError(f"no calls for {horizon} window {session}")
    chs = sorted(cells, key=lambda c: (-len(cells[c]), c))
    W, H = len(tick), len(chs)
    fig, ax = plt.subplots(figsize=(2.8 + W * 1.05, 2.4 + H * 0.42), dpi=150)
    fig.patch.set_facecolor(BG); ax.set_facecolor(BG)
    for i, t in enumerate(tick):
        m = moves.get(t)
        ax.text(i + 0.47, -0.95, CALL_NAMES[t], ha="center", fontsize=9, fontweight="bold")
        ax.text(i + 0.47, -0.45, "n/a" if m is None else f"{m:+.1f}%", ha="center", fontsize=9.5,
                family="DejaVu Sans Mono", fontweight="bold", color=MUTE if m is None else (GREEN if m > 0 else RED))
    for j, c in enumerate(chs):
        for i, t in enumerate(tick):
            v = cells[c].get(t)
            _cell(ax, i, j, EMPTY if not v else BIAS_COL.get(v[0], "#e0cf9a"))
            if v:
                lab = {"bullish": "Bull", "bearish": "Bear", "neutral": "Flat"}.get(v[0], "Mixed")
                ax.text(i + 0.47, j + 0.45, f"{lab} {({True: '✓', False: '✗'}).get(v[1], '')}".strip(),
                        ha="center", va="center", fontsize=8.5, fontweight="bold")
        ok = [v[1] for v in cells[c].values() if v[1] is not None]
        ax.text(-0.12, j + 0.45, c, ha="right", va="center", fontsize=9)
        ax.text(W + 0.1, j + 0.45, f"{sum(ok)}/{len(ok)}" if ok else "", ha="left", va="center",
                fontsize=8.5, family="DejaVu Sans Mono", color=MUTE)
    ax.text(W + 0.1, -0.45, "right", ha="left", fontsize=8, color=MUTE)
    x0 = 0
    for g, ts in CALL_GROUPS:
        ax.plot([x0 + 0.04, x0 + len(ts) - 0.1], [-1.35, -1.35], color=MUTE, lw=1)
        ax.text(x0 + len(ts) / 2 - 0.03, -1.5, g, ha="center", fontsize=8, color=MUTE)
        x0 += len(ts)
    ax.set_xlim(-0.05, W + 0.75); ax.set_ylim(H, -1.75); ax.axis("off")
    day = dt.date.fromisoformat(session).strftime("%a %b %-d, %Y")
    if horizon == "short":
        title = f"Short-term calls for the {day} session"
        sub = f"Every cell is scored on the same move: the prior close to the {_short(session)} close, printed once under each market"
    else:
        title = f"Medium-term calls made before the {_short(session)} close, one week later"
        sub = f"Every cell is scored on the same window: {_short(session)} close to {_short(end)} close, printed once under each market"
    fig.text(0.02, 0.985, title, ha="left", va="top", fontsize=12.5, fontweight="bold")
    fig.text(0.02, 0.985 - 0.36 / (2.4 + H * 0.42), sub, ha="left", va="top", fontsize=9, color=MUTE)
    fig.text(0.02, 0.006, "✓ right  ✗ wrong  (no mark = mixed or conditional, not scored).  Latest call per channel; grey = no call.",
             fontsize=7.5, color=MUTE)
    plt.tight_layout(rect=(0, 0.02, 1, 0.94))
    plt.savefig(out, facecolor=BG); plt.close()
    return out
