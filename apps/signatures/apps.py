from django.apps import AppConfig


class SignaturesConfig(AppConfig):
    name = "apps.signatures"
    label = "signatures"
    verbose_name = "Assinaturas"

    def ready(self):
        from . import signals  # noqa: F401
