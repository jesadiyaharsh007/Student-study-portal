"""Open data for the Books and Videos pages. No API keys.

Books   - Project Gutenberg: the official OPDS catalog feed for search, plain-text files for reading.
Videos  - YouTube's public search page; if that is blocked, the public feeds of well-known education
          channels (filtered by the search words). Playback uses YouTube's privacy-friendly embed.

Everything has short timeouts and small caches so a slow source never hangs a page.
"""
import html
import json
import logging
import re
import threading
import time
import xml.etree.ElementTree as ET
from concurrent.futures import ThreadPoolExecutor
from functools import lru_cache

import requests

log = logging.getLogger(__name__)

GUTENBERG = "https://www.gutenberg.org"
UA = {"User-Agent": "StudentStudyPortal/1.0 (educational project; open data)"}
BROWSER_UA = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0 Safari/537.36",
    "Accept-Language": "en-US,en;q=0.9",
}

_session = requests.Session()
_session.mount("https://", requests.adapters.HTTPAdapter(pool_connections=8, pool_maxsize=16, max_retries=1))


class LibraryError(Exception):
    """A source could not be reached or returned something unusable."""


# ----------------------------------------------------------------------------- tiny TTL cache

_cache = {}
_cache_lock = threading.Lock()


def _cached(key, ttl, make):
    now = time.monotonic()
    with _cache_lock:
        hit = _cache.get(key)
        if hit and hit[0] > now:
            return hit[1]
    value = make()
    with _cache_lock:
        if len(_cache) > 200:
            for k in sorted(_cache, key=lambda k: _cache[k][0])[:50]:
                _cache.pop(k, None)
        _cache[key] = (now + ttl, value)
    return value


# ============================================================================= BOOKS

TOPICS = (
    ("popular", "Most read", ""),
    ("science", "Science", "science"),
    ("math", "Mathematics", "mathematics"),
    ("computing", "Computing", "computer"),
    ("history", "History", "history"),
    ("literature", "Literature", "literature"),
    ("philosophy", "Philosophy", "philosophy"),
    ("poetry", "Poetry", "poetry"),
    ("adventure", "Adventure", "adventure"),
)
_NS = {"a": "http://www.w3.org/2005/Atom", "dc": "http://purl.org/dc/terms/"}
_ID = re.compile(r"/ebooks/(\d+)")
PAGE_SIZE = 24


def search_books(query="", page=1):
    """Search Project Gutenberg. Empty query = most downloaded. Returns {'books': [...], 'has_next': bool}."""
    page = max(1, min(int(page or 1), 40))
    query = (query or "").strip()[:100]

    def make():
        params = {"start_index": (page - 1) * PAGE_SIZE + 1}
        if query:
            params["query"] = query
        else:
            params["sort_order"] = "downloads"
        try:
            r = _session.get(f"{GUTENBERG}/ebooks/search.opds/", params=params, headers=UA, timeout=9)
            r.raise_for_status()
            root = ET.fromstring(r.content)
        except (requests.RequestException, ET.ParseError) as exc:
            raise LibraryError(str(exc)) from exc
        books = []
        for entry in root.findall("a:entry", _NS):
            ident = (entry.findtext("a:id", default="", namespaces=_NS) or "")
            m = _ID.search(ident)
            if not m:
                continue  # "Authors" / "Subjects" shortcut rows
            gid = int(m.group(1))
            names = [n.text for n in entry.findall("a:author/a:name", _NS) if n.text]
            summary = (entry.findtext("a:content", default="", namespaces=_NS) or "").strip()
            books.append({
                "id": gid,
                "title": _tidy_title(entry.findtext("a:title", default="Untitled", namespaces=_NS)),
                # the catalog puts the author line in <content> for most entries
                "authors": ", ".join(_tidy_author(n) for n in (names or [summary]) if n)[:120],
                "cover": f"{GUTENBERG}/cache/epub/{gid}/pg{gid}.cover.medium.jpg",
            })
        has_next = len(books) > PAGE_SIZE or any(link.get("rel") == "next" for link in root.findall("a:link", _NS))
        return {"books": books[:PAGE_SIZE], "has_next": has_next}

    return _cached(("books", query.lower(), page), 1800, make)


