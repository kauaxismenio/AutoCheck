"""Mecânicos da oficina: cadastro independente, sem login nem senha.

Quem acessa o sistema é `accounts.User` (administrador, vendedor, atendente).
O mecânico só é registrado como responsável pelos serviços do atendimento.
"""
import unicodedata

from django.core.exceptions import ValidationError
from django.db import models

from apps.core.django_validators import validate_phone
from apps.core.models import TimeStampedModel, WorkshopOwned
from apps.core.validators.phone import format_phone, normalize_phone
from apps.core.validators.text import to_upper


def clean_name(name):
    return " ".join((name or "").split())


def name_key(name):
    """Chave de comparação: 'JOÃO  Silva' e 'joao silva' são a mesma pessoa.

    Fica em Python porque a comparação sem acento e sem caixa do SQLite e do
    PostgreSQL não se comporta igual para caracteres acentuados.
    """
    decomposed = unicodedata.normalize("NFKD", clean_name(name))
    return "".join(c for c in decomposed if not unicodedata.combining(c)).casefold()


def validate_mechanic_name(value):
    if sum(c.isalpha() for c in value) < 2:
        raise ValidationError("Informe o nome do mecânico.", code="invalid_mechanic_name")


class TeamMember(WorkshopOwned, TimeStampedModel):
    """Pessoa da equipe de uma oficina, sem acesso ao sistema. Cada cadastro define o próprio `name`."""

    name_key = models.CharField(max_length=120, editable=False)
    is_active = models.BooleanField("ativo", default=True, db_index=True)

    class Meta:
        abstract = True
        ordering = ["name"]
        constraints = [models.UniqueConstraint(fields=["workshop", "name_key"], name="uniq_%(class)s_name_per_workshop")]

    def save(self, *args, **kwargs):
        self.name = to_upper(clean_name(self.name))
        self.name_key = name_key(self.name)
        super().save(*args, **kwargs)

    def __str__(self):
        return self.name


class Mechanic(TeamMember):
    name = models.CharField("nome", max_length=120, validators=[validate_mechanic_name])
    phone = models.CharField("telefone", max_length=11, blank=True, validators=[validate_phone])

    class Meta(TeamMember.Meta):
        verbose_name = "mecânico"
        verbose_name_plural = "mecânicos"

    def save(self, *args, **kwargs):
        self.phone = normalize_phone(self.phone)
        super().save(*args, **kwargs)

    @property
    def phone_formatted(self):
        return format_phone(self.phone)
