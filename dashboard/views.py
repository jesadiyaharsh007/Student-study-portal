import functools
from concurrent.futures import ThreadPoolExecutor
import re
from datetime import timedelta

import logging
import requests

_HTTP_SESSION = requests.Session()
from django.contrib import messages
from django.contrib.auth import login, logout
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.http import JsonResponse, StreamingHttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.utils.http import url_has_allowed_host_and_scheme
from django.views import generic
from django.views.decorators.http import require_POST

from .forms import (
    HomeworkForm,
    Notesform,
    StudentLoginForm,
    TodoForm,
    UserRegistrationForm,
)
from . import library, lexi, throttle
from .models import Homework, Notes, Todo

# (attempts, seconds): failed sign-ins per account name and per address, Lexi questions per student.
LOGIN_LIMIT_NAME = (5, 15 * 60)
LOGIN_LIMIT_IP = (30, 15 * 60)
LEXI_LIMIT_BURST = (20, 10 * 60)
LEXI_LIMIT_DAY = (200, 24 * 60 * 60)

# Every page that needs an account uses the same guard; unauthenticated visitors
# are sent to the login page and returned to where they were heading.
student_required = login_required

HTTP_HEADERS = {"User-Agent": "Mozilla/5.0 (StudentStudyPortal)"}


def _is_ajax(request):
    return request.headers.get("x-requested-with") == "XMLHttpRequest"


def _progress(items):
    return sum(1 for i in items if i.is_finished), len(items)


def _pct(done, total):
    return round(done * 100 / total) if total else 0


def _is_part(request):
    """True when the page is asking for just its data region (see static/js/app.js, [data-async])."""
    return request.GET.get("_part") == "1"


def _part_response(request, template, ctx):
    resp = render(request, template, ctx)
    resp["Cache-Control"] = "private, no-store"
    return resp


def _safe_next(request):
    target = request.POST.get("next") or request.GET.get("next") or ""
    if target and url_has_allowed_host_and_scheme(target, {request.get_host()}, request.is_secure()):
        return target
    return ""


# --------------------------------------------------------------------------- auth

def login_view(request):
    if request.user.is_authenticated:
        if not (request.user.is_staff or request.user.is_superuser):
            return redirect("profile")
        logout(request)

    status = 200
    if request.method == "POST":
        # Password guessing is slowed per account and per address; the counts live in the database.
        name_key = throttle.key("login-name", (request.POST.get("username") or "").strip().lower())
        ip_key = throttle.key("login-ip", throttle.client_ip(request))
        if throttle.blocked(name_key, *LOGIN_LIMIT_NAME) or throttle.blocked(ip_key, *LOGIN_LIMIT_IP):
            form = StudentLoginForm(request)
            messages.error(request, "Too many sign-in attempts. Please wait 15 minutes and try again.")
            status = 429
        else:
            form = StudentLoginForm(request, data=request.POST)
            if form.is_valid():
                throttle.reset(name_key)
                user = form.get_user()
                login(request, user)
                messages.success(request, f"Welcome back, {user.username}!")
                return redirect(_safe_next(request) or "profile")
            throttle.allowed(name_key, *LOGIN_LIMIT_NAME)
            throttle.allowed(ip_key, *LOGIN_LIMIT_IP)
    else:
        form = StudentLoginForm()

    return render(request, "dashboard/login.html", {"form": form, "next": _safe_next(request)}, status=status)


def register(request):
    if request.user.is_authenticated:
        return redirect("profile")

    if request.method == "POST":
        form = UserRegistrationForm(request.POST)
        if form.is_valid():
            try:
                form.save()
            except Exception:
                messages.error(request, "We couldn't create your account. Please try again.")
            else:
                messages.success(request, f"Account created for {form.cleaned_data['username']}. Sign in to start!")
                return redirect("login")
    else:
        form = UserRegistrationForm()
    return render(request, "dashboard/register.html", {"form": form})


def logout_view(request):
    if request.method == "POST":
        logout(request)
        return render(request, "dashboard/logout.html", {"done": True})
    return render(request, "dashboard/logout.html", {"done": not request.user.is_authenticated})


# --------------------------------------------------------------------------- public

def home(request):
    # Signed-in students never see the marketing page: their home is the dashboard.
    if request.user.is_authenticated and not (request.user.is_staff or request.user.is_superuser):
        return redirect("profile")
    return render(request, "dashboard/home.html")


