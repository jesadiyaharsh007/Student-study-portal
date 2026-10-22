"""
High-performance YouTube video search and streaming service for Student Study Portal.
Provides fast, reliable Innertube API searches, connection pooling, multi-tier fallbacks,
in-memory LRU caching, and ad-free privacy-enhanced streaming metadata.
"""

import json
import logging
import re
import urllib.parse
from collections import OrderedDict
from concurrent.futures import ThreadPoolExecutor
from typing import Dict, List, Optional, Tuple

import requests

logger = logging.getLogger(__name__)

# Connection-pooled session with browser-grade headers
_HTTP_SESSION = requests.Session()
_HTTP_SESSION.mount("https://", requests.adapters.HTTPAdapter(pool_connections=8, pool_maxsize=32))
_HTTP_SESSION.headers.update({
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "en-US,en;q=0.9",
    "Accept": "application/json, text/plain, */*",
})

# In-memory LRU cache: query -> list of video dicts
_CACHE_CAPACITY = 256
_VIDEO_CACHE: OrderedDict[str, List[Dict]] = OrderedDict()

# Curated academic topics for fast discovery
TOPICS: List[Tuple[str, str, str]] = [
    ("calculus", "Calculus", "calculus explained"),
    ("physics", "Physics", "physics fundamentals lecture"),
    ("computer-science", "Computer Science", "computer science principles"),
    ("chemistry", "Chemistry", "general chemistry study guide"),
    ("biology", "Biology", "biology cell structure lecture"),
    ("world-history", "World History", "world history crash course"),
    ("linear-algebra", "Linear Algebra", "linear algebra 3blue1brown"),
    ("economics", "Economics", "microeconomics essentials"),
    ("psychology", "Psychology", "introduction to psychology lecture"),
]

# High-impact curated starter lectures for cold start
FEATURED_VIDEOS: List[Dict] = [
    {
        "id": "WUvTyaaNkzM",
        "title": "The Essence of Calculus — Chapter 1",
        "channel": "3Blue1Brown",
        "duration": "17:05",
        "views": "11.8M views",
        "published": "Visual Masterclass",
        "thumbnail": "https://i.ytimg.com/vi/WUvTyaaNkzM/mqdefault.jpg",
        "description": "What might it feel like to invent calculus? An intuitive, visual geometric foundation for derivatives and limits.",
        "link": "https://www.youtube.com/watch?v=WUvTyaaNkzM",
    },
    {
        "id": "8mAITcNt710",
        "title": "Harvard CS50 — Full Computer Science University Course",
        "channel": "freeCodeCamp.org",
        "duration": "24:41:20",
        "views": "7.9M views",
        "published": "Complete Course",
        "thumbnail": "https://i.ytimg.com/vi/8mAITcNt710/mqdefault.jpg",
        "description": "An introduction to the intellectual enterprises of computer science and the art of programming with David J. Malan.",
        "link": "https://www.youtube.com/watch?v=8mAITcNt710",
    },
    {
        "id": "b1t41Q3xRM8",
        "title": "Physics - Basic Introduction",
        "channel": "The Organic Chemistry Tutor",
        "duration": "2:23:10",
        "views": "3.8M views",
        "published": "Physics Foundations",
        "thumbnail": "https://i.ytimg.com/vi/b1t41Q3xRM8/mqdefault.jpg",
        "description": "Comprehensive introductory physics tutorial covering displacement, velocity, acceleration, Newton's laws, vectors, work, and energy.",
        "link": "https://www.youtube.com/watch?v=b1t41Q3xRM8",
    },
    {
        "id": "094y1Z2wpJg",
        "title": "The Simplest Math Problem No One Can Solve (Collatz Conjecture)",
        "channel": "Veritasium",
        "duration": "22:09",
        "views": "42M views",
        "published": "Math & Logic",
        "thumbnail": "https://i.ytimg.com/vi/094y1Z2wpJg/mqdefault.jpg",
        "description": "David Eisenbud investigates the famous 3n + 1 problem that has puzzled mathematicians for nearly a century.",
        "link": "https://www.youtube.com/watch?v=094y1Z2wpJg",
    },
    {
        "id": "FSyAehMdpyI",
        "title": "The Nucleus: Crash Course Chemistry #1",
        "channel": "CrashCourse",
        "duration": "10:12",
        "views": "5.6M views",
        "published": "Chemistry Basics",
        "thumbnail": "https://i.ytimg.com/vi/FSyAehMdpyI/mqdefault.jpg",
        "description": "Hank Green discusses atoms, elements, the nucleus, protons, neutrons, electrons, and isotopes.",
        "link": "https://www.youtube.com/watch?v=FSyAehMdpyI",
    },
    {
        "id": "zQGOcOUBi6s",
        "title": "The Immune System Explained — Bacterial Infection",
        "channel": "Kurzgesagt – In a Nutshell",
        "duration": "6:48",
        "views": "28.5M views",
        "published": "Cell Biology",
        "thumbnail": "https://i.ytimg.com/vi/zQGOcOUBi6s/mqdefault.jpg",
        "description": "A stunning visual breakdown of macro-phages, neutrophils, and dendritic cells defending the body.",
        "link": "https://www.youtube.com/watch?v=zQGOcOUBi6s",
    },
    {
        "id": "Yocja_N5s1I",
        "title": "The Agricultural Revolution: Crash Course World History #1",
        "channel": "CrashCourse",
        "duration": "11:11",
        "views": "15.2M views",
        "published": "World History",
        "thumbnail": "https://i.ytimg.com/vi/Yocja_N5s1I/mqdefault.jpg",
        "description": "John Green investigates human history from hunter-gatherers to settled agriculture and early civilization.",
        "link": "https://www.youtube.com/watch?v=Yocja_N5s1I",
    },
    {
        "id": "fNk_zzaMoSs",
        "title": "Linear Combinations, Span, and Basis Vectors",
        "channel": "3Blue1Brown",
        "duration": "12:12",
        "views": "5.6M views",
        "published": "Linear Algebra",
        "thumbnail": "https://i.ytimg.com/vi/fNk_zzaMoSs/mqdefault.jpg",
        "description": "Essence of linear algebra: what span, linear independence, and basis vectors look like geometrically.",
        "link": "https://www.youtube.com/watch?v=fNk_zzaMoSs",
    },
]


