from django.apps import AppConfig


class PhotosConfig(AppConfig):
    name = "apps.photos"
    label = "photos"
    verbose_name = "Fotografias"

    def ready(self):
        from . import signals  # noqa: F401
