"""Score every extracted call against daily closes.

Rules (identical to the pilot tracker so results reproduce; plain English in docs/METHODOLOGY.md):
- Reference close: the last session strictly before the video date, or the video date itself when the
  video was recorded intraday or after the close.
- Next session: reference close -> next close. Short-term bias is a hit if bullish and move > +0.2*thr,
  bearish and move < -0.2*thr, neutral and |move| < thr. thr = 1.2% for crypto, stocks, SI, HG, GDX, GDXJ;
  0.6% otherwise. mixed / none are not scored.
- One week: reference close -> first close on or after ref date + 7 calendar days, threshold 2.2*thr.
- A call is dropped when its quoted price is more than 30% away from the reference close for a stock
  (or an instrument quoted under its own ticker): that usually means the ticker was misheard.
"""
from __future__ import annotations

import datetime as dt
import json
from pathlib import Path
from typing import Callable, Optional

from . import prices
from .config import Exclusions
from .schema import VideoCalls

CANON = {'ES': 'ES=F', 'NQ': 'NQ=F', 'YM': 'YM=F', 'RTY': 'RTY=F', 'GC': 'GC=F', 'SI': 'SI=F', 'HG': 'HG=F',
         'CL': 'CL=F', 'BTC': 'BTC-USD', 'ETH': 'ETH-USD', 'XRP': 'XRP-USD', 'SOL': 'SOL-USD', 'TNX': '^TNX',
         'TYX': '^TYX', 'DXY': 'DX-Y.NYB', 'VIX': '^VIX', 'GDX': 'GDX', 'GDXJ': 'GDXJ'}
# Instruments people quote instead of the canonical one (for reference; prices are scaled via price_at_call).
QUOTED = {'SPY': 'SPY', 'QQQ': 'QQQ', 'IWM': 'IWM', 'DIA': 'DIA', 'SPX': '^GSPC', 'S&P 500': '^GSPC',
          'NDX': '^NDX', 'DOW': '^DJI', 'GLD': 'GLD', 'SLV': 'SLV', 'TLT': 'TLT'}
MAJOR_CRYPTO = ('BTC', 'ETH', 'XRP', 'SOL')
HIGH_VOL_NONSTOCK = ('SI', 'HG', 'GDX', 'GDXJ')
BASE_VOL, HIGH_VOL = 0.006, 0.012
HIT_FRACTION = 0.2          # directional calls must beat 0.2 x threshold
WEEK_MULT = 2.2             # one-week threshold = 2.2 x next-session threshold
MISMATCH = 0.30             # quoted price vs reference close
TARGET_SANITY = 0.25        # unscaled targets further than this from ref are ignored


def yahoo_symbol(ticker: str, group: str | None) -> str:
    t = ticker.upper().strip()
    if group == 'crypto' and t not in CANON:
        return t + '-USD'
    return CANON.get(t, t)


def vol_threshold(ticker: str, group: str | None) -> float:
    if ticker in MAJOR_CRYPTO or group == 'stocks' or ticker in HIGH_VOL_NONSTOCK:
        return HIGH_VOL
    return BASE_VOL


def ref_index(rows: list, date: str, when: str | None) -> Optional[int]:
    """Index of the reference bar: last session strictly before `date`, or `date` itself when the video
    was recorded intraday / after the close (premarket, weekend and unknown use the prior session)."""
    idx = None
    for i, r in enumerate(rows):
        if r[0] < date or (r[0] == date and when in ('intraday', 'after_close')):
            idx = i
    return idx


def bias_ok(bias: str | None, move: float, thr: float) -> Optional[bool]:
    if bias == 'bullish':
        return move > thr * HIT_FRACTION
    if bias == 'bearish':
        return move < -thr * HIT_FRACTION
    if bias == 'neutral':
        return abs(move) < thr
    return None  # mixed / none / missing: not scored


