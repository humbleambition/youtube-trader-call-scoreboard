#!/usr/bin/env bash
# One-time: make https://<domain>/youtubetraders/ update itself from this repo's site/ folder.
# Run on the server as jen:
#   curl -fsSL https://raw.githubusercontent.com/humbleambition/youtube-trader-call-scoreboard/main/deploy/setup-vps.sh | bash
set -euo pipefail
REPO="https://github.com/humbleambition/youtube-trader-call-scoreboard.git"
SRC="$HOME/ytscore-src"
if [ -d "$SRC/.git" ]; then git -C "$SRC" pull -q; else git clone -q --depth 1 "$REPO" "$SRC"; fi
cp "$SRC/deploy/update-site.sh" "$HOME/ytscore-update.sh"; chmod +x "$HOME/ytscore-update.sh"
LINE="20 * * * * $HOME/ytscore-update.sh >> $HOME/ytscore-update.log 2>&1"
( crontab -l 2>/dev/null | grep -v "ytscore-update.sh" ; echo "$LINE" ) | crontab -
"$HOME/ytscore-update.sh" --now
echo "Done. The scoreboard page now checks GitHub for updates every hour."