def about(request):
    return render(request, "dashboard/about.html")


def privacy(request):
    return render(request, "dashboard/privacy.html")


def terms(request):
    return render(request, "dashboard/terms.html")


# --------------------------------------------------------------------------- dashboard

# What to search the library for, per subject a student can pick. Subjects Gutenberg has no books on
# (Spring, Docker...) fall back to a broader topic so the shelf is never empty.
SUBJECT_BOOKS = {
    "Java": "programming", "PHP": "programming", "Python": "programming", "C": "programming",
    "C++": "programming", "Spring": "computer", "Docker": "computer", "ADBMS": "database",
    "ML": "mathematics", "Other": "",
}


def _recommendations(user, pending_subjects):
    """Two book suggestions from what the student is actually working on (rotates daily)."""
    from collections import Counter
    counts = Counter(pending_subjects)
    counts.update(Notes.objects.filter(user=user).values_list("subject", flat=True)[:50])
    subject = next((s for s, _ in counts.most_common() if s != "Other"), "")
    books = library.search_books(SUBJECT_BOOKS.get(subject, ""), 1)["books"] if subject else []
    picked = bool(books)
    if not books:
        books = library.search_books("", 1)["books"]
    start = timezone.localdate().toordinal() % len(books) if books else 0
    return {
        "reco_subject": subject if picked else "",
        "reco_books": [books[(start + i) % len(books)] for i in range(min(2, len(books)))],
    }


def _week(pending):
    """Seven days from today with how much homework is due on each: drives the week strip."""
    today = timezone.localdate()
    due = [timezone.localtime(h.due).date() for h in pending]
    days = []
    for i in range(7):
        d = today + timedelta(days=i)
        count = due.count(d)
        days.append({"num": d.day, "name": d.strftime("%a"), "count": count, "today": i == 0, "level": min(count, 4)})
    return days


@student_required
def profile(request):
    if not _is_part(request):
        # Instant shell: no database work. The data region is fetched by the page right after.
        return render(request, "dashboard/profile.html", {"loading": True})
    todos = list(Todo.objects.filter(user=request.user).only("id", "title", "is_finished").order_by("is_finished", "-id"))
    homework = list(
        Homework.objects.filter(user=request.user)
        .only("id", "subject", "title", "due", "is_finished")
        .order_by("is_finished", "due")
    )
    notes_count = Notes.objects.filter(user=request.user).count()

    pending_todos = [t for t in todos if not t.is_finished]
    pending_homework = [h for h in homework if not h.is_finished]
    total = len(todos) + len(homework)
    done = total - len(pending_todos) - len(pending_homework)

    return _part_response(request, "dashboard/partials/profile_data.html", {
        **_recommendations(request.user, [h.subject for h in pending_homework]),
        "week": _week(pending_homework),
        "overdue": sum(1 for h in pending_homework if timezone.localtime(h.due).date() < timezone.localdate()),
        "latest_notes": list(Notes.objects.filter(user=request.user).only("id", "subject", "title").order_by("-id")[:3]),
        "todos": pending_todos[:6],
        "homework": pending_homework[:5],
        "todo_pending": len(pending_todos),
        "homework_pending": len(pending_homework),
        "notes_count": notes_count,
        "tasks_done": done,
        "tasks_total": total,
        "progress": round(done * 100 / total) if total else 0,
    })


# --------------------------------------------------------------------------- notes

@student_required
def notes(request):
    if request.method == "POST":
        form = Notesform(request.POST)
        if form.is_valid():
            note = form.save(commit=False)
            note.user = request.user
            note.save()
            messages.success(request, "Note saved.")
            return redirect("notes")
    else:
        form = Notesform()
        if not _is_part(request):
            return render(request, "dashboard/notes.html", {"loading": True, "form": form})
    items = list(Notes.objects.filter(user=request.user).only("id", "subject", "title", "description").order_by("-id"))
    ctx = {
        "notes": items,
        "subjects": sorted({n.subject for n in items}),
        "form": form,
        "open_form": request.method == "POST",
    }
    if _is_part(request):
        return _part_response(request, "dashboard/partials/notes_data.html", ctx)
    return render(request, "dashboard/notes.html", ctx)


@student_required
@require_POST
def delete_note(request, pk=None):
    get_object_or_404(Notes, id=pk, user=request.user).delete()
    if _is_ajax(request):
        return JsonResponse({"ok": True})
    messages.success(request, "Note deleted.")
    return redirect("notes")


