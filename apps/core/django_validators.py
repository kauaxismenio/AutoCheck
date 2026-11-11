"""Validadores Django que reutilizam as regras puras de apps.core.validators.

Usados nos modelos e formulários para garantir a validação no backend,
independentemente do JavaScript.
"""
from django.core.exceptions import ValidationError
from django.core.validators import EmailValidator

from apps.core.validators import documents, email, phone, plate, review_link


def validate_cpf(value):
    if not documents.is_valid_cpf(value):
        raise ValidationError("CPF inválido. Confira os números digitados.", code="invalid_cpf")


def validate_cnpj(value):
    if not documents.is_valid_cnpj(value):
        raise ValidationError(
            "CNPJ inválido. Confira os caracteres (letras são aceitas nas 12 primeiras posições).",
            code="invalid_cnpj",
        )


def validate_phone(value):
    if not phone.is_valid_phone(value):
        raise ValidationError(
            "Telefone inválido. Informe DDD + número (fixo com 8 dígitos ou celular com 9).",
            code="invalid_phone",
        )


def validate_plate(value):
    if not plate.is_valid_plate(value):
        raise ValidationError(
            "Placa inválida. Use o padrão antigo (ABC-1234) ou Mercosul (ABC1D23).",
            code="invalid_plate",
        )


_django_email_validator = EmailValidator(message="Informe um e-mail válido.")


def validate_email_address(value):
    _django_email_validator(value)
    if not email.is_valid_email(value):
        raise ValidationError("O domínio do e-mail parece inválido.", code="invalid_email_domain")


def validate_mileage(value):
    if value is None:
        return
    if value < 0 or value > 3_000_000:
        raise ValidationError("Quilometragem fora do intervalo aceito.", code="invalid_mileage")


def validate_review_link(value):
    if not review_link.is_valid_review_link(value):
        raise ValidationError(
            "Informe o link oficial de avaliação do Google, começando com https:// "
            "(por exemplo, https://g.page/r/.../review).",
            code="invalid_review_link",
        )
