"""Usuário customizado: conta de acesso de uma oficina ou proprietário da plataforma.

Criado na Etapa 1 porque o Django exige que o AUTH_USER_MODEL exista antes
da primeira migração; trocá-lo depois exigiria recriar o banco.
"""
from django.contrib.auth.models import AbstractUser
from django.db import models

from apps.core.validators.phone import format_phone
from apps.core.validators.text import to_upper


class User(AbstractUser):
    # Conta de acesso de uma oficina. Vazio só para o proprietário da plataforma (superusuário).
    workshop = models.ForeignKey(
        "workshop.WorkshopSettings", verbose_name="oficina", null=True, blank=True, on_delete=models.PROTECT,
        related_name="accounts",
    )
    phone = models.CharField("telefone", max_length=11, blank=True)

    class Meta:
        verbose_name = "usuário"
        verbose_name_plural = "usuários"
        ordering = ["first_name", "username"]

    def save(self, *args, **kwargs):
        # O nome de acesso (username) fica como foi criado: o login diferencia maiúsculas.
        self.first_name, self.last_name = to_upper(self.first_name), to_upper(self.last_name)
        super().save(*args, **kwargs)

    @property
    def display_name(self):
        return self.workshop.name if self.workshop_id else (self.get_full_name() or to_upper(self.username))

    @property
    def phone_formatted(self):
        return format_phone(self.phone)

    def __str__(self):
        return self.display_name


class LoginAttempt(models.Model):
    """Falhas de login, usadas para bloquear tentativas repetidas.

    Fica no banco, e não em cache de processo, para valer entre os vários
    processos do servidor em produção.
    """

    key = models.CharField(max_length=64, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        verbose_name = "tentativa de login"
        verbose_name_plural = "tentativas de login"
