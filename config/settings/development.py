"""Settings de desenvolvimento local (SQLite, DEBUG ligado)."""
import warnings

from .base import *  # noqa: F401,F403
from .env import env_bool, env_str

DEBUG = env_bool("DJANGO_DEBUG", True)

# staticfiles/ só existe depois do collectstatic, necessário apenas em produção.
warnings.filterwarnings("ignore", message="No directory at", module="django.core.handlers.base")

# Em desenvolvimento, se nenhum SMTP foi configurado, os e-mails aparecem no console.
# Isso NÃO conta como envio confirmado: o módulo de e-mails registra o backend usado.
if not env_str("EMAIL_HOST", default=""):
    EMAIL_BACKEND = "django.core.mail.backends.console.EmailBackend"

STORAGES = {
    "default": {"BACKEND": "apps.core.storage.PrivateMediaStorage"},
    "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"},
}