def _tidy_title(title):
    return re.sub(r"\s+", " ", title or "").strip()


def _tidy_author(name):
    # "Austen, Jane, 1775-1817" -> "Jane Austen"
    name = (name or "").strip()
    m = re.match(r"^([^,]+),\s*([^,\d][^,]*?)(?:,\s*[\d\-\? ]+.*)?$", name)
    if m:
        return f"{m.group(2).strip()} {m.group(1).strip()}"
    return re.sub(r",?\s*\d{3,4}\??-.*$", "", name).strip()


# ----------------------------------------------------------------------------- reading text

class BookUnavailable(Exception):
    pass


_TEXT_URLS = (
    GUTENBERG + "/cache/epub/{id}/pg{id}.txt",
    GUTENBERG + "/files/{id}/{id}-0.txt",
    GUTENBERG + "/ebooks/{id}.txt.utf-8",
)
_MAX_BYTES = 8 * 1024 * 1024


def _fetch_text(gid):
    last = None
    for pattern in _TEXT_URLS:
        try:
            r = _session.get(pattern.format(id=gid), headers=UA, timeout=25, stream=True)
            if r.status_code != 200:
                last = f"HTTP {r.status_code}"
                continue
            raw = r.raw.read(_MAX_BYTES + 1, decode_content=True)
            if len(raw) > _MAX_BYTES:
                raise BookUnavailable("This book is too large to open here.")
            for enc in ("utf-8-sig", "latin-1"):
                try:
                    return raw.decode(enc)
                except UnicodeDecodeError:
                    continue
        except requests.RequestException as exc:
            last = str(exc)
    raise BookUnavailable(last or "The text is not available.")


@lru_cache(maxsize=6)
def load_book(gid):
    """Download and shape one book into chapters. Cached in memory for the life of the server instance."""
    return parse_gutenberg(_fetch_text(int(gid)), int(gid))


_HEAD_WORD = re.compile(
    r"^(chapter|book|part|section|volume|act|scene|canto|letter|stave|preface|introduction|prologue|epilogue|appendix|"
    r"conclusion|foreword|dedication|prelude|contents|argument|prefatory|proem)\b", re.I)
_NUMBERISH = re.compile(r"^(?:[IVXLCDM]{1,8}|\d{1,3})[\.\):]?$")


def _clean_heading(title):
    title = re.sub(r"[\[\]]", "", title)
    return re.sub(r"\s+", " ", title).strip(" .:·")


def _is_heading(raw):
    lines = [ln.strip() for ln in raw.strip().split("\n") if ln.strip()]
    if not lines or len(lines) > 3 or sum(len(x) for x in lines) > 100:
        return None
    first = lines[0]
    if _HEAD_WORD.match(first) or _NUMBERISH.match(first):
        title = " · ".join(x.strip(" .") if i == 0 else x for i, x in enumerate(lines))
        return _clean_heading(title) or None
    return None


def _inline(text):
    text = html.escape(text, quote=False)
    text = re.sub(r"(?<![\w])_([^_\n]+?)_(?![\w])", r"<em>\1</em>", text)
    return text


def _para_html(raw):
    s = raw.strip("\n")
    flat = re.sub(r"\s+", " ", s).strip()
    if re.match(r"^\[(Illustration|Footnote|Transcriber)", flat, re.I) and len(flat) < 400:
        return '<p class="fig">' + _inline(flat) + "</p>"
    lines = [ln.rstrip() for ln in s.split("\n")]
    if len(lines) >= 3 and sum(len(x) for x in lines) / len(lines) < 46 and max(len(x) for x in lines) < 70:
        return '<p class="verse">' + "<br>".join(_inline(x.strip()) for x in lines if x.strip()) + "</p>"
    return "<p>" + _inline(flat) + "</p>"