def score_call(v: VideoCalls, c, rows: list | None) -> tuple[dict, Optional[tuple]]:
    """Return (record, dropped) for one call. `dropped` is set when the call fails the price check."""
    t = c.ticker
    rec = dict(channel=v.channel, video_id=v.video_id, date=v.video_date, when=v.recorded_when, vtype=v.video_type,
               group=c.group, ticker=t, quoted=c.instrument_quoted,
               st=c.short_term.bias, st_t=c.short_term.target, mt=c.medium_term.bias, mt_t=c.medium_term.target,
               lt=c.long_term.bias, lt_t=c.long_term.target, action=c.action, method=c.method, reason=c.reason,
               conviction=c.conviction, ts=c.timestamp, quote=c.quote, cond=c.condition,
               price_at_call=c.price_at_call, support=c.key_levels.support, resistance=c.key_levels.resistance)
    if not rows:
        return rec, None
    i = ref_index(rows, v.video_date, v.recorded_when)
    if i is None:
        return rec, None
    ref = rows[i][4]
    pac = c.price_at_call
    if pac and (c.group == 'stocks' or (c.instrument_quoted or '').upper() == t) and abs(pac / ref - 1) > MISMATCH:
        return rec, (v.channel, t, pac, ref)
    rec['ref_date'] = rows[i][0]
    rec['ref_close'] = round(ref, 4)
    vol = vol_threshold(t, c.group)
    if i + 1 < len(rows):
        m1 = rows[i + 1][4] / ref - 1
        rec['next_date'] = rows[i + 1][0]
        rec['next_day_pct'] = round(m1 * 100, 2)
        rec['next_day_ok'] = bias_ok(rec['st'], m1, vol)
    wend = (dt.date.fromisoformat(rows[i][0]) + dt.timedelta(days=7)).isoformat()
    k = next((n for n in range(i + 1, len(rows)) if rows[n][0] >= wend), None)
    if k is not None and k > i + 1:
        m5 = rows[k][4] / ref - 1
        rec['week_pct'] = round(m5 * 100, 2)
        rec['week_to'] = rows[k][0]
        sb = rec['st'] if rec['st'] not in ('none', 'mixed') else rec['mt']
        rec['week_ok'] = bias_ok(sb, m5, vol * WEEK_MULT)
        rec['mt_early_ok'] = bias_ok(rec['mt'], m5, vol * WEEK_MULT)
        hi = max(r[2] for r in rows[i + 1:k + 1])
        lo = min(r[3] for r in rows[i + 1:k + 1])
        for key in ('st_t', 'mt_t'):  # target hit within the week, scaled from quoted units
            tg = rec[key]
            if tg and pac:
                tgt = ref * (tg / pac)
            elif tg and abs(tg / ref - 1) < TARGET_SANITY:
                tgt = tg
            else:
                continue
            rec[key + '_hit_wk'] = (hi >= tgt) if tgt > ref else (lo <= tgt)
            rec[key + '_dist_pct'] = round((tgt / ref - 1) * 100, 2)
    return rec, None


def load_videos(calls_dir: str | Path) -> list[VideoCalls]:
    return [VideoCalls.model_validate_json(f.read_text()) for f in sorted(Path(calls_dir).glob('*.json'))]


def score_all(videos: list[VideoCalls], ex: Exclusions, price_loader: Callable[[str], list | None]):
    out, dropped = [], []
    for v in videos:
        if v.channel in ex.channels or v.video_id in ex.videos:
            continue
        for c in v.calls:
            if (v.video_id, c.ticker) in ex.calls:
                continue
            rec, drop = score_call(v, c, price_loader(yahoo_symbol(c.ticker, c.group)))
            if drop:
                dropped.append(drop)
            else:
                out.append(rec)
    return out, dropped


def needed_symbols(videos: list[VideoCalls], ex: Exclusions) -> set[str]:
    return {yahoo_symbol(c.ticker, c.group) for v in videos
            if v.channel not in ex.channels and v.video_id not in ex.videos for c in v.calls}


def run(calls_dir, exclusions: Exclusions, cache_dir, out_path, asof: str | None = None, refresh: bool = False):
    videos = load_videos(calls_dir)
    cutoff = asof or prices.complete_cutoff()
    syms = needed_symbols(videos, exclusions)
    missing = sorted(s for s in syms if refresh or prices.is_stale(s, cache_dir, cutoff))
    if missing:
        first = min(v.video_date for v in videos)
        start = (dt.date.fromisoformat(first) - dt.timedelta(days=21)).isoformat()
        end = (dt.date.fromisoformat(cutoff) + dt.timedelta(days=1)).isoformat()
        prices.fetch(missing, cache_dir, start, end)
    out, dropped = score_all(videos, exclusions, lambda s: prices.load(s, cache_dir, cutoff))
    Path(out_path).parent.mkdir(parents=True, exist_ok=True)
    Path(out_path).write_text(json.dumps(out, indent=1, ensure_ascii=False))
    return out, dropped
