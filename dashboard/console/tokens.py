"""Sign-in for the admin console: short-lived access token + rotating refresh token.

Both tokens live in HttpOnly cookies scoped to /admin/, so they are independent of the student
site's session (signing in to one never signs you out of the other).

* Access token  - signed, stateless, valid ACCESS_TTL seconds. Checked on every request without a DB hit.
* Refresh token - signed, backed by an AdminSession row, valid REFRESH_TTL seconds from its last use
                  (sliding), never longer than ABSOLUTE_TTL since the chain started.
                  Every use rotates it: the old row is revoked and a new one issued. Replaying a revoked
                  token (other than a parallel request within GRACE seconds) revokes all the user's
                  sessions, because it means a copy of the cookie is in circulation.
"""
import hashlib
import secrets
import threading
from dataclasses import dataclass
from datetime import timedelta

from django.contrib.auth.models import User
from django.core import signing
from django.db import DatabaseError, connection
from django.utils import timezone

from ..models import AdminSession

ACCESS_TTL = 15 * 60
REFRESH_TTL = 14 * 24 * 3600
ABSOLUTE_TTL = 30 * 24 * 3600
GRACE = 15  # seconds: parallel requests may present a token that was rotated a moment ago

ACCESS_COOKIE = "sd_at"
REFRESH_COOKIE = "sd_rt"
COOKIE_PATH = "/admin/"

_ACCESS_SALT = "console.access.v1"
_REFRESH_SALT = "console.refresh.v1"


@dataclass
class Result:
    user: User | None = None
    session: AdminSession | None = None
    set_cookies: tuple | None = None  # (access, refresh, session) when tokens were (re)issued
    clear: bool = False               # cookies are no good: remove them


_schema_lock = threading.Lock()
_TABLE = AdminSession._meta.db_table


def ensure_schema():
    """Create the console's table on first use if the database has not been migrated yet.

    Makes the console work out of the box on a fresh checkout or a freshly deployed database,
    with no manual `migrate` step. Returns True when the table is there.
    """
    with _schema_lock:
        try:
            if _TABLE in connection.introspection.table_names():
                return True
            from django.core.management import call_command

            call_command("migrate", "dashboard", interactive=False, verbosity=0)
        except Exception:  # another instance may be creating it at the same moment
            pass
        try:
            return _TABLE in connection.introspection.table_names()
        except DatabaseError:
            return False


def _fingerprint(user):
    """Changes whenever the password changes, which invalidates outstanding access tokens."""
    return hashlib.sha256((user.password or "").encode()).hexdigest()[:16]


def _eligible(user):
    return bool(user and user.is_active and user.is_staff)


def make_access(user):
    return signing.dumps({"u": user.pk, "f": _fingerprint(user)}, salt=_ACCESS_SALT, compress=False)


def _make_refresh(session):
    return signing.dumps({"u": session.user_id, "j": session.jti}, salt=_REFRESH_SALT, compress=False)


def _client(request):
    forwarded = request.META.get("HTTP_X_FORWARDED_FOR", "")
    ip = forwarded.split(",")[0].strip() if forwarded else request.META.get("REMOTE_ADDR", "")
    return ip or None, (request.META.get("HTTP_USER_AGENT", "") or "")[:255]


def start_session(request, user, origin=None):
    """Create a refresh-token row; returns (access_token, refresh_token, session)."""
    now = timezone.now()
    origin = origin or now
    expires = min(now + timedelta(seconds=REFRESH_TTL), origin + timedelta(seconds=ABSOLUTE_TTL))
    ip, agent = _client(request)
    try:
        ip_value = ip if ip else None
        session = AdminSession.objects.create(
            jti=secrets.token_urlsafe(24), user=user, created_at=now, last_used_at=now,
            expires_at=expires, origin_at=origin, user_agent=agent, ip=ip_value,
        )
    except Exception:  # an unparsable proxy header must not block sign-in
        session = AdminSession.objects.create(
            jti=secrets.token_urlsafe(24), user=user, created_at=now, last_used_at=now,
            expires_at=expires, origin_at=origin, user_agent=agent,
        )
    return make_access(user), _make_refresh(session), session