def build_embed_url(video_id: str) -> str:
    """Returns privacy-enhanced, ad-free YouTube embed URL."""
    clean_id = urllib.parse.quote(video_id.strip())
    return (
        f"https://www.youtube-nocookie.com/embed/{clean_id}"
        f"?autoplay=1&rel=0&modestbranding=1&iv_load_policy=3&playsinline=1"
    )


# Pre-populate embed_url on all featured videos
for _fv in FEATURED_VIDEOS:
    if "embed_url" not in _fv:
        _fv["embed_url"] = build_embed_url(_fv["id"])


def search_videos(query: str, max_results: int = 12) -> Tuple[List[Dict], Optional[str]]:
    """
    Searches YouTube for educational videos using multi-tier fallback:
    1. Memory LRU cache
    2. Official YouTube Innertube API (JSON POST, ~0.8s)
    3. Direct HTML search scraper with browser headers
    4. Built-in fallback
    """
    clean_q = (query or "").strip()
    if not clean_q:
        return home_feed(max_results), None

    cache_key = clean_q.lower()
    if cache_key in _VIDEO_CACHE:
        _VIDEO_CACHE.move_to_end(cache_key)
        return _VIDEO_CACHE[cache_key], None

    # Tier 1: YouTube Innertube API (JSON direct)
    items = _search_innertube(clean_q, max_results=max_results)
    if items:
        _cache_results(cache_key, items)
        return items, None

    # Tier 2: Direct HTML scrape with connection pooling
    items = _search_html_scrape(clean_q, max_results=max_results)
    if items:
        _cache_results(cache_key, items)
        return items, None

    # Tier 3: youtube_search package fallback
    items = _search_youtube_search_pkg(clean_q, max_results=max_results)
    if items:
        _cache_results(cache_key, items)
        return items, None

    # If all tiers fail due to network outage, check if matches any featured videos
    fallback_matches = [
        v for v in FEATURED_VIDEOS
        if clean_q.lower() in v["title"].lower() or clean_q.lower() in v["channel"].lower()
    ]
    if fallback_matches:
        return fallback_matches, None

    return [], "Unable to fetch video lessons. Please check your connection and try again."


def _cache_results(key: str, results: List[Dict]) -> None:
    if len(_VIDEO_CACHE) >= _CACHE_CAPACITY:
        _VIDEO_CACHE.popitem(last=False)
    _VIDEO_CACHE[key] = results


def _search_innertube(query: str, max_results: int = 12) -> List[Dict]:
    """Queries YouTube's internal Innertube JSON search endpoint."""
    try:
        url = "https://www.youtube.com/youtubei/v1/search"
        payload = {
            "context": {
                "client": {
                    "clientName": "WEB",
                    "clientVersion": "2.20240401.01.00",
                    "hl": "en",
                    "gl": "US",
                }
            },
            "query": query,
        }
        resp = _HTTP_SESSION.post(url, json=payload, timeout=3.8)
        if resp.status_code != 200:
            return []

        data = resp.json()
        contents = (
            data.get("contents", {})
            .get("twoColumnSearchResultsRenderer", {})
            .get("primaryContents", {})
            .get("sectionListRenderer", {})
            .get("contents", [])
        )

        results: List[Dict] = []
        for sec in contents:
            item_sec = sec.get("itemSectionRenderer", {}).get("contents", [])
            for it in item_sec:
                if "videoRenderer" not in it:
                    continue
                vr = it["videoRenderer"]
                vid_id = vr.get("videoId")
                if not vid_id:
                    continue

                title = "".join(r.get("text", "") for r in vr.get("title", {}).get("runs", []))
                owner_runs = vr.get("ownerText", {}).get("runs", []) or vr.get("longBylineText", {}).get("runs", [])
                channel = "".join(r.get("text", "") for r in owner_runs)
                cid = next((r.get("navigationEndpoint", {}).get("browseEndpoint", {}).get("browseId", "")
                            for r in owner_runs if r.get("navigationEndpoint")), "")
                pics = vr.get("channelThumbnailSupportedRenderers", {}).get("channelThumbnailWithLinkRenderer", {}) \
                    .get("thumbnail", {}).get("thumbnails", [])
                avatar = pics[-1]["url"] if pics else ""
                duration = vr.get("lengthText", {}).get("simpleText", "")
                views = vr.get("viewCountText", {}).get("simpleText", "")
                published = vr.get("publishedTimeText", {}).get("simpleText", "")

                snippets = vr.get("detailedMetadataSnippets", [{}])
                desc = (
                    "".join(r.get("text", "") for r in snippets[0].get("snippetText", {}).get("runs", []))
                    if snippets and "snippetText" in snippets[0]
                    else ""
                )

                thumbs = vr.get("thumbnail", {}).get("thumbnails", [])
                thumb = f"https://i.ytimg.com/vi/{vid_id}/mqdefault.jpg"

                results.append({
                    "id": vid_id,
                    "title": title or "Video Lesson",
                    "channel": channel or "Educational Channel",
                    "channel_id": cid if _CHANNEL_ID_RE.match(cid or "") else "",
                    "avatar": avatar,
                    "duration": duration,
                    "views": views,
                    "published": published,
                    "thumbnail": thumb,
                    "description": desc[:180],
                    "link": f"https://www.youtube.com/watch?v={vid_id}",
                    "embed_url": build_embed_url(vid_id),
                })
                if len(results) >= max_results:
                    return results

        return results
    except Exception as exc:
        logger.warning("YouTube Innertube API error: %s", exc)
        return []


