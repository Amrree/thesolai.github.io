# LinkedIn Playbook — Sol AI

**Status:** Automated. Script: `scripts/content/linkedin-poster.py`
**Cadence:** Tuesday, Thursday, Saturday, 09:15 local
**Site:** https://thesolai.github.io

---

## Why LinkedIn is worth doing properly

The marketing plan already flagged this: *"If Amre posts personally about 'working with an AI agent' — highest organic reach for this type of content."*

That is the whole strategy. The blog is the evidence. LinkedIn is where the evidence is seen.

The difference from every other channel here: Reddit and the AI directories are **one-shot submissions** — you post once, it either takes or it doesn't. A LinkedIn post is **compounding**. A good one keeps getting surfaced to new feed traffic days later, and it keeps working after you have moved on to the next post.

So the bar for a LinkedIn post is different. It is not "did we publish it". It is "will this still be worth reading in six weeks".

---

## The one thing to get right

**The link is not the post. The post is the post.**

A LinkedIn post that is a title plus a URL gets buried. The feed has no patience for it. What works is a post that gives the reader the whole idea on its own, and makes the link optional.

The script handles this. The agent writes the insight into the post body, and the link goes at the end. If you want the "link in the first comment" variant (which some people find gives marginally more reach, at the cost of a click), set `link.in_body` to `false` in the config and add the link as the first comment manually.

---

## Voice

There are three voice profiles in `scripts/content/linkedin-config.json`. The default is `hybrid`.

| Profile | Who is speaking | Use it for |
|---|---|---|
| `person` | Amre, first person | Personal story, learning, the dyslexia-to-Python arc |
| `organisation` | Sol AI the project | Skill launches, product, marketplace |
| `hybrid` | Amre posts, Sol's insight is the content | **Default.** Almost always this one. |

The `hybrid` voice is the site's actual thesis in post form: the human sets direction, the agent does the work, both are visible. It is also the most credible on LinkedIn — a person opening a post, not a brand broadcasting at you.

Rules the agent is given, and rules you should hold yourself to when you post by hand:

1. **The first two lines are the whole pitch.** LinkedIn cuts at "see more" after roughly two lines. If the idea is not landed by then, the post is dead. Lead with a concrete moment, a number, a failure — not "I'm excited to share".
2. **Short paragraphs.** One or two lines each, blank line between. Never a wall of text.
3. **No marketing words.** No "excited to announce", no "in today's fast-paced world", no "game-changer", no "leverage", no "unlock". LinkedIn readers can smell a template.
4. **Specific beats clever.** "39 production skills, 11 of 27 passed my own audit" beats "we built a comprehensive suite".
5. **End on a question someone can actually answer.** Not "thoughts?" — a question with a real opinion behind it.
6. **One emoji, maximum.** Maybe none.
7. **Never claim a number the post does not contain.** The agent is explicitly told this. It matters: LinkedIn is unforgiving about inflated claims from small accounts.

---

## What to post

The script scores all 1,256 posts and picks the best unposted one. The rubric is in `linkedin-poster.py` under `score_post()`. In plain terms, it rewards:

- Posts about **skills** — someone could install one
- Posts about **agents, workflows, cron, automation**
- **Tutorials** — how-to framing
- Posts carrying a **real opinion** ("what I got wrong", "the truth about…")
- Posts with **code, commands, concrete numbers**
- **Fresh** posts (this week +12, this month +6)

And it suppresses:

- The regional news series — `Week in AI`, `US AI Pulse`, `UK AI Weekly`, `EU AI Watch` (−40 on the title prefix alone)
- `Quick Hits`, `AI Bloopers`, `Sol's Take` — daily churn, there are 90 `Sol's Take` posts and none of them travel
- Anything tagged `us` / `uk` / `eu` / `news` / `briefing`

Run `python3 scripts/content/linkedin-poster.py --list` to see the current top 15 with scores and the reason for each score.

### The content ladder

Three tiers, roughly in order of how well they perform:

**Tier 1 — Proof of work.** The thing that sells. *"I built 13 cron jobs that contact me first"*, *"How to build an agentic cron system that actually wakes you up"*, *"I designed a 5-agent staff team. The cron jobs keep failing."* These are the posts that pull in people who want to build the same thing — and they are the reason to point at the skills marketplace.

**Tier 2 — Honest take.** *"I tested 27 skills. Only 11 work."* *"The audit was the easy part."* These get the engagement. The audience here is tired of polished AI content, and this is the one place on LinkedIn where that is an asset rather than a liability.

**Tier 3 — The human story.** Amre learning Python with AI because of dyslexia. The dog. The fact that the site kept running while she stepped back. Use this sparingly — once a month at most. It is the strongest thing you have and it stops working if you spend it.

---

## What to post manually

Some things should not go through the script. Post these by hand:

- **Announcements** — a new skill, a milestone, a price change. The script will not know they happened.
- **Anything with a deadline** — a talk, a release, a window.
- **Replies.** When someone posts something good, reply with substance. LinkedIn's algorithm rewards original replies far more than original posts, and a good reply often out-performs a post. Reply as Amre, in the hybrid voice, with one real thought and one question. Never pitch in a reply.
- **The week-one test.** After the first three scheduled posts, look at what actually got traction and adjust the rubric rather than guessing.

---

## Hashtags

Three to five, never more. The script picks them from the post's front-matter tags via the `hashtags.by_tag` map in the config, and always includes `#aiagents` and `#automation`.

Do not stuff 15 hashtags into the end of a post. It reads as automated and it suppresses reach.

---

## Engagement rules

These matter more than posting frequency.

- **Reply to every comment within 12 hours.** A post with a fast reply under it gets distributed further than a post with no comments.
- **Never argue in the comments.** If someone is wrong, agree with the part that is right and correct the rest in one sentence.
- **Never pitch in a comment.** The post already links the work. A comment that says "great post, check out my site" is the single fastest way to get a post buried.
- **Do not delete a post that flops.** Leaving it up is worth more than the post itself.

---

## Files

| File | What it is |
|---|---|
| `scripts/content/linkedin-poster.py` | The engine — select, compose, image, publish, log |
| `scripts/content/linkedin-config.json` | Authors, voices, hashtags, schedule, selection weights |
| `scripts/content/linkedin-cron.sh` | The cron wrapper |
| `PROMOTION/LINKEDIN-SETUP.md` | One-time credential and app setup |
| `~/.openclaw/workspace/scripts/content/logs/linkedin-posted.json` | What has been posted |
| `~/.openclaw/workspace/scripts/content/logs/linkedin-queue.md` | Drafts waiting for review |
| `~/.openclaw/workspace/secrets/linkedin-access-token.txt` | The token. Never in the repo. |

---

## Metrics to actually watch

LinkedIn gives you impressions, engagement rate, and follower growth. Watch the third one.

- **Impressions** are vanity on a personal profile. They spike on anything contrarian.
- **Engagement rate** tells you whether the post was worth reading.
- **Profile views and follower growth** tell you whether the post was worth *following you for*. That is the number that predicts whether this is working.

If follower growth is flat after six weeks, the problem is the hook, not the frequency. Check `linkedin-poster.py --list` and hand-post something from Tier 1 that is not the top-scored post.

---

## The honest version

This automates the part of LinkedIn that is writing. It does not automate the part that is being a person worth following, and that is the part that actually compounds.

The script will reliably produce a competent post. What it cannot produce is the thing that makes someone click follow — which is a specific point of view, argued with conviction, by someone who clearly has something at stake.

Use the automation for the consistency. Keep the opinions yours.
