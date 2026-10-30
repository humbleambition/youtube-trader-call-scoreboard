"""Hit rates and the two baselines every channel is compared with."""
from __future__ import annotations

from math import comb


def binom_p_at_least(k: int, n: int, p: float = 0.5) -> float:
    """One-sided P(X >= k) for X ~ Binomial(n, p). With p=0.5: chance a coin flip does at least this well."""
    if n == 0:
        return 1.0
    return sum(comb(n, i) * p ** i * (1 - p) ** (n - i) for i in range(k, n + 1))


def summarize(records: list[dict], ok_key: str, pct_key: str) -> dict:
    """n scored calls, hit rate, 'always long' baseline (share of those same calls where the market rose),
    and the coin-flip p-value."""
    c = [r for r in records if r.get(ok_key) is not None]
    n = len(c)
    k = sum(bool(r[ok_key]) for r in c)
    up = sum((r.get(pct_key) or 0) > 0 for r in c)
    return dict(n=n, hits=k,
                hit=round(k / n, 4) if n else None,
                long=round(up / n, 4) if n else None,
                edge=round((k - up) / n, 4) if n else None,
                p=round(binom_p_at_least(k, n), 4))
