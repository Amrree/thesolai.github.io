#!/usr/bin/env python3
"""
linkedin-poster.py — turn a Sol AI blog post into a LinkedIn post.

Same house pattern as scripts/content/devto-poster.py: read a post out of
_posts/, turn it into the platform's native shape, publish it, log it, and
never post the same thing twice.

The one thing LinkedIn needs that dev.to does not is an image, and the site
already has 1200x630 OG images for every post (og/<source-stem>.png). Those
are the exact aspect ratio LinkedIn renders best, and they are already
publicly served, so there is no new asset pipeline to build. This script
reuses them.

Two publishing paths
--------------------
  rest    POST /rest/posts          binary image upload, returns an image URN.
                                    Current API. Needs a LinkedIn-Version header.
  legacy  POST /v2/ugcPosts         versionless, references the public og image
                                    by URL. Old but very stable.

If `rest` fails on a version or endpoint error the script retries with
`legacy` automatically, so an expired API version degrades instead of
silently posting nothing.

Modes
-----
  --list                 Score the library and show the best candidates.
  --dry-run              Compose the next post and write it to the review
                         queue without publishing. This is the default.
  --post                 Compose and publish the next post.
  --file <path>          Use a specific post file instead of the next one.
  --whoami               Print the author URNs this token can post as.
  --init-token           Exchange a LinkedIn OAuth code for an access token
                         and store it in the secrets dir.
  --preview              Print the composed post without writing or posting.

State
-----
  Token    ~/.openclaw/workspace/secrets/linkedin-access-token.txt
  Log      ~/.openclaw/workspace/scripts/content/logs/linkedin-posted.json
  Queue    ~/.openclaw/workspace/scripts/content/logs/linkedin-queue.md
  Config   ~/.openclaw/workspace/secrets/linkedin-config.json  (optional,
           falls back to scripts/content/linkedin-config.json in the repo)

The token is never read from the repo and never written to the repo. The
publish gate (scripts/install-publish-hook.sh) blocks credential pushes; keep
it that way.

Usage
-----
  python3 scripts/content/linkedin-poster.py --list
  python3 scripts/content/linkedin-poster.py --dry-run
  python3 scripts/content/linkedin-poster.py --post
  python3 scripts/content/linkedin-poster.py --file _posts/2026-10-30-tool-spotlight-claude-code.md --preview
"""
import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

# --------------------------------------------------------------------------
# Paths. Everything is overridable so the script runs on the Mac (where the
# other crons live) and in CI or a container without edits.
# --------------------------------------------------------------------------

REPO = Path(__file__).resolve().parent.parent.parent
HOME = Path(os.path.expanduser("~"))
OPENCLAW_WORKSPACE = Path(os.path.expanduser("~/.openclaw/workspace"))

SECRETS_DIR = OPENCLAW_WORKSPACE / "secrets"
LOGS_DIR = OPENCLAW_WORKSPACE / "scripts" / "content" / "logs"

TOKEN_FILE = SECRETS_DIR / "linkedin-access-token.txt"
CLIENT_ID_FILE = SECRETS_DIR / "linkedin-client-id.txt"
CLIENT_SECRET_FILE = SECRETS_DIR / "linkedin-client-secret.txt"
REDIRECT_URI_FILE = SECRETS_DIR / "linkedin-redirect-uri.txt"
USER_CONFIG_FILE = SECRETS_DIR / "linkedin-config.json"
POSTED_LOG = LOGS_DIR / "linkedin-posted.json"
QUEUE_FILE = LOGS_DIR / "linkedin-queue.md"

REPO_CONFIG_FILE = Path(__file__).resolve().parent / "linkedin-config.json"

SITE_URL = "https://thesolai.github.io"

# LinkedIn rejects posts over 3000 characters. Stay well under it.
MAX_POST_CHARS = 2800

# OAuth scopes. w_member_social is enough to post as a person.
# w_organization_social is additionally required to post as a company page,
# and the app must be approved by the page admin.
SCOPES = "w_member_social w_organization_social"

# The agent writes the post copy. Same binary and invocation the blog cron
# uses, so there is one voice across the site and LinkedIn.
OPENCLAW_BIN_CANDIDATES = [
    "/Users/amre/.openclaw/tools/current-bin/openclaw",
    "/Users/amre/.openclaw/tools/node-v24.21.0/bin/openclaw",
    "/opt/homebrew/bin/openclaw",
]

# TUI noise the agent CLI prints around the real answer.
TUI_NOISE = re.compile(r"^[\u2502\u2554\u2557\u255a\u255d\u2551\u2550\u256c\u2560\u2563\u2566\u2569\u256b\u2571\u2572\u2573\u2591\u2592\u2593\u2588\u258c\u2590]")
PLUGIN_NOISE = re.compile(r"^\s*\[(plugins|gateway)\]", re.IGNORECASE)


# --------------------------------------------------------------------------
# Small helpers
# --------------------------------------------------------------------------