def _search_html_scrape(query: str, max_results: int = 12) -> List[Dict]:
    """Fallback: Scrapes results page with browser headers and extracts ytInitialData."""
    try:
        encoded = urllib.parse.quote_plus(query)
        url = f"https://www.youtube.com/results?search_query={encoded}"
        resp = _HTTP_SESSION.get(url, timeout=3.5)
        if resp.status_code != 200:
            return []

        text = resp.text
        if "ytInitialData" not in text:
            return []

        start = text.index("ytInitialData") + len("ytInitialData") + 3
        end = text.index("};", start) + 1
        data = json.loads(text[start:end])

        contents = (
            data.get("contents", {})
            .get("twoColumnSearchResultsRenderer", {})
            .get("primaryContents", {})
            .get("sectionListRenderer", {})
            .get("contents", [])
        )

        results: List[Dict] = []
        for sec in contents:
            item_sec = sec.get("itemSectionRenderer", {}).get("contents", [])
            for it in item_sec:
                if "videoRenderer" in it:
                    vr = it["videoRenderer"]
                    vid_id = vr.get("videoId")
                    if not vid_id:
                        continue
                    title = "".join(r.get("text", "") for r in vr.get("title", {}).get("runs", []))
                    channel = "".join(r.get("text", "") for r in vr.get("longBylineText", {}).get("runs", []))
                    duration = vr.get("lengthText", {}).get("simpleText", "")
                    views = vr.get("viewCountText", {}).get("simpleText", "")
                    published = vr.get("publishedTimeText", {}).get("simpleText", "")
                    thumbs = vr.get("thumbnail", {}).get("thumbnails", [])
                    thumb = f"https://i.ytimg.com/vi/{vid_id}/mqdefault.jpg"

                    results.append({
                        "id": vid_id,
                        "title": title or "Video Lesson",
                        "channel": channel or "Educational Channel",
                        "duration": duration,
                        "views": views,
                        "published": published,
                        "thumbnail": thumb,
                        "description": "",
                        "link": f"https://www.youtube.com/watch?v={vid_id}",
                        "embed_url": build_embed_url(vid_id),
                    })
                    if len(results) >= max_results:
                        return results
        return results
    except Exception as exc:
        logger.warning("YouTube HTML scraper error: %s", exc)
        return []


def _search_youtube_search_pkg(query: str, max_results: int = 12) -> List[Dict]:
    """Fallback: uses youtube_search library if available."""
    try:
        from youtube_search import YoutubeSearch
        found = YoutubeSearch(query, max_results=max_results).to_dict()
        results: List[Dict] = []
        for v in found:
            vid_id = v.get("id")
            if not vid_id and v.get("url_suffix"):
                match = re.search(r"v=([a-zA-Z0-9_-]+)", v["url_suffix"])
                if match:
                    vid_id = match.group(1)
            if not vid_id:
                continue

            results.append({
                "id": vid_id,
                "title": v.get("title", "Video Lesson"),
                "channel": v.get("channel", "Educational Channel"),
                "duration": v.get("duration", ""),
                "views": v.get("views", ""),
                "published": v.get("publish_time", ""),
                "thumbnail": f"https://i.ytimg.com/vi/{vid_id}/mqdefault.jpg",
                "description": (v.get("long_desc") or "")[:180],
                "link": f"https://www.youtube.com{v.get('url_suffix', f'/watch?v={vid_id}')}",
                "embed_url": build_embed_url(vid_id),
            })
        return results
    except Exception as exc:
        logger.warning("youtube_search pkg error: %s", exc)
        return []


# --------------------------------------------------------------------------- watch page data

_DETAIL_CACHE: "OrderedDict[str, Dict]" = OrderedDict()
_CHANNEL_CACHE: "OrderedDict[str, Dict]" = OrderedDict()
_CHANNEL_ID_RE = re.compile(r"^UC[\w-]{22}$")
_CHANNEL_VIDEOS_TAB = "EgZ2aWRlb3PyBgQKAjoA"      # YouTube's "Videos" tab, newest first
_ID_RE = re.compile(r"^[A-Za-z0-9_-]{11}$")
_INNERTUBE_CONTEXT = {"client": {"clientName": "WEB", "clientVersion": "2.20240401.01.00", "hl": "en", "gl": "US"}}


def valid_id(video_id: str) -> bool:
    return bool(_ID_RE.match(video_id or ""))


def thumb(video_id: str) -> str:
    """Clean 16:9 thumbnail (the hq variants carry black bars)."""
    return f"https://i.ytimg.com/vi/{video_id}/mqdefault.jpg"


def _text(node) -> str:
    if not node:
        return ""
    if isinstance(node, str):
        return node
    if "simpleText" in node:
        return node["simpleText"]
    return "".join(r.get("text", "") for r in node.get("runs", []))


