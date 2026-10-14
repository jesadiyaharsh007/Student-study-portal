from django.apps import AppConfig


class DashboardConfig(AppConfig):
    name = 'dashboard'
    verbose_name = 'Study content'

    def ready(self):
        # Friendlier names in the admin (breadcrumbs, headings)
        from django.apps import apps
        apps.get_app_config('auth').verbose_name = 'Accounts'