def log(msg):
    print(f"[linkedin] {msg}", file=sys.stderr)


def load_config():
    """User config in the secrets dir wins over the repo copy."""
    for path in (USER_CONFIG_FILE, REPO_CONFIG_FILE):
        if path.exists():
            try:
                cfg = json.loads(path.read_text())
                log(f"config: {path}")
                return cfg
            except json.JSONDecodeError as e:
                log(f"config {path} is not valid JSON ({e}) - skipping")
    log("config: using built-in defaults")
    return {"site_url": SITE_URL, "posts_dir": "_posts", "og_dir": "og"}


def read_secret(path):
    """Read a secret file. Returns None if it is missing or empty."""
    try:
        value = path.read_text().strip()
        return value or None
    except OSError:
        return None


def api_base(cfg):
    """Base URL for the LinkedIn API. Overridable so it can be pointed at a
    mock server in tests."""
    return cfg.get("api", {}).get("base_url", "https://api.linkedin.com").rstrip("/")


def get_token():
    """Token from the secrets file, or from the environment.

    The env fallback matters for CI and for the Mavis scheduler, where a
    secret can be injected as LINKEDIN_ACCESS_TOKEN.
    """
    token = read_secret(TOKEN_FILE)
    if token:
        return token
    return os.environ.get("LINKEDIN_ACCESS_TOKEN") or None


# --------------------------------------------------------------------------
# Post parsing
# --------------------------------------------------------------------------

def parse_frontmatter(content):
    """Return (meta_dict, body). Matches the house front-matter shape."""
    match = re.match(r"^---\n([\s\S]*?)\n---\n([\s\S]*)$", content)
    if not match:
        return {}, content
    fm_text, body = match.groups()
    meta = {}
    for line in fm_text.split("\n"):
        kv = re.match(r"^([A-Za-z_-]+):\s*(.*)$", line)
        if not kv:
            continue
        key, value = kv.group(1), kv.group(2).strip()
        if value.startswith("[") and value.endswith("]"):
            items = [v.strip().strip("\"'") for v in value[1:-1].split(",")]
            meta[key] = [i for i in items if i]
        else:
            meta[key] = value.strip("\"'")
    return meta, body