def _meta(text, key):
    m = re.search(rf"^{key}:\s*(.+(?:\n[ \t]+\S.*)*)", text[:6000], re.I | re.M)
    return re.sub(r"\s+", " ", m.group(1)).strip() if m else ""


def parse_gutenberg(text, gid):
    text = text.replace("\r\n", "\n").replace("\r", "\n").replace("﻿", "")
    title = _meta(text, "Title")
    author = _meta(text, "Author")
    start = re.search(r"\*\*\*\s*START OF (?:THE |THIS )?PROJECT GUTENBERG EBOOK[^\n]*\n", text, re.I)
    end = re.search(r"\*\*\*\s*END OF (?:THE |THIS )?PROJECT GUTENBERG EBOOK", text, re.I)
    body = text[start.end() if start else 0: end.start() if end else len(text)].strip("\n")

    paragraphs = [p for p in re.split(r"\n[ \t]*\n+", body) if p.strip()]
    chapters, cur = [], {"title": "Beginning", "paras": [], "chars": 0}

    def close():
        if cur["paras"]:
            chapters.append({"title": cur["title"], "paras": cur["paras"], "chars": cur["chars"]})

    for raw in paragraphs:
        head = _is_heading(raw)
        if head and cur["chars"] >= 250:
            close()
            cur = {"title": head, "paras": [], "chars": 0}
            continue
        if head and not cur["paras"]:
            # consecutive headings ("BOOK I" then "CHAPTER II") share one title; a bare "Contents" label is replaced
            replace = cur["title"] == "Beginning" or cur["title"].lower().startswith("contents")
            cur["title"] = head if replace else cur["title"] + " · " + head
            continue
        cur["paras"].append(_para_html(raw))
        cur["chars"] += len(raw)
    close()

    # merge tiny leftovers (contents lists, half-title pages) into the next section
    merged = []
    for ch in chapters:
        if merged and merged[-1]["chars"] < 250:
            prev = merged.pop()
            ch = {"title": ch["title"] if ch["title"] != "Beginning" else prev["title"], "paras": prev["paras"] + ch["paras"], "chars": prev["chars"] + ch["chars"]}
        merged.append(ch)
    chapters = merged

    total_chars = sum(c["chars"] for c in chapters)
    if len(chapters) < 3 and total_chars > 24000:  # no usable headings: cut into even parts at paragraph borders
        flat = [p for c in chapters for p in c["paras"]]
        chapters, buf, size = [], [], 0
        for p in flat:
            buf.append(p)
            size += len(p)
            if size >= 14000:
                chapters.append({"title": f"Part {len(chapters) + 1}", "paras": buf, "chars": size})
                buf, size = [], 0
        if buf:
            chapters.append({"title": f"Part {len(chapters) + 1}", "paras": buf, "chars": size})

    out = []
    for i, c in enumerate(chapters):
        words = max(1, c["chars"] // 6)
        out.append({"i": i, "t": c["title"][:120], "html": "".join(c["paras"]), "words": words})
    if not out:
        raise BookUnavailable("This book has no readable text.")
    return {
        "id": gid,
        "title": title or f"Book {gid}",
        "author": _tidy_author(author),
        "cover": f"{GUTENBERG}/cache/epub/{gid}/pg{gid}.cover.medium.jpg",
        "words": sum(c["words"] for c in out),
        "chapters": out,
        "source": f"{GUTENBERG}/ebooks/{gid}",
    }


# ============================================================================= VIDEOS

# Verified public channel feeds (no key needed). Used as the fallback and for the topic shelves.
CHANNELS = {
    "Khan Academy": "UC4a-Gbdw7vOaccHmFo40b9g", "CrashCourse": "UCX6b17PVsYBQ0ip5gyeme-Q",
    "3Blue1Brown": "UCYO_jab_esuFRV4b17AJtAw", "freeCodeCamp": "UC8butISFwT-Wl7EV0hUK0BQ",
    "MIT OpenCourseWare": "UCEBb1b_L6zDS3xTUrIALZOw", "TED-Ed": "UCsooa4yRKGN_zEE8iknghZA",
    "Veritasium": "UCHnyfMqiRRG1u-2MsSQLbXA", "The Organic Chemistry Tutor": "UCEWpbFLzoYGPfuWUMFPSaoA",
    "Computerphile": "UC9-y-6csu5WGm29I7JiwpnA", "CS50": "UCcabW7890RKJzL968QWEykA",
    "Numberphile": "UCoxcjq-8xIDTYp3uz647V5A", "StatQuest": "UCtYLUTtgS3k1Fg4y5tAhLbw",
    "Kurzgesagt": "UCsXVk37bltHxD1rDPwtNM8Q", "Physics Girl": "UC7DdEm33SyaTDtWYGO2CwdA",
    "Programming with Mosh": "UCWv7vMbMWH4-V0ZXdmDpPBA", "Fireship": "UCsBjURrPoezykLs9EqgamOA",
    "Professor Leonard": "UCoHhuummRZaIVX7bD4t2czg", "Mathologer": "UC1_uAIS3r8Vu6JjXWvastJg",
    "Sabine Hossenfelder": "UC1yNl2E66ZzKApQdRuTQ4tw", "Two Minute Papers": "UCbfYPyITQ-7l4upoX8nvctg",
    "NeetCode": "UC_mYaQAE6-71rjSN6CeCA-g", "Traversy Media": "UC29ju8bIPH5as8OGnQzwJyA",
}
VIDEO_TOPICS = (
    ("all", "Everything", tuple(CHANNELS)),
    ("math", "Maths", ("Khan Academy", "3Blue1Brown", "Numberphile", "Mathologer", "Professor Leonard", "The Organic Chemistry Tutor")),
    ("science", "Science", ("Veritasium", "Kurzgesagt", "Physics Girl", "CrashCourse", "TED-Ed", "Sabine Hossenfelder", "MIT OpenCourseWare", "The Organic Chemistry Tutor")),
    ("computing", "Computing", ("freeCodeCamp", "CS50", "Computerphile", "Fireship", "NeetCode", "Traversy Media", "Programming with Mosh", "Two Minute Papers")),
    ("stats", "Data and stats", ("StatQuest", "Khan Academy", "Two Minute Papers", "3Blue1Brown")),
)
_ATOM = "{http://www.w3.org/2005/Atom}"
_YT = "{http://www.youtube.com/xml/schemas/2015}"
_MEDIA = "{http://search.yahoo.com/mrss/}"


def _video(vid, title, channel, thumb="", duration="", views="", published=""):
    return {"id": vid, "title": title, "channel": channel, "thumbnail": thumb or f"https://i.ytimg.com/vi/{vid}/hqdefault.jpg",
            "duration": duration, "views": views, "published": published, "link": f"https://www.youtube.com/watch?v={vid}"}


def _yt_search_page(query):
    try:
        r = _session.get(
            "https://www.youtube.com/results", params={"search_query": query, "sp": "EgIQAQ%3D%3D"},
            headers=BROWSER_UA, cookies={"CONSENT": "YES+1", "SOCS": "CAI"}, timeout=7,
        )
        r.raise_for_status()
        m = re.search(r"var ytInitialData = (\{.*?\});</script>", r.text, re.S)
        if not m:
            raise LibraryError("no data on the page")
        data = json.loads(m.group(1))
    except (requests.RequestException, ValueError) as exc:
        raise LibraryError(str(exc)) from exc
    found = []

    def walk(node):
        if isinstance(node, dict):
            v = node.get("videoRenderer")
            if v and v.get("videoId"):
                runs = (v.get("title") or {}).get("runs") or [{}]
                owner = ((v.get("ownerText") or {}).get("runs") or [{}])[0].get("text", "")
                found.append(_video(
                    v["videoId"], "".join(r.get("text", "") for r in runs), owner,
                    duration=(v.get("lengthText") or {}).get("simpleText", ""),
                    views=(v.get("viewCountText") or {}).get("simpleText", ""),
                    published=(v.get("publishedTimeText") or {}).get("simpleText", ""),
                ))
            for child in node.values():
                walk(child)
        elif isinstance(node, list):
            for child in node:
                walk(child)

    walk(data)
    if not found:
        raise LibraryError("no videos on the page")
    return found[:24]


def _channel_feed(name):
    cid = CHANNELS[name]

    def make():
        try:
            r = _session.get("https://www.youtube.com/feeds/videos.xml", params={"channel_id": cid}, headers=UA, timeout=7)
            r.raise_for_status()
            root = ET.fromstring(r.content)
        except (requests.RequestException, ET.ParseError):
            return []
        items = []
        for e in root.findall(f"{_ATOM}entry"):
            vid = e.findtext(f"{_YT}videoId")
            if not vid:
                continue
            group = e.find(f"{_MEDIA}group")
            desc = (group.findtext(f"{_MEDIA}description") if group is not None else "") or ""
            stats = group.find(f"{_MEDIA}community/{_MEDIA}statistics") if group is not None else None
            thumb = group.find(f"{_MEDIA}thumbnail") if group is not None else None
            views = stats.get("views") if stats is not None else ""
            item = _video(vid, e.findtext(f"{_ATOM}title") or "", name, thumb.get("url") if thumb is not None else "",
                          views=f"{int(views):,} views" if views and views.isdigit() else "", published=(e.findtext(f"{_ATOM}published") or "")[:10])
            item["_desc"] = desc.lower()
            item["_date"] = item["published"]
            items.append(item)
        return items

    return _cached(("feed", cid), 1800, make)


def _from_channels(names, query=""):
    with ThreadPoolExecutor(max_workers=8) as pool:
        feeds = list(pool.map(_channel_feed, names))
    seen, videos = set(), []
    for feed in feeds:
        for v in feed:
            if v["id"] not in seen:
                seen.add(v["id"])
                videos.append(v)
    words = [w for w in re.findall(r"[\w\+#]+", query.lower()) if len(w) > 1]
    if words:
        scored = []
        for v in videos:
            hay = f"{v['title'].lower()} {v['channel'].lower()} {v['_desc']}"
            score = sum(1 for w in words if w in hay) + sum(2 for w in words if w in v["title"].lower())
            if score:
                scored.append((score, v["_date"], v))
        scored.sort(key=lambda t: (t[0], t[1]), reverse=True)
        videos = [v for _, _, v in scored]
    else:
        videos.sort(key=lambda v: v["_date"], reverse=True)
    return [{k: v for k, v in item.items() if not k.startswith("_")} for item in videos[:24]]


def search_videos(query="", topic="all"):
    """Returns {'videos': [...], 'source': 'search'|'channels'}. Never raises; empty list if nothing found."""
    query = (query or "").strip()[:100]
    names = next((n for key, _, n in VIDEO_TOPICS if key == topic), VIDEO_TOPICS[0][2])

    def make():
        if query:
            try:
                return {"videos": _yt_search_page(query), "source": "search"}
            except LibraryError as exc:
                log.info("YouTube search unavailable (%s); using channel feeds", exc)
            return {"videos": _from_channels(tuple(CHANNELS) if topic == "all" else names, query), "source": "channels"}
        return {"videos": _from_channels(names), "source": "channels"}

    return _cached(("videos", query.lower(), topic), 900, make)
