"""force.nuts.services — Google News, as a Star Wars crawl."""
import logging
import os
import re
import time
from pathlib import Path
from typing import Optional
from urllib.parse import quote_plus

import httpx
from fastapi import FastAPI, Header, HTTPException, Query, Request
from fastapi.responses import FileResponse, JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("force")

# Local default: grub running on Docker at localhost:6792, no auth.
# Production deploy.sh sets both URLs to point at the hosted services.
NUTS_AUTH     = os.environ.get("NUTS_AUTH_URL", "").rstrip("/")
GRUB          = os.environ.get("GRUB_URL", "http://localhost:6792").rstrip("/")
RETURN_URL    = os.environ.get("RETURN_URL", "http://localhost:8080/auth")
DEFAULT_TOPIC = os.environ.get("DEFAULT_TOPIC", "war")
YT_VIDEO      = os.environ.get("YT_VIDEO_ID", "_D0ZQPqeJkk")  # Star Wars Main Title
CACHE_TTL     = int(os.environ.get("CACHE_TTL", "300"))

def _truthy(s: str) -> bool:
    return (s or "").strip().lower() in ("1", "true", "yes", "on")

AUTH_ENABLED = bool(NUTS_AUTH) and not _truthy(os.environ.get("DISABLE_AUTH", ""))

logger.info("force config: auth=%s grub=%s",
            "ON via " + NUTS_AUTH if AUTH_ENABLED else "OFF (anonymous)", GRUB)

app = FastAPI(title="force", docs_url=None, redoc_url=None)
STATIC = Path(__file__).parent / "static"
app.mount("/static", StaticFiles(directory=STATIC), name="static")

_cache: dict = {}


# ── auth ───────────────────────────────────────────────────────────────────
ANON_CLAIMS = {"sub": "anonymous@local", "user_uid": "anon", "valid": True, "anonymous": True}

async def _verify(token: str) -> Optional[dict]:
    if not AUTH_ENABLED:
        return ANON_CLAIMS
    if not token:
        return None
    try:
        async with httpx.AsyncClient(timeout=8) as c:
            if token.startswith("ahp_"):
                r = await c.post(f"{NUTS_AUTH}/api/validate", json={"token": token})
                if r.status_code == 200 and r.json().get("valid"):
                    return r.json()
            else:
                r = await c.get(
                    f"{NUTS_AUTH}/api/verify",
                    headers={"Authorization": f"Bearer {token}"},
                )
                if r.status_code == 200:
                    return r.json()
    except Exception as e:
        logger.warning(f"auth verify error: {e}")
    return None


def _bearer(authorization: Optional[str]) -> str:
    if authorization and authorization.startswith("Bearer "):
        return authorization[len("Bearer "):].strip()
    return ""


# ── news pipeline ──────────────────────────────────────────────────────────
def _parse_rss(xml: str, limit: int = 18) -> list[dict]:
    """Extract stories from Google News RSS. Returns [{title, source, link, date}]."""
    stories: list[dict] = []
    for m in re.finditer(r"<item>(.*?)</item>", xml, re.DOTALL):
        block = m.group(1)
        t = re.search(r"<title>(.*?)</title>", block, re.DOTALL)
        s = re.search(r"<source[^>]*>(.*?)</source>", block, re.DOTALL)
        d = re.search(r"<pubDate>(.*?)</pubDate>", block, re.DOTALL)
        l = re.search(r"<link>(.*?)</link>", block, re.DOTALL)
        if not t:
            continue
        title = re.sub(r"<!\[CDATA\[(.*?)\]\]>", r"\1", t.group(1).strip(), flags=re.DOTALL)
        src = ""
        if s:
            src = re.sub(r"<!\[CDATA\[(.*?)\]\]>", r"\1", s.group(1).strip(), flags=re.DOTALL)
        if not src and " - " in title:
            title, _, src = title.rpartition(" - ")
        # Always strip the trailing " - <source>" from the title even if we
        # picked up <source> separately — Google News commonly duplicates it.
        if src and title.lower().endswith(" - " + src.lower()):
            title = title[: -(len(src) + 3)]
        link = l.group(1).strip() if l else ""
        link = re.sub(r"<!\[CDATA\[(.*?)\]\]>", r"\1", link, flags=re.DOTALL)
        stories.append({
            "title":  title.strip(),
            "source": src.strip(),
            "link":   link,
            "date":   d.group(1).strip() if d else "",
        })
        if len(stories) >= limit:
            break
    return stories


