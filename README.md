# force — News from a Far Galaxy

Google News, rendered as a Star Wars opening crawl.

Live at **[force.nuts.services](https://force.nuts.services)**.

Sign in (via `auth.nuts.services`), pick a topic (defaults to **war**), and watch
the day's headlines scroll into hyperspace over a starfield, with John Williams
piped in from YouTube.

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
- Hosted on **Google Cloud Run** (`gnosis-459403`, `us-central1`)
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

## Deploy

```bash
bash deploy.sh
```

Builds the image via Cloud Build, deploys to Cloud Run as service `force`,
maps the custom domain `force.nuts.services` (idempotent).

### Env vars

| Var | Default | What |
|---|---|---|
| `NUTS_AUTH_URL` | `https://auth.nuts.services` | Auth backend |
| `GRUB_URL` | `https://grub.nuts.services` | Crawler backend |
| `RETURN_URL` | `https://force.nuts.services/auth` | OAuth callback |
| `DEFAULT_TOPIC` | `war` | Pre-filled topic input |
| `YT_VIDEO_ID` | `_D0ZQPqeJkk` | Star Wars Main Title (music) |
| `CACHE_TTL` | `300` | Seconds to cache news per topic |

## Security note

The current flow accepts the bearer token via a URL `?token=` redirect from
`auth.nuts.services`, then immediately bounces it to a `#fragment` and stashes
it in `localStorage`. That leaves a single `/auth?token=…` line in the Cloud
Run access log per login; everything afterward is fragment-only. To fully
close that, `auth.nuts.services` would need to redirect with `#token=`
instead of `?token=`.

## License

Internal. Don't ship without sign-off.
