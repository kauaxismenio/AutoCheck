"""Telefones brasileiros (fixo e celular) com DDD.

- Celular: DDD + 9 dígitos começando por 9  → (81) 9 9000-1712
- Fixo:    DDD + 8 dígitos começando por 2–5 → (81) 3456-7890
O DDD não pode conter o dígito 0 (faixa 11–99, conforme o plano de numeração).
Um prefixo "55" (código do país) ou "0" de discagem é removido na normalização.
"""
import re

MOBILE = "celular"
LANDLINE = "fixo"


def normalize_phone(value):
    digits = re.sub(r"\D", "", value or "")
    if len(digits) in (12, 13) and digits.startswith("55"):
        digits = digits[2:]
    if len(digits) in (11, 12) and digits.startswith("0"):
        digits = digits[1:]
    return digits


def phone_type(value):
    """Retorna 'celular', 'fixo' ou None se inválido."""
    digits = normalize_phone(value)
    if len(digits) not in (10, 11):
        return None
    ddd = digits[:2]
    if "0" in ddd:
        return None
    local = digits[2:]
    if len(local) == 9 and local[0] == "9":
        return MOBILE
    if len(local) == 8 and local[0] in "2345":
        return LANDLINE
    return None


def is_valid_phone(value):
    return phone_type(value) is not None


def format_phone(value):
    digits = normalize_phone(value)
    kind = phone_type(digits)
    if kind == MOBILE:
        return f"({digits[:2]}) {digits[2]} {digits[3:7]}-{digits[7:]}"
    if kind == LANDLINE:
        return f"({digits[:2]}) {digits[2:6]}-{digits[6:]}"
    return value or ""
