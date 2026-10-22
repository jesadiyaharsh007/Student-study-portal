"""
Video service for Student Study Portal.

A small always-on server that finds a video's streams with yt-dlp and relays the bytes to the player in the browser.
The website (on Vercel) stays as it is; it only hands the player a short-lived signed pass (see youtube_token in
dashboard/views.py). This service checks that pass, so only people signed in to the site can use it.

Run it:   uvicorn media_service.app:app --host 0.0.0.0 --port 8080
Needs:    MEDIA_SERVICE_SECRET (the same value as on the website) and ALLOWED_ORIGINS (the website's address).
"""
import hashlib
import hmac
import os
import re
import time
from urllib.parse import quote

import requests
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, StreamingResponse

from dashboard import videos          # the same stream and caption code the website uses locally

SECRET = os.environ.get("MEDIA_SERVICE_SECRET", "").strip()
ORIGINS = [o.strip().rstrip("/") for o in os.environ.get("ALLOWED_ORIGINS", "").split(",") if o.strip()]

if not SECRET or not ORIGINS:
    for _env_path in [
        os.path.join(os.path.dirname(__file__), "..", ".env"),
        os.path.join(os.path.dirname(__file__), ".env"),
    ]:
        if os.path.exists(_env_path):
            try:
                with open(_env_path, encoding="utf-8") as _f:
                    for _l in _f:
                        _l = _l.strip()
                        if _l.startswith("#") or "=" not in _l:
                            continue
                        _k, _v = _l.split("=", 1)
                        _k, _v = _k.strip(), _v.strip(' "\'')
                        if _k == "MEDIA_SERVICE_SECRET" and not SECRET:
                            SECRET = _v
                        elif _k == "ALLOWED_ORIGINS" and not ORIGINS:
                            ORIGINS = [o.strip().rstrip("/") for o in _v.split(",") if o.strip()]
            except Exception:
                pass
            if SECRET and ORIGINS:
                break

app = FastAPI(title="Study Portal video service", docs_url=None, redoc_url=None, openapi_url=None)
app.add_middleware(
    CORSMiddleware, allow_origins=ORIGINS or ["*"], allow_methods=["GET", "OPTIONS"], allow_headers=["Range"],
    expose_headers=["Content-Range", "Content-Length", "Accept-Ranges", "Content-Disposition"], max_age=3600,
)


def sign(exp: int) -> str:
    return hmac.new(SECRET.encode(), str(exp).encode(), hashlib.sha256).hexdigest()


def check(token: str) -> None:
    try:
        exp_s, sig = (token or "").split(".", 1)
        exp = int(exp_s)
    except ValueError:
        raise HTTPException(401, "invalid pass")
    if not SECRET or exp < time.time() or not hmac.compare_digest(sig, sign(exp)):
        raise HTTPException(401, "invalid or expired pass")


def need_id(video_id: str) -> None:
    if not videos.valid_id(video_id):
        raise HTTPException(400, "bad video id")


@app.get("/")
def index():
    return {"service": "Student Study Portal Video Relay", "status": "active", "health": "/health"}


@app.get("/health")
def health():
    return {"ok": True, "yt_dlp": getattr(__import__("yt_dlp").version, "__version__", "?")}


@app.get("/stream/{video_id}")
def stream(video_id: str, token: str = ""):
    check(token); need_id(video_id)
    try:
        data = videos.stream_manifest(video_id)
    except videos.StreamUnavailable as exc:
        return JSONResponse({"ok": False, "error": str(exc) or "This video cannot be played here."}, status_code=404)
    return JSONResponse({"ok": True, **data["public"]}, headers={"Cache-Control": "private, max-age=60"})


def relay(request: Request, url: str, **kw):
    headers = {"User-Agent": videos._BROWSER_UA}
    if request.headers.get("range"):
        headers["Range"] = request.headers["range"]
    return videos._HTTP_SESSION.get(url, headers=headers, stream=True, timeout=(6, 25), **kw)


@app.get("/media/{video_id}/{itag}")
def media(video_id: str, itag: str, request: Request, token: str = ""):
    check(token); need_id(video_id)
    if not re.match(r"^[\w-]+$", itag):
        raise HTTPException(400, "bad stream")
    try:
        upstream = relay(request, videos.media_url(video_id, itag))
        if upstream.status_code in (403, 404, 410):          # an expired link: resolve again once
            upstream.close()
            upstream = relay(request, videos.media_url(video_id, itag, refresh=True))
    except (videos.StreamUnavailable, requests.RequestException):
        raise HTTPException(502, "stream unavailable")
    out = {k: upstream.headers[k] for k in ("Content-Type", "Content-Length", "Content-Range") if upstream.headers.get(k)}
    out["Accept-Ranges"] = "bytes"; out["Cache-Control"] = "private, max-age=3600"
    return StreamingResponse(upstream.iter_content(64 * 1024), status_code=upstream.status_code, headers=out)


_BAD_NAME = re.compile('[' + re.escape('\\/:*?"<>|') + chr(13) + chr(10) + ']+')


def safe_name(title: str, ext: str) -> str:
    base = _BAD_NAME.sub(" ", title or "video").strip()[:90] or "video"
    return f"{base}.{ext}"


@app.get("/download/{video_id}/{kind}")
def download(video_id: str, kind: str, request: Request, token: str = "", itag: str = ""):
    check(token); need_id(video_id)
    try:
        if kind == "mp4":
            m = videos.muxed_stream(video_id)
            if not m:
                raise videos.StreamUnavailable("no file")
            url, title, ext = m["url"], m["title"], "mp4"
        else:
            data = videos.stream_manifest(video_id)
            title = data["public"]["title"]
            if kind == "audio":
                itag, ext = data["public"]["audio"]["itag"], "m4a"
            else:
                ext = "mp4"
                if itag not in data["urls"]:
                    raise HTTPException(400, "bad stream")
            url = data["urls"][itag]
        upstream = relay(request, url)
    except (videos.StreamUnavailable, requests.RequestException):
        raise HTTPException(502, "download unavailable")
    headers = {"Content-Type": upstream.headers.get("Content-Type", "application/octet-stream"),
               "Content-Disposition": f"attachment; filename*=UTF-8''{quote(safe_name(title, ext))}"}
    if upstream.headers.get("Content-Length") and upstream.status_code != 206:
        headers["Content-Length"] = upstream.headers["Content-Length"]
    return StreamingResponse(upstream.iter_content(256 * 1024), status_code=200 if upstream.status_code == 206 else upstream.status_code, headers=headers)


@app.get("/captions/{video_id}")
def captions(video_id: str, token: str = ""):
    check(token); need_id(video_id)
    return {"ok": True, "tracks": videos.caption_tracks(video_id)}


@app.get("/captions/{video_id}/{lang}")
def caption_cues(video_id: str, lang: str, token: str = ""):
    check(token); need_id(video_id)
    return {"ok": True, "cues": videos.caption_cues(video_id, lang)}
