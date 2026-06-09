# force — News from a Far Galaxy

Google News, rendered as a Star Wars opening crawl. Live at **[force.nuts.services](https://force.nuts.services)**.

Pick a topic, hit Engage, watch the headlines roll into hyperspace.

## Quick start

```bash
git clone https://github.com/kordless/force-news.git
cd force-news
bash deploy.sh
```

Open **<http://localhost:8080>**. Done.

That's a `docker compose up` of two containers:

- **[grubcrawler](https://github.com/DeepBlueDynamics/grub-crawler)** on `localhost:6792` (the stealth crawler that actually fetches news.google.com)
- **force** on `localhost:8080` (this app — splash → crawl)

Tear it down: `bash deploy.sh stop`. Tail logs: `bash deploy.sh logs`.

## Ship to Cloud Run

```bash
bash deploy.sh cloudrun
```

Builds via Cloud Build, deploys to Cloud Run, maps `force.nuts.services`. Defaults are tuned for the DeepBlue Dynamics GCP project — override with `PROJECT_ID=… DOMAIN=… bash deploy.sh cloudrun`.

## How it works

```
Browser  →  force/api/news  →  grub/api/crawl  →  news.google.com/rss  →  parsed → JSON → crawl
```

In production force is gated behind a JWT login via [auth.nuts.services](https://auth.nuts.services); locally auth is off.

## Env vars

| Var | Default | What |
|---|---|---|
| `GRUB_URL` | `http://grub:6792` (compose) | Crawler URL. |
| `NUTS_AUTH_URL` | *(empty → off)* | Auth backend. Set to enable login. |
| `RETURN_URL` | `http://localhost:8080/auth` | Auth callback URL. Must match the origin you're serving from. |
| `DEFAULT_TOPIC` | `war` | Pre-fills the topic input. |
| `YT_VIDEO_ID` | `_D0ZQPqeJkk` | YouTube video for the soundtrack. |
| `CACHE_TTL` | `300` | Server-side cache (seconds, per topic). |

## License

MIT (see [LICENSE](./LICENSE)).
