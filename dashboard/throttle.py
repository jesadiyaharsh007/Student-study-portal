"""Fixed-window rate limits stored in the database, so every serverless instance shares the same counts.

    if not throttle.allowed("lexi:42", limit=30, window=600): ...   # counts this attempt
    if throttle.blocked("login:...", 5, 900): ...                    # only looks
"""
import functools
import hashlib
import logging
import random
from datetime import timedelta

from django.db import DatabaseError, IntegrityError, transaction
from django.db.models import F
from django.utils import timezone

from .models import Throttle


def _fail_open(default):
    """If the counters' table is unreachable (e.g. a deploy whose migration did not run), log it and let the
    request through rather than breaking sign-in or Lexi for everyone."""
    def wrap(fn):
        @functools.wraps(fn)
        def inner(*args, **kwargs):
            try:
                return fn(*args, **kwargs)
            except DatabaseError:
                logging.getLogger(__name__).exception("rate limit table unavailable")
                return default
        return inner
    return wrap


def key(kind, value):
    """A short, fixed-length key: names and addresses are hashed, never stored as typed."""
    return f"{kind}:" + hashlib.sha256(str(value).encode("utf-8")).hexdigest()[:40]


def client_ip(request):
    # Vercel puts the real visitor address in x-real-ip; locally there is only REMOTE_ADDR.
    return (request.headers.get("x-real-ip") or request.META.get("REMOTE_ADDR") or "").strip()[:64]


def _sweep():
    """Now and then, drop counters nobody has touched for a day."""
    if random.random() < 0.02:
        Throttle.objects.filter(window_start__lt=timezone.now() - timedelta(days=1)).delete()


@_fail_open(False)
def blocked(k, limit, window):
    row = Throttle.objects.filter(key=k).only("window_start", "count").first()
    return bool(row and row.window_start >= timezone.now() - timedelta(seconds=window) and row.count >= limit)


@_fail_open(True)
def allowed(k, limit, window):
    """Count one attempt. False when the limit for the current window is already used up."""
    now = timezone.now()
    with transaction.atomic():
        row = Throttle.objects.select_for_update().filter(key=k).first()
        if row is None:
            try:
                with transaction.atomic():
                    Throttle.objects.create(key=k, window_start=now, count=1)
                _sweep()
                return True
            except IntegrityError:                      # another request created it first
                row = Throttle.objects.select_for_update().get(key=k)
        if row.window_start < now - timedelta(seconds=window):
            row.window_start, row.count = now, 1
            row.save(update_fields=["window_start", "count"])
            return True
        if row.count >= limit:
            return False
        Throttle.objects.filter(pk=row.pk).update(count=F("count") + 1)
        return True


@_fail_open(None)
def reset(k):
    Throttle.objects.filter(key=k).delete()
