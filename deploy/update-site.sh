#!/usr/bin/env bash
# Hourly from cron: pull the repo and, if site/ changed, copy it to the live scoreboard folder.
set -euo pipefail
SRC="$HOME/ytscore-src"; DEST="$HOME/striatum/site/youtubetraders"
old=$(git -C "$SRC" rev-parse HEAD:site 2>/dev/null || echo none)
git -C "$SRC" pull -q
new=$(git -C "$SRC" rev-parse HEAD:site)
if [ "$old" != "$new" ] || [ "${1:-}" = "--now" ]; then
  mkdir -p "$DEST"
  cp -r "$SRC/site/." "$DEST/"
  echo "$(date -Is) scoreboard page updated ($new)"
fi
