"""Settings comuns a todos os ambientes do AutoCheck."""
from .env import BASE_DIR, env_bool, env_int, env_list, env_str

SECRET_KEY = env_str("DJANGO_SECRET_KEY", required=True)
DEBUG = False
ALLOWED_HOSTS = env_list("DJANGO_ALLOWED_HOSTS", default=["localhost", "127.0.0.1"])
CSRF_TRUSTED_ORIGINS = env_list("DJANGO_CSRF_TRUSTED_ORIGINS")

# ---------------------------------------------------------------------------
# Aplicações
# ---------------------------------------------------------------------------
DJANGO_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
]

# Cada módulo de negócio é um app independente (ver PROJECT_CONTEXT.md).
LOCAL_APPS = [
    "apps.core",
    "apps.accounts",
    "apps.workshop",
    "apps.customers",
    "apps.vehicles",
    "apps.mechanics",
    "apps.employees",
    "apps.attendances",
    "apps.photos",
    "apps.checklist",
    "apps.tires",
    "apps.services",
    "apps.replacements",
    "apps.signatures",
    "apps.reports",
    "apps.mailing",
    "apps.integrations",
    "apps.aftersales",
    "apps.platform_admin",
]

INSTALLED_APPS = DJANGO_APPS + LOCAL_APPS

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "apps.core.middleware.SecurityHeadersMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.locale.LocaleMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "apps.core.middleware.WorkshopScopeMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "config.urls"
WSGI_APPLICATION = "config.wsgi.application"
ASGI_APPLICATION = "config.asgi.application"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
                "apps.core.context_processors.app_info",
            ],
        },
    },
]

# ---------------------------------------------------------------------------
# Banco de dados: SQLite em desenvolvimento, PostgreSQL em produção.
# DB_ENGINE=sqlite | postgresql
# ---------------------------------------------------------------------------
DB_ENGINE = env_str("DB_ENGINE", default="sqlite")

if DB_ENGINE == "postgresql":
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.postgresql",
            "NAME": env_str("POSTGRES_DB", required=True),
            "USER": env_str("POSTGRES_USER", required=True),
            "PASSWORD": env_str("POSTGRES_PASSWORD", required=True),
            "HOST": env_str("POSTGRES_HOST", default="localhost"),
            "PORT": env_str("POSTGRES_PORT", default="5432"),
            "CONN_MAX_AGE": env_int("POSTGRES_CONN_MAX_AGE", 60),
            "OPTIONS": {"sslmode": env_str("POSTGRES_SSLMODE", default="prefer")},
        }
    }
else:
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.sqlite3",
            "NAME": BASE_DIR / env_str("SQLITE_NAME", default="db.sqlite3"),
        }
    }

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# ---------------------------------------------------------------------------
# Autenticação
# ---------------------------------------------------------------------------
AUTH_USER_MODEL = "accounts.User"
AUTHENTICATION_BACKENDS = ["apps.accounts.backends.WorkshopAccountBackend"]
LOGIN_URL = "accounts:login"
LOGIN_REDIRECT_URL = "core:home"
LOGOUT_REDIRECT_URL = "accounts:login"

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator", "OPTIONS": {"min_length": 8}},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

# ---------------------------------------------------------------------------
# Internacionalização
# ---------------------------------------------------------------------------
LANGUAGE_CODE = "pt-br"
TIME_ZONE = env_str("DJANGO_TIME_ZONE", default="America/Recife")
USE_I18N = True
USE_TZ = True

# ---------------------------------------------------------------------------
# Arquivos estáticos (públicos) e mídia privada
# ---------------------------------------------------------------------------
STATIC_URL = "/static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
STATICFILES_DIRS = [BASE_DIR / "static"]
STORAGES = {
    "default": {"BACKEND": "apps.core.storage.PrivateMediaStorage"},
    "staticfiles": {"BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage"},
}

# Fotografias, assinaturas, logotipo e PDFs ficam FORA de qualquer pasta pública.
# Não existe MEDIA_URL servida pelo servidor web: todo arquivo passa por uma view
# autenticada que verifica permissão (apps.core.protected_files).
PRIVATE_MEDIA_ROOT = BASE_DIR / env_str("PRIVATE_MEDIA_DIR", default="private_media")
MEDIA_ROOT = PRIVATE_MEDIA_ROOT

