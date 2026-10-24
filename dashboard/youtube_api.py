"""Videos from YouTube's official Data API.

Needs a free API key in YOUTUBE_API_KEY. Every answer is cached: each search costs quota on YouTube's
side, and a whole class can use up the daily allowance in minutes without a cache.
"""
import hashlib
import logging
import re
from datetime import datetime

import requests
from django.conf import settings
from django.core.cache import cache

log = logging.getLogger(__name__)

API = "https://www.googleapis.com/youtube/v3"
TIMEOUT = (4, 12)
SEARCH_TTL = 60 * 30
VIDEO_TTL = 60 * 60
AVATAR_TTL = 60 * 60 * 6

VIDEO_ID_RE = re.compile(r"^[A-Za-z0-9_-]{11}$")
CHANNEL_ID_RE = re.compile(r"^UC[\w-]{22}$")

DEFAULT_QUERY = "study lessons explained"
TOPICS = (
    # key, label, search text
    ("math", "Maths", "maths lessons explained"),
    ("science", "Science", "science lessons explained"),
    ("computing", "Computing", "programming tutorial for beginners"),
    ("stats", "Statistics", "statistics explained"),
    ("english", "English", "english grammar lessons"),
    ("history", "History", "history lessons explained"),
)


class VideoApiError(Exception):
    """A message a student can read: why videos are not showing right now."""


def _key(*parts):
    """Cache keys must be plain text for every cache backend, so hash whatever the search text was."""
    return "yt:" + hashlib.sha1(repr(parts).encode("utf-8")).hexdigest()


def valid_id(video_id):
    return bool(VIDEO_ID_RE.match(video_id or ""))


def _get(endpoint, **params):
    key = settings.YOUTUBE_API_KEY
    if not key:
        raise VideoApiError("Videos are not switched on yet. The site needs a YouTube API key (YOUTUBE_API_KEY).")
    try:
        resp = requests.get(f"{API}/{endpoint}", params={**params, "key": key}, timeout=TIMEOUT)
    except requests.RequestException as exc:
        log.warning("YouTube API unreachable (%s)", exc.__class__.__name__)
        raise VideoApiError("YouTube did not respond. Please try again in a moment.") from None
    if resp.status_code != 200:
        log.warning("YouTube API %s answered %s", endpoint, resp.status_code)
        raise VideoApiError("Videos are unavailable right now. YouTube's daily limit may have been reached; try again later.")
    return resp.json()


def _thumb(snippet):
    thumbs = snippet.get("thumbnails") or {}
    for size in ("medium", "high", "default"):
        if size in thumbs:
            return thumbs[size]["url"]
    return ""


def _when(iso):
    try:
        return datetime.fromisoformat(iso.replace("Z", "+00:00"))
    except (AttributeError, ValueError):
        return None


def channel_avatars(channel_ids):
    """Channel id -> picture URL ("" when there is none). Looked up once per channel, then cached."""
    ids = [c for c in set(channel_ids) if CHANNEL_ID_RE.match(c or "")]
    found, missing = {}, []
    for cid in ids:
        hit = cache.get(_key("avatar", cid))
        if hit is None:
            missing.append(cid)
        else:
            found[cid] = hit
    for start in range(0, len(missing), 50):
        batch = missing[start:start + 50]
        data = _get("channels", part="snippet", id=",".join(batch), maxResults=50)
        for ch in data.get("items", []):
            found[ch["id"]] = _thumb(ch.get("snippet", {}))
        for cid in batch:
            found.setdefault(cid, "")
            cache.set(_key("avatar", cid), found[cid], AVATAR_TTL)
    return found


def search(query, limit=12):
    """Videos for a search: one card per video, each with its channel's name and picture."""
    key = _key("search", query.lower(), limit)
    cached = cache.get(key)
    if cached is not None:
        return cached
    data = _get(
        "search", part="snippet", type="video", q=query, maxResults=limit,
        safeSearch="moderate", videoEmbeddable="true", relevanceLanguage="en",
    )
    videos, seen = [], set()
    for item in data.get("items", []):
        sn = item.get("snippet", {})
        vid = (item.get("id") or {}).get("videoId", "")
        if not valid_id(vid) or vid in seen:
            continue
        seen.add(vid)
        videos.append({
            "id": vid,
            "title": sn.get("title", ""),
            "channel": sn.get("channelTitle", ""),
            "channel_id": sn.get("channelId", ""),
            "thumbnail": _thumb(sn),
            "published": _when(sn.get("publishedAt", "")),
        })
    try:
        avatars = channel_avatars([v["channel_id"] for v in videos])
    except VideoApiError:
        avatars = {}   # the grid still shows; only the pictures are missing
    for v in videos:
        v["channel_avatar"] = avatars.get(v["channel_id"], "")
    cache.set(key, videos, SEARCH_TTL)
    return videos


def video(video_id):
    """One video's details, or None when YouTube does not have it (removed, private or never existed)."""
    key = _key("video", video_id)
    hit = cache.get(key)
    if hit is not None:
        return hit or None
    data = _get("videos", part="snippet,statistics", id=video_id)
    items = data.get("items", [])
    if not items:
        cache.set(key, {}, VIDEO_TTL)
        return None
    sn, st = items[0].get("snippet", {}), items[0].get("statistics", {})
    views = int(st["viewCount"]) if "viewCount" in st else None
    info = {
        "id": video_id,
        "title": sn.get("title", ""),
        "channel": sn.get("channelTitle", ""),
        "channel_id": sn.get("channelId", ""),
        "description": sn.get("description", ""),
        "published": _when(sn.get("publishedAt", "")),
        "views_label": f"{views:,} views" if views is not None else "",
    }
    try:
        info["channel_avatar"] = channel_avatars([info["channel_id"]]).get(info["channel_id"], "")
    except VideoApiError:
        info["channel_avatar"] = ""
    cache.set(key, info, VIDEO_TTL)
    return info
