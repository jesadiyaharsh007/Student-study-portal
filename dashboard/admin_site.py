from datetime import timedelta

from django.contrib import admin
from django.contrib.auth.models import User
from django.db.models import Count, Q
from django.utils import timezone


class StudyAdminSite(admin.AdminSite):
    """Admin with an Overview dashboard (headline numbers, subjects, newest students)."""

    site_header = "Study Portal"
    site_title = "Study Portal Admin"
    index_title = "Overview"
    site_url = "/"
    enable_nav_sidebar = False  # navigation lives in the header pills instead

    def index(self, request, extra_context=None):
        context = {**(extra_context or {}), **self._overview()}
        return super().index(request, context)

    def _overview(self):
        from .models import Homework, Notes, Todo

        now = timezone.now()
        week_ago = now - timedelta(days=7)

        users = User.objects.aggregate(
            total=Count("id"),
            week=Count("id", filter=Q(date_joined__gte=week_ago)),
            staff=Count("id", filter=Q(is_staff=True)),
        )
        hw = Homework.objects.aggregate(
            total=Count("id"),
            done=Count("id", filter=Q(is_finished=True)),
            overdue=Count("id", filter=Q(is_finished=False, due__lt=now)),
        )
        todo = Todo.objects.aggregate(total=Count("id"), done=Count("id", filter=Q(is_finished=True)))
        notes_total = Notes.objects.count()

        subjects = {}
        for model in (Notes, Homework):
            for row in model.objects.values("subject").annotate(n=Count("id")):
                subjects[row["subject"]] = subjects.get(row["subject"], 0) + row["n"]
        top = sorted(subjects.items(), key=lambda kv: -kv[1])[:6]
        peak = top[0][1] if top else 1

        tasks_total = hw["total"] + todo["total"]
        tasks_done = hw["done"] + todo["done"]
        recent = list(User.objects.order_by("-date_joined").only("id", "username", "email", "date_joined", "is_staff")[:5])

        return {
            "ov_users": users,
            "ov_notes": notes_total,
            "ov_hw": {**hw, "open": hw["total"] - hw["done"]},
            "ov_todo": {**todo, "open": todo["total"] - todo["done"]},
            "ov_completion": round(tasks_done * 100 / tasks_total) if tasks_total else 0,
            "ov_subjects": [{"name": k, "count": v, "pct": round(v * 100 / peak)} for k, v in top],
            "ov_recent": recent,
        }
