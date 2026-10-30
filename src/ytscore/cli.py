"""Command line: ytscore ingest | extract | score | leaderboard | chart"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from . import __version__


def _load_env(path: str = ".env"):
    import os
    p = Path(path)
    if p.exists():
        for line in p.read_text().splitlines():
            if "=" in line and not line.lstrip().startswith("#"):
                k, v = line.split("=", 1)
                os.environ.setdefault(k.strip(), v.strip())


def cmd_ingest(a):
    from .config import load_channels
    from .ingest import ingest, list_channel_videos
    ids = list(a.video_ids)
    if a.channels:
        for ch in load_channels(a.channels):
            if a.only and ch["name"] not in a.only:
                continue
            vids = list_channel_videos(ch, max_days=a.days)
            ids += [v["id"] for v in vids if v["id"]]
            if a.list_out:
                Path(a.list_out).parent.mkdir(parents=True, exist_ok=True)
                with open(a.list_out, "a") as f:
                    for v in vids:
                        f.write(json.dumps(v, ensure_ascii=False) + "\n")
    st = ingest(dict.fromkeys(ids), a.out, force=a.force)
    for k, v in st.items():
        print(k, v)


def cmd_extract(a):
    from .extract import extract_file
    _load_env()
    meta = dict(video_id=a.video_id or Path(a.transcript).stem, channel=a.channel, title=a.title or "",
                approx_date=a.date)
    print(extract_file(a.transcript, meta, a.out))


def cmd_score(a):
    from .config import load_exclusions
    from .score import run
    out, dropped = run(a.calls, load_exclusions(a.exclusions), a.prices, a.out, asof=a.asof, refresh=a.refresh)
    n1 = sum(x.get("next_day_ok") is not None for x in out)
    nw = sum(x.get("week_ok") is not None for x in out)
    print(f"{len(out)} calls scored -> {a.out}  (next-session scored: {n1}, 1-week scored: {nw})")
    if dropped:
        print("dropped for price mismatch (channel, ticker, quoted, ref close):")
        for d in dropped:
            print("  ", d)


def cmd_leaderboard(a):
    from .leaderboard import build, to_markdown
    rows = build(json.loads(Path(a.scored).read_text()), a.since, a.until, a.min_n)
    if a.json:
        Path(a.json).write_text(json.dumps(rows, indent=1))
    print(to_markdown(rows))


def cmd_chart(a):
    from .leaderboard import build
    from .viz import leaderboard_chart, session_heatmap
    scored = json.loads(Path(a.scored).read_text())
    Path(a.out).mkdir(parents=True, exist_ok=True)
    sess, _ = session_heatmap(scored, Path(a.out) / "session_heatmap.png", min_channel_calls=a.min_n)
    rows = build(scored, min_n=a.min_n)
    dates = sorted(x["date"] for x in scored)
    leaderboard_chart(rows, Path(a.out) / "leaderboard.png", window=f"calls made {dates[0]} to {dates[-1]}")
    print("wrote", Path(a.out) / "session_heatmap.png", Path(a.out) / "leaderboard.png")


def main(argv=None):
    p = argparse.ArgumentParser(prog="ytscore", description=__doc__)
    p.add_argument("--version", action="version", version=__version__)
    sub = p.add_subparsers(dest="cmd", required=True)

    s = sub.add_parser("ingest", help="fetch captions into a local, git-ignored transcripts/ folder")
    s.add_argument("video_ids", nargs="*")
    s.add_argument("--channels", help="channels.yaml: list each channel's recent videos and ingest them")
    s.add_argument("--only", nargs="*", help="limit --channels to these channel names")
    s.add_argument("--days", type=int, default=2, help="with --channels: videos from the last N days")
    s.add_argument("--list-out", help="append the video listing (JSON lines) here")
    s.add_argument("--out", default="transcripts")
    s.add_argument("--force", action="store_true")
    s.set_defaults(func=cmd_ingest)

    s = sub.add_parser("extract", help="extract calls from one transcript with an LLM")
    s.add_argument("transcript")
    s.add_argument("--channel", required=True)
    s.add_argument("--date", required=True, help="listing date YYYY-MM-DD (the host's stated date wins)")
    s.add_argument("--title")
    s.add_argument("--video-id")
    s.add_argument("--out", default="data/calls")
    s.set_defaults(func=cmd_extract)

    s = sub.add_parser("score", help="score calls against Yahoo daily closes")
    s.add_argument("--calls", default="data/calls")
    s.add_argument("--exclusions", default="exclusions.yaml")
    s.add_argument("--prices", default=".cache/prices", help="price cache directory")
    s.add_argument("--asof", help="use only bars before this date (YYYY-MM-DD) for a reproducible snapshot")
    s.add_argument("--refresh", action="store_true", help="re-download prices even if cached")
    s.add_argument("--out", default="data/scored_calls.json")
    s.set_defaults(func=cmd_score)

    s = sub.add_parser("leaderboard", help="print the per-channel leaderboard (markdown)")
    s.add_argument("--scored", default="data/scored_calls.json")
    s.add_argument("--since", default="0000")
    s.add_argument("--until", default="9999")
    s.add_argument("--min-n", type=int, default=15)
    s.add_argument("--json", help="also write rows as JSON here")
    s.set_defaults(func=cmd_leaderboard)

    s = sub.add_parser("chart", help="session heatmap + leaderboard chart (PNG)")
    s.add_argument("--scored", default="data/scored_calls.json")
    s.add_argument("--min-n", type=int, default=15)
    s.add_argument("--out", default="out")
    s.set_defaults(func=cmd_chart)

    a = p.parse_args(argv)
    a.func(a)


if __name__ == "__main__":
    sys.exit(main())
