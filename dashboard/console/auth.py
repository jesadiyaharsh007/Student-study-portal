from functools import wraps
from urllib.parse import quote

from django.core.cache import cache
from django.shortcuts import redirect
from django.urls import reverse

from . import tokens

MAX_ATTEMPTS = 5
LOCK_SECONDS = 300


def console_required(view):
    """Only signed-in staff get in. Expired access tokens are refreshed transparently (see tokens.py)."""

    @wraps(view)
    def wrapped(request, *args, **kwargs):
        result = tokens.authenticate(request)
        if not result.user:
            target = reverse("console:login")
            if request.method == "GET":
                target += "?next=" + quote(request.get_full_path())
            response = redirect(target)
            if result.clear:
                tokens.clear_cookies(response)
            return response
        request.console_user = result.user
        request._console_session = result.session
        response = view(request, *args, **kwargs)
        if result.set_cookies:
            tokens.set_cookies(response, request, result.set_cookies[0], result.set_cookies[1])
        response["Cache-Control"] = "private, no-store"
        response["X-Robots-Tag"] = "noindex, nofollow"
        return response

    return wrapped


# ---- brute-force protection for the login form (per IP + identifier, and per IP) ----

def _keys(ip, ident):
    return f"console-login:{ip}:{ident.lower()[:80]}", f"console-login-ip:{ip}"


def is_locked(ip, ident):
    a, b = _keys(ip, ident)
    return (cache.get(a, 0) >= MAX_ATTEMPTS) or (cache.get(b, 0) >= MAX_ATTEMPTS * 4)


def record_failure(ip, ident):
    for key in _keys(ip, ident):
        cache.add(key, 0, LOCK_SECONDS)
        try:
            cache.incr(key)
        except ValueError:
            cache.set(key, 1, LOCK_SECONDS)


def clear_failures(ip, ident):
    cache.delete(_keys(ip, ident)[0])
