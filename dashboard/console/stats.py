"""Read-only numbers for the admin console.

Everything here is a count or an account fact (username, email, active flag, dates). Note titles, note
text, homework descriptions and to-do wording are never loaded, so the console cannot show them.
"""
from datetime import timedelta

from django.contrib.auth.models import User
from django.db.models import Count, F, Q
from django.db.models.functions import TruncDate
from django.utils import timezone

from ..models import Homework, Notes, Todo


def students():
    """Student accounts only. Staff and admin accounts are not part of the people being tracked."""
    return User.objects.filter(is_staff=False, is_superuser=False)


def _pct_change(now_value, before):
    if before == 0:
        return None if now_value == 0 else 100
    return round((now_value - before) * 100 / before)


def overview(days):
    now = timezone.now()
    start_today = now.replace(hour=0, minute=0, second=0, microsecond=0)
    base = students()

    totals = base.aggregate(
        total=Count("id"),
        active=Count("id", filter=Q(is_active=True)),
        inactive=Count("id", filter=Q(is_active=False)),
        today=Count("id", filter=Q(date_joined__gte=start_today)),
        week=Count("id", filter=Q(date_joined__gte=now - timedelta(days=7))),
        month=Count("id", filter=Q(date_joined__gte=now - timedelta(days=30))),
        seen_week=Count("id", filter=Q(last_login__gte=now - timedelta(days=7))),
        never=Count("id", filter=Q(last_login__isnull=True)),
    )

    # sign-ups per day for the chart, gaps filled with zero
    since = start_today - timedelta(days=days - 1)
    rows = {
        r["d"]: r["n"]
        for r in base.filter(date_joined__gte=since)
        .annotate(d=TruncDate("date_joined")).values("d").annotate(n=Count("id")).order_by("d")
    }
    series = []
    for i in range(days):
        day = (since + timedelta(days=i)).date()
        series.append({"date": day, "n": rows.get(day, 0)})
    peak = max((p["n"] for p in series), default=0) or 1
    for p in series:
        p["h"] = round(p["n"] * 100 / peak) if p["n"] else 0
    in_range = sum(p["n"] for p in series)
    before = base.filter(date_joined__gte=since - timedelta(days=days), date_joined__lt=since).count()

    # how much content exists, in numbers only
    hw = Homework.objects.filter(user__is_staff=False).aggregate(total=Count("id"), done=Count("id", filter=Q(is_finished=True)))
    todo = Todo.objects.filter(user__is_staff=False).aggregate(total=Count("id"), done=Count("id", filter=Q(is_finished=True)))
    notes = Notes.objects.filter(user__is_staff=False).count()
    tasks_total = hw["total"] + todo["total"]
    tasks_done = hw["done"] + todo["done"]

    # engagement: how many students have created how much (counts only)
    buckets = {"none": 0, "light": 0, "regular": 0, "power": 0}
    counts = base.annotate(n=Count("notes", distinct=True) + Count("homework", distinct=True) + Count("todo", distinct=True)).values_list("n", flat=True)
    for n in counts:
        buckets["none" if n == 0 else "light" if n <= 5 else "regular" if n <= 15 else "power"] += 1
    total_students = totals["total"] or 1
    engagement = [
        {"label": "Nothing yet", "n": buckets["none"], "pct": round(buckets["none"] * 100 / total_students)},
        {"label": "1 to 5 items", "n": buckets["light"], "pct": round(buckets["light"] * 100 / total_students)},
        {"label": "6 to 15 items", "n": buckets["regular"], "pct": round(buckets["regular"] * 100 / total_students)},
        {"label": "16 or more", "n": buckets["power"], "pct": round(buckets["power"] * 100 / total_students)},
    ]

    recent = list(base.order_by("-date_joined").only("id", "username", "email", "date_joined", "last_login", "is_active")[:8])

    return {
        "totals": totals,
        "days": days,
        "series": series,
        "first_day": series[0]["date"],
        "last_day": series[-1]["date"],
        "in_range": in_range,
        "change": _pct_change(in_range, before),
        "content": {"notes": notes, "homework": hw, "todo": todo,
                    "completion": round(tasks_done * 100 / tasks_total) if tasks_total else 0},
        "engagement": engagement,
        "recent": recent,
    }


SORTS = {
    "newest": ("Newest first", ("-date_joined",)),
    "oldest": ("Oldest first", ("date_joined",)),
    "name": ("Username A to Z", ("username",)),
    "seen": ("Last sign-in", (F("last_login").desc(nulls_last=True), "-date_joined")),
}


def user_list(q="", status="", joined="", sort="newest"):
    qs = students().annotate(
        n_notes=Count("notes", distinct=True),
        n_homework=Count("homework", distinct=True),
        n_todos=Count("todo", distinct=True),
    ).only("id", "username", "email", "is_active", "date_joined", "last_login")
    if q:
        qs = qs.filter(Q(username__icontains=q) | Q(email__icontains=q))
    if status == "active":
        qs = qs.filter(is_active=True)
    elif status == "inactive":
        qs = qs.filter(is_active=False)
    if joined in ("7", "30", "90"):
        qs = qs.filter(date_joined__gte=timezone.now() - timedelta(days=int(joined)))
    return qs.order_by(*SORTS.get(sort, SORTS["newest"])[1])


def user_detail(pk):
    return (
        students().filter(pk=pk)
        .annotate(
            n_notes=Count("notes", distinct=True),
            n_homework=Count("homework", distinct=True),
            n_homework_done=Count("homework", distinct=True, filter=Q(homework__is_finished=True)),
            n_todos=Count("todo", distinct=True),
            n_todos_done=Count("todo", distinct=True, filter=Q(todo__is_finished=True)),
        )
        .only("id", "username", "email", "first_name", "last_name", "is_active", "date_joined", "last_login")
        .first()
    )
