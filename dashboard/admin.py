import csv
from datetime import timedelta

from django.contrib import admin, messages
from django.contrib.auth.admin import UserAdmin as DjangoUserAdmin
from django.contrib.auth.models import Group, User
from django.db.models import Count
from django.http import HttpResponse
from django.utils import timezone
from django.utils.html import format_html

from .models import Homework, Notes, Todo

# The portal has no use for groups or per-user permissions: access is just student / staff / admin.
admin.site.unregister(Group)


# --------------------------------------------------------------------------- helpers

def _safe_cell(value):
    """Neutralise spreadsheet formulas so an exported title can't run as one."""
    text = "" if value is None else str(value)
    return "'" + text if text[:1] in ("=", "+", "-", "@", "\t", "\r") else text


def csv_export(filename, columns):
    """Build an admin action that downloads the selected rows as CSV. columns: [(header, callable(obj))]."""

    @admin.action(description="Export selected to CSV")
    def action(modeladmin, request, queryset):
        response = HttpResponse(content_type="text/csv; charset=utf-8")
        response["Content-Disposition"] = f'attachment; filename="{filename}-{timezone.now():%Y%m%d}.csv"'
        response.write("﻿")  # BOM so Excel reads UTF-8
        writer = csv.writer(response)
        writer.writerow([h for h, _ in columns])
        for obj in queryset.iterator():
            writer.writerow([_safe_cell(fn(obj)) for _, fn in columns])
        return response

    return action


def pill(text, tone):
    return format_html('<span class="sd-pill sd-{}">{}</span>', tone, text)


class DueFilter(admin.SimpleListFilter):
    title = "deadline"
    parameter_name = "deadline"

    def lookups(self, request, model_admin):
        return (("overdue", "Overdue"), ("today", "Due today"), ("week", "Next 7 days"))

    def queryset(self, request, queryset):
        now = timezone.now()
        value = self.value()
        if value == "overdue":
            return queryset.filter(is_finished=False, due__lt=now)
        if value == "today":
            return queryset.filter(due__date=timezone.localdate())
        if value == "week":
            return queryset.filter(is_finished=False, due__gte=now, due__lt=now + timedelta(days=7))
        return queryset


class StatusFilter(admin.SimpleListFilter):
    title = "status"
    parameter_name = "state"

    def lookups(self, request, model_admin):
        return (("open", "Open"), ("done", "Done"))

    def queryset(self, request, queryset):
        if self.value() == "open":
            return queryset.filter(is_finished=False)
        if self.value() == "done":
            return queryset.filter(is_finished=True)
        return queryset


class AccountFilter(admin.SimpleListFilter):
    title = "account"
    parameter_name = "account"

    def lookups(self, request, model_admin):
        return (("active", "Active"), ("disabled", "Disabled"))

    def queryset(self, request, queryset):
        if self.value() == "active":
            return queryset.filter(is_active=True)
        if self.value() == "disabled":
            return queryset.filter(is_active=False)
        return queryset


class RoleFilter(admin.SimpleListFilter):
    title = "role"
    parameter_name = "role"

    def lookups(self, request, model_admin):
        return (("student", "Students"), ("staff", "Staff"), ("admin", "Admins"))

    def queryset(self, request, queryset):
        if self.value() == "student":
            return queryset.filter(is_staff=False)
        if self.value() == "staff":
            return queryset.filter(is_staff=True, is_superuser=False)
        if self.value() == "admin":
            return queryset.filter(is_superuser=True)
        return queryset


class ContentAdmin(admin.ModelAdmin):
    """Shared behaviour for student-created content: admins review and moderate, students create.

    No "Add" here (students write their own notes, homework and to-dos on the site), no facet counts,
    and a single Save button. Hints appear under the page title (see admin/base_site.html).
    """

    list_hint = ""
    form_hint = ""
    show_facets = admin.ShowFacets.NEVER
    list_select_related = ("user",)
    autocomplete_fields = ("user",)
    list_per_page = 20
    actions_on_bottom = False

    def has_add_permission(self, request):
        return False

    def changelist_view(self, request, extra_context=None):
        return super().changelist_view(request, {"sd_hint": self.list_hint, **(extra_context or {})})

    def changeform_view(self, request, object_id=None, form_url="", extra_context=None):
        return super().changeform_view(request, object_id, form_url, {"sd_hint": self.form_hint, **(extra_context or {})})


