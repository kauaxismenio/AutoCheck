"""Placas brasileiras: padrão antigo (ABC-1234) e Mercosul (ABC1D23).

Armazenamento normalizado sem hífen e em maiúsculas: ABC1234 / ABC1D23.
"""
import re

OLD = "antiga"
MERCOSUL = "mercosul"

_OLD = re.compile(r"^[A-Z]{3}[0-9]{4}$")
_MERCOSUL = re.compile(r"^[A-Z]{3}[0-9][A-Z][0-9]{2}$")


def normalize_plate(value):
    return re.sub(r"[^A-Za-z0-9]", "", value or "").upper()


def plate_type(value):
    plate = normalize_plate(value)
    if _OLD.fullmatch(plate):
        return OLD
    if _MERCOSUL.fullmatch(plate):
        return MERCOSUL
    return None


def is_valid_plate(value):
    return plate_type(value) is not None


def format_plate(value):
    plate = normalize_plate(value)
    kind = plate_type(plate)
    if kind == OLD:
        return f"{plate[:3]}-{plate[3:]}"
    if kind == MERCOSUL:
        return plate
    return value or ""