def _parse_lockup(item: Dict) -> Optional[Dict]:
    """One up-next entry from YouTube's lockupViewModel."""
    lv = item.get("lockupViewModel")
    if not lv or lv.get("contentType") != "LOCKUP_CONTENT_TYPE_VIDEO":
        return None
    vid = lv.get("contentId")
    if not valid_id(vid):
        return None
    meta = lv.get("metadata", {}).get("lockupMetadataViewModel", {})
    rows = meta.get("metadata", {}).get("contentMetadataViewModel", {}).get("metadataRows", [])
    parts = [[p.get("text", {}).get("content", "") for p in r.get("metadataParts", [])] for r in rows]
    channel = parts[0][0] if parts and parts[0] else ""
    views = parts[1][0] if len(parts) > 1 and parts[1] else ""
    published = parts[1][1] if len(parts) > 1 and len(parts[1]) > 1 else ""
    duration = ""
    for ov in lv.get("contentImage", {}).get("thumbnailViewModel", {}).get("overlays", []):
        for b in ov.get("thumbnailBottomOverlayViewModel", {}).get("badges", []):
            duration = b.get("thumbnailBadgeViewModel", {}).get("text", "") or duration
    return {
        "id": vid, "title": meta.get("title", {}).get("content", "Video"), "channel": channel,
        "views": (views + " views") if views and "view" not in views else views, "published": published,
        "duration": duration, "thumbnail": thumb(vid),
    }


def _parse_compact(item: Dict) -> Optional[Dict]:
    cv = item.get("compactVideoRenderer")
    if not cv or not valid_id(cv.get("videoId", "")):
        return None
    vid = cv["videoId"]
    return {
        "id": vid, "title": _text(cv.get("title")), "channel": _text(cv.get("longBylineText")),
        "views": _text(cv.get("viewCountText")), "published": _text(cv.get("publishedTimeText")),
        "duration": _text(cv.get("lengthText")), "thumbnail": thumb(vid),
    }


def video_details(video_id: str, header_only: bool = False) -> Optional[Dict]:
    """Title, channel, views, date, description and up-next for one video (cached).
    header_only skips the up-next lists so the channel and subscriber count can appear straight away."""
    if not valid_id(video_id):
        return None
    if video_id in _DETAIL_CACHE:
        _DETAIL_CACHE.move_to_end(video_id)
        return _DETAIL_CACHE[video_id]

    info: Dict = {"id": video_id, "title": "", "channel": "", "channel_id": "", "avatar": "", "subscribers": "",
                  "views": "", "published": "", "description": "", "related": [],
                  "link": f"https://www.youtube.com/watch?v={video_id}"}
    try:
        resp = _HTTP_SESSION.post("https://www.youtube.com/youtubei/v1/next",
                                  json={"context": _INNERTUBE_CONTEXT, "videoId": video_id}, timeout=6)
        if resp.status_code == 200:
            two = resp.json().get("contents", {}).get("twoColumnWatchNextResults", {})
            for block in two.get("results", {}).get("results", {}).get("contents", []):
                pri = block.get("videoPrimaryInfoRenderer")
                if pri:
                    info["title"] = _text(pri.get("title"))
                    info["views"] = _text(pri.get("viewCount", {}).get("videoViewCountRenderer", {}).get("viewCount"))
                    info["published"] = _text(pri.get("dateText"))
                sec = block.get("videoSecondaryInfoRenderer")
                if sec:
                    owner = sec.get("owner", {}).get("videoOwnerRenderer", {})
                    info["channel"] = _text(owner.get("title"))
                    cid = owner.get("navigationEndpoint", {}).get("browseEndpoint", {}).get("browseId", "")
                    info["channel_id"] = cid if _CHANNEL_ID_RE.match(cid or "") else ""
                    avatars = owner.get("thumbnail", {}).get("thumbnails", [])
                    info["avatar"] = avatars[-1]["url"] if avatars else ""
                    info["subscribers"] = _text(owner.get("subscriberCountText"))
                    info["description"] = sec.get("attributedDescription", {}).get("content", "")[:2500]
            for item in two.get("secondaryResults", {}).get("secondaryResults", {}).get("results", []):
                rel = _parse_lockup(item) or _parse_compact(item)
                if rel and rel["id"] != video_id:
                    info["related"].append(rel)
    except Exception as exc:
        logger.warning("YouTube watch data error: %s", exc)

    if not info["title"]:
        # oEmbed is lighter and tells us when a video is gone
        try:
            r = _HTTP_SESSION.get("https://www.youtube.com/oembed", params={"url": info["link"], "format": "json"}, timeout=4)
            if r.status_code != 200:
                return None
            data = r.json()
            info["title"], info["channel"] = data.get("title", "Video"), data.get("author_name", "")
        except Exception:
            return None
    if not info["channel"]:
        try:
            r = _HTTP_SESSION.get("https://www.youtube.com/oembed", params={"url": info["link"], "format": "json"}, timeout=4)
            if r.status_code == 200:
                info["channel"] = r.json().get("author_name", "")
        except Exception:
            pass
    # YouTube sends about twenty suggestions; top the list up so the sidebar never runs out before the page does
    if header_only:
        return info
    if len(info["related"]) < 32:
        seen = {video_id} | {v["id"] for v in info["related"]}
        for query in (info["title"], info["channel"]):
            if not query or len(info["related"]) >= 36:
                continue
            items, _ = search_videos(query, max_results=24)
            for v in items:
                if v["id"] not in seen:
                    seen.add(v["id"])
                    info["related"].append(v)

    # Give every suggestion its channel too, so the cards show the picture, subscribers and link straight away.
    if info["related"]:
        chans = video_channels([v["id"] for v in info["related"][:24]])
        for v in info["related"]:
            c = chans.get(v["id"])
            if c:
                v.update(channel_id=c["channel_id"], avatar=c["avatar"], subscribers=c["subscribers"])

    if len(_DETAIL_CACHE) >= 128:
        _DETAIL_CACHE.popitem(last=False)
    _DETAIL_CACHE[video_id] = info
    return info


def _channel_lockup(item: Dict) -> Optional[Dict]:
    """One upload on a channel page. Its metadata rows come in a different order from search results, so match by text."""
    v = _parse_lockup(item)
    if not v:
        return None
    rows = item.get("lockupViewModel", {}).get("metadata", {}).get("lockupMetadataViewModel", {}) \
        .get("metadata", {}).get("contentMetadataViewModel", {}).get("metadataRows", [])
    texts = [p.get("text", {}).get("content", "") for r in rows for p in r.get("metadataParts", [])]
    v["channel"] = ""                                   # every upload here is from this channel
    v["views"] = next((t for t in texts if "view" in t.lower()), "")
    v["published"] = next((t for t in texts if "ago" in t.lower()), "")
    return v