class FinishActionsMixin:
    @admin.action(description="Mark selected as done")
    def mark_done(self, request, queryset):
        n = queryset.update(is_finished=True)
        self.message_user(request, f"{n} marked as done.", messages.SUCCESS)

    @admin.action(description="Mark selected as not done")
    def mark_pending(self, request, queryset):
        n = queryset.update(is_finished=False)
        self.message_user(request, f"{n} marked as not done.", messages.SUCCESS)


# --------------------------------------------------------------------------- content

@admin.register(Notes)
class NotesAdmin(ContentAdmin):
    list_hint = "Notes students have written. Search by title, text or student, filter by subject, or select rows to export."
    form_hint = "Review or correct a note. Changes show on the student's Notes page straight away."
    search_help_text = "Search title, note text or student username."
    list_display = ("title", "user", "subject_pill", "words")
    list_display_links = ("title",)
    list_filter = ("subject",)
    search_fields = ("title", "description", "user__username")
    ordering = ("-id",)
    actions = [csv_export("notes", [
        ("ID", lambda o: o.pk), ("Student", lambda o: o.user.username), ("Subject", lambda o: o.subject),
        ("Title", lambda o: o.title), ("Note", lambda o: o.description),
    ])]
    fields = ("user", "subject", "title", "description")

    @admin.display(description="Subject", ordering="subject")
    def subject_pill(self, obj):
        return pill(obj.subject, "info")

    @admin.display(description="Words")
    def words(self, obj):
        return len(obj.description.split())


@admin.register(Homework)
class HomeworkAdmin(FinishActionsMixin, ContentAdmin):
    list_hint = "Assignments with deadlines. Filter by deadline to find what is overdue or due today; tick the box to mark one done."
    form_hint = "Changing the due date or finished state updates the student's Homework page and progress ring."
    search_help_text = "Search title, description or student username."
    list_display = ("title", "user", "subject_pill", "due", "state", "is_finished")
    list_display_links = ("title",)
    list_editable = ("is_finished",)
    list_filter = (DueFilter, StatusFilter, "subject")
    search_fields = ("title", "description", "user__username")
    ordering = ("is_finished", "due")
    actions = ["mark_done", "mark_pending", csv_export("homework", [
        ("ID", lambda o: o.pk), ("Student", lambda o: o.user.username), ("Subject", lambda o: o.subject),
        ("Title", lambda o: o.title), ("Due", lambda o: o.due.isoformat()), ("Finished", lambda o: o.is_finished),
        ("Description", lambda o: o.description),
    ])]
    fields = ("user", "subject", "title", "description", "due", "is_finished")

    @admin.display(description="Subject", ordering="subject")
    def subject_pill(self, obj):
        return pill(obj.subject, "info")

    @admin.display(description="Status")
    def state(self, obj):
        if obj.is_finished:
            return pill("Done", "ok")
        if obj.due < timezone.now():
            return pill("Overdue", "bad")
        if obj.due.date() == timezone.localdate():
            return pill("Due today", "warn")
        return pill("Upcoming", "muted")


@admin.register(Todo)
class TodoAdmin(FinishActionsMixin, ContentAdmin):
    list_hint = "Quick tasks. Tick the box to mark one done, or select rows to bulk update or export."
    form_hint = "A to-do is just a title and a finished state."
    search_help_text = "Search task title or student username."
    list_display = ("title", "user", "is_finished")
    list_display_links = ("title",)
    list_editable = ("is_finished",)
    list_filter = (StatusFilter,)
    search_fields = ("title", "user__username")
    list_per_page = 30
    ordering = ("is_finished", "-id")
    actions = ["mark_done", "mark_pending", csv_export("todos", [
        ("ID", lambda o: o.pk), ("Student", lambda o: o.user.username), ("Task", lambda o: o.title),
        ("Finished", lambda o: o.is_finished),
    ])]
    fields = ("user", "title", "is_finished")


# --------------------------------------------------------------------------- students

admin.site.unregister(User)


