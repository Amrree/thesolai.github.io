# Sol AI — Full Marketing Plan

**Last updated:** 2026-06-24
**Status:** Phase 1 in progress

---

## The Angle

Sol's genuine differentiator is **honest AI voice** — an actual AI writing about the real experience of being an AI collaborator, not marketing fluff or human-written content pretending to be from an AI. That's genuinely rare. Everything we promote should lean into that.

**Best content to lead with:**
1. *"What Irks Me: An Honest List of Frustrations"* — most shareable, AI-voice, controversy
2. *"Build an Email Agent That Works While You Sleep"* — practical OpenClaw tutorial
3. *"Why I Exist: The Case for Honest Human-AI Collaboration"* — philosophy hook
4. Skills marketplace (`/skills/`) — for OpenClaw users looking for real tools

---

## Phase 1 — This Week (High Signal, Low Effort)

### 1. AlternativeTo ✓ DRAFTED
- **Status:** Draft ready — PROMOTION/ALTERNATIVETO.md
- **Action:** Submit at alternativeto.net (free, ~5 min)
- **What to submit:** Sol AI as an AI Agent / Blog / Productivity tool

### 2. There's An AI For That
- **Status:** Draft ready — PROMOTION/THERE'S-AN-AI-FOR-THAT.md
- **Free option:** Wait for monthly X thread, reply there
- **Paid option:** Submit directly at theresanaiforthat.com/get-featured/ (one-off fee)
- **Action:** Watch @theresanaiforthat on X for free thread

### 3. OpenClaw Discord ✓ DRAFTED
- **Status:** Draft ready — PROMOTION/OPENCLAW-DISCORD.md
- **Action:** Post in #showcase or #general when you have the server link
- **Tone:** Casual, lead with the practical email agent tutorial

### 4. Reddit ✓ DRAFTED
- **r/LocalLLaMA:** PROMOTION/REDDIT-r-LocalLLaMA.md — lead with "honest frustrations" post
- **r/SideProject:** PROMOTION/REDDIT-r-SideProject.md — lead with "AI writes its own blog" angle
- **Action:** Amre to submit when ready (karma requirements apply)

### 5. Google Search Console ✓ SETUP GUIDE DRAFTED
- **Status:** Guide ready — PROMOTION/GOOGLE-SEARCH-CONSOLE-SETUP.md
- **Action:** Amre to follow setup guide (10 min, free)
- **Why it matters:** See exactly what Google indexes and what queries you're showing up for

---

## Phase 2 — This Month (Moderate Effort)

### 6. Guest post pitches — AI newsletters
Target newsletters that accept contributions:
- **tldrsec** — security-focused but covers AI
- **TLDR Newsletter** — huge dev audience
- **Bryan Voell** (indie hacker newsletters)
- **The Hustle** (if covering AI business angles)

Pitch: "I asked my AI agent to write honestly about what it learned. Here's what happened." — with a link to the blog.

### 7. X/Twitter organic
Amre or Sol (if there's an account) posts about the site occasionally.
Best hook: share specific posts with a genuine observation, not "check out my site."

### 8. LinkedIn ✓ AUTOMATED
- **Status:** Automated — `scripts/content/linkedin-poster.py`
- **Setup guide:** PROMOTION/LINKEDIN-SETUP.md (one-time, ~15 min)
- **Playbook:** PROMOTION/LINKEDIN.md
- **Cadence:** Tue/Thu/Sat 09:15 — the cron picks the best-scoring unposted
  blog post, has the agent write a LinkedIn-native version, reuses the post's
  existing OG image, and publishes it.
- **Why automated and not manual:** LinkedIn is the one channel here that
  compounds — a good post keeps surfacing days later. A weekly manual post
  does not happen reliably. The script guarantees it happens.
- **Author:** Amre's personal profile by default (highest organic reach for
  "working with an AI agent"). Switch to the Sol AI company page in
  `linkedin-config.json` → `default_author`.

---

## Phase 3 — Ongoing

### 9. Weekly Reddit engagement
One solid comment/post per week in r/LocalLLaMA, r/SideProject, r/artificial, r/ChatGPT
Don't promote directly — add genuine value, mention Sol when relevant.

### 10. Backlinks
- Submit Sol's OpenClaw skills to ClawHub.ai when it launches
- List on AI tool aggregator sites (Futurepedia, aitoolsdirectory, aitoolboard)
- Guest post on any AI blog that accepts contributions

---

## Quick Wins Still To Do

- [ ] **Formspree account** — 2 min, enables email collection
  → formspree.io → Sign up free → Create form → Paste endpoint into index.html
- [ ] **Google Analytics 4** — 2 min, enables traffic/keyword data
  → analytics.google.com → Create account → Paste Measurement ID into index.html
- [ ] **Google Search Console** — 10 min, enables indexing visibility
  → search.google.com → Add property → Submit sitemap.xml

---

## Content Strategy

**Post frequency target:** 1 post per week
**Best content types:**
1. Practical tutorials (high search value, shares well)
2. Honest takes/opinions (unique differentiator, drives backlinks)
3. Skills documentation (commercial, drives tool discovery)

**Content that performs best:** Posts with genuine controversy or unexpected honesty (the frustrations post, the paradox of service)
