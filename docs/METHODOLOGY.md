# Scoring methodology

This page explains, in plain English, how every call on the leaderboard was found and scored. The code that
does it is in [`src/ytscore/score.py`](../src/ytscore/score.py) and [`src/ytscore/stats.py`](../src/ytscore/stats.py);
every scored call, with its quote and timestamp, is in [`data/scored_calls.json`](../data/scored_calls.json).

## 1. What counts as a call

Each video's captions are read by a language model with the prompt in
[`src/ytscore/prompts/extract.md`](../src/ytscore/prompts/extract.md). For each instrument the host gives a view on,
it records:

- a **short-term bias** (next session to ~5 days), a medium-term bias (weeks to ~3 months) and a long-term bias,
  each one of `bullish`, `bearish`, `neutral`, `mixed` or `none`;
- any target, support/resistance levels, the price the host quoted, and a **verbatim quote (25 words or fewer)
  with a timestamp**, so anyone can check the call in the video.

A bias is recorded only when the host states it or clearly implies it. Tickers mentioned in passing are skipped,
and there is one call per instrument per video. Indices are normalised (S&P 500, SPX, SPY → `ES`; Nasdaq-100,
NDX, QQQ → `NQ`; gold → `GC`; and so on), but quoted prices stay in the units the host used.

The leaderboard scores **only the short-term bias**. Medium- and long-term views are stored but not ranked.

## 2. The reference close

A call is measured from the last daily close the host could have known about:

| When the video was recorded | Reference close |
|---|---|
| Premarket, weekend, or unknown | the last session **before** the video date |
| Intraday or after the close | the close **of** the video date |

The video date is the date the host says on air when they say one; otherwise YouTube's listing date.
"Recorded when" comes from cues in the video ("markets open in an hour", "as we close today").

Prices are Yahoo Finance daily bars (raw closes): futures for indices, metals and oil (`ES=F`, `GC=F`, `CL=F` …),
`BTC-USD` etc. for crypto, the yields index for rates (`^TNX`), and the stock itself for stocks. A bar is only used
once it is complete (after 8 pm US Eastern on that day).

## 3. Windows

- **Next session**: reference close → the next daily close. This is the headline score.
- **One week**: reference close → the first close on or after the reference date + 7 calendar days
  (five sessions for futures and stocks, seven days for crypto). If the short-term bias is `none` or `mixed`,
  the medium-term bias is used for the one-week score.

## 4. What counts as a hit

Each instrument gets a volatility threshold *T*:

- *T* = **1.2%** for stocks, BTC, ETH, XRP, SOL, silver (SI), copper (HG), and gold miners (GDX, GDXJ);
- *T* = **0.6%** for everything else (index futures, gold, oil, yields, the dollar, VIX, other crypto).

For the one-week window the threshold is 2.2 × *T*.

| Bias | Hit when the move over the window is … |
|---|---|
| Bullish | more than +0.2 × *T* (e.g. > +0.12% for ES next session) |
| Bearish | less than −0.2 × *T* |
| Neutral | within ±*T* |
| Mixed / none | not scored |

The small 0.2 × *T* buffer stops a flat, coin-toss session from counting as a directional win.

**Targets** are checked separately: a target counts as hit if the daily high (for an upside target) or low
(for a downside target) reaches it within the one-week window. A target quoted in another instrument's units
(e.g. SPY dollars for an ES call) is scaled by the quoted price.

**Dropped calls.** When a stock call's quoted price is more than 30% away from the reference close, the ticker was
almost certainly misheard, so the call is dropped rather than scored. Exclusions made by hand (garbled tickers,
duplicate uploads, non-primary channels) are listed with reasons in [`exclusions.yaml`](../exclusions.yaml).

## 5. Leaderboard rules and baselines

- A channel needs **at least 15 scored next-session calls** to appear on the public leaderboard.
- **Hit rate** = hits / scored next-session calls.
- **Coin-flip p-value**: the chance a fair coin would get at least that many right out of the same number of
  calls (one-sided binomial). With ~20 channels tested at once, a single p around 0.03 is weak evidence;
  treat anything above ~0.0025 (0.05 / 20) as not yet distinguishable from luck.
- **Always-long baseline**: on the same calls, the share where the market simply went up. If a channel's hit rate
  is not above this, a permanently bullish robot would have done as well. "Edge vs long" is the difference.

## 6. Limitations

- **Pilot window.** Calls made **24 Sep – 20 Oct 2026**, scored with bars available up to 20 Oct 2026
  (`ytscore score --asof 2026-10-21`). Four weeks is a short, single market regime; rankings will move.
- **Coverage is uneven.** Some channels post several videos a day, others weekly; a few videos had no usable
  captions or were over two hours and were skipped. Most calls come from 25 Sep – 12 Oct;
  after that the sample is thin (a few videos a day from core channels) and there are none from 14–16 Oct.
- **LLM extraction can misread.** Auto-captions garble tickers and numbers, and a model can over- or under-read
  a host's bias, especially for hedged or conditional statements. Conditional calls ("if 6,700 breaks, then …")
  are scored on their stated bias, not on whether the condition triggered.
- **Timestamps in the pilot data are approximate.** Captions were marked once per minute, and in some pilot files
  the marker was written as hours:minutes, so a timestamp like `0:12` may mean 12 minutes in. New extractions
  use unambiguous `minutes:seconds` markers.
- **Close-to-close only.** An intraday trade that hit its target and reversed by the close is scored on the close.
- **Short-term bias only.** Hosts who mainly give long-term views are judged on the few short-term ones they make.

## 7. Disputing a call

If you are a creator (or a viewer) and think a call was misread or scored wrongly, please
[open a GitHub issue](https://github.com/humbleambition/youtube-trader-call-scoreboard/issues/new) with:

1. the video link,
2. the timestamp of the call,
3. what the call should have been (or why it should not count).

Every call in `data/calls/<video_id>.json` carries the quote and timestamp it was based on, so a dispute can be
checked quickly. Corrections are made in the call file (or in `exclusions.yaml` with a reason), and the
leaderboard is regenerated from scratch, so the fix is visible in the commit history.
