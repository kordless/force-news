# force — News from a Far Galaxy

Google News, rendered as a Star Wars opening crawl.

Live at **[force.nuts.services](https://force.nuts.services)**.

Pick a topic (defaults to **war**) and watch the day's headlines scroll into
hyperspace over a starfield, with John Williams piped in from YouTube.

---

## Quick start — run it locally, no auth, no extras

```bash
git clone https://github.com/kordless/force-news.git
cd force-news

python -m venv .venv
# Linux/macOS:
source .venv/bin/activate
# Windows PowerShell:
.venv\Scripts\Activate.ps1

pip install -r requirements.txt
uvicorn app.main:app --host 0.0.0.0 --port 8080 --reload
```

Open **<http://localhost:8080>**, hit **Engage**, watch the crawl.

That's the whole local-dev story. **No login, no nuts.services account, no
grub instance required.** Out of the box, with no env vars set:

- **Auth is off** → no login prompt, the engage button just works
- **Grub is off** → news.google.com's RSS feed is fetched directly via
  HTTP. Same XML, same parser, no stealth browser in the loop.

The defaults are tuned for "I just want to play with this". Production
(`force.nuts.services`) explicitly opts back into both via env vars set
by `deploy.sh`.

### What gets toggled by what

| Env var | Empty / unset | Set |
|---|---|---|
| `NUTS_AUTH_URL` | auth disabled (anonymous) | auth required — JWT validated against the URL |
| `GRUB_URL` | direct RSS fetch via httpx | crawl through [grubcrawler](https://grub.nuts.services) on the user's bearer |

You can also force-disable either even when its URL is set:

| Override | Effect |
|---|---|
| `DISABLE_AUTH=true` | skip JWT validation, treat everyone as anonymous |
| `DISABLE_GRUB=true` | bypass grub even if `GRUB_URL` is set; fetch RSS direct |

---

## How it works

```
Browser
  ↓ Engage
[ optional ] auth.nuts.services        ← JWT login if AUTH is on
  ↓ token in URL fragment
force.../api/news?topic=…
  ↓ [ if GRUB ] user's bearer
  ↓ [ else ] httpx direct
news.google.com/rss/search?q=…
  ↓ XML
  → parse <item> blocks → JSON
  → render as Star Wars crawl
```

## Stack

- **FastAPI** + **uvicorn** behind a single static HTML/CSS/JS frontend
- Hosted on **Google Cloud Run** (canonical: `gnosis-459403`, `us-central1`)
- Optional auth via [nuts-auth](https://auth.nuts.services) — bearer JWT, validated server-side
- Optional crawl via [grubcrawler](https://grub.nuts.services) on the user's same bearer
- Server-side cache on news payloads: 5 min per topic
- YouTube IFrame Player API for both background visual + music (two players)

## Layout

```
app/
├── __init__.py
├── main.py              ← FastAPI routes + grub bridge + RSS parser + auth gate
└── static/
    ├── show.html        ← splash + prelude + logo bloom + crawl + controls
    ├── stars.png        ← background starfield
    └── og.png           ← OG / Twitter card image
Dockerfile               ← python:3.12-slim + uvicorn
deploy.sh                ← gcloud builds submit + gcloud run deploy
requirements.txt
```

---

## Other ways to run it

### Docker

```bash
docker build -t force-news .
docker run --rm -p 8080:8080 force-news
```

Same defaults — no auth, no grub. Open <http://localhost:8080>.

Add `-e DEFAULT_TOPIC=mars` (or any other env var below) to tune the run.

### Run grub locally too (the full sovereign loop)

If you want the *whole* pipeline on your laptop — no hosted backend in
the picture, the crawl going through a real stealth browser — spin up
[grubcrawler](https://github.com/DeepBlueDynamics/grub-crawler) on Docker
and point force at it:

```bash
# 1. Start grub on port 6792 with auth turned off
docker run -d --name grub \
    -p 6792:6792 \
    -e DISABLE_AUTH=true \
    deepbluedynamics/grubcrawler

# 2. Start force pointing at it
GRUB_URL=http://localhost:6792 \
uvicorn app.main:app --host 0.0.0.0 --port 8080 --reload
```

Engage → force calls `http://localhost:6792/api/crawl` →
grub's Camoufox stealth browser actually drives news.google.com → result
flows back. You can watch grub's logs with `docker logs -f grub`.

**Cleanup when you're done:** `docker stop grub && docker rm grub`.

#### Both in containers? Use a shared network.

If you also `docker run` force (instead of running it bare), you need
both containers on the same Docker network so force can reach grub by
container name:

```bash
docker network create force-net
docker run -d --name grub --network force-net \
    -e DISABLE_AUTH=true \
    deepbluedynamics/grubcrawler
docker run --rm --name force --network force-net -p 8080:8080 \
    -e GRUB_URL=http://grub:6792 \
    force-news
```

(Inside the shared network `grub` resolves as a hostname pointing at the
grub container.)

### Local with the hosted nuts.services backends

If you want to test the full pipeline (auth + grub) against a local server:

```bash
NUTS_AUTH_URL=https://auth.nuts.services \
GRUB_URL=https://grub.nuts.services \
RETURN_URL=http://localhost:8080/auth \
uvicorn app.main:app --host 0.0.0.0 --port 8080 --reload
```

Caveat: `auth.nuts.services` maintains a `CORS_ORIGINS` allowlist. Until
your local origin is added (or you self-host nuts-auth), the login bounce
back to `localhost:8080` will fail. Easiest workaround: leave
`NUTS_AUTH_URL` unset and run anonymous.

### Deploy a fork to your own Cloud Run

1. Fork the repo and clone your fork.
2. Edit `deploy.sh` at the top:
   ```bash
   PROJECT_ID="your-gcp-project"
   REGION="us-central1"
   SERVICE="force"
   DOMAIN="force.example.com"
   ```
3. Edit the `--set-env-vars` line. If you want a public anonymous deploy,
   drop `NUTS_AUTH_URL` and `GRUB_URL` and the service runs against direct
   RSS with no login. If you want auth + crawl, point the URLs at services
   you control:
   ```
   NUTS_AUTH_URL=https://auth.example.com,GRUB_URL=https://grub.example.com,RETURN_URL=https://force.example.com/auth
   ```
4. Run:
   ```bash
   bash deploy.sh
   ```
   Cloud Build, deploy, domain mapping. Add the printed `CNAME` to DNS;
   cert provisions in 5–15 min.

---

## Environment variables

| Var | Default | What |
|---|---|---|
| `NUTS_AUTH_URL` | *(empty → auth off)* | Auth backend. Empty means anonymous mode. Point at your own nuts-auth instance to self-host identity. |
| `GRUB_URL` | *(empty → direct fetch)* | Crawler backend. Empty means httpx fetches news.google.com/rss directly. Point at your own grub instance for sovereign crawling. |
| `RETURN_URL` | `http://localhost:8080/auth` | OAuth callback URL. **Must match the origin you're serving from** (scheme + host + port). Only used when auth is on. |
| `DISABLE_AUTH` | `false` | Force auth off even if `NUTS_AUTH_URL` is set. |
| `DISABLE_GRUB` | `false` | Force grub off even if `GRUB_URL` is set. |
| `DEFAULT_TOPIC` | `war` | What the topic input pre-fills with. |
| `YT_VIDEO_ID` | `_D0ZQPqeJkk` | YouTube video ID for the soundtrack. Swap freely. |
| `CACHE_TTL` | `300` | Seconds to cache news payloads per topic (server-side). |

---

## Security note

When auth is on, force accepts the bearer token via a URL `?token=`
redirect from `auth.nuts.services`, then immediately 302's to a
`#fragment` and stashes it in `localStorage`. That leaves a single
`/auth?token=…` line in the Cloud Run access log per login; everything
afterward is fragment-only.

`Referrer-Policy: strict-origin-when-cross-origin` is set on every
response so the token can't leak via `Referer` to YouTube / Google Fonts
during the brief moment it's in the URL.

---

## License

MIT (see [LICENSE](./LICENSE)).
