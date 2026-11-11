from django.apps import AppConfig


class ReportsConfig(AppConfig):
    name = "apps.reports"
    label = "reports"
    verbose_name = "Relatórios PDF"

    def ready(self):
        from . import signals  # noqa: F401
