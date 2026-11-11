"""Vendedor/atendente (mesma função): quem realiza o atendimento, sem login, senha nem e-mail.

O login do sistema é da oficina. O cadastro fica em Configurações e a pessoa é
escolhida ao iniciar cada atendimento, permanecendo responsável até a finalização.
"""
from django.core.exceptions import ValidationError
from django.db import models

from apps.mechanics.models import TeamMember


def validate_employee_name(value):
    if sum(c.isalpha() for c in value) < 2:
        raise ValidationError("Informe o nome completo.", code="invalid_employee_name")


class Employee(TeamMember):
    name = models.CharField("nome completo", max_length=120, validators=[validate_employee_name])

    class Meta(TeamMember.Meta):
        verbose_name = "vendedor/atendente"
        verbose_name_plural = "vendedores/atendentes"