def revoke_all(user, keep=None):
    qs = AdminSession.objects.filter(user=user, revoked_at__isnull=True)
    if keep is not None:
        qs = qs.exclude(pk=keep.pk)
    return qs.update(revoked_at=timezone.now())


def revoke(session):
    if session and session.revoked_at is None:
        AdminSession.objects.filter(pk=session.pk, revoked_at__isnull=True).update(revoked_at=timezone.now())


def _load_user(uid):
    from ..auth_backend import CachedUserBackend  # in-memory cache first, DB on a miss

    return CachedUserBackend().get_user(uid)


def _refresh_row(request):
    raw = request.COOKIES.get(REFRESH_COOKIE)
    if not raw:
        return None
    try:
        data = signing.loads(raw, salt=_REFRESH_SALT, max_age=REFRESH_TTL + 60)
    except signing.BadSignature:
        return None
    try:
        return AdminSession.objects.select_related("user").filter(jti=data.get("j"), user_id=data.get("u")).first()
    except DatabaseError:  # table not created yet: treat as signed out; sign-in will create it
        return None


def authenticate(request):
    """Resolve the console user for a request, refreshing the tokens when the access token ran out."""
    # 1. a valid access token is enough (no database work)
    raw = request.COOKIES.get(ACCESS_COOKIE)
    if raw:
        try:
            data = signing.loads(raw, salt=_ACCESS_SALT, max_age=ACCESS_TTL)
        except signing.BadSignature:
            data = None
        if data:
            user = _load_user(data.get("u"))
            if _eligible(user) and data.get("f") == _fingerprint(user):
                return Result(user=user, session=getattr(request, "_console_session", None))

    # 2. otherwise exchange the refresh token for a new pair
    row = _refresh_row(request)
    if not row:
        return Result(clear=bool(raw or request.COOKIES.get(REFRESH_COOKIE)))
    now = timezone.now()
    user = row.user
    if not _eligible(user):
        return Result(clear=True)

    if row.revoked_at is not None:
        # A parallel request that raced the rotation is fine; a later replay means the cookie was copied.
        if row.replaced_by and (now - row.revoked_at).total_seconds() <= GRACE:
            return Result(user=user, session=row)
        revoke_all(user)
        return Result(clear=True)

    if row.expires_at <= now or row.origin_at + timedelta(seconds=ABSOLUTE_TTL) <= now:
        return Result(clear=True)

    # rotate: only one concurrent caller wins the conditional update
    successor = secrets.token_urlsafe(24)
    won = AdminSession.objects.filter(pk=row.pk, revoked_at__isnull=True).update(
        revoked_at=now, replaced_by=successor, last_used_at=now
    )
    if not won:
        return Result(user=user, session=row)
    expires = min(now + timedelta(seconds=REFRESH_TTL), row.origin_at + timedelta(seconds=ABSOLUTE_TTL))
    ip, agent = _client(request)
    fresh = AdminSession(
        jti=successor, user=user, created_at=now, last_used_at=now, expires_at=expires,
        origin_at=row.origin_at, user_agent=agent or row.user_agent, ip=row.ip,
    )
    try:
        fresh.ip = ip or row.ip
        fresh.save()
    except Exception:
        fresh.ip = row.ip
        fresh.save()
    return Result(user=user, session=fresh, set_cookies=(make_access(user), _make_refresh(fresh), fresh))


def set_cookies(response, request, access, refresh):
    secure = request.is_secure()
    common = {"httponly": True, "samesite": "Lax", "secure": secure, "path": COOKIE_PATH}
    response.set_cookie(ACCESS_COOKIE, access, max_age=ACCESS_TTL, **common)
    response.set_cookie(REFRESH_COOKIE, refresh, max_age=REFRESH_TTL, **common)


def clear_cookies(response):
    response.delete_cookie(ACCESS_COOKIE, path=COOKIE_PATH)
    response.delete_cookie(REFRESH_COOKIE, path=COOKIE_PATH)


def current_session(request):
    """The AdminSession of the refresh cookie on this request, if any (used to mark 'this device')."""
    row = _refresh_row(request)
    return row if row and row.revoked_at is None else getattr(request, "_console_session", None)