class NoteDetailview(LoginRequiredMixin, generic.DetailView):
    model = Notes

    def get_queryset(self):
        return Notes.objects.filter(user=self.request.user)


# --------------------------------------------------------------------------- homework

@student_required
def homework(request):
    if request.method == "POST":
        form = HomeworkForm(request.POST)
        if form.is_valid():
            item = form.save(commit=False)
            item.user = request.user
            item.save()
            messages.success(request, "Homework added.")
            return redirect("homework")
    else:
        form = HomeworkForm()
        if not _is_part(request):
            return render(request, "dashboard/homework.html", {"loading": True, "form": form})
    items = (
        Homework.objects.filter(user=request.user)
        .only("id", "subject", "title", "description", "due", "is_finished")
        .order_by("is_finished", "due")
    )
    items = list(items)
    done, total = _progress(items)
    ctx = {
        "homework": items,
        "done": done,
        "total": total,
        "pct": _pct(done, total),
        "form": form,
        "open_form": request.method == "POST",
    }
    if _is_part(request):
        return _part_response(request, "dashboard/partials/homework_data.html", ctx)
    return render(request, "dashboard/homework.html", ctx)


@student_required
@require_POST
def update_homework(request, pk=None):
    item = get_object_or_404(Homework, id=pk, user=request.user)
    item.is_finished = not item.is_finished
    item.save(update_fields=["is_finished"])
    if _is_ajax(request):
        return JsonResponse({"ok": True, "finished": item.is_finished})
    return redirect(_safe_next(request) or "homework")


@student_required
@require_POST
def delete_homework(request, pk=None):
    get_object_or_404(Homework, id=pk, user=request.user).delete()
    if _is_ajax(request):
        return JsonResponse({"ok": True})
    messages.success(request, "Homework deleted.")
    return redirect(_safe_next(request) or "homework")


# --------------------------------------------------------------------------- to-do

@student_required
def todo(request):
    if request.method == "POST":
        form = TodoForm(request.POST)
        if form.is_valid():
            item = form.save(commit=False)
            item.user = request.user
            item.save()
            if _is_ajax(request):
                return JsonResponse({
                    "ok": True,
                    "id": item.id,
                    "title": item.title,
                    "finished": item.is_finished,
                    "toggle": reverse("update-todo", args=[item.id]),
                    "delete": reverse("delete-todo", args=[item.id]),
                })
            messages.success(request, "Task added.")
            return redirect("todo")
        if _is_ajax(request):
            return JsonResponse({"ok": False, "error": "Please enter a task (max 100 characters)."}, status=400)
    else:
        form = TodoForm()
        if not _is_part(request):
            return render(request, "dashboard/todo.html", {"loading": True, "form": form})
    items = Todo.objects.filter(user=request.user).only("id", "title", "is_finished").order_by("is_finished", "-id")
    items = list(items)
    done, total = _progress(items)
    ctx = {"form": form, "todos": items, "done": done, "total": total, "pct": _pct(done, total)}
    if _is_part(request):
        return _part_response(request, "dashboard/partials/todo_data.html", ctx)
    return render(request, "dashboard/todo.html", ctx)


@student_required
@require_POST
def update_todo(request, pk=None):
    item = get_object_or_404(Todo, id=pk, user=request.user)
    item.is_finished = not item.is_finished
    item.save(update_fields=["is_finished"])
    if _is_ajax(request):
        return JsonResponse({"ok": True, "finished": item.is_finished})
    return redirect(_safe_next(request) or "todo")


@student_required
@require_POST
def delete_todo(request, pk=None):
    get_object_or_404(Todo, id=pk, user=request.user).delete()
    if _is_ajax(request):
        return JsonResponse({"ok": True})
    return redirect(_safe_next(request) or "todo")


# --------------------------------------------------------------------------- research tools

def _query(request):
    return request.GET.get("q", "").strip()[:100]


# --------------------------------------------------------------------------- videos

def youtube(request, rest=""):
    """Videos are being rebuilt. The menu link and every old video link land on this notice."""
    return render(request, "dashboard/coming_soon.html", {"feature": "Videos"})


OPENLIBRARY_FIELDS = "key,title,author_name,cover_i,first_publish_year,number_of_pages_median,subject,ratings_average"


