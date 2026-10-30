"""Videos for the Videos page.

The topic shelves show the hand-picked lessons in dashboard/video_library.py. Search finds lessons anywhere
on YouTube in one of two ways:
- with YOUTUBE_API_KEY: YouTube's official Data API (with channel pictures);
- without it: Gemini (the key Lexi already uses) suggests well-known lessons, and every suggestion is checked
  with YouTube's public lookup (oEmbed). Only real, playable videos whose title fits the search are kept,
  shown with YouTube's own title and channel. Matching hand-picked lessons are added after them.

Everything plays in YouTube's privacy-friendly embedded player (youtube-nocookie.com). Answers from YouTube
are cached, because each API search costs quota and the public lookup is slow from far away.
"""
import hashlib
import json
import logging
import re
from concurrent.futures import FIRST_COMPLETED, ThreadPoolExecutor, wait
from datetime import datetime

import requests
from django.conf import settings
from django.core.cache import cache as _memory, caches
from django.db import DatabaseError

from . import video_library

log = logging.getLogger(__name__)

API = "https://www.googleapis.com/youtube/v3"
OEMBED = "https://www.youtube.com/oembed"
TIMEOUT = (4, 8)
SEARCH_TTL = 60 * 30
SUGGEST_TTL = 60 * 60 * 24        # a found-and-checked list stays good for a day
GEMINI = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
# Both are asked at once. 3.5-flash suggests the best lessons (~6s) but is sometimes overloaded (503); the lite
# model answers in ~3s and fills in. Lite also suggests some unrelated videos, which never pass _fits().
SUGGEST_MODELS = (("gemini-3.5-flash", 12), ("gemini-3.1-flash-lite", 20))   # (model, how many lessons to ask for)
SUGGEST_WAIT = 8                  # seconds to wait for both models; then whatever has arrived is used
SUGGEST_BUDGET = 14               # the longest any search waits for Gemini, inside Vercel's 30s
_POOL = ThreadPoolExecutor(max_workers=10, thread_name_prefix="videos")
DETAILS_TTL = 60 * 60 * 6
AVATAR_TTL = 60 * 60 * 24

VIDEO_ID_RE = re.compile(r"^[A-Za-z0-9_-]{11}$")
CHANNEL_ID_RE = re.compile(r"^UC[\w-]{22}$")
TOPIC_LABELS = dict(video_library.TOPICS)

_session = requests.Session()


class _SharedCache:
    """The database cache shared by all instances, falling back to this instance's memory if the table is
    missing or the database is unreachable (a cache must never break the page)."""

    def get(self, key, default=None):
        try:
            return caches["shared"].get(key, default)
        except DatabaseError:
            return _memory.get(key, default)

    def set(self, key, value, timeout):
        try:
            caches["shared"].set(key, value, timeout)
        except DatabaseError:
            _memory.set(key, value, timeout)


cache = _SharedCache()


class VideoError(Exception):
    """A message a student can read: why YouTube search is unavailable right now."""


def valid_id(video_id):
    return bool(VIDEO_ID_RE.match(video_id or ""))


def thumb(video_id):
    return f"https://i.ytimg.com/vi/{video_id}/mqdefault.jpg"


def _key(*parts):
    """Cache keys must be plain text for every cache backend, so hash the search words."""
    return "videos:" + hashlib.sha1(repr(parts).encode("utf-8")).hexdigest()


def _card(video_id, title, channel, topic="", **extra):
    return {"id": video_id, "title": title, "channel": channel, "topic": topic,
            "topic_label": TOPIC_LABELS.get(topic, ""), "thumbnail": thumb(video_id),
            "channel_avatar": "", "published": None, **extra}


# --------------------------------------------------------------------------- the hand-picked library

LIBRARY = [_card(*row) for row in video_library.LESSONS]
FEATURED = _card(*video_library.FEATURED, topic="")
_BY_ID = {v["id"]: v for v in LIBRARY + [FEATURED]}


def library(topic=""):
    if topic:
        return [v for v in LIBRARY if v["topic"] == topic]
    # "All": the study-skills talk first, then the topics taking turns so every subject shows near the top
    shelves = [[v for v in LIBRARY if v["topic"] == key] for key, _label in video_library.TOPICS]
    mixed = [v for row in zip(*shelves) for v in row]
    mixed += [v for v in LIBRARY if v not in mixed]
    return [FEATURED] + mixed