FILE_UPLOAD_MAX_MEMORY_SIZE = 5 * 1024 * 1024
DATA_UPLOAD_MAX_MEMORY_SIZE = 15 * 1024 * 1024
FILE_UPLOAD_PERMISSIONS = 0o640
MAX_PHOTO_UPLOAD_BYTES = env_int("MAX_PHOTO_UPLOAD_MB", 12) * 1024 * 1024

# ---------------------------------------------------------------------------
# E-mail (SMTP configurado por variáveis de ambiente)
# ---------------------------------------------------------------------------
EMAIL_BACKEND = env_str("EMAIL_BACKEND", default="django.core.mail.backends.smtp.EmailBackend")
EMAIL_HOST = env_str("EMAIL_HOST", default="")
EMAIL_PORT = env_int("EMAIL_PORT", 587)
EMAIL_HOST_USER = env_str("EMAIL_HOST_USER", default="")
EMAIL_HOST_PASSWORD = env_str("EMAIL_HOST_PASSWORD", default="")
EMAIL_USE_TLS = env_bool("EMAIL_USE_TLS", True)
EMAIL_USE_SSL = env_bool("EMAIL_USE_SSL", False)
EMAIL_TIMEOUT = env_int("EMAIL_TIMEOUT", 30)
DEFAULT_FROM_EMAIL = env_str("DEFAULT_FROM_EMAIL", default="AutoCheck <nao-responda@localhost>")

# ---------------------------------------------------------------------------
# Segurança comum
# ---------------------------------------------------------------------------
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_AGE = env_int("SESSION_COOKIE_AGE_SECONDS", 60 * 60 * 10)
CSRF_COOKIE_HTTPONLY = False  # o JS lê o token para requisições fetch; o cookie não contém dado sensível.
X_FRAME_OPTIONS = "DENY"
SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_REFERRER_POLICY = "same-origin"

# ---------------------------------------------------------------------------
# Regras de negócio configuráveis
# ---------------------------------------------------------------------------
AUTOCHECK = {
    # Retenção em meses de calendário após a conclusão do atendimento.
    "RETENTION_MONTHS": env_int("AUTOCHECK_RETENTION_MONTHS", 6),
    # Integração com BrasilAPI (gratuita, sem credencial).
    "BRASILAPI_BASE_URL": env_str("BRASILAPI_BASE_URL", default="https://brasilapi.com.br/api"),
    "BRASILAPI_TIMEOUT": env_int("BRASILAPI_TIMEOUT", 8),
    # Sistema de gestão da oficina: aguardando documentação e credenciais.
    "MANAGEMENT_API_BASE_URL": env_str("MANAGEMENT_API_BASE_URL", default=""),
    "MANAGEMENT_API_TOKEN": env_str("MANAGEMENT_API_TOKEN", default=""),
    "MANAGEMENT_API_TIMEOUT": env_int("MANAGEMENT_API_TIMEOUT", 10),
    # Só ligue atrás de um proxy que controla o X-Forwarded-For. Sem proxy, o cliente
    # poderia forjar o IP usado na auditoria e no bloqueio de login.
    "TRUST_PROXY_HEADERS": env_bool("AUTOCHECK_TRUST_PROXY", False),
}

# ---------------------------------------------------------------------------
# Logs: erros detalhados vão para o log do servidor, nunca para o usuário.
# ---------------------------------------------------------------------------
LOG_LEVEL = env_str("DJANGO_LOG_LEVEL", default="INFO")
LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "standard": {"format": "%(asctime)s %(levelname)s %(name)s: %(message)s"},
    },
    "handlers": {
        "console": {"class": "logging.StreamHandler", "formatter": "standard"},
    },
    "root": {"handlers": ["console"], "level": LOG_LEVEL},
    "loggers": {
        "django": {"handlers": ["console"], "level": LOG_LEVEL, "propagate": False},
        "autocheck": {"handlers": ["console"], "level": LOG_LEVEL, "propagate": False},
    },
}