@functools.lru_cache(maxsize=128)
@student_required
def books(request):
    q = _query(request)
    topic = request.GET.get("topic", "")
    topic_query = next((tq for key, _label, tq in library.TOPICS if key == topic), None)
    try:
        page = max(1, int(request.GET.get("page") or 1))
    except ValueError:
        page = 1
    ctx = {"q": q, "topic": topic if topic_query is not None else "", "page": page,
           "topics": [(key, label) for key, label, _tq in library.TOPICS]}
    if not _is_part(request):
        return render(request, "dashboard/books.html", {**ctx, "loading": True})

    search, recommended = q or (topic_query or ""), False
    if not q and topic_query is None:
        latest = Homework.objects.filter(user=request.user, is_finished=False).only("subject").order_by("-id").first()
        if latest and page == 1:
            search, recommended = latest.subject, True
            ctx["subject"] = latest.subject
    try:
        data = library.search_books(search, page)
        if recommended and not data["books"]:
            data, recommended = library.search_books("", 1), False
        ctx.update(books=data["books"], has_next=data["has_next"], recommended=recommended)
    except library.LibraryError:
        logging.getLogger(__name__).warning("book catalog unavailable", exc_info=True)
        ctx["error"] = "The free book library did not respond. Please try again in a moment."
    return _part_response(request, "dashboard/partials/books_data.html", ctx)


@student_required
def book_read(request, pg_id):
    return render(request, "dashboard/reader.html", {
        "gid": pg_id, "title": (request.GET.get("t") or "")[:160], "author": (request.GET.get("a") or "")[:120],
    })


@student_required
def book_data(request, pg_id):
    try:
        book = library.load_book(pg_id)
    except library.BookUnavailable as exc:
        return JsonResponse({"ok": False, "error": str(exc)}, status=502)
    except Exception:
        logging.getLogger(__name__).exception("could not load book %s", pg_id)
        return JsonResponse({"ok": False, "error": "This book could not be opened right now."}, status=502)
    resp = JsonResponse({"ok": True, "book": book})
    resp["Cache-Control"] = "private, max-age=86400"
    return resp


@functools.lru_cache(maxsize=256)
def _lookup_dictionaryapi(word):
    r = requests.get(f"https://api.dictionaryapi.dev/api/v2/entries/en/{word}", timeout=4, headers=HTTP_HEADERS)
    if r.status_code != 200:
        return None
    entry = r.json()[0]
    phonetics = audio = ""
    for p in entry.get("phonetics", []):
        phonetics = phonetics or p.get("text", "")
        audio = audio or p.get("audio", "")
    if audio.startswith("//"):
        audio = "https:" + audio
    meanings, synonyms = [], []
    for m in entry.get("meanings", [])[:3]:
        d = (m.get("definitions") or [{}])[0]
        meanings.append({"pos": m.get("partOfSpeech", ""), "definition": d.get("definition", ""), "example": d.get("example", "")})
        for s in m.get("synonyms", []):
            if s not in synonyms:
                synonyms.append(s)
    if not meanings:
        return None
    return {"phonetics": phonetics, "audio": audio, "meanings": meanings, "synonyms": synonyms[:8]}


@functools.lru_cache(maxsize=256)
def _lookup_wiktionary(word):
    r = requests.get(f"https://en.wiktionary.org/api/rest_v1/page/definition/{word}", headers=HTTP_HEADERS, timeout=5)
    if r.status_code != 200:
        return None
    meanings = []
    for entry in r.json().get("en", [])[:3]:
        if not entry.get("definitions"):
            continue
        first = entry["definitions"][0]
        example = ""
        if first.get("examples"):
            example = re.sub(r"<[^<]+?>", "", first["examples"][0]).strip()
        meanings.append({
            "pos": entry.get("partOfSpeech", ""),
            "definition": re.sub(r"<[^<]+?>", "", first.get("definition", "")).strip(),
            "example": example,
        })
    if not meanings:
        return None
    try:
        syn = requests.get("https://api.datamuse.com/words", params={"rel_syn": word, "max": 8}, timeout=3).json()
        synonyms = [s["word"] for s in syn]
    except Exception:
        synonyms = []
    return {"phonetics": "", "audio": "", "meanings": meanings, "synonyms": synonyms}


def _safe_lookup(lookup, word):
    try:
        return lookup(word)
    except Exception:
        return None


def _lookup_word(word):
    """Ask both dictionaries at once (instead of one after the other); prefer the first."""
    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = [pool.submit(_safe_lookup, f, word) for f in (_lookup_dictionaryapi, _lookup_wiktionary)]
        for fut in futures:
            entry = fut.result()
            if entry:
                return entry
    return None