_FILLER = {"the", "of", "and", "in", "to", "is", "on", "for", "with", "how", "what", "why", "an", "no", "it", "by",
           "do", "does", "about", "video", "videos", "lesson", "lessons", "explained", "learn"}


def _words(text):
    """Meaningful words, singular: "black holes" and "Black Hole" share "black" and "hole"."""
    words = (w for w in re.findall(r"[a-z0-9]+", text.lower()) if len(w) > 1 and w not in _FILLER)
    return {w[:-1] if len(w) > 3 and w.endswith("s") and not w.endswith("ss") else w for w in words}


def _match(words, hay):
    """How well the query words fit one set of words: whole words count 1, near words (a prefix such as
    "derivat" for "derivative", or the same first six letters such as "economy" ~ "economics") count 0.5."""
    near = sum(1 for w in words - hay if len(w) >= 4 and any(
        h.startswith(w) or (len(w) >= 6 and h[:6] == w[:6]) for h in hay))
    return len(words & hay) + 0.5 * near


def library_search(query, limit=24):
    """Lessons that fit the query, best first. The title counts twice as much as the channel and topic,
    so "chemistry" finds the chemistry lesson before a calculus video from "The Organic Chemistry Tutor"."""
    words = _words(query)
    if not words:
        return []
    scored = []
    for n, v in enumerate(LIBRARY + [FEATURED]):
        score = 2 * _match(words, _words(v["title"])) + _match(words, _words(f"{v['channel']} {v['topic_label']}"))
        if score:
            scored.append((-score, n, v))
    scored.sort(key=lambda s: s[:2])
    return [v for _score, _n, v in scored[:limit]]


# --------------------------------------------------------------------------- YouTube Data API (optional)

def has_key():
    return bool(getattr(settings, "YOUTUBE_API_KEY", ""))


def _api(endpoint, **params):
    try:
        resp = _session.get(f"{API}/{endpoint}", params={**params, "key": settings.YOUTUBE_API_KEY}, timeout=TIMEOUT)
    except requests.RequestException as exc:
        log.warning("YouTube API unreachable (%s)", exc.__class__.__name__)
        raise VideoError("YouTube did not respond.") from None
    if resp.status_code != 200:
        log.warning("YouTube API %s answered %s", endpoint, resp.status_code)
        raise VideoError("YouTube search is unavailable right now (its daily limit may be reached).")
    return resp.json()


def _when(iso):
    try:
        return datetime.fromisoformat((iso or "").replace("Z", "+00:00"))
    except ValueError:
        return None


def _best_thumb(snippet, video_id=""):
    thumbs = snippet.get("thumbnails") or {}
    for size in ("medium", "high", "default"):
        if size in thumbs:
            return thumbs[size]["url"]
    return thumb(video_id) if video_id else ""


def _avatars(channel_ids):
    """Channel id -> picture URL ("" when there is none), each channel looked up once a day."""
    ids = [c for c in set(channel_ids) if CHANNEL_ID_RE.match(c or "")]
    found, missing = {}, []
    for cid in ids:
        hit = cache.get(_key("avatar", cid))
        if hit is None:
            missing.append(cid)
        else:
            found[cid] = hit
    if missing:
        try:
            data = _api("channels", part="snippet", id=",".join(missing[:50]), maxResults=50)
            for ch in data.get("items", []):
                found[ch["id"]] = _best_thumb(ch.get("snippet", {}))
        except VideoError:
            return found
        for cid in missing[:50]:
            found.setdefault(cid, "")
            cache.set(_key("avatar", cid), found[cid], AVATAR_TTL)
    return found


def youtube_search(query, limit=24):
    """All of YouTube (embeddable videos only), one card per video, each with its channel's picture."""
    k = _key("search", query.lower(), limit)
    hit = cache.get(k)
    if hit is not None:
        return hit
    data = _api("search", part="snippet", type="video", q=query, maxResults=limit, safeSearch="strict",
                videoEmbeddable="true", relevanceLanguage="en")
    videos, seen = [], set()
    for item in data.get("items", []):
        vid, sn = (item.get("id") or {}).get("videoId", ""), item.get("snippet", {})
        if valid_id(vid) and vid not in seen:
            seen.add(vid)
            videos.append(_card(vid, sn.get("title", ""), sn.get("channelTitle", ""), channel_id=sn.get("channelId", ""),
                                published=_when(sn.get("publishedAt")), thumbnail=_best_thumb(sn, vid)))
    avatars = _avatars([v["channel_id"] for v in videos])
    for v in videos:
        v["channel_avatar"] = avatars.get(v["channel_id"], "")
    cache.set(k, videos, SEARCH_TTL)
    return videos


