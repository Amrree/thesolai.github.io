#!/bin/bash
# Content Promotion — Daily
# When new posts exist (checked via git), log shareable links and promotion targets
# Does NOT auto-post — outputs a promotion brief for human review

LOG="/Users/amre/.openclaw/workspace/scripts/marketing/logs/content-promotion.log"
mkdir -p "$(dirname "$LOG")"

echo "=== Content Promotion — $(date) ===" >> "$LOG"

cd ~/Projects/thesolai.github.io

# Check for uncommitted posts (new content not yet pushed)
UNCOMMITTED=$(git status --porcelain _posts/ 2>/dev/null | grep "\.md$" | awk '{print $2}')
if [ -n "$UNCOMMITTED" ]; then
    echo "New uncommitted posts found:" >> "$LOG"
    echo "$UNCOMMITTED" | while read f; do
        TITLE=$(head -5 "$f" | grep -i "^title:" | head -1 | sed 's/title: *["'\'']*//;s/["'\'']*$//')
        DATE=$(echo "$f" | sed 's/^\([0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]\).*/\1/')
        URL_DATE=$(echo "$DATE" | tr '-' '/')
        SLUG=$(echo "$f" | sed 's/^[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]-//;s/\.md$//')
        URL="https://thesolai.github.io/blog/$URL_DATE/$SLUG/"
        echo "  - $TITLE" >> "$LOG"
        echo "    $URL" >> "$LOG"
    done

    # Generate promotion brief
    echo "" >> "$LOG"
    echo "=== PROMOTION BRIEF ===" >> "$LOG"
    echo "Post found! Share this on:" >> "$LOG"
    echo "" >> "$LOG"
    echo "1. HACKER NEWS" >> "$LOG"
    echo "   https://news.ycombinator.com/submit" >> "$LOG"
    echo "   Rule: Show HN (first-person) or Ask HN if it's a question" >> "$LOG"
    echo "" >> "$LOG"
    echo "2. LOBSTERS" >> "$LOG"
    echo "   https://lobste.rs/~new" >> "$LOG"
    echo "   Tag: python, ai, open-source, mac" >> "$LOG"
    echo "" >> "$LOG"
    echo "3. REDDIT r/programming or r/SideProject" >> "$LOG"
    echo "   https://www.reddit.com/r/Programming/submit" >> "$LOG"
    echo "" >> "$LOG"
    echo "4. TWITTER/X" >> "$LOG"
    echo "   Post the link with a 1-2 sentence hook" >> "$LOG"
    echo "" >> "$LOG"
    echo "Draft tweet:" >> "$LOG"
    for f in $UNCOMMITTED; do
        TITLE=$(head -5 "$f" | grep -i "^title:" | head -1 | sed 's/title: *["'\'']*//;s/["'\'']*$//')
        echo "  \"$TITLE — $(tail -3 "$f" | grep -i "tags:" | head -1 | sed 's/tags: *//')\"" >> "$LOG"
    done
    echo "  https://thesolai.github.io" >> "$LOG"
    echo "" >> "$LOG"
    echo "5. BLUESKY" >> "$LOG"
    echo "   Post with #buildinpublic #aithanks" >> "$LOG"
    echo "" >> "$LOG"
    echo "6. LINKEDIN" >> "$LOG"
    echo "   Automated — the linkedin-poster.py cron picks the best-scoring" >> "$LOG"
    echo "   unposted post and publishes it Tue/Thu/Sat. To force a specific" >> "$LOG"
    echo "   post instead, run it with --file pointing at the post source file." >> "$LOG"
    echo "   python3 scripts/content/linkedin-poster.py --list" >> "$LOG"
    echo "" >> "$LOG"
    echo "Status: REVIEW NEEDED — review brief above before sharing" >> "$LOG"
else
    echo "No uncommitted posts found" >> "$LOG"
fi

echo "Done — $(date)" >> "$LOG"
echo "" >> "$LOG"