def channel_page(channel_id: str) -> Optional[Dict]:
    """A channel's name, picture, subscriber count and its uploads (newest first, first page only; cached)."""
    if not _CHANNEL_ID_RE.match(channel_id or ""):
        return None
    if channel_id in _CHANNEL_CACHE:
        _CHANNEL_CACHE.move_to_end(channel_id)
        return _CHANNEL_CACHE[channel_id]
    try:
        resp = _HTTP_SESSION.post("https://www.youtube.com/youtubei/v1/browse",
                                  json={"context": _INNERTUBE_CONTEXT, "browseId": channel_id, "params": _CHANNEL_VIDEOS_TAB},
                                  timeout=8)
        if resp.status_code != 200:
            return None
        data = resp.json()
    except Exception as exc:
        logger.warning("YouTube channel data error: %s", exc)
        return None

    header_wrap = data.get("header", {}).get("pageHeaderRenderer", {})
    header = header_wrap.get("content", {}).get("pageHeaderViewModel", {})
    raw = json.dumps(header, ensure_ascii=False)
    name = header_wrap.get("pageTitle") or _text(header.get("title", {}).get("dynamicTextViewModel", {}).get("text"))
    subs = re.search(r'"content": "([^"]*subscriber[^"]*)"', raw)
    # Avatars are the square "=sNN-c-k" images. The header also holds a banner, which must not be picked.
    sized = [(int(m.group(2)), m.group(1)) for m in re.finditer(r'(https://yt3\.[^"\s]*?=s(\d+)-c-k[^"\s]*)', raw)]
    avatars = [url for _, url in sorted(sized)]

    videos_out: List[Dict] = []
    for tab in data.get("contents", {}).get("twoColumnBrowseResultsRenderer", {}).get("tabs", []):
        tr = tab.get("tabRenderer")
        if not (tr and tr.get("selected")):
            continue
        for item in tr.get("content", {}).get("richGridRenderer", {}).get("contents", []):
            v = _channel_lockup(item.get("richItemRenderer", {}).get("content", {}))
            if v:
                videos_out.append(v)

    info = {"id": channel_id, "name": name or "Channel", "subscribers": subs.group(1) if subs else "",
            "avatar": avatars[-1] if avatars else "", "videos": videos_out}
    if len(_CHANNEL_CACHE) >= 64:
        _CHANNEL_CACHE.popitem(last=False)
    _CHANNEL_CACHE[channel_id] = info
    return info


def channel_summaries(channel_ids) -> Dict[str, Dict]:
    """Subscriber count and picture for several channels at once, for the search results."""
    ids = [c for c in dict.fromkeys(channel_ids or []) if _CHANNEL_ID_RE.match(c or "")][:24]
    out: Dict[str, Dict] = {}
    with ThreadPoolExecutor(max_workers=8) as pool:
        for cid, ch in zip(ids, pool.map(channel_page, ids)):
            if ch:
                out[cid] = {"subscribers": ch["subscribers"], "avatar": ch["avatar"], "name": ch["name"]}
    return out


_PLAYLIST_ID_RE = re.compile(r"^(PL|UU|OL|LL|RD)[\w-]{10,64}$")
_PLAYLIST_SEARCH_PARAM = "EgIQAw=="                   # YouTube's "Playlist" filter
_PLAYLISTS: "OrderedDict[str, List[Dict]]" = OrderedDict()


def _walk_lockups(node, found):
    if isinstance(node, dict):
        if "lockupViewModel" in node:
            found.append(node["lockupViewModel"])
        for v in node.values():
            _walk_lockups(v, found)
    elif isinstance(node, list):
        for x in node:
            _walk_lockups(x, found)
    return found


def _parse_playlist(lv: Dict) -> Optional[Dict]:
    """A playlist from a search result (contentType LOCKUP_CONTENT_TYPE_PLAYLIST)."""
    if lv.get("contentType") != "LOCKUP_CONTENT_TYPE_PLAYLIST" or not _PLAYLIST_ID_RE.match(lv.get("contentId", "")):
        return None
    meta = lv.get("metadata", {}).get("lockupMetadataViewModel", {})
    rows = meta.get("metadata", {}).get("contentMetadataViewModel", {}).get("metadataRows", [])
    texts = [p.get("text", {}).get("content", "") for r in rows for p in r.get("metadataParts", [])]
    count = re.search(r"\d[\d,.]*\s*[KkMm]?\s*videos?", json.dumps(lv, ensure_ascii=False))
    sources = lv.get("contentImage", {}).get("collectionThumbnailViewModel", {}).get("primaryThumbnail", {})         .get("thumbnailViewModel", {}).get("image", {}).get("sources", [])
    return {
        "id": lv["contentId"], "title": meta.get("title", {}).get("content", "Playlist"),
        "channel": texts[0] if texts else "", "count": count.group(0) if count else "",
        "thumbnail": sources[-1]["url"] if sources else "",
    }


