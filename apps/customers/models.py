"""Cliente (pessoa física, jurídica ou ambos).

CPF, CNPJ e telefone são armazenados normalizados (sem máscara). As opções
"não deseja informar CPF/CNPJ/e-mail" são registradas POR ATENDIMENTO
(apps.attendances.Attendance), e não apagam dados históricos do cliente.
"""
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import Q

from apps.core.django_validators import (
    validate_cnpj, validate_cpf, validate_email_address, validate_phone,
)
from apps.core.models import TimeStampedModel, WorkshopOwned
from apps.core.validators.documents import format_cnpj, format_cpf, normalize_cnpj, normalize_cpf
from apps.core.validators.email import normalize_email
from apps.core.validators.phone import format_phone, normalize_phone
from apps.core.validators.text import to_upper


class PersonType(models.TextChoices):
    PF = "pf", "CPF — Pessoa Física"
    PJ = "pj", "CNPJ — Pessoa Jurídica"
    AMBOS = "ambos", "Ambos"


class Customer(WorkshopOwned, TimeStampedModel):
    person_type = models.CharField("tipo", max_length=5, choices=PersonType.choices, default=PersonType.PF)

    # Pessoa física
    full_name = models.CharField("nome completo", max_length=150, blank=True)
    cpf = models.CharField("CPF", max_length=14, null=True, blank=True, validators=[validate_cpf])

    # Pessoa jurídica
    cnpj = models.CharField("CNPJ", max_length=18, null=True, blank=True, validators=[validate_cnpj])
    legal_name = models.CharField("razão social", max_length=200, blank=True)
    trade_name = models.CharField("nome fantasia", max_length=200, blank=True)
    contact_person = models.CharField("responsável", max_length=150, blank=True)

    # Contato
    phone = models.CharField("telefone", max_length=20, validators=[validate_phone])
    email = models.EmailField("e-mail", blank=True, validators=[validate_email_address])

    # Dados históricos que não aparecem na tela de atendimento, mas são preservados.
    address = models.CharField("endereço", max_length=255, blank=True)

    # Identificador no sistema de gestão da oficina (integração futura).
    external_id = models.CharField("ID no sistema de gestão", max_length=64, blank=True, db_index=True)

    class Meta:
        verbose_name = "cliente"
        verbose_name_plural = "clientes"
        ordering = ["full_name", "legal_name"]
        constraints = [
            models.UniqueConstraint(fields=["workshop", "cpf"], condition=Q(cpf__isnull=False), name="uniq_customer_workshop_cpf"),
            models.UniqueConstraint(fields=["workshop", "cnpj"], condition=Q(cnpj__isnull=False), name="uniq_customer_workshop_cnpj"),
        ]
        indexes = [models.Index(fields=["phone"])]

    # ------------------------------------------------------------------
    def normalize(self):
        self.cpf = normalize_cpf(self.cpf) or None
        self.cnpj = normalize_cnpj(self.cnpj) or None
        self.phone = normalize_phone(self.phone)
        self.email = normalize_email(self.email)
        self.full_name = to_upper(self.full_name)
        self.legal_name = to_upper(self.legal_name)
        self.trade_name = to_upper(self.trade_name)

    def clean(self):
        super().clean()
        self.normalize()
        errors = {}
        if self.person_type in (PersonType.PF, PersonType.AMBOS) and not self.full_name:
            errors["full_name"] = "Informe o nome completo."
        if self.person_type in (PersonType.PJ, PersonType.AMBOS) and not self.legal_name:
            errors["legal_name"] = "Informe a razão social."
        if self.person_type == PersonType.PF and self.cnpj:
            errors["cnpj"] = "Cliente pessoa física não deve ter CNPJ. Selecione 'Ambos'."
        if self.person_type == PersonType.PJ and self.cpf:
            errors["cpf"] = "Cliente pessoa jurídica não deve ter CPF. Selecione 'Ambos'."
        if errors:
            raise ValidationError(errors)

    def save(self, *args, **kwargs):
        self.normalize()
        super().save(*args, **kwargs)

    # ------------------------------------------------------------------
    @property
    def display_name(self):
        if self.person_type == PersonType.PJ:
            return self.trade_name or self.legal_name
        return self.full_name or self.trade_name or self.legal_name

    @property
    def cpf_formatted(self):
        return format_cpf(self.cpf) if self.cpf else ""

    @property
    def cnpj_formatted(self):
        return format_cnpj(self.cnpj) if self.cnpj else ""

    @property
    def phone_formatted(self):
        return format_phone(self.phone)

    def __str__(self):
        return self.display_name or f"Cliente #{self.pk}"