@student_required
def dictionary(request):
    q = _query(request)
    ctx = {"q": q}
    if q:
        word = q.lower()
        entry = _lookup_word(word)
        ctx["searched"] = True
        if entry:
            ctx.update(entry, word=q)
    return render(request, "dashboard/dictionary.html", ctx)


def _trim(text, limit=1400):
    if len(text) <= limit:
        return text
    cut = text[:limit]
    end = max(cut.rfind(". "), cut.rfind("\n"))
    return cut[: end + 1] if end > limit // 2 else cut.rstrip() + "…"


WIKI_HEADERS = {
    "User-Agent": "StudentStudyPortal/1.0 (educational-portal; contact: admin@studentstudyportal.local)",
    "Accept": "application/json",
}


_WIKI_CACHE = {}


def _parse_wikipedia_sections(text):
    """
    Parses plain-text Wikipedia article into structured sections, omitting
    uninformative back-matter like References, See also, External links.
    Returns: (lead_paragraphs, list_of_sections, total_word_count)
    """
    if not text:
        return [], [], 0

    IGNORE_SECTIONS = {
        "see also", "references", "external links", "further reading",
        "notes", "sources", "bibliography", "citations", "notes and references"
    }

    lines = text.strip().split("\n")
    sections = []
    lead_paragraphs = []
    current_lines = []
    current_sec = None
    in_lead = True

    for line in lines:
        match = re.match(r"^(={2,4})\s*(.*?)\s*\1$", line.strip())
        if match:
            eqs, h_title = match.groups()
            level = len(eqs)
            content = "\n".join(current_lines).strip()
            paras = [p.strip() for p in re.split(r"\n\s*\n", content) if p.strip()]

            if in_lead:
                lead_paragraphs = paras
                in_lead = False
            else:
                if current_sec and current_sec["title"].lower() not in IGNORE_SECTIONS and paras:
                    current_sec["paragraphs"] = paras
                    sections.append(current_sec)

            current_lines = []
            slug = re.sub(r"[^a-z0-9]+", "-", h_title.lower()).strip("-")
            current_sec = {
                "title": h_title,
                "level": level,
                "paragraphs": [],
                "id": f"sec-{slug}" if slug else f"sec-{len(sections)}",
            }
        else:
            current_lines.append(line)

    # Flush last section
    content = "\n".join(current_lines).strip()
    paras = [p.strip() for p in re.split(r"\n\s*\n", content) if p.strip()]
    if in_lead:
        lead_paragraphs = paras
    elif current_sec and current_sec["title"].lower() not in IGNORE_SECTIONS and paras:
        current_sec["paragraphs"] = paras
        sections.append(current_sec)

    words = sum(len(p.split()) for p in lead_paragraphs)
    words += sum(len(p.split()) for s in sections for p in s["paragraphs"])

    return lead_paragraphs, sections, words


def _build_wiki_payload(s_data, full_extract=""):
    import urllib.parse
    title = s_data.get("title", "")
    safe_title = urllib.parse.quote(title.replace(" ", "_"))
    link = (
        s_data.get("content_urls", {}).get("desktop", {}).get("page")
        or f"https://en.wikipedia.org/wiki/{safe_title}"
    )
    extract = (s_data.get("extract") or "").strip()
    desc = (s_data.get("description") or "").strip()

    # Image extraction (prefer original image or clear thumbnail)
    image_url = ""
    if s_data.get("originalimage") and s_data["originalimage"].get("source"):
        image_url = s_data["originalimage"]["source"]
    elif s_data.get("thumbnail") and s_data["thumbnail"].get("source"):
        image_url = s_data["thumbnail"]["source"]

    # Coordinates formatting
    coordinates = None
    if s_data.get("coordinates"):
        c = s_data["coordinates"]
        lat = c.get("lat")
        lon = c.get("lon")
        if lat is not None and lon is not None:
            lat_dir = "N" if lat >= 0 else "S"
            lon_dir = "E" if lon >= 0 else "W"
            coordinates = f"{abs(lat):.2f}\u00b0 {lat_dir}, {abs(lon):.2f}\u00b0 {lon_dir}"

    # Extract key takeaways from summary sentences
    sentences = [s.strip() for s in re.split(r"(?<=[.!?])\s+", extract) if len(s.strip()) > 28]
    highlights = sentences[:4]

    lead_paras, sections, word_count = _parse_wikipedia_sections(full_extract or extract)
    if not lead_paras and extract:
        lead_paras = [extract]
        word_count = len(extract.split())

    read_time = max(1, round(word_count / 200)) if word_count else 2

    return {
        "title": title,
        "description": desc,
        "link": link,
        "details": extract,
        "summary": extract,
        "lead_paragraphs": lead_paras,
        "highlights": highlights,
        "image_url": image_url,
        "coordinates": coordinates,
        "sections": sections,
        "section_count": len(sections),
        "word_count": word_count,
        "read_time": read_time,
    }


