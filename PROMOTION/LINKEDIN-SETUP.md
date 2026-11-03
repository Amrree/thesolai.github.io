# LinkedIn Setup — one time, about 15 minutes

Everything below is one-time. After it, the cron posts on its own.

You need a **LinkedIn account**, a **LinkedIn company page** (required even if you only want to post personally), and about 15 minutes.

---

## Before you start

LinkedIn's API has no "just give me the token" button. You create an app, give it permission to post, then exchange a code for a token. There is no way around the app creation step.

---

## Step 1 — Create the app

1. Go to <https://www.linkedin.com/developers/apps> → **Create app**
2. **App name:** `Sol AI Poster`
   - LinkedIn rejects app names containing the word "LinkedIn". `Sol AI Poster` is fine.
3. **LinkedIn Page:** select your Sol AI company page
   - You must associate a page even if you only ever post as yourself. Create one if you have not got a page yet.
4. **Legal name / logo / description:** whatever you have. The app stays in development mode, so nothing here is public-facing.
5. **Create app**

## Step 2 — Add the "Sign In with LinkedIn" product

On the app's **Products** tab:

- Click **Add product** → **Sign In with LinkedIn using OAuth 2.0**

## Step 3 — Add the scopes

Still on **Products**, under *Sign In with LinkedIn using OAuth 2.0*, click **Add scopes** and select:

- ✅ **`w_member_social`** — post as your personal profile
- ✅ **`w_organization_social`** — post as the company page

Add `w_organization_social` even if you only want personal posts. You can add it later, but adding it now avoids a second round trip.

Leave the default **Product Sign** and **Sign In with LinkedIn** scopes as they are.

## Step 4 — Set the redirect URL

**Auth** tab → **Authorized redirect URLs** → **Add URL**:

```
https://localhost
```

Then **Apply**. LinkedIn can take a few minutes to propagate this. If the next step gives you a redirect error, wait five minutes and try again.

## Step 5 — Copy the client id and secret

**Auth** tab → **Application credentials**:

- **Client ID** — copy it
- **Client secret** — click the eye icon to reveal it, then copy it

Save both into the secrets directory on your Mac:

```bash
mkdir -p ~/.openclaw/workspace/secrets
printf '%s' 'YOUR_CLIENT_ID'      > ~/.openclaw/workspace/secrets/linkedin-client-id.txt
printf '%s' 'YOUR_CLIENT_SECRET'  > ~/.openclaw/workspace/secrets/linkedin-client-secret.txt
printf '%s' 'https://localhost'    > ~/.openclaw/workspace/secrets/linkedin-redirect-uri.txt
chmod 600 ~/.openclaw/workspace/secrets/linkedin-*.txt
```

> **Never put the client secret in the repo.** `scripts/install-publish-hook.sh` installs a pre-push gate that blocks credential pushes — that gate is there because this has already bitten once. Keep the secrets in `~/.openclaw/workspace/secrets/`.

## Step 6 — Get the authorisation code

Open this URL in a browser, signed in as the account you want to post from:

```
https://www.linkedin.com/oauth/v2/authorization?response_type=code&client_id=YOUR_CLIENT_ID&redirect_uri=https://localhost&scope=w_member_social%20w_organization_social
```

You will land on a LinkedIn consent screen. Click **Allow**.

LinkedIn then redirects to `https://localhost/?code=XXXXXX&state=YYYYY`. The page will fail to load — **that is expected**, there is nothing running on localhost. Look at the URL in your browser and copy the `code` value:

```
https://localhost/?code=AQBxxxxxx&state=abc123
                 ^^^^^^^^^^^^^^^^
```

## Step 7 — Exchange it for a token

```bash
cd ~/Projects/thesolai.github.io
python3 scripts/content/linkedin-poster.py --init-token 'AQBxxxxxx'
```

Expected output:

```
token stored in /Users/amre/.openclaw/workspace/secrets/linkedin-access-token.txt
expires in 5184000 seconds
```

The token is valid for about 60 days. **You will need to refresh it roughly every two months.** The fastest way is to redo Steps 6 and 7 — the app and its credentials do not change.

If you would rather not use the script:

```bash
curl -s -X POST https://www.linkedin.com/oauth/v2/accessToken \
  -H 'Content-Type: application/x-www-form-urlencoded' \
  -d "grant_type=authorization_code&code=AQBxxxxxx&client_id=YOUR_CLIENT_ID&client_secret=YOUR_CLIENT_SECRET&redirect_uri=https://localhost" \
  | python3 -c "import sys,json; print(json.load(sys.stdin)['access_token'])" \
  > ~/.openclaw/workspace/secrets/linkedin-access-token.txt
```

