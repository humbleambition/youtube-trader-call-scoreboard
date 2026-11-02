"""Random-day twin test: is a channel's timing better than the same calls made on random days?

For every scored next-session call, a "twin" keeps the instrument, the bias (bullish / bearish / neutral) and the
hit threshold, but is scored on a random session drawn from a pool of recent sessions for that instrument instead
of the day the call was made. One twin set = one random twin for every call a channel made. With N twin sets
(default 10,000), a channel's twin p-value is

    p = (1 + number of twin sets with at least as many hits as the real calls) / (N + 1)

A channel whose real hit count sits inside its twins' range has no timing edge: its calls would have done just as
well on any other day. Twins control for the channel's mix of bias and instruments (a channel that is bullish on
everything in a rising market gets the same help on random days), which the coin-flip test does not.

Because ~20 channels are tested at once, the p-values are Holm-corrected (family-wise error at 5%).
"""
from __future__ import annotations

import datetime as dt
import random
from typing import Callable

from .score import bias_ok, vol_threshold, yahoo_symbol

N_SETS = 10_000  # enough resolution for a Holm correction across ~20 channels (min p = 1/10,001)
POOL_SESSIONS = 120  # sessions before the scoring cutoff that twins are drawn from (about six months)


def _pool(rows: list, until: str, size: int) -> list[float]:
    """Next-session moves (close to next close) for the last `size` reference sessions with ref date < until."""
    moves = [rows[i + 1][4] / rows[i][4] - 1 for i in range(len(rows) - 1) if rows[i + 1][0] < until]
    return moves[-size:]


def holm(pvals: list[float]) -> list[float]:
    """Holm step-down adjusted p-values, in the input order."""
    m = len(pvals)
    order = sorted(range(m), key=lambda i: pvals[i])
    adj, running = [0.0] * m, 0.0
    for rank, i in enumerate(order):
        running = max(running, min(1.0, (m - rank) * pvals[i]))
        adj[i] = running
    return adj


def twin_test(scored: list[dict], price_loader: Callable[[str], list | None], channels: list[str],
              until: str, n_sets: int = N_SETS, pool: int = POOL_SESSIONS, seed: int = 7) -> dict[str, dict]:
    """Returns {channel: {n, hits, twin_mean, twin_p, twin_p_holm}} for the given channels."""
    rng = random.Random(seed)
    pools: dict[str, list[float]] = {}
    out = {}
    for ch in channels:
        calls = [r for r in scored if r["channel"].strip() == ch and r.get("next_day_ok") is not None]
        usable = []
        for r in calls:
            sym = yahoo_symbol(r["ticker"], r["group"])
            if sym not in pools:
                rows = price_loader(sym)
                pools[sym] = _pool(rows, until, pool) if rows else []
            if len(pools[sym]) >= 20:
                usable.append((pools[sym], r["st"], vol_threshold(r["ticker"], r["group"]), bool(r["next_day_ok"])))
        k = sum(u[3] for u in usable)
        sets = [sum(bool(bias_ok(b, rng.choice(p), t)) for p, b, t, _ in usable) for _ in range(n_sets)]
        out[ch] = dict(n=len(usable), hits=k,
                       hit=round(k / len(usable), 4) if usable else None,
                       twin_mean=round(sum(sets) / n_sets / len(usable), 4) if usable else None,
                       twin_p=round((1 + sum(s >= k for s in sets)) / (n_sets + 1), 4))
    names = list(out)
    for ch, a in zip(names, holm([out[c]["twin_p"] for c in names])):
        out[ch]["twin_p_holm"] = round(a, 4)
    return out


def pool_start(until: str, pool: int = POOL_SESSIONS) -> str:
    """A download start date comfortably before the pool (calendar days, with room for weekends and holidays)."""
    return (dt.date.fromisoformat(until) - dt.timedelta(days=int(pool * 1.6) + 30)).isoformat()