def _fetch_wikipedia(query):
    """Cached wrapper: only successful lookups are remembered, so a timeout is never cached."""
    key = (query or "").strip().lower()
    if key in _WIKI_CACHE:
        return _WIKI_CACHE[key], None
    article, error = _fetch_wikipedia_uncached(query)
    if article:
        if len(_WIKI_CACHE) >= 128:
            _WIKI_CACHE.pop(next(iter(_WIKI_CACHE)))
        _WIKI_CACHE[key] = article
    return article, error


def _fetch_wikipedia_uncached(query):
    """
    Fetches Wikipedia articles using the official Wikimedia REST v1 and Query APIs,
    with smart disambiguation resolution, rich photo and structured section extraction,
    and lightning-fast connection pooling.
    """
    import urllib.parse

    q = (query or "").strip()
    if not q:
        return None, "Please enter a search term."

    safe = urllib.parse.quote(q.replace(" ", "_"))
    api_url = "https://en.wikipedia.org/w/api.php"

    def _fetch_full_extract(page_title):
        try:
            params = {
                "action": "query",
                "prop": "extracts",
                "explaintext": "1",
                "titles": page_title,
                "redirects": "1",
                "format": "json",
            }
            resp = _HTTP_SESSION.get(api_url, params=params, headers=WIKI_HEADERS, timeout=3.5)
            if resp.status_code == 200:
                pages = resp.json().get("query", {}).get("pages", {})
                for pid, pdata in pages.items():
                    if pid != "-1" and pdata.get("extract"):
                        return pdata.get("extract", "")
        except Exception:
            pass
        return ""

    try:
        # Fast Path: Direct REST summary (follows redirects automatically)
        s_data = None
        try:
            resp = _HTTP_SESSION.get(
                f"https://en.wikipedia.org/api/rest_v1/page/summary/{safe}",
                headers=WIKI_HEADERS,
                timeout=3.0,
            )
            if resp.status_code == 200:
                data = resp.json()
                if data.get("type") != "disambiguation" and data.get("extract"):
                    s_data = data
        except Exception:
            pass

        # Fallback Path: Search API if direct hit wasn't clean or was a disambiguation
        if not s_data:
            search_params = {
                "action": "query",
                "list": "search",
                "srsearch": q,
                "srlimit": 6,
                "format": "json",
            }
            s_resp = _HTTP_SESSION.get(api_url, params=search_params, headers=WIKI_HEADERS, timeout=3.5)
            candidates = []
            if s_resp.status_code == 200:
                candidates = [r["title"] for r in s_resp.json().get("query", {}).get("search", []) if "title" in r]

            if not candidates:
                op_resp = _HTTP_SESSION.get(
                    api_url,
                    params={"action": "opensearch", "search": q, "limit": 6, "namespace": 0, "format": "json"},
                    headers=WIKI_HEADERS,
                    timeout=3.5,
                )
                if op_resp.status_code == 200:
                    op_data = op_resp.json()
                    if len(op_data) > 1 and op_data[1]:
                        candidates = op_data[1]

            if not candidates:
                return None, "No Wikipedia article matched that search."

            def _summary(title):
                s_safe = urllib.parse.quote(title.replace(" ", "_"))
                try:
                    return _HTTP_SESSION.get(
                        f"https://en.wikipedia.org/api/rest_v1/page/summary/{s_safe}",
                        headers=WIKI_HEADERS,
                        timeout=3.0,
                    )
                except Exception:
                    return None

            top = candidates[:4]
            with ThreadPoolExecutor(max_workers=len(top)) as pool:
                summaries = list(pool.map(_summary, top))

            disambig_data = None
            for r_sum in summaries:
                if r_sum is not None and r_sum.status_code == 200:
                    c_data = r_sum.json()
                    if c_data.get("extract"):
                        if c_data.get("type") == "disambiguation":
                            if not disambig_data:
                                disambig_data = c_data
                            continue
                        s_data = c_data
                        break

            if not s_data and disambig_data:
                s_data = disambig_data

        if not s_data or not s_data.get("extract"):
            return None, "No summary could be loaded for this topic. Try adding a few more words."

        canonical_title = s_data.get("title", q)
        full_extract = _fetch_full_extract(canonical_title)

        payload = _build_wiki_payload(s_data, full_extract)
        return payload, None

    except Exception as exc:
        logging.getLogger(__name__).warning("Wikipedia API error: %s", exc)
        return None, "Wikipedia didn't respond. Please check your network connection and try again."