## Step 8 — Find your author URNs

```bash
python3 scripts/content/linkedin-poster.py --whoami
```

This prints your personal URN (`urn:li:person:...`) and lists any organisation you can post as. Take the values you need and put them in `scripts/content/linkedin-config.json`:

```json
"authors": {
  "person":       { "urn": "urn:li:person:abc123", ... },
  "organisation": { "urn": "urn:li:organization:98765", ... }
}
```

Set `"default_author"` to `"person"` or `"organisation"` depending on where you want the posts to land.

If `--whoami` shows an empty organisation list, the company page has not approved the app yet — see Troubleshooting.

## Step 9 — Test it

```bash
# See what it would pick, and why
python3 scripts/content/linkedin-poster.py --list

# Read the composed post without publishing anything
python3 scripts/content/linkedin-poster.py --preview

# Publish for real
python3 scripts/content/linkedin-poster.py --post
```

Check your LinkedIn feed. If it is there, you are done with the hard part.

## Step 10 — Turn on the cron

```bash
crontab -e
```

Add this line:

```cron
15 9 * * 2,4,6 /Users/amre/Projects/thesolai.github.io/scripts/content/linkedin-cron.sh
```

That is **Tuesday, Thursday and Saturday at 09:15**. Make sure the file is executable:

```bash
chmod +x ~/Projects/thesolai.github.io/scripts/content/linkedin-cron.sh
```

The cron wrapper publishes when a token is present and drops a draft into `linkedin-queue.md` when there is not, so a missing token never loses a post.

Check it ran:

```bash
tail -20 ~/.openclaw/workspace/scripts/content/logs/linkedin-cron.log
```

---

## Troubleshooting

**`redirect_uri_mismatch` / `INVALID_REDIRECT_URI`**
The redirect URL is not registered exactly as `https://localhost` — no trailing slash, no `http`. Check **Auth** → *Authorized redirect URLs*. If you just added it, wait five minutes; LinkedIn caches this.

**`unauthorized_client` / scope errors**
The app is in development mode, so the scopes only work for people who have a role on the app. Make sure the account you are authorising with is listed under **Auth** → *App roles* as a Developer or Admin of the app itself.

**`403` on the organisation list, or an empty list**
The company page has not approved the app. Open the company page admin panel → **Settings** → **Page access** or *LinkedIn apps*, and request access to the Sol AI page. Your request gets approved by a page admin. Until then, post as a person — set `"default_author": "person"`.

**`403` when posting as the organisation**
Same as above, plus: the app must be in **Development mode** only for admins of the app. If the app is in *Live* mode it needs LinkedIn review, which is a longer process. Development mode is fine for your own page.

**The token works for one post then stops**
That is the 60-day expiry. Redo Steps 6 and 7.

**`RestliProtocolException` or a version error**
The `api.version` in the config has been retired by LinkedIn. The script falls back to the legacy `v2/ugcPosts` endpoint automatically, so the post still goes out — but update `api.version` in `linkedin-config.json` to a current `YYYYMM` value to silence it.

**The image is not showing**
The `rest` path uploads the binary and references an image URN. If the upload fails the script posts without media rather than not posting at all, and logs `no image urn - posting without media`. Check that `og/<post-stem>.png` exists — the file name must be the post source file name without the extension.

**Post says "not published" and the queue file has the draft**
That means no token was found. Check the token file exists and is not empty:
```bash
wc -c ~/.openclaw/workspace/secrets/linkedin-access-token.txt
```

---

## Refreshing the token without doing it by hand

Once the app exists, refreshing is two steps. Put this in a cron of its own, monthly:

```bash
#!/bin/bash
# Refresh the LinkedIn token. Prints a URL to open, then exchanges the code.
echo "Open this URL, approve it, and copy the code from the redirect:"
echo "https://www.linkedin.com/oauth/v2/authorization?response_type=code&client_id=$(cat ~/.openclaw/workspace/secrets/linkedin-client-id.txt)&redirect_uri=https://localhost&scope=w_member_social%20w_organization_social"
```

A fully automatic refresh needs a headless browser and a persistent session, which is more moving parts than a two-minute manual job once every two months. Keep it manual.
