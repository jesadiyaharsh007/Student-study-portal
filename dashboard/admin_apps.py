from django.contrib.admin import apps as admin_apps


class StudyAdminConfig(admin_apps.AdminConfig):
    """django.contrib.admin, but with the Study Portal admin site (see admin_site.py)."""

    default_site = 'dashboard.admin_site.StudyAdminSite'
