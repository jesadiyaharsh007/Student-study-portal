from urllib.parse import urlencode

from django.contrib.auth import authenticate
from django.contrib.auth.models import User
from django.core.paginator import Paginator
from django.db import DatabaseError
from django.db.models import Q
from django.http import Http404
from django.shortcuts import redirect, render
from django.urls import reverse
from django.utils import timezone
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_POST, require_safe

from ..models import AdminSession
from . import stats, tokens
from .auth import MAX_ATTEMPTS, clear_failures, console_required, is_locked, record_failure


def _safe_next(request):
    target = request.POST.get("next") or request.GET.get("next") or ""
    if target.startswith("/console/") and url_has_allowed_host_and_scheme(target, {request.get_host()}, request.is_secure()):
        return target
    return reverse("console:overview")


# --------------------------------------------------------------------------- sign in / out

@never_cache
def login_view(request):
    existing = tokens.authenticate(request)
    if existing.user:
        response = redirect(_safe_next(request))
        if existing.set_cookies:
            tokens.set_cookies(response, request, existing.set_cookies[0], existing.set_cookies[1])
        return response

    error, status, ident = "", 200, ""
    if request.method == "POST":
        ident = (request.POST.get("username") or "").strip()[:150]
        password = request.POST.get("password") or ""
        ip, _ = tokens._client(request)
        if is_locked(ip, ident):
            error, status = "Too many attempts. Please wait a few minutes and try again.", 429
        else:
            match = User.objects.filter(Q(email__iexact=ident) | Q(username__iexact=ident)).only("username").first() if ident else None
            user = authenticate(request, username=match.username if match else ident, password=password) if ident and password else None
            if user and user.is_staff and user.is_active:
                try:
                    access, refresh, _session = tokens.start_session(request, user)
                except DatabaseError:
                    error, status = "The console is not fully set up yet: the database needs its latest migration (python manage.py migrate).", 503
                else:
                    clear_failures(ip, ident)
                    response = redirect(_safe_next(request))
                    tokens.set_cookies(response, request, access, refresh)
                    return response
            else:
                record_failure(ip, ident)
                error = "That username or password is not right, or the account is not allowed in the console."
    response = render(request, "console/login.html", {"error": error, "ident": ident, "next": request.GET.get("next", ""), "max_attempts": MAX_ATTEMPTS}, status=status)
    if tokens.REFRESH_COOKIE in request.COOKIES or tokens.ACCESS_COOKIE in request.COOKIES:
        if not existing.user:
            tokens.clear_cookies(response)
    return response


@require_POST
def logout_view(request):
    session = tokens.current_session(request)
    tokens.revoke(session)
    response = redirect("console:login")
    tokens.clear_cookies(response)
    return response


# --------------------------------------------------------------------------- pages

def _page(request, **ctx):
    ctx["me"] = request.console_user
    return ctx


@console_required
@require_safe
def overview(request):
    days = {"7": 7, "30": 30, "90": 90}.get(request.GET.get("range", "30"), 30)
    return render(request, "console/overview.html", _page(request, nav="overview", **stats.overview(days)))


@console_required
@require_safe
def users(request):
    q = (request.GET.get("q") or "").strip()[:100]
    status = request.GET.get("status", "")
    joined = request.GET.get("joined", "")
    sort = request.GET.get("sort", "newest")
    if sort not in stats.SORTS:
        sort = "newest"
    page = Paginator(stats.user_list(q, status, joined, sort), 15).get_page(request.GET.get("page"))
    keep = {k: v for k, v in {"q": q, "status": status, "joined": joined, "sort": sort if sort != "newest" else ""}.items() if v}
    return render(request, "console/users.html", _page(
        request, nav="users", page=page, q=q, status=status, joined=joined, sort=sort, sorts=stats.SORTS,
        base_qs=urlencode(keep), total=page.paginator.count,
    ))


@console_required
@require_safe
def user_detail(request, pk):
    person = stats.user_detail(pk)
    if person is None:
        raise Http404("No such student")
    tasks = person.n_homework + person.n_todos
    done = person.n_homework_done + person.n_todos_done
    return render(request, "console/user_detail.html", _page(
        request, nav="users", person=person, completion=round(done * 100 / tasks) if tasks else 0,
        tasks=tasks, done=done, back=request.GET.get("back", ""),
    ))


@console_required
def security(request):
    now = timezone.now()
    if request.method == "POST":
        action = request.POST.get("action")
        here = tokens.current_session(request)
        if action == "revoke_others" and here:
            tokens.revoke_all(request.console_user, keep=here)
        elif action == "revoke_one":
            AdminSession.objects.filter(pk=request.POST.get("id") or 0, user=request.console_user, revoked_at__isnull=True).exclude(pk=getattr(here, "pk", 0)).update(revoked_at=now)
        return redirect("console:security")
    here = tokens.current_session(request)
    rows = AdminSession.objects.filter(user=request.console_user, revoked_at__isnull=True, expires_at__gt=now).order_by("-last_used_at")
    sessions = [{"s": s, "here": bool(here and s.pk == here.pk), "device": _device(s.user_agent)} for s in rows]
    return render(request, "console/security.html", _page(
        request, nav="security", sessions=sessions, access_minutes=tokens.ACCESS_TTL // 60, refresh_days=tokens.REFRESH_TTL // 86400,
    ))


def _device(agent):
    a = (agent or "").lower()
    browser = "Edge" if "edg/" in a else "Opera" if "opr/" in a else "Chrome" if "chrome" in a else "Firefox" if "firefox" in a else "Safari" if "safari" in a else "Browser"
    system = "Windows" if "windows" in a else "Android" if "android" in a else "iPhone" if "iphone" in a else "iPad" if "ipad" in a else "Mac" if "mac os" in a else "Linux" if "linux" in a else "Unknown device"
    return f"{browser} on {system}"
