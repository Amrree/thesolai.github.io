#!/bin/bash
# LinkedIn Cron — turn the best unread blog post into a LinkedIn post
#
# Same shape as scripts/content/blog-cron.sh: a thin wrapper that finds the
# work, calls the tool that does the work, and writes a log line so the
# health check (scripts/cron-health-check.py) can see whether it ran.
#
# Install in crontab:
#   15 9 * * 2,4,6  ~/Projects/thesolai.github.io/scripts/content/linkedin-cron.sh
#
# That is Tuesday, Thursday and Saturday at 09:15 local time. Change the
# schedule in linkedin-config.json too if you move it.

export PATH="/opt/homebrew/bin:$HOME/.openclaw/tools/node-v24.15.0/bin:$PATH"

REPO="${SOL_REPO:-$HOME/Projects/thesolai.github.io}"
LOG="$HOME/.openclaw/workspace/scripts/content/logs/linkedin-cron.log"
POSTER="$REPO/scripts/content/linkedin-poster.py"

mkdir -p "$(dirname "$LOG")"

log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1" >> "$LOG"
}

log "=== LINKEDIN CRON START ==="

if [ ! -f "$POSTER" ]; then
    log "poster not found at $POSTER - skipping"
    echo "LinkedIn cron: poster not found at $POSTER"
    exit 1
fi

cd "$REPO" || { log "repo not found at $REPO - skipping"; exit 1; }

# Refuse to run twice in the same hour. The blog cron publishes several
# posts in a morning window, and if the LinkedIn cron lands in the same
# window a second post can go out before the first has settled.
HOUR_MARK="--- hour $(date '+%Y-%m-%d %H') ---"
# The mark starts with dashes, so grep needs -- or it parses the pattern as
# an end-of-options flag and matches nothing.
if grep -qF -- "$HOUR_MARK" "$LOG" 2>/dev/null; then
    log "already ran this hour - skipping"
    echo "LinkedIn cron: already ran this hour."
    exit 0
fi
echo "$HOUR_MARK" >> "$LOG"

# --post publishes when a token is present and queues the draft when there
# is not, so a missing credential never loses a post.
OUTPUT=$(python3 "$POSTER" --post 2>&1)
STATUS=$?

echo "$OUTPUT" >> "$LOG"

if [ $STATUS -eq 0 ]; then
    log "published"
    echo "LinkedIn cron: published."
else
    log "not published (status $STATUS) - a draft is in linkedin-queue.md"
    echo "LinkedIn cron: not published. Check linkedin-queue.md."
fi

log "=== LINKEDIN CRON END ==="