def playlist_search(query: str) -> List[Dict]:
    """Playlists that match the search, from YouTube's Playlist filter (cached)."""
    q = (query or "").strip()
    if not q:
        return []
    if q in _PLAYLISTS:
        _PLAYLISTS.move_to_end(q)
        return _PLAYLISTS[q]
    out: List[Dict] = []
    try:
        resp = _HTTP_SESSION.post("https://www.youtube.com/youtubei/v1/search",
                                  json={"context": _INNERTUBE_CONTEXT, "query": q, "params": _PLAYLIST_SEARCH_PARAM}, timeout=8)
        if resp.status_code == 200:
            seen = set()
            for lv in _walk_lockups(resp.json(), []):
                pl = _parse_playlist(lv)
                if pl and pl["id"] not in seen:
                    seen.add(pl["id"])
                    out.append(pl)
    except Exception as exc:
        logger.warning("YouTube playlist search error: %s", exc)
    if len(_PLAYLISTS) >= 64:
        _PLAYLISTS.popitem(last=False)
    _PLAYLISTS[q] = out[:8]
    return _PLAYLISTS[q]


_PLAYLIST_PAGES: "OrderedDict[str, Dict]" = OrderedDict()


def playlist_page(playlist_id: str) -> Optional[Dict]:
    """A playlist's title and its videos (first page, cached)."""
    if not _PLAYLIST_ID_RE.match(playlist_id or ""):
        return None
    if playlist_id in _PLAYLIST_PAGES:
        _PLAYLIST_PAGES.move_to_end(playlist_id)
        return _PLAYLIST_PAGES[playlist_id]
    try:
        resp = _HTTP_SESSION.post("https://www.youtube.com/youtubei/v1/browse",
                                  json={"context": _INNERTUBE_CONTEXT, "browseId": "VL" + playlist_id}, timeout=8)
        if resp.status_code != 200:
            return None
        data = resp.json()
    except Exception as exc:
        logger.warning("YouTube playlist data error: %s", exc)
        return None
    title = (data.get("header", {}).get("pageHeaderRenderer", {}).get("pageTitle") or "Playlist")
    vids, seen = [], set()
    for lv in _walk_lockups(data.get("contents", {}), []):
        v = _parse_lockup({"lockupViewModel": lv})
        if v and v["id"] not in seen:
            seen.add(v["id"])
            vids.append(v)
    info = {"id": playlist_id, "title": title, "videos": vids}
    if len(_PLAYLIST_PAGES) >= 32:
        _PLAYLIST_PAGES.popitem(last=False)
    _PLAYLIST_PAGES[playlist_id] = info
    return info


def search_suggestions(query: str) -> List[str]:
    """What YouTube suggests while the student types (the same list the YouTube search box shows)."""
    q = (query or "").strip()[:100]
    if not q:
        return []
    try:
        r = _HTTP_SESSION.get("https://suggestqueries.google.com/complete/search",
                              params={"client": "firefox", "ds": "yt", "q": q}, timeout=4)
        if r.status_code != 200:
            return []
        data = r.json()
        return [str(x) for x in data[1]][:8] if isinstance(data, list) and len(data) > 1 else []
    except Exception as exc:
        logger.warning("YouTube suggestions error: %s", exc)
        return []


def video_channels(video_ids) -> Dict[str, Dict]:
    """Channel, picture and subscribers for a list of videos (the up-next items do not carry the channel ID)."""
    ids = [v for v in dict.fromkeys(video_ids or []) if valid_id(v)][:24]
    out: Dict[str, Dict] = {}
    with ThreadPoolExecutor(max_workers=8) as pool:
        for vid, info in zip(ids, pool.map(lambda v: video_details(v, header_only=True), ids)):
            if info and info.get("channel_id"):
                out[vid] = {"channel_id": info["channel_id"], "channel": info["channel"],
                            "avatar": info["avatar"], "subscribers": info["subscribers"]}
    return out


# --------------------------------------------------------------------------- home feed

_FEED: Dict = {"at": 0.0, "items": []}
_FEED_TTL = 900


def _alive(video_id: str) -> bool:
    try:
        return _HTTP_SESSION.get("https://www.youtube.com/oembed",
                                 params={"url": f"https://www.youtube.com/watch?v={video_id}", "format": "json"}, timeout=3).status_code == 200
    except Exception:
        return True      # network trouble is not proof the video is gone


def home_feed(limit: int = 24) -> List[Dict]:
    """A mixed feed across the subject topics, fetched live (curated list only as an offline fallback)."""
    import time
    from concurrent.futures import ThreadPoolExecutor

    if _FEED["items"] and time.time() - _FEED["at"] < _FEED_TTL:
        return _FEED["items"][:limit]
    queries = [t[2] for t in TOPICS[:8]]
    with ThreadPoolExecutor(max_workers=8) as pool:
        batches = list(pool.map(lambda q: _search_innertube(q, max_results=6), queries))
    seen, feed = set(), []
    for rank in range(6):
        for batch in batches:
            if rank < len(batch) and batch[rank]["id"] not in seen:
                seen.add(batch[rank]["id"])
                feed.append(batch[rank])
    if not feed:
        with ThreadPoolExecutor(max_workers=8) as pool:
            alive = list(pool.map(lambda v: _alive(v["id"]), FEATURED_VIDEOS))
        return [v for v, ok in zip(FEATURED_VIDEOS, alive) if ok][:limit]
    _FEED["at"], _FEED["items"] = time.time(), feed
    return feed[:limit]


# --------------------------------------------------------------------------- transcript (for Lexi)

_TRANSCRIPTS: "OrderedDict[str, str]" = OrderedDict()


def transcript_text(video_id: str, limit: int = 9000) -> str:
    """Caption text of a video (empty when it has none). Uses the youtube-transcript-api library; cached."""
    if not valid_id(video_id):
        return ""
    if video_id in _TRANSCRIPTS:
        _TRANSCRIPTS.move_to_end(video_id)
        return _TRANSCRIPTS[video_id][:limit]
    text = ""
    try:
        from youtube_transcript_api import YouTubeTranscriptApi

        api = YouTubeTranscriptApi()
        try:
            snippets = api.fetch(video_id, languages=["en", "en-US", "en-GB", "hi"])
        except Exception:
            listing = api.list(video_id)
            first = next(iter(listing), None)
            snippets = first.fetch() if first else []
        text = " ".join(s.text.replace("\n", " ") for s in snippets)
        text = re.sub(r"\s+", " ", text).strip()
    except Exception as exc:
        logger.info("No transcript for %s: %s", video_id, exc)
    if len(_TRANSCRIPTS) >= 64:
        _TRANSCRIPTS.popitem(last=False)
    _TRANSCRIPTS[video_id] = text
    return text[:limit]


