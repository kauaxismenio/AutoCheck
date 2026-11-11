"""Settings usados pela suíte de testes automatizados."""
import atexit
import os
import shutil
import tempfile
import warnings
from pathlib import Path

# Todo arquivo temporário dos testes fica dentro do projeto, e não no %TEMP% do Windows.
# TMP/TEMP valem também para os processos filhos (navegador dos testes).
_TEST_TMP = Path(__file__).resolve().parents[2] / ".test_tmp"
_TEST_TMP.mkdir(exist_ok=True)
os.environ["TMP"] = os.environ["TEMP"] = str(_TEST_TMP)
tempfile.tempdir = str(_TEST_TMP)
atexit.register(shutil.rmtree, _TEST_TMP, ignore_errors=True)

# Permite rodar os testes sem .env (CI ou máquina nova). Chave usada só em testes.
os.environ.setdefault("DJANGO_SECRET_KEY", "test-only-insecure-key-nao-usar-em-producao")
os.environ.setdefault("DB_ENGINE", "sqlite")
# Respostas 403/404 esperadas não devem poluir a saída dos testes.
os.environ.setdefault("DJANGO_LOG_LEVEL", "CRITICAL")

from .base import *  # noqa: E402,F401,F403

DEBUG = False
DATABASES = {"default": {"ENGINE": "django.db.backends.sqlite3", "NAME": ":memory:"}}
if os.environ.get("RUN_E2E") == "1":
    # O servidor do navegador usa várias threads: em memória, o SQLite compartilhado
    # gera "table is locked", algo que não existe com banco em arquivo.
    _e2e_db = Path(tempfile.gettempdir()) / f"autocheck-e2e-{os.getpid()}.sqlite3"
    DATABASES["default"].update({"NAME": _e2e_db, "OPTIONS": {"timeout": 30}, "TEST": {"NAME": _e2e_db}})
PASSWORD_HASHERS = ["django.contrib.auth.hashers.MD5PasswordHasher"]
EMAIL_BACKEND = "django.core.mail.backends.locmem.EmailBackend"

# staticfiles/ só existe depois do collectstatic, que não é necessário nos testes.
warnings.filterwarnings("ignore", message="No directory at", module="django.core.handlers.base")

PRIVATE_MEDIA_ROOT = Path(tempfile.mkdtemp(prefix="autocheck-test-media-"))
MEDIA_ROOT = PRIVATE_MEDIA_ROOT
STORAGES = {
    "default": {"BACKEND": "apps.core.storage.PrivateMediaStorage"},
    "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"},
}
