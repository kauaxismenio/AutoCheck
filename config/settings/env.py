"""Leitura tipada de variáveis de ambiente.

Credenciais e chaves ficam SOMENTE em variáveis de ambiente (arquivo .env local,
nunca versionado). Este módulo não depende do Django para poder ser usado
antes do carregamento dos settings.
"""
import os
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent.parent

# Carrega .env da raiz do projeto, sem sobrescrever variáveis já definidas no sistema.
load_dotenv(BASE_DIR / ".env", override=False)

_TRUE = {"1", "true", "yes", "on", "sim"}


class ImproperlyConfiguredEnv(RuntimeError):
    """Variável de ambiente obrigatória ausente ou inválida."""


def env_str(name, default=None, required=False):
    value = os.environ.get(name)
    if value is None or value == "":
        if required:
            raise ImproperlyConfiguredEnv(f"Variável de ambiente obrigatória ausente: {name}")
        return default
    return value


def env_bool(name, default=False):
    value = os.environ.get(name)
    if value is None or value == "":
        return default
    return value.strip().lower() in _TRUE


def env_int(name, default=0):
    value = os.environ.get(name)
    if value is None or value == "":
        return default
    try:
        return int(value)
    except ValueError as exc:
        raise ImproperlyConfiguredEnv(f"{name} deve ser um número inteiro.") from exc


def env_list(name, default=None, sep=","):
    value = os.environ.get(name)
    if value is None or value.strip() == "":
        return list(default or [])
    return [item.strip() for item in value.split(sep) if item.strip()]
