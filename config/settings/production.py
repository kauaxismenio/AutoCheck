"""Settings de produção (PostgreSQL, HTTPS obrigatório)."""
from .base import *  # noqa: F401,F403
from .base import DB_ENGINE
from .env import ImproperlyConfiguredEnv, env_bool, env_int

DEBUG = False

if SECRET_KEY == "troque-esta-chave" or len(SECRET_KEY) < 40:  # noqa: F405
    raise ImproperlyConfiguredEnv("Em produção, defina um DJANGO_SECRET_KEY forte (ver .env.example).")

if DB_ENGINE != "postgresql":
    raise ImproperlyConfiguredEnv("Em produção, defina DB_ENGINE=postgresql.")

SECURE_SSL_REDIRECT = env_bool("DJANGO_SECURE_SSL_REDIRECT", True)
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
SECURE_HSTS_SECONDS = env_int("DJANGO_HSTS_SECONDS", 60 * 60 * 24 * 30)
SECURE_HSTS_INCLUDE_SUBDOMAINS = env_bool("DJANGO_HSTS_INCLUDE_SUBDOMAINS", False)
SECURE_HSTS_PRELOAD = False
