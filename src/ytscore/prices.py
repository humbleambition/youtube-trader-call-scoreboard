"""Daily OHLC bars from Yahoo Finance (via yfinance), cached as JSON.

Cache format, one file per symbol (`^` replaced by `_`):
  {"complete_before": "YYYY-MM-DD", "bars": [[YYYY-MM-DD, open, high, low, close], ...]}
Only complete bars are cached (a bar still forming at download time is never stored), and a file is
re-downloaded when a later cutoff needs bars it does not have. A bare list of bars (the pilot tracker's
format) is also accepted and treated as complete, so an archived price snapshot can be replayed offline.
Closes are raw (auto_adjust=False), matching Yahoo's chart close used in the pilot.
"""
from __future__ import annotations

import datetime as dt
import json
import logging
import warnings
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Iterable
from zoneinfo import ZoneInfo

ET = ZoneInfo("America/New_York")
Bar = list  # [date, open, high, low, close]


def cache_path(cache_dir: str | Path, symbol: str) -> Path:
    return Path(cache_dir) / f"{symbol.replace('^', '_')}.json"


def complete_cutoff(now: dt.datetime | None = None) -> str:
    """First date whose daily bar may still be incomplete: today in US Eastern, or tomorrow after 8 pm ET."""
    now = (now or dt.datetime.now(dt.timezone.utc)).astimezone(ET)
    day = now.date() + dt.timedelta(days=1 if now.hour >= 20 else 0)
    return day.isoformat()


def fetch(symbols: Iterable[str], cache_dir: str | Path, start: str, end: str | None = None,
          workers: int = 8) -> dict[str, bool]:
    """Download daily bars for each symbol into the cache. Returns {symbol: success}."""
    import yfinance as yf

    logging.getLogger("yfinance").setLevel(logging.CRITICAL)
    warnings.filterwarnings("ignore", category=FutureWarning)
    Path(cache_dir).mkdir(parents=True, exist_ok=True)
    end = end or (dt.date.today() + dt.timedelta(days=2)).isoformat()

    done = complete_cutoff()

    def one(sym: str) -> bool:
        try:
            df = yf.Ticker(sym).history(start=start, end=end, interval="1d", auto_adjust=False)
            rows = [[idx.strftime("%Y-%m-%d"), float(r.Open), float(r.High), float(r.Low), float(r.Close)]
                    for idx, r in df.iterrows() if r.Close == r.Close]  # drop NaN closes
            rows = [r for r in rows if r[0] < done]
            if rows:
                cache_path(cache_dir, sym).write_text(json.dumps({"complete_before": done, "bars": rows}))
            return bool(rows)
        except Exception:
            return False

    syms = list(symbols)
    with ThreadPoolExecutor(workers) as ex:
        return dict(zip(syms, ex.map(one, syms)))


def _read(f: Path) -> tuple[str | None, list[Bar]]:
    d = json.loads(f.read_text())
    if isinstance(d, list):  # legacy snapshot: trust as complete
        return None, d
    return d.get("complete_before"), d.get("bars") or []


def is_stale(symbol: str, cache_dir: str | Path, cutoff: str) -> bool:
    """True when the cache is missing or was written before bars up to `cutoff` were complete."""
    f = cache_path(cache_dir, symbol)
    if not f.exists():
        return True
    done, _ = _read(f)
    return done is not None and done < min(cutoff, complete_cutoff())


def load(symbol: str, cache_dir: str | Path, cutoff: str) -> list[Bar] | None:
    """Cached bars strictly before `cutoff` (YYYY-MM-DD), sorted and de-duplicated by date."""
    f = cache_path(cache_dir, symbol)
    if not f.exists():
        return None
    d = {r[0]: r for r in _read(f)[1] if r[0] < cutoff}
    return [d[k] for k in sorted(d)] or None
