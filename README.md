# force — News from a Far Galaxy

Google News, rendered as a Star Wars opening crawl. Live at **[force.nuts.services](https://force.nuts.services)**.

Pick a topic, hit Engage, watch the headlines roll into hyperspace.

## Quick start

```bash
git clone https://github.com/kordless/force-news.git
cd force-news
bash deploy.sh
```

Open **<http://localhost:8084>**. Done.

That's a `docker compose up` of two containers:

- **[grubcrawler](https://github.com/DeepBlueDynamics/grub-crawler)** on `localhost:6792` (the stealth crawler that actually fetches news.google.com)
- **force** on `localhost:8084` (this app — splash → crawl)

Tear it down: `bash deploy.sh stop`. Tail logs: `bash deploy.sh logs`.

## Ship to Cloud Run

Override your GCP project and domain (the defaults point at the
DeepBlue Dynamics canonical deploy — you'll want your own):

```bash
PROJECT_ID=my-gcp-project \
DOMAIN=force.example.com \
bash deploy.sh cloudrun
```

Builds via Cloud Build, deploys to Cloud Run, maps the domain. Add the
printed `CNAME` to your DNS provider — cert provisions in 5–15 min.

## How it works

```
Browser  →  force/api/news  →  grub/api/crawl  →  news.google.com/rss  →  parsed → JSON → crawl
```

In production force is gated behind a JWT login via [auth.nuts.services](https://auth.nuts.services); locally auth is off.

## Yeah, "vibe coded"

It's a term. Doesn't have to be a slur. I architected this thing — the
auth flow, the perspective math on the crawl, the autoplay-policy timing
fix on the music, the soft-restart over `location.reload()`. Claude wrote
a lot of the code under those decisions. I read every line.

If you want the long form on why "AI slop" is an *effort* problem and
not a *tooling* problem:
**[AI Slop is an Effort Problem](https://deepbluedynamics.com/blog/ai-slop-effort-problem)**.

It's my prerogative to call it vibe coding. It's your prerogative to
downvote me for it. We're both having a great time.

## Env vars

| Var | Default | What |
|---|---|---|
| `GRUB_URL` | `http://grub:6792` (compose) | Crawler URL. |
| `NUTS_AUTH_URL` | *(empty → off)* | Auth backend. Set to enable login. |
| `RETURN_URL` | `http://localhost:8084/auth` | Auth callback URL. Must match the origin you're serving from. |
| `DEFAULT_TOPIC` | `war` | Pre-fills the topic input. |
| `YT_VIDEO_ID` | `_D0ZQPqeJkk` | YouTube video for the soundtrack. |
| `CACHE_TTL` | `300` | Server-side cache (seconds, per topic). |

## License

MIT (see [LICENSE](./LICENSE)).
