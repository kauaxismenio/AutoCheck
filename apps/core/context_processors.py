from django.utils.functional import SimpleLazyObject

from .navigation import build_navigation


def _request_workshop(request):
    user = getattr(request, "user", None)
    return user.workshop if user is not None and user.is_authenticated else None


def app_info(request):
    return {
        "APP_NAME": "AutoCheck",
        "APP_VERSION": "1.0.0",
        "workshop": _request_workshop(request),
        "nav_items": SimpleLazyObject(lambda: build_navigation(request)),
    }
