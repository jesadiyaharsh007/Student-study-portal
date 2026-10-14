import csv

from django.contrib import admin, messages
from django.contrib.auth.admin import UserAdmin as DjangoUserAdmin
from django.contrib.auth.models import User
from django.db.models import Count
from datetime import timedelta

from django.http import HttpResponse
from django.utils import timezone
from django.utils.html import format_html

from .models import Homework, Notes, Todo


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
        return (
            ("overdue", "Overdue"),
            ("today", "Due today"),
            ("week", "Next 7 days"),
        )

    def queryset(self, request, queryset):
        now = timezone.now()
        today = timezone.localdate()
        value = self.value()
        if value == "overdue":
            return queryset.filter(is_finished=False, due__lt=now)
        if value == "today":
            return queryset.filter(due__date=today)
        if value == "week":
            return queryset.filter(is_finished=False, due__gte=now, due__lt=now + timedelta(days=7))
        return queryset


class FinishActionsMixin:
    @admin.action(description="Mark selected as done")
    def mark_done(self, request, queryset):
        n = queryset.update(is_finished=True)
        self.message_user(request, f"{n} marked as done.", messages.SUCCESS)

    @admin.action(description="Mark selected as not done")
    def mark_pending(self, request, queryset):
        n = queryset.update(is_finished=False)
        self.message_user(request, f"{n} marked as not done.", messages.SUCCESS)


# --------------------------------------------------------------------------- models

@admin.register(Notes)
class NotesAdmin(admin.ModelAdmin):
    list_display = ("title", "user", "subject_pill", "words")
    list_display_links = ("title",)
    list_filter = ("subject", "user")
    search_fields = ("title", "description", "user__username")
    list_select_related = ("user",)
    autocomplete_fields = ("user",)
    list_per_page = 25
    ordering = ("-id",)
    save_on_top = True
    actions = [csv_export("notes", [
        ("ID", lambda o: o.pk), ("Student", lambda o: o.user.username), ("Subject", lambda o: o.subject),
        ("Title", lambda o: o.title), ("Note", lambda o: o.description),
    ])]
    fieldsets = (
        (None, {"fields": ("user", "subject", "title")}),
        ("Content", {"fields": ("description",)}),
    )

    @admin.display(description="Subject", ordering="subject")
    def subject_pill(self, obj):
        return pill(obj.subject, "info")

    @admin.display(description="Words")
    def words(self, obj):
        return len(obj.description.split())


@admin.register(Homework)
class HomeworkAdmin(FinishActionsMixin, admin.ModelAdmin):
    list_display = ("title", "user", "subject_pill", "due", "state", "is_finished")
    list_display_links = ("title",)
    list_editable = ("is_finished",)
    list_filter = ("is_finished", DueFilter, "subject", "user")
    search_fields = ("title", "description", "user__username")
    list_select_related = ("user",)
    autocomplete_fields = ("user",)
    date_hierarchy = "due"
    list_per_page = 25
    ordering = ("is_finished", "due")
    save_on_top = True
    actions = ["mark_done", "mark_pending", csv_export("homework", [
        ("ID", lambda o: o.pk), ("Student", lambda o: o.user.username), ("Subject", lambda o: o.subject),
        ("Title", lambda o: o.title), ("Due", lambda o: o.due.isoformat()), ("Finished", lambda o: o.is_finished),
        ("Description", lambda o: o.description),
    ])]
    fieldsets = (
        (None, {"fields": ("user", "subject", "title", "description")}),
        ("Deadline", {"fields": ("due", "is_finished")}),
    )

    @admin.display(description="Subject", ordering="subject")
    def subject_pill(self, obj):
        return pill(obj.subject, "info")

    @admin.display(description="Status")
    def state(self, obj):
        if obj.is_finished:
            return pill("Done", "ok")
        now = timezone.now()
        if obj.due < now:
            return pill("Overdue", "bad")
        if obj.due.date() == timezone.localdate():
            return pill("Due today", "warn")
        return pill("Upcoming", "muted")


@admin.register(Todo)
class TodoAdmin(FinishActionsMixin, admin.ModelAdmin):
    list_display = ("title", "user", "is_finished")
    list_display_links = ("title",)
    list_editable = ("is_finished",)
    list_filter = ("is_finished", "user")
    search_fields = ("title", "user__username")
    list_select_related = ("user",)
    autocomplete_fields = ("user",)
    list_per_page = 50
    ordering = ("is_finished", "-id")
    actions = ["mark_done", "mark_pending", csv_export("todos", [
        ("ID", lambda o: o.pk), ("Student", lambda o: o.user.username), ("Task", lambda o: o.title),
        ("Finished", lambda o: o.is_finished),
    ])]


# --------------------------------------------------------------------------- users

admin.site.unregister(User)


@admin.register(User)
class StudentAdmin(DjangoUserAdmin):
    list_display = ("username", "email", "full_name", "role", "active_pill", "notes_n", "homework_n", "todos_n", "date_joined", "last_login")
    list_filter = ("is_staff", "is_active", "is_superuser", "date_joined")
    search_fields = ("username", "email", "first_name", "last_name")
    date_hierarchy = "date_joined"
    list_per_page = 25
    ordering = ("-date_joined",)
    actions = ["activate", "deactivate", csv_export("students", [
        ("ID", lambda o: o.pk), ("Username", lambda o: o.username), ("Email", lambda o: o.email),
        ("Name", lambda o: o.get_full_name()), ("Staff", lambda o: o.is_staff), ("Active", lambda o: o.is_active),
        ("Joined", lambda o: o.date_joined.isoformat()),
    ])]

    def get_queryset(self, request):
        return super().get_queryset(request).annotate(
            _notes=Count("notes", distinct=True),
            _homework=Count("homework", distinct=True),
            _todos=Count("todo", distinct=True),
        )

    @admin.display(description="Name")
    def full_name(self, obj):
        return obj.get_full_name() or "—"

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
