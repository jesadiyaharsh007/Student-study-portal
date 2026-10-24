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