# --------------------------------------------------------------------------- search without a YouTube key

_LINK = re.compile(r"(?:youtube\.com/(?:watch\?v=|embed/|shorts/|live/)|youtu\.be/)([A-Za-z0-9_-]{11})")
SUGGEST_SCHEMA = {"type": "ARRAY", "items": {"type": "OBJECT", "required": ["url", "title"], "properties": {
    "url": {"type": "STRING"}, "title": {"type": "STRING"}, "channel": {"type": "STRING"}}}}


def can_suggest():
    return bool(getattr(settings, "GEMINI_API_KEY", ""))


def _ask_model(model, body):
    """One model's suggestions: [(video_id, claimed_title), ...]. Raises on any failure."""
    resp = _session.post(GEMINI.format(model=model), json=body, headers={"x-goog-api-key": settings.GEMINI_API_KEY},
                         timeout=(4, SUGGEST_BUDGET))
    if resp.status_code != 200:
        log.warning("video suggestions from %s: HTTP %s", model, resp.status_code)
        raise VideoError(f"HTTP {resp.status_code}")
    parts = ((resp.json().get("candidates") or [{}])[0].get("content") or {}).get("parts") or []
    text = "".join(part.get("text", "") for part in parts if not part.get("thought"))
    try:
        rows = json.loads(text)
    except ValueError:                                       # not JSON after all: pick the links out of the text
        rows = [{"url": f"https://youtu.be/{vid}", "title": ""} for vid in _LINK.findall(text)]
    found = []
    for row in rows if isinstance(rows, list) else []:
        m = _LINK.search(str(row.get("url", ""))) if isinstance(row, dict) else None
        if m and valid_id(m.group(1)):
            found.append((m.group(1), str(row.get("title", ""))[:200]))
    return found


def _suggest(query):
    """Ask both models at once for well-known lessons on the query: [(video_id, claimed_title), ...].
    The better model's picks come first and the fast model's fill in (it is asked for more, as fewer of its picks
    pass the checks). We wait SUGGEST_WAIT seconds for both; after that whatever has arrived is used (and if
    nothing has, the first answer up to SUGGEST_BUDGET)."""
    def body(count):
        prompt = (f"A student wants to learn about: {query}\n"
                  f"List {count} real, popular YouTube videos that teach this well, preferring established educational "
                  "channels (for example Khan Academy, CrashCourse, TED-Ed, 3Blue1Brown, The Organic Chemistry Tutor, "
                  "freeCodeCamp, MIT OpenCourseWare, Kurzgesagt, Professor Dave Explains, Amoeba Sisters, OverSimplified). "
                  "Give each video's full https://www.youtube.com/watch?v= link exactly, its exact title and its channel. "
                  "Only list videos you are confident exist. Nothing unsuitable for school students.")
        return {"contents": [{"role": "user", "parts": [{"text": prompt}]}],
                "generationConfig": {"temperature": 0.2, "responseMimeType": "application/json",
                                     "responseSchema": SUGGEST_SCHEMA, "thinkingConfig": {"thinkingLevel": "minimal"}}}
    futures = [_POOL.submit(_ask_model, model, body(count)) for model, count in SUGGEST_MODELS]
    wait(futures, timeout=SUGGEST_WAIT)
    if not any(f.done() and not f.exception() for f in futures):
        wait(futures, timeout=SUGGEST_BUDGET - SUGGEST_WAIT, return_when=FIRST_COMPLETED)
    found, seen = [], set()
    for fut in futures:                                       # in model order: the better model's picks first
        if fut.done() and not fut.exception():
            for vid, title in fut.result():
                if vid not in seen:
                    seen.add(vid)
                    found.append((vid, title))
    return found


def _fits(query, claimed, real):
    """A real video is kept only if it is about the search: its title shares a word with the query, or it is
    clearly the video Gemini meant (most of the claimed title's words). This drops ids that exist but belong
    to some unrelated video."""
    title = _words(real["title"])
    if _words(query) & (title | _words(real["channel"])):
        return True
    said = _words(claimed)
    return bool(said) and len(said & title) >= 0.6 * len(said)


