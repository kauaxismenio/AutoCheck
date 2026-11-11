#!/usr/bin/env python
"""Utilitário de linha de comando do Django para o AutoCheck."""
import os
import sys


def main():
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.development")
    try:
        from django.core.management import execute_from_command_line
    except ImportError as exc:
        raise ImportError(
            "Django não encontrado. Ative o ambiente virtual (.venv) e instale "
            "as dependências com: pip install -r requirements/development.txt"
        ) from exc
    execute_from_command_line(sys.argv)


if __name__ == "__main__":
    main()
