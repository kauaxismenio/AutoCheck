"""Bloqueio temporário de login após falhas repetidas (por usuário + IP)."""
from datetime import timedelta
from hashlib import sha256

from django.conf import settings
from django.utils import timezone

from apps.core.audit import client_ip

from .models import LoginAttempt

MAX_FAILURES = 5
WINDOW = timedelta(minutes=15)


def _key(username, request):
    raw = f"{settings.SECRET_KEY}|{(username or '').strip().lower()}|{client_ip(request) or ''}"
    return sha256(raw.encode("utf-8")).hexdigest()


def is_locked(username, request):
    since = timezone.now() - WINDOW
    return LoginAttempt.objects.filter(key=_key(username, request), created_at__gte=since).count() >= MAX_FAILURES


def register_failure(username, request):
    LoginAttempt.objects.filter(created_at__lt=timezone.now() - WINDOW).delete()
    LoginAttempt.objects.create(key=_key(username, request))


def clear(username, request):
    LoginAttempt.objects.filter(key=_key(username, request)).delete()