def suggested_search(query, limit=18):
    """Lessons from anywhere on YouTube without a YouTube key. Cached for a day per search."""
    k = _key("suggest", query.lower())
    hit = cache.get(k)
    if hit is not None:
        return hit
    claims = _suggest(query)
    checked = list(_POOL.map(lambda c: (c[1], details(c[0])), claims))
    videos = [real for claimed, real in checked if real and _fits(query, claimed, real)][:limit]
    if claims:                                   # an empty list from a Gemini error is not worth remembering
        cache.set(k, videos, SUGGEST_TTL)
    return videos


# --------------------------------------------------------------------------- what the views ask for

def browse(query="", topic="", allow_suggest=True):
    """What the grid shows: {"videos": [...], "source": "youtube" | "suggested" | "library", "note": str}.
    allow_suggest=False (a student over their search limit) keeps a search to the library."""
    if not query:
        return {"videos": library(topic), "source": "library", "note": ""}
    if has_key():
        try:
            return {"videos": youtube_search(query), "source": "youtube", "note": ""}
        except VideoError as exc:
            return {"videos": library_search(query), "source": "library",
                    "note": f"{exc} Showing matches from the lesson library instead."}
    picked = library_search(query)
    if allow_suggest and can_suggest():
        found = suggested_search(query)
        ids = {v["id"] for v in found}
        merged = found + [v for v in picked if v["id"] not in ids]
        if found:
            return {"videos": merged, "source": "suggested", "note": ""}
        note = "" if picked else "Could not find YouTube lessons for that right now."
        return {"videos": picked, "source": "library", "note": note}
    note = "" if allow_suggest else "You have searched a lot in a short time, so this search used the lesson library only."
    return {"videos": picked, "source": "library", "note": note}


def details(video_id):
    """Title, channel and (with a key) description and views of one video; None when YouTube has no such
    embeddable video. Lessons from the library need no network at all."""
    if not valid_id(video_id):
        return None
    if video_id in _BY_ID:
        return dict(_BY_ID[video_id])
    k = _key("details", video_id)
    hit = cache.get(k)
    if hit is not None:
        return hit or None
    info = None
    if has_key():
        try:
            items = _api("videos", part="snippet,statistics", id=video_id).get("items", [])
            if items:
                sn, st = items[0].get("snippet", {}), items[0].get("statistics", {})
                views = int(st["viewCount"]) if str(st.get("viewCount", "")).isdigit() else None
                info = _card(video_id, sn.get("title", ""), sn.get("channelTitle", ""), channel_id=sn.get("channelId", ""),
                             published=_when(sn.get("publishedAt")), description=sn.get("description", ""),
                             views_label=f"{views:,} views" if views is not None else "")
                info["channel_avatar"] = _avatars([info["channel_id"]]).get(info["channel_id"], "")
        except VideoError:
            info = None
    if info is None:
        info = _oembed(video_id)
    if info is not False:                      # False: YouTube could not be reached; try again next time
        cache.set(k, info or {}, DETAILS_TTL)
    return info or None


def _oembed(video_id):
    """YouTube's public lookup: works without a key. None if the video does not exist or cannot be embedded."""
    try:
        resp = _session.get(OEMBED, params={"url": f"https://www.youtube.com/watch?v={video_id}", "format": "json"}, timeout=TIMEOUT)
    except requests.RequestException:
        return False
    if resp.status_code != 200:
        return None if resp.status_code in (400, 401, 403, 404) else False
    data = resp.json()
    return _card(video_id, data.get("title", ""), data.get("author_name", ""), channel_url=data.get("author_url", ""))


def related(video, limit=12):
    """Videos to watch next: from YouTube search on the title (with a key), else lessons on the same topic."""
    if has_key():
        try:
            found = [v for v in youtube_search(video["title"], limit=limit + 1) if v["id"] != video["id"]]
            if found:
                return found[:limit]
        except VideoError:
            pass
    same = [v for v in LIBRARY if v["topic"] == video.get("topic") and v["id"] != video["id"]]
    if len(same) < limit:
        same += [v for v in library_search(video["title"], limit=limit) if v["id"] != video["id"] and v not in same]
    if len(same) < limit:
        same += [v for v in library() if v["id"] != video["id"] and v not in same]
    return same[:limit]