async def _fetch_via_grub(topic: str, token: str) -> str:
    rss_url = (
        f"https://news.google.com/rss/search?q={quote_plus(topic)}"
        f"&hl=en-US&gl=US&ceid=US:en"
    )
    async with httpx.AsyncClient(timeout=30) as c:
        r = await c.post(
            f"{GRUB}/api/crawl",
            headers={"Authorization": f"Bearer {token}"} if token else {},
            json={
                "url": rss_url,
                "options": {"enable_javascript": False, "wait_for_load": False},
            },
        )
        if r.status_code != 200:
            raise HTTPException(
                status_code=502,
                detail=f"grub crawl returned {r.status_code}",
            )
        data = r.json()
        # try a few field names; grub's response shape can vary
        for key in ("html", "content", "raw_html", "body"):
            if key in data and isinstance(data[key], str) and "<item" in data[key]:
                return data[key]
        # markdown form fallback
        md = data.get("markdown", "")
        if md:
            return md
        return ""


# ── routes ─────────────────────────────────────────────────────────────────
@app.get("/health")
async def health():
    return {"status": "ok", "service": "force"}


@app.get("/")
async def root():
    return RedirectResponse("/show")


_REFERRER_POLICY = {"Referrer-Policy": "strict-origin-when-cross-origin"}


@app.get("/show")
async def show():
    return FileResponse(STATIC / "show.html", headers=_REFERRER_POLICY)


@app.get("/auth")
async def auth_callback(token: Optional[str] = None):
    """Catches the redirect-back from auth.nuts.services.

    If a ?token=... came in, immediately bounce the browser to /show with the
    token in the URL fragment. The fragment never reaches the server on
    subsequent requests, never appears in Cloud Run access logs after this
    hop, never gets sent in Referer headers, and never gets bookmarked into
    history once the SPA's replaceState fires.

    If no token, serve the SPA — covers direct hits that already have a token
    in localStorage.
    """
    if token:
        return RedirectResponse(
            f"/show#token={token}",
            status_code=302,
            headers=_REFERRER_POLICY,
        )
    return FileResponse(STATIC / "show.html", headers=_REFERRER_POLICY)


def _login_url() -> Optional[str]:
    if not AUTH_ENABLED:
        return None
    return f"{NUTS_AUTH}/login?return_url={RETURN_URL}"


@app.get("/api/login-url")
async def login_url():
    return {"url": _login_url()}


@app.get("/api/config")
async def cfg():
    return {
        "default_topic": DEFAULT_TOPIC,
        "yt_video_id":   YT_VIDEO,
        "return_url":    RETURN_URL,
        "login_url":     _login_url(),
        "auth_required": AUTH_ENABLED,
    }


@app.get("/api/news")
async def news(
    topic: str = Query(default=DEFAULT_TOPIC),
    authorization: Optional[str] = Header(default=None),
):
    token = _bearer(authorization)
    claims = await _verify(token)
    if not claims:
        return JSONResponse(
            {"error": "unauthenticated", "login_url": _login_url()},
            status_code=401,
        )

    key = f"{topic.lower().strip()}"
    now = time.time()
    if key in _cache and (now - _cache[key]["at"]) < CACHE_TTL:
        return _cache[key]["data"]

    try:
        body = await _fetch_via_grub(topic, token)
        stories = _parse_rss(body) if "<item" in body else []
    except HTTPException as e:
        return JSONResponse({"error": "crawl failed", "detail": e.detail}, status_code=502)
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=502)

    if not stories:
        return JSONResponse(
            {"error": "no stories", "topic": topic},
            status_code=502,
        )

    payload = {
        "topic":    topic,
        "stardate": _stardate(),
        "stories":  stories,
        "subject":  claims.get("subject") or claims.get("sub") or "",
    }
    _cache[key] = {"at": now, "data": payload}
    return payload


def _stardate() -> str:
    import datetime as dt
    n = dt.datetime.now(dt.timezone.utc)
    return f"{n.year}.{n.timetuple().tm_yday:03d}"
