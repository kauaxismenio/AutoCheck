"""Validação e formatação de CPF e CNPJ (numérico e alfanumérico).

Python puro, sem dependência do Django, para ser reutilizado por formulários,
serializers, serviços e testes. O JavaScript replica as mesmas regras apenas
para dar retorno imediato; a decisão final é sempre do backend.

CNPJ alfanumérico (Receita Federal, IN RFB 2.229/2024, vigente desde julho/2026):
- 14 caracteres: 12 primeiras posições com A–Z ou 0–9; 2 últimas numéricas (DVs).
- Cada caractere vale (código ASCII − 48): '0'..'9' → 0..9, 'A' → 17 ... 'Z' → 42.
- DVs por módulo 11, pesos 5,4,3,2,9,8,7,6,5,4,3,2 (DV1) e 6,5,4,3,2,9,8,7,6,5,4,3,2 (DV2).
- Resto < 2 → DV 0; senão DV = 11 − resto.
- Para CNPJ só numérico o resultado é idêntico ao cálculo tradicional.
Exemplo oficial do FAQ da Receita: 12.ABC.345/01DE-35.
"""
import re

_CPF_WEIGHTS_1 = list(range(10, 1, -1))
_CPF_WEIGHTS_2 = list(range(11, 1, -1))
_CNPJ_WEIGHTS_1 = [5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2]
_CNPJ_WEIGHTS_2 = [6, 5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2]

_CNPJ_PATTERN = re.compile(r"^[A-Z0-9]{12}[0-9]{2}$")
_CNPJ_SEPARATORS = re.compile(r"[.\-/\s]")


# ---------------------------------------------------------------------------
# CPF
# ---------------------------------------------------------------------------
def normalize_cpf(value):
    """Mantém somente os dígitos."""
    return re.sub(r"\D", "", value or "")


def _mod11_digit(total):
    remainder = total % 11
    return 0 if remainder < 2 else 11 - remainder


def is_valid_cpf(value):
    cpf = normalize_cpf(value)
    if len(cpf) != 11 or cpf == cpf[0] * 11:
        return False
    numbers = [int(d) for d in cpf]
    dv1 = _mod11_digit(sum(n * w for n, w in zip(numbers[:9], _CPF_WEIGHTS_1, strict=True)))
    dv2 = _mod11_digit(sum(n * w for n, w in zip(numbers[:10], _CPF_WEIGHTS_2, strict=True)))
    return numbers[9] == dv1 and numbers[10] == dv2


def format_cpf(value):
    cpf = normalize_cpf(value)
    if len(cpf) != 11:
        return value or ""
    return f"{cpf[:3]}.{cpf[3:6]}.{cpf[6:9]}-{cpf[9:]}"


# ---------------------------------------------------------------------------
# CNPJ (numérico e alfanumérico)
# ---------------------------------------------------------------------------
def normalize_cnpj(value):
    """Remove pontuação/espaços e converte letras para maiúsculas.

    Não remove outros caracteres inválidos: eles devem fazer a validação falhar,
    em vez de serem descartados silenciosamente.
    """
    return _CNPJ_SEPARATORS.sub("", value or "").upper()


def _cnpj_char_value(char):
    return ord(char) - 48


def calculate_cnpj_check_digits(base12):
    """Calcula os 2 DVs a partir das 12 primeiras posições (já normalizadas)."""
    base = normalize_cnpj(base12)
    if not re.fullmatch(r"[A-Z0-9]{12}", base):
        raise ValueError("A base do CNPJ deve ter 12 caracteres A–Z/0–9.")
    values = [_cnpj_char_value(c) for c in base]
    dv1 = _mod11_digit(sum(v * w for v, w in zip(values, _CNPJ_WEIGHTS_1, strict=True)))
    dv2 = _mod11_digit(sum(v * w for v, w in zip(values + [dv1], _CNPJ_WEIGHTS_2, strict=True)))
    return f"{dv1}{dv2}"


def is_valid_cnpj(value):
    cnpj = normalize_cnpj(value)
    if not _CNPJ_PATTERN.fullmatch(cnpj):
        return False
    if cnpj == cnpj[0] * 14:
        return False
    return calculate_cnpj_check_digits(cnpj[:12]) == cnpj[12:]


def is_alphanumeric_cnpj(value):
    """True quando o CNPJ (normalizado) contém alguma letra."""
    return any(c.isalpha() for c in normalize_cnpj(value))


def format_cnpj(value):
    cnpj = normalize_cnpj(value)
    if len(cnpj) != 14:
        return value or ""
    return f"{cnpj[:2]}.{cnpj[2:5]}.{cnpj[5:8]}/{cnpj[8:12]}-{cnpj[12:]}"