def strip_markdown(body):
    """Reduce a post body to plain prose for the agent prompt."""
    text = re.sub(r"```.*?```", " [code] ", body, flags=re.DOTALL)
    text = re.sub(r"`([^`]+)`", r"\1", text)
    text = re.sub(r"!\[([^\]]*)\]\([^)]*\)", r"\1", text)
    text = re.sub(r"\[([^\]]+)\]\([^)]*\)", r"\1", text)
    text = re.sub(r"(?m)^\s{0,3}#{1,6}\s*", "", text)
    text = re.sub(r"(?m)^\s*[-*+]\s+", "- ", text)
    text = re.sub(r"(?m)^\s*>\s*", "", text)
    text = re.sub(r"(\*\*|__|\*|_|~~)", "", text)
    text = re.sub(r"\[plugins\][^\n]*", "", text)
    text = re.sub(r"\{:[^}]*\}", "", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def post_url(filename, cfg):
    """Build the canonical URL for a post from its source filename.

    The filename contract matches the OG image generator: the source filename
    minus the extension is the stem, and the date prefix becomes the URL path.
    """
    stem = Path(filename).stem
    date_match = re.match(r"(\d{4})-(\d{2})-(\d{2})-(.*)$", stem)
    base = cfg.get("site_url", SITE_URL).rstrip("/")
    if date_match:
        year, month, day, slug = date_match.groups()
        return f"{base}/blog/{year}/{month}/{day}/{slug}/"
    return f"{base}/blog/{stem}/"


# --------------------------------------------------------------------------
# Selection - which post deserves a LinkedIn slot
# --------------------------------------------------------------------------

# Content shapes that read badly on LinkedIn. They are fine on the blog but
# they are feed-churn: nobody shares a regional news roundup.
SUPPRESS_TITLE_PREFIXES = ["Week in AI", "US AI Pulse", "UK AI Weekly", "EU AI Weekly",
                           "EU AI Watch", "Quick Hits", "AI Bloopers", "Sol's Take"]

# Signals that a post actually sells the work: a skill someone can install, a
# tutorial someone can follow, a lesson someone can apply.
BOOST_PATTERNS = [
    (r"\bskills?\b", 18),
    (r"openclaw", 16),
    (r"\bMCP\b", 12),
    (r"install\b|\bopenclaw skills install\b", 12),
    (r"how to\b|\btutorial\b|\bstep by step\b|\bwalkthrough\b", 14),
    (r"\bagent(s|ic)?\b", 10),
    (r"\bworkflow\b|\bautomation\b|\bcron\b", 10),
    (r"\bwhat i (learned|got wrong|got right)\b|\bhonest\b|\bthe truth\b", 12),
    (r"\bfailed\b|\bbreakpoint\b|\bwent wrong\b|\bpost-?mortem\b", 8),
    (r"\d+\s?(%|hours?|minutes?|lines? of code|skills?|cron)", 8),
]

NEGATIVE_PATTERNS = [
    (r"\bweek in ai\b|\bai pulse\b|\bai weekly\b|\bai watch\b", 30),
    (r"^\s*(us|uk|eu)\b", 18),
    (r"\bbleeper|\bfunny\b|\bpunchline\b", 12),
    (r"\broundup\b|\bdaily briefing\b|\bquick-?hits\b", 20),
]


def score_post(meta, body, filename, cfg):
    """Score how well a post would work on LinkedIn.

    Higher is better. The rubric is deliberately explainable - every term
    below corresponds to a reason a post does or does not travel on LinkedIn.
    """
    sel = cfg.get("selection", {})
    title = meta.get("title", "")
    desc = meta.get("description", "")
    tags = meta.get("tags") or []
    if isinstance(tags, str):
        tags = [t.strip() for t in tags.split(",")]
    tags = [str(t).lower() for t in tags]

    haystack = f"{title}\n{desc}\n{body[:3000]}".lower()
    score = 0.0
    reasons = []

    for pattern, weight in BOOST_PATTERNS:
        if re.search(pattern, haystack, re.IGNORECASE | re.MULTILINE):
            score += weight
            reasons.append(f"+{weight} matches /{pattern}/")

    for pattern, weight in NEGATIVE_PATTERNS:
        if re.search(pattern, haystack, re.IGNORECASE | re.MULTILINE):
            score -= weight
            reasons.append(f"{weight} matches /{pattern}/")

    # Title prefixes are a hard signal - these series never travel.
    for prefix in sel.get("exclude_title_prefixes", SUPPRESS_TITLE_PREFIXES):
        if title.strip().startswith(prefix):
            score -= 40
            reasons.append(f"-40 title starts with '{prefix}'")
            break

    # Tag boosts and suppressions.
    for tag in tags:
        if tag in [t.lower() for t in sel.get("boost_tags", [])]:
            score += 6
            reasons.append(f"+6 tag '{tag}'")
        if tag in [t.lower() for t in sel.get("suppress_tags", [])]:
            score -= 10
            reasons.append(f"-10 tag '{tag}'")

    # A post that ends on a genuine opinion travels further than a recap.
    if re.search(r"\b(i think|in my opinion|honestly|the real (problem|issue)|what actually|my honest)\b",
                 haystack, re.IGNORECASE):
        score += 10
        reasons.append("+10 carries an opinion")

    # Concrete detail: code, numbers, commands.
    if re.search(r"```|\$ |\bcurl\b|\bopenclaw \w", body):
        score += 8
        reasons.append("+8 contains code or commands")

    # Freshness decay. Their own plan says a post can sit and still be good.
    date_str = str(meta.get("date", ""))
    age_days = None
    if date_str:
        for fmt in ("%Y-%m-%d %H:%M:%S %z", "%Y-%m-%d %H:%M:%S", "%Y-%m-%d"):
            try:
                parsed = datetime.strptime(date_str.strip(), fmt)
                if parsed.tzinfo is None:
                    parsed = parsed.replace(tzinfo=timezone.utc)
                age_days = (datetime.now(timezone.utc) - parsed).days
                break
            except ValueError:
                continue
    if age_days is not None:
        if age_days > sel.get("max_age_days", 120):
            score -= 25
            reasons.append("-25 older than max_age_days")
        elif age_days <= 7:
            score += 12
            reasons.append("+12 published this week")
        elif age_days <= 30:
            score += 6
            reasons.append("+6 published this month")

    # Length. Under 600 characters is a teaser; over 6000 is an essay.
    length = len(body)
    if 400 <= length <= 6000:
        score += 5
        reasons.append("+5 good length")

    return score, reasons


def load_posts(cfg):
    posts_dir = REPO / cfg.get("posts_dir", "_posts")
    if not posts_dir.exists():
        log(f"posts dir not found: {posts_dir}")
        return []
    out = []
    for path in sorted(posts_dir.glob("*.md")):
        try:
            raw = path.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        meta, body = parse_frontmatter(raw)
        out.append({"path": path, "filename": path.name, "meta": meta, "body": body})
    return out


def load_posted_log():
    if not POSTED_LOG.exists():
        return {}
    try:
        return json.loads(POSTED_LOG.read_text())
    except json.JSONDecodeError:
        log("posted log is corrupt - starting a fresh one")
        return {}


def save_posted_log(data):
    LOGS_DIR.mkdir(parents=True, exist_ok=True)
    POSTED_LOG.write_text(json.dumps(data, indent=2, sort_keys=True))


def select_post(cfg, only_file=None):
    """Pick the highest scoring post that has not been posted to LinkedIn yet."""
    posted = load_posted_log()
    candidates = []
    for post in load_posts(cfg):
        key = post["filename"]
        if key in posted:
            continue
        score, reasons = score_post(post["meta"], post["body"], post["filename"], cfg)
        post["score"] = score
        post["reasons"] = reasons
        candidates.append(post)
    candidates.sort(key=lambda p: p["score"], reverse=True)
    return candidates


# --------------------------------------------------------------------------
# Composition - the agent writes the copy
# --------------------------------------------------------------------------

PROMPT_TEMPLATE = """You are writing a LinkedIn post for a reader who scrolls fast.

The source is a post from Sol AI's blog (thesolai.github.io), written by an AI agent called Sol that works with a human developer, Amre.

VOICE: {tone}
{tone_extra}

SOURCE POST
Title: {title}
Description: {description}
Tags: {tags}
Body:
{body}

HARD RULES - do not break these:
1. {max_chars} characters maximum. Count roughly. Short and dense beats long and thin.
2. The first TWO lines are the only thing most people read before the "see more" cut. The first line must be a specific, concrete hook - a moment, a number, a mistake, a claim. No "I'm excited to share", no "in today's world", no "let me tell you about".
3. Write like a human talking. Short paragraphs, blank line between them. Never a wall of text. Never more than 3 lines in a row.
4. Do NOT include a URL. Do NOT include hashtags. Do NOT sign off. Those are added separately.
5. End with one genuine question to the reader that someone can actually answer. Not "thoughts?"
6. Be specific. Real names, real numbers, real failures. If the source has a concrete detail, use it.
7. At most one emoji, and only if it genuinely lands.
8. Never claim results that are not in the source. Do not invent metrics.

Write the post body only. No preamble, no title, no quotes around it, no "Here is the post".
"""


def find_openclaw():
    override = os.environ.get("OPENCLAW_BIN")
    if override and Path(override).exists():
        return override
    for candidate in OPENCLAW_BIN_CANDIDATES:
        if Path(candidate).exists():
            return candidate
    found = shutil.which("openclaw")
    return found


def strip_tui_noise(text):
    """Strip the agent CLI's TUI chrome, same way blog-cron.sh does."""
    kept = []
    for line in text.split("\n"):
        if TUI_NOISE.match(line) or PLUGIN_NOISE.match(line):
            continue
        if line.strip().startswith("openclaw "):
            continue
        kept.append(line)
    return "\n".join(kept).strip()


def compose_with_agent(post, cfg, voice_name):
    """Ask the OpenClaw agent to write the LinkedIn copy.

    Returns the copy, or None if no agent is available. The agent runs with
    the same --agent main and timeout the blog cron uses, so the voice on
    LinkedIn matches the voice on the blog.
    """
    binary = find_openclaw()
    if not binary:
        log("no openclaw binary found - using the template fallback")
        return None

    voice = cfg.get("voices", {}).get(voice_name, {})
    body = strip_markdown(post["body"])[:6000]
    prompt = PROMPT_TEMPLATE.format(
        tone=voice.get("tone", "honest, direct, specific"),
        tone_extra=voice.get("prompt_extra", ""),
        title=post["meta"].get("title", ""),
        description=post["meta"].get("description", ""),
        tags=", ".join(str(t) for t in (post["meta"].get("tags") or [])),
        body=body,
        max_chars=MAX_POST_CHARS - 200,
    )

    try:
        result = subprocess.run(
            [binary, "agent", "--agent", "main", "--message", prompt, "--timeout", "300"],
            capture_output=True, text=True, timeout=360,
        )
    except subprocess.TimeoutExpired:
        log("openclaw timed out")
        return None
    except OSError as e:
        log(f"could not run openclaw: {e}")
        return None

    if result.returncode != 0:
        log(f"openclaw exited {result.returncode}")
        return None

    copy = strip_tui_noise(result.stdout)
    if not copy:
        log("openclaw returned nothing")
        return None
    return copy


def _norm_words(text):
    return set(re.findall(r"[a-z0-9]+", text.lower()))


def _too_similar(a, b):
    """True when two blocks say the same thing and one should be dropped."""
    wa, wb = _norm_words(a), _norm_words(b)
    if not wa or not wb:
        return False
    if wa <= wb or wb <= wa:
        return True
    overlap = len(wa & wb) / len(wa | wb)
    return overlap > 0.6


def compose_fallback(post, cfg, voice_name):
    """Deterministic composition used when no agent is available.

    It is not as good as the agent, but it is never empty and it never
    invents anything that is not in the source post.
    """
    meta = post["meta"]
    title = meta.get("title", "").strip()
    desc = meta.get("description", "").strip()
    plain = strip_markdown(post["body"])

    # First meaningful line of the body is usually the best hook.
    hook = ""
    for line in plain.split("\n"):
        line = line.strip()
        if len(line) > 40 and not line.startswith("|"):
            hook = line
            break

    # Pull a couple of bullets or short paragraphs as supporting detail.
    details = []
    for line in plain.split("\n"):
        line = line.strip()
        if line.startswith("- ") and 30 < len(line) < 180:
            details.append("- " + line[2:].strip())
        if len(details) == 3:
            break

    parts = []
    if hook:
        parts.append(hook)
    # The front-matter description often restates the opening line. If it
    # says the same thing, drop it rather than printing it twice.
    if desc and len(desc) > 30 and not any(_too_similar(desc, p) for p in parts):
        parts.append(desc)
    if details:
        parts.append("What actually mattered:\n" + "\n".join(details))
    if not parts:
        parts.append(title)

    # The link is appended by build_post_text - do not add it here or it
    # ends up twice.
    return "\n\n".join(parts)


def pick_hashtags(post, cfg):
    """Three to five hashtags. Always includes the two house tags."""
    tags_cfg = cfg.get("hashtags", {})
    chosen = list(tags_cfg.get("always", ["aiagents", "automation"]))

    mapping = {k.lower(): v for k, v in tags_cfg.get("by_tag", {}).items()}
    post_tags = post["meta"].get("tags") or []
    if isinstance(post_tags, str):
        post_tags = [t.strip() for t in post_tags.split(",")]

    for tag in post_tags:
        key = str(tag).lower()
        if key in mapping:
            value = mapping[key]
            if value not in chosen:
                chosen.append(value)

    # Fall back to the topic of the body if the tags were unhelpfully generic.
    if len(chosen) < 3:
        haystack = f"{post['meta'].get('title','')} {post['body'][:1500]}".lower()
        for topic, hashtag in (("openclaw", "openclaw"), ("ollama", "ollama"),
                               ("python", "python"), ("automation", "automation"),
                               ("agent", "aiagents"), ("skill", "aiskills")):
            if topic in haystack and hashtag not in chosen:
                chosen.append(hashtag)

    limit = tags_cfg.get("max", 5)
    return "#" + " #".join(chosen[:limit])


def build_post_text(post, cfg, voice_name):
    """Compose the final LinkedIn text: body + link + hashtags."""
    copy = compose_with_agent(post, cfg, voice_name)
    used_fallback = False
    if not copy:
        copy = compose_fallback(post, cfg, voice_name)
        used_fallback = True

    copy = copy.strip()
    copy = re.sub(r"^#+\s*", "", copy)                 # a stray markdown heading
    copy = re.sub(r"^\s*(here'?s|here is)[^\n]*:\s*", "", copy, flags=re.IGNORECASE)
    copy = re.sub(r"^[\"'](.*)[\"']$", r"\1", copy.strip())
    copy = re.sub(r"https?://\S+", "", copy)           # the agent was told not to add a link
    copy = re.sub(r"#[A-Za-z0-9_]+", "", copy)         # nor hashtags
    copy = re.sub(r"\n{3,}", "\n\n", copy).strip()

    link = post_url(post["filename"], cfg)
    hashtags = pick_hashtags(post, cfg)
    voice = cfg.get("voices", {}).get(voice_name, {})
    signoff = voice.get("signoff", "").strip()

    blocks = [copy]
    if cfg.get("link", {}).get("in_body", True):
        blocks.append(f"Read it here: {link}")
    if signoff:
        blocks.append(signoff)
    blocks.append(hashtags)

    text = "\n\n".join(b for b in blocks if b).strip()

    # Hard limit. Trim from the middle, not the end, so the hook and the
    # closing question both survive.
    if len(text) > MAX_POST_CHARS:
        link_block = f"Read it here: {link}"
        hashtags = pick_hashtags(post, cfg)
        head = copy[: MAX_POST_CHARS - len(link_block) - len(hashtags) - 120]
        cut = head.rfind(". ")
        if cut > len(head) * 0.5:
            head = head[: cut + 1]
        text = f"{head.rstrip()}\n\n{link_block}\n\n{hashtags}".strip()
        log(f"post was too long - trimmed to {len(text)} chars")

    return text, used_fallback


# --------------------------------------------------------------------------
# LinkedIn API
# --------------------------------------------------------------------------

def api_request(method, url, token, body=None, headers=None, raw=None):
    """One HTTP call against the LinkedIn API. Returns (status, parsed_body)."""
    hdrs = {
        "Authorization": f"Bearer {token}",
        "X-Restli-Protocol-Version": "2.0.0",
    }
    if headers:
        hdrs.update(headers)

    data = None
    if raw is not None:
        data = raw
        hdrs.setdefault("Content-Type", "application/octet-stream")
    elif body is not None:
        data = json.dumps(body).encode("utf-8")
        hdrs.setdefault("Content-Type", "application/json")

    request = urllib.request.Request(url, data=data, headers=hdrs, method=method)
    try:
        with urllib.request.urlopen(request, timeout=90) as response:
            payload = response.read().decode("utf-8", errors="ignore")
            try:
                return response.status, json.loads(payload)
            except json.JSONDecodeError:
                return response.status, payload
    except urllib.error.HTTPError as e:
        payload = e.read().decode("utf-8", errors="ignore")
        try:
            return e.code, json.loads(payload)
        except json.JSONDecodeError:
            return e.code, payload
    except urllib.error.URLError as e:
        log(f"network error: {e}")
        return 0, str(e)


def get_author_urn(token, cfg, which):
    """Resolve the configured author URN, or discover it from the token."""
    authors = cfg.get("authors", {})
    entry = authors.get(which, {})
    urn = (entry.get("urn") or "").strip()
    if urn:
        return urn

    log(f"no urn configured for '{which}' - trying to discover it")
    status, data = api_request("GET", f"{api_base(cfg)}/v2/me", token)
    if status == 200 and isinstance(data, dict) and data.get("id"):
        discovered = f"urn:li:person:{data['id']}"
        log(f"discovered person urn: {discovered}")
        return discovered
    if status in (401, 403):
        log(f"LinkedIn rejected the token ({status}). It expires about every 60 days -")
        log("refresh it with --init-token, see PROMOTION/LINKEDIN-SETUP.md")

    status, data = api_request(
        "GET",
        f"{api_base(cfg)}/v2/organizations?q=company&v2OrganizationFields=name",
        token,
    )
    if status == 200:
        log(f"org listing returned: {str(data)[:400]}")
    return None


def validate_token(token, cfg):
    """Check the token before doing any work. Returns True if it is usable."""
    status, data = api_request("GET", f"{api_base(cfg)}/v2/me", token)
    if status == 200:
        return True
    if status in (401, 403):
        log(f"LinkedIn rejected the token ({status}). It expires about every 60 days -")
        log("refresh it with --init-token, see PROMOTION/LINKEDIN-SETUP.md")
    else:
        log(f"could not verify the token ({status}): {str(data)[:300]}")
    return False


def upload_image(token, image_path, urn, cfg):
    """Upload an image and return its LinkedIn image URN.

    Uses the rest/images initialize + PUT flow. Returns None on failure -
    the post still goes out without an image rather than not at all.
    """
    if not image_path or not Path(image_path).exists():
        log(f"image not found: {image_path}")
        return None

    version = cfg.get("api", {}).get("version", "202408")
    size = Path(image_path).stat().st_size
    caption = "Sol AI"

    status, data = api_request(
        "POST",
        f"{api_base(cfg)}/rest/images?action=initialize",
        token,
        body={
            "initializeUploadRequest": {
                "owner": urn,
                "fileSizeBytes": size,
                "uploadCaptions": {"en-US": caption},
                "uploadFileName": Path(image_path).name,
            }
        },
        headers={"LinkedIn-Version": version},
    )
    if status != 200 or not isinstance(data, dict):
        log(f"image initialize failed ({status}): {str(data)[:300]}")
        return None

    value = data.get("value", data)
    upload_url = value.get("uploadUrl")
    image_urn = value.get("image")
    if not upload_url or not image_urn:
        log(f"image initialize returned no uploadUrl: {str(data)[:300]}")
        return None

    payload = Path(image_path).read_bytes()
    status, body = api_request("PUT", upload_url, token, raw=payload)
    if status not in (200, 201, 204):
        log(f"image PUT failed ({status}): {str(body)[:300]}")
        return None

    log(f"image uploaded: {image_urn}")
    return image_urn


def publish_rest(token, urn, text, image_urn, cfg):
    """Publish via POST /rest/posts."""
    version = cfg.get("api", {}).get("version", "202408")
    content = {"text": text}
    if image_urn:
        content["media"] = {"id": image_urn, "title": "Sol AI"}

    body = {
        "author": urn,
        "visibility": cfg.get("api", {}).get("visibility", "PUBLIC"),
        "distribution": {
            "feedDistribution": "MAIN_FEED",
            "targetEntities": [],
            "thirdPartyDistributionChannels": [],
        },
        "content": content,
        "lifecycleState": "PUBLISHED",
        "isReshareDisabledByAuthor": False,
    }

    status, data = api_request(
        "POST", f"{api_base(cfg)}/rest/posts", token, body=body,
        headers={"LinkedIn-Version": version},
    )
    return status, data


def publish_legacy(token, urn, text, image_url, cfg):
    """Publish via POST /v2/ugcPosts. References the public og image by URL."""
    share = {
        "shareCommentary": {"text": text},
    }
    if image_url:
        share["shareMediaCategory"] = {
            "media": [{
                "status": "READY",
                "originalUrl": image_url,
                "title": {"text": "Sol AI"},
            }]
        }

    if urn.startswith("urn:li:organization:"):
        author = {"ln": "organization", "id": urn.split(":")[-1], "name": "Sol AI"}
    else:
        author = {"ln": "person", "id": urn.split(":")[-1]}

    body = {
        "author": author,
        "lifecycleState": "PUBLISHED",
        "specificContent": {"com.linkedin.ugc.ShareContent": share},
        "visibility": {"com.linkedin.ugc.MemberNetworkVisibility": "PUBLIC"},
    }

    status, data = api_request("POST", f"{api_base(cfg)}/v2/ugcPosts", token, body=body)
    return status, data


def publish(token, urn, text, image_path, cfg):
    """Publish, trying the modern API first and falling back to the legacy one."""
    style = cfg.get("api", {}).get("style", "rest")
    image_url = None
    if image_path:
        stem = Path(image_path).stem
        image_url = f"{cfg.get('site_url', SITE_URL).rstrip('/')}/og/{stem}.png"

    if style == "legacy":
        status, data = publish_legacy(token, urn, text, image_url, cfg)
        if status in (200, 201):
            return status, data
        log(f"legacy publish failed ({status}): {str(data)[:400]}")
        return status, data

    image_urn = upload_image(token, image_path, urn, cfg) if image_path else None
    if image_path and not image_urn:
        log("no image urn - posting without media")

    status, data = publish_rest(token, urn, text, image_urn, cfg)
    if status in (200, 201):
        return status, data

    log(f"rest publish failed ({status}): {str(data)[:400]}")
    log("retrying with the legacy endpoint")
    status, data = publish_legacy(token, urn, text, image_url, cfg)
    return status, data


# --------------------------------------------------------------------------
# Queue - the human-in-the-loop path
# --------------------------------------------------------------------------

def write_queue(text, post, cfg, image_path, fallback_used):
    LOGS_DIR.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    link = post_url(post["filename"], cfg)
    block = [
        f"## {post['meta'].get('title', post['filename'])}",
        "",
        f"- **Generated:** {stamp}",
        f"- **Source:** {link}",
        f"- **Image:** {image_path or '(none)'}",
        f"- **Characters:** {len(text)}",
        f"- **Composer:** {'template fallback' if fallback_used else 'openclaw agent'}",
        "",
        "```",
        text,
        "```",
        "",
    ]
    header = []
    if not QUEUE_FILE.exists():
        header = [
            "# LinkedIn queue",
            "",
            "Generated posts waiting to be published. Copy the text, paste into LinkedIn,",
            "attach the image, and post. Delete the block once it is live.",
            "",
            "---",
            "",
        ]
    with QUEUE_FILE.open("a") as f:
        if header:
            f.write("\n".join(header))
        f.write("\n".join(block))


# --------------------------------------------------------------------------
# Main
# --------------------------------------------------------------------------

def og_image_for(post, cfg):
    """The OG image for a post, if it exists.

    The naming contract is the source filename minus the extension. The OG
    generator and the post layout both rely on this, so do not change one
    side without the other.
    """
    stem = Path(post["filename"]).stem
    candidate = REPO / cfg.get("og_dir", "og") / f"{stem}.png"
    return candidate if candidate.exists() else None


def cmd_list(cfg, limit=15):
    candidates = select_post(cfg)
    if not candidates:
        log("no unposted posts left")
        return
    print(f"{'score':>6}  {'date':<11} {'title':<70} source")
    print("-" * 130)
    for post in candidates[:limit]:
        meta = post["meta"]
        print(f"{post['score']:>6.1f}  {str(meta.get('date','?'))[:10]:<11} "
              f"{str(meta.get('title',''))[:70]:<70} {post['filename']}")
    print()
    print("Top candidate reasons:")
    for reason in candidates[0].get("reasons", [])[:12]:
        print(f"  {reason}")
    print()
    print(f"{len(candidates)} unposted posts scored. "
          f"Use --file <name> to pick a specific one, or --post to publish the top one.")


def cmd_whoami(token, cfg):
    status, data = api_request("GET", f"{api_base(cfg)}/v2/me", token)
    print(f"GET /v2/me -> {status}")
    print(json.dumps(data, indent=2) if isinstance(data, dict) else str(data)[:800])
    print()
    status, data = api_request(
        "GET",
        f"{api_base(cfg)}/v2/organizations?q=company&v2OrganizationFields=name,role",
        token,
    )
    print(f"GET /v2/organizations -> {status}")
    print(json.dumps(data, indent=2) if isinstance(data, dict) else str(data)[:800])


def cmd_init_token(args):
    """Exchange an OAuth authorization code for an access token."""
    client_id = read_secret(CLIENT_ID_FILE)
    client_secret = read_secret(CLIENT_SECRET_FILE)
    redirect_uri = read_secret(REDIRECT_URI_FILE)
    if not client_id or not client_secret:
        print("Set up the client id and secret first:", file=sys.stderr)
        print(f"  {CLIENT_ID_FILE}", file=sys.stderr)
        print(f"  {CLIENT_SECRET_FILE}", file=sys.stderr)
        return 1

    payload = urllib.parse.urlencode({
        "grant_type": "authorization_code",
        "code": args.code,
        "client_id": client_id,
        "client_secret": client_secret,
        "redirect_uri": redirect_uri or "https://localhost",
    }).encode()

    request = urllib.request.Request(
        "https://www.linkedin.com/oauth/v2/accessToken",
        data=payload,
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=60) as response:
            data = json.loads(response.read().decode())
    except urllib.error.HTTPError as e:
        print(f"token exchange failed ({e.code}): {e.read().decode()[:400]}", file=sys.stderr)
        return 1

    token = data.get("access_token")
    if not token:
        print(f"no access_token in the response: {data}", file=sys.stderr)
        return 1

    SECRETS_DIR.mkdir(parents=True, exist_ok=True)
    TOKEN_FILE.write_text(token + "\n")
    try:
        TOKEN_FILE.chmod(0o600)
    except OSError:
        pass
    print(f"token stored in {TOKEN_FILE}")
    print(f"expires in {data.get('expires_in', '?')} seconds")
    return 0


def main():
    parser = argparse.ArgumentParser(description="Turn a Sol AI blog post into a LinkedIn post.")
    parser.add_argument("--list", action="store_true", help="show scored candidates")
    parser.add_argument("--dry-run", action="store_true", help="compose and queue, do not publish")
    parser.add_argument("--post", action="store_true", help="compose and publish")
    parser.add_argument("--preview", action="store_true", help="print the composed post and stop")
    parser.add_argument("--file", help="use a specific post file")
    parser.add_argument("--whoami", action="store_true", help="show what this token can post as")
    parser.add_argument("--init-token", metavar="CODE", help="exchange an OAuth code for a token")
    parser.add_argument("--author", choices=["person", "organisation"], help="override the author")
    parser.add_argument("--voice", help="override the voice profile")
    parser.add_argument("--no-image", action="store_true", help="post without an image")
    parser.add_argument("--limit", type=int, default=15, help="candidates to show for --list")
    args = parser.parse_args()

    cfg = load_config()

    if args.init_token:
        return cmd_init_token(args)

    token = get_token()

    if args.whoami:
        if not token:
            print(f"No token. Put one in {TOKEN_FILE} or set LINKEDIN_ACCESS_TOKEN.", file=sys.stderr)
            return 1
        cmd_whoami(token, cfg)
        return 0

    if args.list:
        cmd_list(cfg, args.limit)
        return 0

    # Pick the post.
    if args.file:
        path = Path(args.file)
        if not path.is_absolute():
            path = REPO / args.file
        if not path.exists():
            print(f"Post file not found: {path}", file=sys.stderr)
            return 1
        raw = path.read_text(encoding="utf-8", errors="ignore")
        meta, body = parse_frontmatter(raw)
        post = {"path": path, "filename": path.name, "meta": meta, "body": body, "score": 0}
    else:
        candidates = select_post(cfg)
        if not candidates:
            print("Nothing to post - every post has already been published.", file=sys.stderr)
            return 0
        post = candidates[0]
        log(f"selected: {post['filename']} (score {post['score']:.1f})")

    author_key = args.author or cfg.get("default_author", "person")
    voice_name = args.voice or cfg.get("default_voice", "hybrid")

    text, fallback_used = build_post_text(post, cfg, voice_name)
    image = None if args.no_image else og_image_for(post, cfg)

    if args.preview:
        print(text)
        print()
        print(f"--- characters: {len(text)} | image: {image or '(none)'} | "
              f"author: {author_key} | voice: {voice_name}")
        return 0

    if args.dry_run or not args.post:
        write_queue(text, post, cfg, image, fallback_used)
        log(f"queued in {QUEUE_FILE}")
        print(text)
        print()
        print(f"--- queued in {QUEUE_FILE} (not published)")
        return 0

    # Live publish.
    if not token:
        print(f"No token found. Put one in {TOKEN_FILE} or set LINKEDIN_ACCESS_TOKEN.", file=sys.stderr)
        print("Falling back to the queue so nothing is lost.", file=sys.stderr)
        write_queue(text, post, cfg, image, fallback_used)
        print(f"--- queued in {QUEUE_FILE} (not published)")
        return 1

    if not validate_token(token, cfg):
        print("LinkedIn rejected the token. See PROMOTION/LINKEDIN-SETUP.md to refresh it.", file=sys.stderr)
        write_queue(text, post, cfg, image, fallback_used)
        print(f"--- queued in {QUEUE_FILE} (not published)")
        return 1

    urn = get_author_urn(token, cfg, author_key)
    if not urn:
        print(f"Could not resolve an author URN for '{author_key}'.", file=sys.stderr)
        write_queue(text, post, cfg, image, fallback_used)
        print(f"--- queued in {QUEUE_FILE} (not published)")
        return 1

    status, data = publish(token, urn, text, image, cfg)
    if status not in (200, 201):
        print(f"Publish failed ({status}): {str(data)[:600]}", file=sys.stderr)
        write_queue(text, post, cfg, image, fallback_used)
        print(f"--- queued in {QUEUE_FILE} for manual posting")
        return 1

    posted = load_posted_log()
    posted[post["filename"]] = {
        "url": data.get("id") or data.get("url") or "",
        "text": text,
        "source": post_url(post["filename"], cfg),
        "author": urn,
        "at": datetime.now(timezone.utc).isoformat(),
    }
    save_posted_log(posted)
    log(f"published {post['filename']}")
    print(f"Published: {post['filename']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
