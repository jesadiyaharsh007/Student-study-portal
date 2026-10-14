from datetime import timedelta

from django.contrib import admin
from django.contrib.admin.forms import AdminAuthenticationForm
from django.contrib.auth.models import User
from django.db.models import Count, Q
from django.utils import timezone


class StaffLoginForm(AdminAuthenticationForm):
    """Admin login form with the same widgets/classes as the student login."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["username"].widget.attrs.update({"class": "input", "placeholder": "Username", "autocomplete": "username", "autofocus": True})
        self.fields["password"].widget.attrs.update({"class": "input", "placeholder": "Password", "autocomplete": "current-password"})
        self.fields["username"].label = "Username"


class StudyAdminSite(admin.AdminSite):
    """Admin with an Overview dashboard (headline numbers, subjects, newest students)."""

    site_header = "Study Portal"
    site_title = "Study Portal Admin"
    index_title = "Overview"
    site_url = "/"
    login_form = StaffLoginForm
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
            disabled=Count("id", filter=Q(is_active=False)),
        )
        hw = Homework.objects.aggregate(
            total=Count("id"),
            done=Count("id", filter=Q(is_finished=True)),
            overdue=Count("id", filter=Q(is_finished=False, due__lt=now)),
            today=Count("id", filter=Q(is_finished=False, due__date=timezone.localdate(), due__gte=now)),
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

        attention = []
        if hw["overdue"]:
            attention.append({"tone": "bad", "icon": "alert", "count": hw["overdue"], "text": "homework overdue", "hint": "Students are past the deadline.", "url": "admin:dashboard_homework_changelist", "query": "?deadline=overdue"})
        if hw["today"]:
            attention.append({"tone": "warn", "icon": "clock", "count": hw["today"], "text": "homework due today", "hint": "Still open and due before midnight.", "url": "admin:dashboard_homework_changelist", "query": "?deadline=today"})
        if users["disabled"]:
            attention.append({"tone": "muted", "icon": "lock", "count": users["disabled"], "text": "disabled accounts", "hint": "These students cannot log in.", "url": "admin:auth_user_changelist", "query": "?account=disabled"})
        if users["week"]:
            attention.append({"tone": "info", "icon": "user-plus", "count": users["week"], "text": "new students this week", "hint": "Welcome them and check their accounts.", "url": "admin:auth_user_changelist", "query": "?role=student"})

        return {
            "ov_attention": attention,
            "ov_users": users,
            "ov_notes": notes_total,
            "ov_hw": {**hw, "open": hw["total"] - hw["done"]},
            "ov_todo": {**todo, "open": todo["total"] - todo["done"]},
            "ov_completion": round(tasks_done * 100 / tasks_total) if tasks_total else 0,
            "ov_subjects": [{"name": k, "count": v, "pct": round(v * 100 / peak)} for k, v in top],
            "ov_recent": recent,
        }
