"""Oficina: cada registro é uma conta independente da plataforma, com as próprias configurações.

Senhas SMTP e chaves de API NÃO ficam aqui: ficam em variáveis de ambiente.
Aqui ficam apenas dados cadastrais e o e-mail fixo do responsável.
"""
from django.db import models

from apps.core.django_validators import validate_cnpj, validate_email_address, validate_phone, validate_review_link
from apps.core.models import TimeStampedModel
from apps.core.storage import UUIDUploadTo
from apps.core.validators.documents import normalize_cnpj
from apps.core.validators.phone import normalize_phone
from apps.core.validators.text import to_upper


class WorkshopSettings(TimeStampedModel):
    name = models.CharField("nome da oficina", max_length=150, default="Minha Oficina")
    logo = models.ImageField("logotipo", upload_to=UUIDUploadTo("workshop/logo"), blank=True)
    cnpj = models.CharField("CNPJ", max_length=18, blank=True, validators=[validate_cnpj])
    phone = models.CharField("telefone", max_length=20, blank=True, validators=[validate_phone])
    address = models.CharField("endereço", max_length=255, blank=True)
    report_email = models.EmailField(
        "e-mail do responsável (recebe todos os relatórios)", blank=True,
        validators=[validate_email_address],
    )
    google_review_url = models.URLField(
        "link de avaliação da oficina no Google", max_length=500, blank=True, validators=[validate_review_link],
    )

    is_active = models.BooleanField("oficina ativa", default=True)

    class Meta:
        verbose_name = "oficina"
        verbose_name_plural = "oficinas"

    def save(self, *args, **kwargs):
        self.name = to_upper(self.name)
        self.cnpj = normalize_cnpj(self.cnpj)
        self.phone = normalize_phone(self.phone)
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):  # noqa: ARG002
        raise RuntimeError("Oficinas não são excluídas; desative o acesso na administração da plataforma.")

    @property
    def is_ready_for_reports(self):
        return bool(self.report_email)

    def __str__(self):
        return self.name