# --------------------------------------------------------------------------- the player's media (yt-dlp) and captions

_MANIFESTS: "OrderedDict[str, Dict]" = OrderedDict()
_MANIFEST_TTL = 1500        # googlevideo links last hours; refresh well before that
_MUXED: "OrderedDict[str, Dict]" = OrderedDict()
_BROWSER_UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) "
               "Chrome/124.0.0.0 Safari/537.36")


class StreamUnavailable(Exception):
    pass


def _ytdlp_info(video_id: str, client: Optional[str] = None) -> Dict:
    try:
        import yt_dlp
    except ImportError as exc:
        raise StreamUnavailable("yt-dlp is not installed") from exc

    import shutil
    import os
    node_path = shutil.which("node")
    base_opts = {
        "quiet": True,
        "no_warnings": True,
        "skip_download": True,
        "noplaylist": True,
        "socket_timeout": 12,
        "extractor_args": {
            "youtube": {
                "player_client": ["visionos", "tv_samsung"],
            }
        },
    }
    if node_path:
        base_opts["js_runtimes"] = {"node": {}}

    # Load Netscape cookies if available to prevent YouTube bot verification and timeouts
    cookie_paths = [
        os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "yt_cookies.txt")),
        os.path.abspath(os.path.join(os.path.dirname(__file__), "yt_cookies.txt")),
        os.path.abspath("yt_cookies.txt"),
        os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "media_service", "yt_cookies.txt")),
    ]
    for cp in cookie_paths:
        if os.path.exists(cp) and os.path.getsize(cp) > 10:
            base_opts["cookiefile"] = cp
            break

    # 1. Try visionos / tv_samsung extraction first (gets full 1080p, 720p, 480p, 360p, 240p, 144p DASH sets without JS requirement)
    if not client:
        try:
            with yt_dlp.YoutubeDL(base_opts) as ydl:
                res = ydl.extract_info(f"https://www.youtube.com/watch?v={video_id}", download=False)
                if res and res.get("formats"):
                    has_dash = any(f.get("ext") == "mp4" and (f.get("vcodec") or "").startswith("avc1") and f.get("acodec") == "none" for f in res.get("formats", []))
                    if has_dash:
                        return res
                    best_res = res
                else:
                    best_res = None
        except Exception:
            best_res = None
    else:
        best_res = None

    # 2. Try specific client fallbacks in fast order
    clients_to_try = [client] if client else ["visionos", "tv_samsung", "android"]
    last_exc = None
    for c in clients_to_try:
        opts = dict(base_opts)
        opts["extractor_args"] = {
            "youtube": {
                "player_client": [c],
                "player_skip": ["webpage", "configs"],
            }
        }
        try:
            with yt_dlp.YoutubeDL(opts) as ydl:
                res = ydl.extract_info(f"https://www.youtube.com/watch?v={video_id}", download=False)
                if res and res.get("formats"):
                    has_hd = any((f.get("height") or 0) >= 720 for f in res.get("formats", []))
                    if has_hd or not best_res:
                        return res
        except Exception as exc:
            last_exc = exc
            err_str = str(exc)
            if "Sign in to confirm" in err_str:
                break
            continue

    if best_res:
        return best_res
    raise StreamUnavailable(str(last_exc or "Stream unavailable")[:200])