@admin.register(User)
class StudentAdmin(DjangoUserAdmin):
    show_facets = admin.ShowFacets.NEVER
    search_help_text = "Search username, email or name."
    list_display = ("student", "role", "active_pill", "activity", "joined")
    list_display_links = ("student",)
    list_filter = (RoleFilter, AccountFilter)
    search_fields = ("username", "email", "first_name", "last_name")
    list_per_page = 20
    ordering = ("-date_joined",)
    actions_on_bottom = False
    actions = ["activate", "deactivate", csv_export("students", [
        ("ID", lambda o: o.pk), ("Username", lambda o: o.username), ("Email", lambda o: o.email),
        ("Name", lambda o: o.get_full_name()), ("Staff", lambda o: o.is_staff), ("Active", lambda o: o.is_active),
        ("Joined", lambda o: o.date_joined.isoformat()),
    ])]
    # No groups / per-user permissions: keep the form to what an admin actually decides.
    fieldsets = (
        ("Account", {"fields": ("username", "password")}),
        ("Personal info", {"fields": ("first_name", "last_name", "email")}),
        ("Access", {"fields": ("is_active", "is_staff", "is_superuser"),
                    "description": "Active lets them log in. Staff lets them open this admin. Admin can do everything."}),
        ("Activity", {"fields": ("last_login", "date_joined")}),
    )
    readonly_fields = ("last_login", "date_joined")
    add_fieldsets = (
        ("Create a student", {"classes": ("wide",), "fields": ("username", "password1", "password2")}),
    )
    list_hint = "Everyone who can sign in. Counts show what each student has created. Disabled accounts cannot log in but keep their data."
    form_hint = "Use Active to allow or block login. Only give Staff to people who should reach this admin."

    def changelist_view(self, request, extra_context=None):
        return super().changelist_view(request, {"sd_hint": self.list_hint, "title": "Students", **(extra_context or {})})

    def changeform_view(self, request, object_id=None, form_url="", extra_context=None):
        title = "Edit student" if object_id else "Add student"
        extra_context = dict(extra_context or {})
        if object_id and str(object_id).isdigit():
            uid = int(object_id)
            extra_context["sd_activity"] = {
                "notes": list(Notes.objects.filter(user_id=uid).order_by("-id").only("id", "title", "subject")[:4]),
                "homework": list(Homework.objects.filter(user_id=uid).order_by("is_finished", "due").only("id", "title", "due", "is_finished")[:4]),
                "todos": list(Todo.objects.filter(user_id=uid).order_by("is_finished", "-id").only("id", "title", "is_finished")[:4]),
                "n_notes": Notes.objects.filter(user_id=uid).count(),
                "n_homework": Homework.objects.filter(user_id=uid).count(),
                "n_todos": Todo.objects.filter(user_id=uid).count(),
            }
        return super().changeform_view(request, object_id, form_url, {"sd_hint": self.form_hint if object_id else "Choose a username and password. You can set their details and access after saving.", "title": title, **(extra_context or {})})

    def get_queryset(self, request):
        return super().get_queryset(request).annotate(
            _notes=Count("notes", distinct=True),
            _homework=Count("homework", distinct=True),
            _todos=Count("todo", distinct=True),
        )

    @admin.display(description="Student", ordering="username")
    def student(self, obj):
        return format_html(
            '<span class="sd-user"><span class="avatar">{}</span><span><b>{}</b><small>{}</small></span></span>',
            (obj.username[:1] or "?").upper(), obj.username, obj.email or obj.get_full_name() or "No email",
        )

    @admin.display(description="Activity")
    def activity(self, obj):
        def chip(n, one, many):
            return format_html('<span class="sd-chip{}">{} {}</span>', "" if n else " zero", n, one if n == 1 else many)
        return format_html(
            "{}{}{}",
            chip(obj._notes, "note", "notes"), chip(obj._homework, "homework", "homework"), chip(obj._todos, "to-do", "to-dos"),
        )

    @admin.display(description="Joined", ordering="date_joined")
    def joined(self, obj):
        return obj.date_joined.strftime("%b %d, %Y").replace(" 0", " ")

    @admin.display(description="Role", ordering="is_staff")
    def role(self, obj):
        if obj.is_superuser:
            return pill("Admin", "bad")
        return pill("Staff", "warn") if obj.is_staff else pill("Student", "muted")

    @admin.display(description="Status", ordering="is_active")
    def active_pill(self, obj):
        return pill("Active", "ok") if obj.is_active else pill("Disabled", "bad")

    @admin.display(description="Notes", ordering="_notes")
    def notes_n(self, obj):
        return obj._notes

    @admin.display(description="Homework", ordering="_homework")
    def homework_n(self, obj):
        return obj._homework

    @admin.display(description="To-dos", ordering="_todos")
    def todos_n(self, obj):
        return obj._todos

    @admin.action(description="Activate selected accounts")
    def activate(self, request, queryset):
        n = queryset.update(is_active=True)
        self.message_user(request, f"{n} account(s) activated.", messages.SUCCESS)

    @admin.action(description="Disable selected accounts")
    def deactivate(self, request, queryset):
        safe = queryset.exclude(pk=request.user.pk)
        n = safe.update(is_active=False)
        if safe.count() != queryset.count():
            self.message_user(request, "Your own account was left active.", messages.WARNING)
        self.message_user(request, f"{n} account(s) disabled.", messages.SUCCESS)