@student_required
def wiki(request):
    q = _query(request)
    view_mode = request.GET.get("view", "summary").strip().lower()
    ctx = {"q": q, "view_mode": view_mode}
    if q:
        article, error = _fetch_wikipedia(q)
        if article:
            ctx.update(article)
        else:
            ctx["error"] = error
    return render(request, "dashboard/wiki.html", ctx)


@student_required
def conversion(request):
    return render(request, "dashboard/conversion.html")


# --------------------------------------------------------------------------- Lexi

def _lexi_chunks(resp):
    """Pass Gemini's answer on piece by piece; if the connection drops midway, say so instead of stopping silently."""
    sent = False
    try:
        for piece in lexi.iter_text(resp):
            sent = True
            yield piece
    except requests.RequestException:
        yield "\n\n_(The answer was cut off. Please ask again.)_"
        return
    if not sent:
        yield "_(Lexi had no answer for that. Please rephrase your question.)_"


@student_required
def chatbot(request):
    from django.conf import settings

    # History lives in the browser (localStorage) and is sent with each question, so
    # chatting never touches the database or the session.
    if request.GET.get("clear") == "true" or (request.method == "POST" and request.POST.get("clear")):
        if _is_ajax(request):
            return JsonResponse({"ok": True})
        return redirect("chatbot")

    ctx = {}
    if request.method == "POST":
        prompt = (request.POST.get("prompt") or "").strip()[:2000]
        history = lexi.clean_history(request.POST.get("history"))
        error, status, reply = None, 200, None
        if not prompt:
            error, status = "Please type a question first.", 400
        elif not settings.GEMINI_API_KEY:
            error, status = "Lexi isn't configured yet. Please add GEMINI_API_KEY in your Vercel project settings.", 503
        elif not (throttle.allowed(throttle.key("lexi", request.user.pk), *LEXI_LIMIT_BURST)
                  and throttle.allowed(throttle.key("lexi-day", request.user.pk), *LEXI_LIMIT_DAY)):
            error, status = "You're asking very quickly. Take a short break and try again in a few minutes.", 429

        if error is None and request.POST.get("stream") == "1":
            try:
                upstream = lexi.open_stream(settings.GEMINI_API_KEY, history, prompt)
            except lexi.LexiError as exc:
                logging.getLogger(__name__).warning("Lexi call failed: %s", exc)
                error, status = "Lexi couldn't answer right now. Please try again.", 503
            else:
                out = StreamingHttpResponse(_lexi_chunks(upstream), content_type="text/plain; charset=utf-8")
                out["Cache-Control"] = "no-store"
                out["X-Accel-Buffering"] = "no"
                return out
        elif error is None:
            try:
                reply = lexi.answer(settings.GEMINI_API_KEY, history, prompt)
            except lexi.LexiError as exc:
                logging.getLogger(__name__).warning("Lexi call failed: %s", exc)
                error, status = "Lexi couldn't answer right now. Please try again.", 503

        if _is_ajax(request):
            if error:
                return JsonResponse({"ok": False, "error": error}, status=status)
            return JsonResponse({"ok": True, "reply": reply})
        ctx.update(
            chat_history=[{"role": "user", "text": prompt}, {"role": "model", "text": reply}] if reply else [],
            error=error,
        )
        return render(request, "dashboard/chatbot.html", ctx, status=status)

    return render(request, "dashboard/chatbot.html", ctx)


# --------------------------------------------------------------------------- error pages

def handler400(request, exception=None):
    return render(request, "400.html", status=400)


def handler403(request, exception=None):
    return render(request, "403.html", status=403)


def handler404(request, exception=None):
    return render(request, "404.html", status=404)


def handler500(request):
    return render(request, "500.html", status=500)
