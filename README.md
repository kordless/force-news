# force — News from a Far Galaxy

Google News, rendered as a Star Wars opening crawl.

Live at **[force.nuts.services](https://force.nuts.services)**.

Sign in (via `auth.nuts.services`), pick a topic (defaults to **war**), and
watch the day's headlines scroll into hyperspace over a starfield, with John
Williams piped in from YouTube.

---

## How it works

```
Browser
  ↓ Engage
auth.nuts.services        ← JWT login (magic link / Google / GitHub)
  ↓ token in URL fragment
force.nuts.services/api/news?topic=…
  ↓ user's bearer
grub.nuts.services/api/crawl  ← target: news.google.com/rss/search?q=…
  ↓ XML
  → parse <item> blocks → JSON
  → render as Star Wars crawl
```

## Stack

- **FastAPI** + **uvicorn** behind a single static HTML/CSS/JS frontend
- Hosted on **Google Cloud Run** (canonical: `gnosis-459403`, `us-central1`)
- Auth via [nuts-auth](https://auth.nuts.services) — bearer JWT, validated server-side
- News fetched via [grubcrawler](https://grub.nuts.services) on the user's same bearer
- Server-side cache on news payloads: 5 min per topic
- YouTube IFrame Player API for both background visual + music (two players)

## Layout

```
app/
├── __init__.py
├── main.py              ← FastAPI routes + grub bridge + RSS parser
└── static/
    ├── show.html        ← splash + prelude + logo bloom + crawl + controls
    ├── stars.png        ← background starfield
    └── og.png           ← OG / Twitter card image
Dockerfile               ← python:3.12-slim + uvicorn
deploy.sh                ← gcloud builds submit + gcloud run deploy
requirements.txt
```

---

## Run it yourself

You have three ways to run force locally: **bare Python**, **Docker**, or
**deploy a fork to your own Cloud Run project**. All three need an account
on [nuts.services](https://nuts.services) so the crawl can flow through
the same `auth → grub` pipeline that the hosted version uses. (Self-hosting
auth + grub is doable but out of scope for this README — see
[Going fully sovereign](#going-fully-sovereign) at the bottom.)

### Prerequisites

1. **A nuts.services account.** Sign in once at
   [auth.nuts.services](https://auth.nuts.services) (magic link, Google,
   or GitHub). You don't need to do anything else — the JWT-based browser
   login flow will work out of the box once your local URL is the return target.
2. **Python 3.12+** (for bare-Python run) or **Docker** (for the container
   path) or **gcloud CLI authenticated to your GCP project** (for the
   Cloud Run path).

### Path A — bare Python

```bash
git clone https://github.com/kordless/force-news.git
cd force-news

python -m venv .venv
# Linux/macOS:
source .venv/bin/activate
# Windows (PowerShell):
.venv\Scripts\Activate.ps1

pip install -r requirements.txt
```

Then start the server with the **return URL pointing at localhost**:

```bash
# Linux/macOS
RETURN_URL="http://localhost:8080/auth" uvicorn app.main:app --host 0.0.0.0 --port 8080 --reload

# Windows PowerShell
$env:RETURN_URL = "http://localhost:8080/auth"
uvicorn app.main:app --host 0.0.0.0 --port 8080 --reload
```

Open <http://localhost:8080> in a browser. Engage → log in at
auth.nuts.services → land back on `localhost:8080/auth#token=…` →
news fetches via grub.nuts.services and the crawl runs.

### Path B — Docker

```bash
docker build -t force-news .

docker run --rm -p 8080:8080 \
    -e RETURN_URL="http://localhost:8080/auth" \
    -e DEFAULT_TOPIC="war" \
    force-news
```

Same as Path A but containerized. Open <http://localhost:8080>.

### Path C — deploy to your own Cloud Run

If you want force running at your own domain (e.g. `force.example.com`):

1. **Fork the repo** and clone your fork.

2. **Edit `deploy.sh`** at the top:
   ```bash
   PROJECT_ID="your-gcp-project"
   REGION="us-central1"          # or any region you prefer
   SERVICE="force"
   DOMAIN="force.example.com"    # your domain
   ```

3. **Edit the deploy script's `--set-env-vars` line** so `RETURN_URL`
   points at your domain's `/auth`:
   ```
   RETURN_URL=https://force.example.com/auth
   ```

4. **Run:**
   ```bash
   bash deploy.sh
   ```
   This builds via Cloud Build, deploys to Cloud Run, and creates the
   domain mapping (idempotent).

5. **Add the CNAME DNS record** the script prints —
   `force CNAME ghs.googlehosted.com.` — at your DNS provider. Cert
   provisions automatically in 5–15 minutes.

6. **Ask nuts-auth to allow your origin.** The hosted `auth.nuts.services`
   maintains a `CORS_ORIGINS` allowlist. Open an issue (or DM Kord) with
   your domain and it'll be added. **Until that's in, the login redirect
   back to your origin will fail.**

---

## Environment variables

| Var | Default | What |
|---|---|---|
| `NUTS_AUTH_URL` | `https://auth.nuts.services` | Auth backend. Point at your own nuts-auth instance to self-host identity. |
| `GRUB_URL` | `https://grub.nuts.services` | Crawler backend. Point at your own grub instance for sovereign crawling. |
| `RETURN_URL` | `https://force.nuts.services/auth` | OAuth callback. **Must match the origin you're serving from**, including scheme + port for local. |
| `DEFAULT_TOPIC` | `war` | What the topic input pre-fills with. |
| `YT_VIDEO_ID` | `_D0ZQPqeJkk` | YouTube video for the soundtrack. Swap to any video ID. |
| `CACHE_TTL` | `300` | Seconds to cache news payloads per topic (server-side). |

Set them in your shell, in `docker run -e …`, or via
`gcloud run services update --update-env-vars …`.

---

## Going fully sovereign

If you want zero dependency on the hosted nuts.services fleet:

1. **Self-host auth.** Stand up your own [nuts-auth](https://github.com/DeepBlueDynamics/nuts-auth)
   instance — set `NUTS_AUTH_URL` to point at it and `RETURN_URL` to your
   force origin. Add force's origin to nuts-auth's `CORS_ORIGINS`.
2. **Self-host the crawler.** Run your own
   [grubcrawler](https://github.com/DeepBlueDynamics/grub-crawler) and set
   `GRUB_URL` to it. Force passes the user's bearer through to grub
   unchanged, so the same auth backend has to validate it on both ends.
3. **Or skip auth entirely.** If you want a public demo without login,
   open `app/main.py`, find the `_verify()` call in the `/api/news`
   handler, and short-circuit it to always return a dummy claims dict.
   You'll also want to add a rate limiter — `news.google.com` will not
   thank you otherwise.

---

## Troubleshooting

**"Login bounces back but says auth required."**
The `RETURN_URL` env var doesn't match the origin the browser is on. They
must match exactly (scheme, host, port). If you're on `http://localhost:8080`
the env must be `http://localhost:8080/auth`, not `http://127.0.0.1:8080/auth`
and not `https://...`.

**"Login redirect fails with CORS / Origin not allowed."**
nuts-auth maintains an allowlist of `CORS_ORIGINS`. Your origin isn't in it.
Either ask to be added, run your own nuts-auth, or use the hosted
`force.nuts.services`.

**"No stories returned."**
Either grub failed to crawl Google News (rare — grub uses Camoufox stealth)
or the topic is so niche the RSS feed comes back empty. Try a more common
topic.

**"Music plays for 'war' but not for other topics."**
Should be fixed as of the latest revision — earlier code unmuted the
YouTube player after grub returned, which only worked when grub's response
came back fast enough to still be inside the browser's user-activation
window. The current code claims audio permission synchronously on the
Engage click (`unMute()` + `setVolume(0)`), then swells the volume up to
100 after grub returns.

---

## Security note

The current flow accepts the bearer token via a URL `?token=` redirect
from `auth.nuts.services`, then immediately 302's to a `#fragment` and
stashes it in `localStorage`. That leaves a single `/auth?token=…` line
in the Cloud Run access log per login; everything afterward is
fragment-only. To fully close that, `auth.nuts.services` would need to
redirect with `#token=` instead of `?token=`.

`Referrer-Policy: strict-origin-when-cross-origin` is set on every
response so the token never leaks via `Referer` to YouTube / Google Fonts
during the brief moment it's in the URL.

---

## License

MIT (see [LICENSE](./LICENSE)).
