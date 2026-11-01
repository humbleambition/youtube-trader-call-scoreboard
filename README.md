# youtube-call-scoreboard

**How often are YouTube market channels right about the next session?**

This repo extracts the short-term calls (bullish / bearish / neutral) that trading and market-analysis channels make
in their videos, scores each one against what the market actually did, and publishes every call, quote, timestamp
and score so creators and viewers can audit the result.

> **Not financial advice.** Scores reflect only each channel's *stated short-term bias* over a short pilot window.
> They say nothing about a channel's long-term views, education value, or trading performance.

## Pipeline

```
 channels.yaml
      │  ytscore ingest      YouTube captions (youtube-transcript-api) → rolling-caption dedupe
      ▼                       → transcripts/<id>.txt   (local only, git-ignored, never published)
 transcripts/
      │  ytscore extract     LLM (any OpenAI-compatible endpoint, e.g. OpenRouter) + prompts/extract.md
      ▼                       → validated JSON (pydantic), quotes ≤ 25 words
 data/calls/<id>.json
      │  ytscore score       Yahoo daily bars (yfinance) → reference close → next session / 1 week
      ▼                       → hit / miss with volatility thresholds, exclusions.yaml applied
 data/scored_calls.json
      │  ytscore leaderboard hit rate vs coin flip (binomial p) and vs an always-long baseline
      │  ytscore chart       out/session_heatmap.png, out/leaderboard.png
      ▼
 leaderboard
```

## Quickstart

```bash
git clone https://github.com/humbleambition/youtube-trader-call-scoreboard
cd youtube-call-scoreboard
pip install -e ".[dev]"

# re-score the published calls exactly as in the snapshot below
ytscore score --asof 2026-10-31
ytscore leaderboard
ytscore chart
pytest

# process new videos
ytscore ingest --channels channels.yaml --days 2          # captions → transcripts/ (git-ignored)
cp .env.example .env                                      # add YTSCORE_LLM_API_KEY and YTSCORE_LLM_MODEL
ytscore extract transcripts/<id>.txt --channel "HJTrades" --date 2026-10-20
ytscore score && ytscore leaderboard && ytscore chart
```

Prices are cached in `.cache/prices/`. `--asof YYYY-MM-DD` uses only bars before that date, so a snapshot can be
re-created later (Yahoo occasionally revises past bars, so tiny differences are possible).

## Leaderboard: one fixed month (calls made 24 Sep – 23 Oct 2026)

Every video from every tracked channel in that window: 3,844 calls from 615 videos across 30 channels. Channels with at
least 15 scored next-session calls are ranked. "Always-long" is the share of the same calls where the market simply
rose; "edge" is hit rate minus that baseline. With 22 channels compared, p-values above ~0.0023 are not
distinguishable from luck — none clear that bar.

| # | Channel | Next-session hit rate | Scored calls | Always-long baseline | Edge vs long | p (vs coin flip) | 1-week hit rate (n) |
|---|---|---|---|---|---|---|---|
| 1 | Ricky Gutierrez | 64% | 64 | 33% | +31 pts | 0.016 | 43% (92) |
| 2 | BitcoinHyper | 61% | 46 | 46% | +15 pts | 0.092 | 47% (49) |
| 3 | TheTechnicalTraders | 60% | 94 | 41% | +18 pts | 0.040 | 54% (118) |
| 4 | Money Making Market | 55% | 31 | 61% | -6 pts | 0.360 | 53% (45) |
| 5 | Trade Brigade | 54% | 139 | 47% | +7 pts | 0.198 | 44% (151) |
| 6 | tastylive | 54% | 356 | 42% | +12 pts | 0.092 | 55% (454) |
| 7 | Ross Givens | 53% | 30 | 37% | +17 pts | 0.428 | 47% (83) |
| 8 | Meet Kevin | 51% | 101 | 46% | +6 pts | 0.421 | 54% (213) |
| 9 | Crypto World | 48% | 106 | 44% | +4 pts | 0.686 | 56% (118) |
| 10 | Verified Investing | 46% | 489 | 43% | +2 pts | 0.977 | 49% (577) |
| 11 | HJTrades | 43% | 127 | 43% | +1 pts | 0.945 | 42% (165) |
| 12 | David Lin | 43% | 35 | 51% | -9 pts | 0.845 | 49% (133) |
| 13 | Slope of Hope | 42% | 130 | 55% | -12 pts | 0.968 | 33% (207) |
| 14 | Gareth Soloway | 41% | 49 | 43% | -2 pts | 0.924 | 59% (56) |
| 15 | Joseph James Trading With JJ | 39% | 18 | 56% | -17 pts | 0.881 | 44% (18) |
| 16 | Geeks of Finance | 39% | 67 | 45% | -6 pts | 0.975 | 37% (83) |
| 17 | StockedUp | 38% | 110 | 42% | -4 pts | 0.995 | 53% (135) |
| 18 | Arete Trading | 38% | 184 | 39% | -1 pts | 1.000 | 49% (265) |
| 19 | The Traveling Trader | 38% | 16 | 38% | +0 pts | 0.895 | 36% (45) |
| 20 | ShadowTrader | 35% | 34 | 47% | -12 pts | 0.971 | 54% (37) |
| 21 | A1 Trading | 30% | 20 | 50% | -20 pts | 0.979 | 46% (28) |
| 22 | Figuring Out Money | 23% | 26 | 38% | -15 pts | 0.999 | 39% (33) |


![Leaderboard](out/leaderboard.png)

![Hit rate by session](out/session_heatmap.png)

How each call is scored — reference close, windows, thresholds, baselines, limitations, and how to dispute a call —
is explained in **[docs/METHODOLOGY.md](docs/METHODOLOGY.md)**.

## What each channel called

Per-call heatmaps put every channel's call on each market side by side, scored over one shared window, with the actual move printed once per column.

![Short-term calls, Oct 8 2026 session](out/calls_short_2026-10-08.png)
![Short-term calls, Oct 13 2026 session](out/calls_short_2026-10-13.png)
![Short-term calls, Oct 22 2026 session](out/calls_short_2026-10-22.png)
![Medium-term calls, one week from the Oct 7 close](out/calls_week_2026-10-07.png)
![Medium-term calls, one week from the Oct 15 close](out/calls_week_2026-10-15.png)

Make your own: `ytscore chart --session 2026-10-08 --week 2026-10-07`

## Data

- `data/calls/` — one JSON file per video: channel, date, each call's biases, levels, a ≤ 25-word quote and its
  timestamp. No transcripts or captions are stored in this repo.
- `data/scored_calls.json` — every call with its reference close, next-session and one-week moves, and hit/miss.
- `data/leaderboard.json` — the table above as JSON.
- `channels.yaml`, `exclusions.yaml` — what is tracked, and what was excluded and why.

## Disputes

Think a call was misread? [Open an issue](https://github.com/humbleambition/youtube-trader-call-scoreboard/issues/new)
with the video link and timestamp. See [Disputing a call](docs/METHODOLOGY.md#7-disputing-a-call).

## Suggest a channel

Want a channel scored? [Open a channel request](https://github.com/humbleambition/youtube-trader-call-scoreboard/issues/new?template=suggest_channel.md)
or email **jen@striatumos.consulting** with the channel name and link. Channels are added when they post
explicit, time-bound calls (a direction on a named market) at least a few times a week.

## License

MIT © 2026 Jennifer Hsieh. Video content belongs to its creators; this repo stores only short quotes for
commentary and verification.