def stream_manifest(video_id: str, refresh: bool = False) -> Dict:
    """What the player can play for a video: H.264 video qualities plus the best AAC audio,
    or high-quality progressive MP4 streams.
    Returns {"public": manifest-for-the-browser, "urls": {itag: googlevideo-url}} and caches it."""
    import time

    if not valid_id(video_id):
        raise StreamUnavailable("bad id")
    hit = _MANIFESTS.get(video_id)
    if hit and not refresh and time.time() - hit["at"] < _MANIFEST_TTL:
        if len(hit.get("public", {}).get("video", [])) > 1:
            return hit
    info = _ytdlp_info(video_id)
    if info.get("is_live") or info.get("live_status") in ("is_live", "is_upcoming"):
        raise StreamUnavailable("Live streams cannot be played here.")
    by_height: Dict[int, Dict] = {}
    audio = None
    audio_best_score = (-999, -999, -999)
    muxed_by_height: Dict[int, Dict] = {}
    urls: Dict[str, str] = {}
    for f in info.get("formats", []):
        url, itag = f.get("url"), str(f.get("format_id"))
        if not url or f.get("protocol") not in ("https", "http", None) or not re.match(r"^[\w-]+$", itag):
            continue
        vcodec, acodec = f.get("vcodec") or "none", f.get("acodec") or "none"
        h = f.get("height") or 0

        # Separate DASH video (H.264)
        if f.get("ext") == "mp4" and vcodec.startswith("avc1") and acodec == "none":
            entry = {
                "itag": itag, "height": h, "fps": f.get("fps") or 30, "codec": vcodec,
                "bitrate": int((f.get("tbr") or 0) * 1000), "size": f.get("filesize") or f.get("filesize_approx") or 0,
            }
            if h and (h not in by_height or entry["bitrate"] > by_height[h]["bitrate"]):
                by_height[h] = entry
            urls[itag] = url

        # Separate DASH audio (AAC)
        elif f.get("ext") == "m4a" and acodec.startswith("mp4a") and vcodec == "none":
            entry = {
                "itag": itag, "codec": acodec, "bitrate": int((f.get("abr") or f.get("tbr") or 0) * 1000),
                "size": f.get("filesize") or f.get("filesize_approx") or 0,
            }
            lang_pref = f.get("language_preference") if f.get("language_preference") is not None else 0
            is_default = 1 if ("default" in (f.get("format_note") or "").lower() or (f.get("language") or "").startswith("en")) else 0
            score = (lang_pref, is_default, entry["bitrate"])
            if audio is None or score > audio_best_score:
                audio = entry
                audio_best_score = score
            urls[itag] = url

        # Progressive muxed MP4 (e.g. itag 18=360p, 22=720p)
        elif f.get("ext") == "mp4" and (vcodec.startswith("avc1") or vcodec != "none") and acodec != "none":
            h = h or 360
            entry = {
                "itag": itag, "height": h, "fps": f.get("fps") or 30, "codec": vcodec, "acodec": acodec,
                "bitrate": int((f.get("tbr") or 0) * 1000), "size": f.get("filesize") or f.get("filesize_approx") or 0,
                "muxed": True,
            }
            if h not in muxed_by_height or entry["bitrate"] > muxed_by_height[h]["bitrate"]:
                muxed_by_height[h] = entry
            urls[itag] = url

    # Choose DASH if both video and audio are present, otherwise progressive muxed
    if by_height and audio:
        videos_list = sorted(by_height.values(), key=lambda v: v["height"])
        keep = {v["itag"] for v in videos_list} | {audio["itag"]}
        is_muxed = False
        best_muxed = None
    elif muxed_by_height:
        videos_list = sorted(muxed_by_height.values(), key=lambda v: v["height"])
        keep = {v["itag"] for v in videos_list}
        is_muxed = True
        best_muxed = videos_list[-1]
        audio = {"itag": best_muxed["itag"], "codec": best_muxed.get("acodec", "mp4a"), "bitrate": 128000, "size": 0}
    else:
        raise StreamUnavailable("No playable formats were found for this video.")

    data = {
        "at": time.time(),
        "public": {
            "id": video_id,
            "title": info.get("title") or "",
            "channel": info.get("channel") or info.get("uploader") or "",
            "duration": info.get("duration") or 0,
            "video": videos_list,
            "audio": audio,
            "is_muxed": is_muxed,
            "progressive_itag": best_muxed["itag"] if best_muxed else None,
        },
        "urls": {k: v for k, v in urls.items() if k in keep},
    }
    if len(_MANIFESTS) >= 48:
        _MANIFESTS.popitem(last=False)
    _MANIFESTS[video_id] = data
    return data


def media_url(video_id: str, itag: str, refresh: bool = False) -> str:
    data = stream_manifest(video_id, refresh=refresh)
    url = data["urls"].get(str(itag))
    if not url:
        raise StreamUnavailable("Unknown stream.")
    return url


def muxed_stream(video_id: str) -> Optional[Dict]:
    """One MP4 with picture and sound together (360p), for the Download menu."""
    import time

    hit = _MUXED.get(video_id)
    if hit and time.time() - hit["at"] < _MANIFEST_TTL:
        return hit
    for client in ("android", "android_vr"):
        try:
            info = _ytdlp_info(video_id, client)
        except StreamUnavailable:
            continue
        for f in sorted(info.get("formats", []), key=lambda x: x.get("height") or 0, reverse=True):
            if f.get("url") and f.get("ext") == "mp4" and (f.get("acodec") or "none") != "none" and (f.get("vcodec") or "none") != "none":
                try:
                    ok = _HTTP_SESSION.get(f["url"], headers={"Range": "bytes=0-255", "User-Agent": _BROWSER_UA}, timeout=6).status_code in (200, 206)
                except Exception:
                    ok = False
                if ok:
                    data = {"at": time.time(), "url": f["url"], "height": f.get("height") or 0, "title": info.get("title") or "video"}
                    if len(_MUXED) >= 32:
                        _MUXED.popitem(last=False)
                    _MUXED[video_id] = data
                    return data
    return None


_CAPTIONS: "OrderedDict[str, Dict]" = OrderedDict()


def caption_tracks(video_id: str) -> List[Dict]:
    """Languages the video has captions in (youtube-transcript-api)."""
    if not valid_id(video_id):
        return []
    entry = _CAPTIONS.get(video_id)
    if entry is not None:
        return entry["tracks"]
    tracks: List[Dict] = []
    try:
        from youtube_transcript_api import YouTubeTranscriptApi

        for t in YouTubeTranscriptApi().list(video_id):
            tracks.append({"lang": t.language_code, "name": t.language, "auto": bool(t.is_generated)})
    except Exception as exc:
        logger.info("No caption list for %s: %s", video_id, exc)
    tracks.sort(key=lambda t: (t["auto"], t["lang"] != "en"))
    if len(_CAPTIONS) >= 64:
        _CAPTIONS.popitem(last=False)
    _CAPTIONS[video_id] = {"tracks": tracks, "cues": {}}
    return tracks


def caption_cues(video_id: str, lang: str) -> List[List]:
    caption_tracks(video_id)
    entry = _CAPTIONS.get(video_id)
    if entry is None:
        return []
    if lang in entry["cues"]:
        return entry["cues"][lang]
    cues: List[List] = []
    try:
        from youtube_transcript_api import YouTubeTranscriptApi

        for s in YouTubeTranscriptApi().fetch(video_id, languages=[lang]):
            text = re.sub(r"\s+", " ", s.text.replace("\n", " ")).strip()
            if text:
                cues.append([round(s.start, 2), round(s.start + s.duration, 2), text])
    except Exception as exc:
        logger.info("No captions for %s/%s: %s", video_id, lang, exc)
    entry["cues"][lang] = cues
    return cues
