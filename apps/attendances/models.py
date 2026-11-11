"""Atendimento: agrega todas as etapas de uma passagem do veículo pela oficina."""
import uuid

from django.conf import settings
from django.db import models
from django.utils import timezone

from apps.core.dates import add_months
from apps.core.django_validators import validate_mileage
from apps.core.models import TimeStampedModel, WorkshopOwned
from apps.customers.models import PersonType

from . import workflow as wf


class Origin(models.TextChoices):
    INDICACAO = "indicacao", "Indicação"
    INSTAGRAM = "instagram", "Instagram"
    ANUNCIO = "anuncio", "Anúncio"
    GOOGLE = "google", "Google/Internet"
    JA_CLIENTE = "ja_cliente", "Já é cliente"
    FACHADA = "fachada", "Fachada"
    OUTRO = "outro", "Outro"


class Attendance(WorkshopOwned, TimeStampedModel):
    # UUID usado nas URLs, para não expor uma sequência adivinhável.
    public_id = models.UUIDField("identificador", default=uuid.uuid4, unique=True, editable=False)
    code = models.CharField("código", max_length=20, unique=True, null=True, blank=True, editable=False)

    customer = models.ForeignKey(
        "customers.Customer", verbose_name="cliente", on_delete=models.PROTECT, related_name="attendances",
    )
    vehicle = models.ForeignKey(
        "vehicles.Vehicle", verbose_name="veículo", on_delete=models.PROTECT, related_name="attendances",
    )
    mechanic = models.ForeignKey(
        "mechanics.Mechanic", verbose_name="mecânico responsável", on_delete=models.PROTECT,
        related_name="attendances",
    )
    # Escolhido ao iniciar e fixo até a finalização. Vazio só em registro antigo sem autor.
    attendant = models.ForeignKey(
        "employees.Employee", verbose_name="vendedor/atendente", null=True, on_delete=models.PROTECT,
        related_name="attendances",
    )
    # Conta logada (a da oficina), para auditoria. Não identifica quem atendeu.
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, verbose_name="aberto por", null=True, on_delete=models.SET_NULL,
        related_name="attendances_created",
    )

    mileage = models.PositiveIntegerField("quilometragem", validators=[validate_mileage])
    origin = models.CharField("como conheceu nossa loja?", max_length=20, choices=Origin.choices)

    # Opções do cliente registradas neste atendimento
    cpf_not_informed = models.BooleanField("cliente não deseja informar CPF", default=False)
    cnpj_not_informed = models.BooleanField("cliente não sabe/não deseja informar CNPJ", default=False)
    email_opt_out = models.BooleanField("cliente não deseja informar e-mail ou receber o relatório", default=False)
    # Modalidade e dados empresariais informados NESTE atendimento. Não vêm do cadastro do cliente:
    # CPF e CNPJ são independentes, e um nunca é buscado ou preenchido a partir do outro.
    person_type = models.CharField("modalidade", max_length=5, choices=PersonType.choices, default=PersonType.PF)
    cnpj = models.CharField("CNPJ informado", max_length=18, blank=True, db_index=True)
    legal_name = models.CharField("razão social", max_length=200, blank=True)
    trade_name = models.CharField("nome fantasia", max_length=200, blank=True)
    contact_person = models.CharField("responsável", max_length=150, blank=True)
    # E-mail usado neste atendimento (cópia; o e-mail do cadastro não é apagado).
    customer_email = models.EmailField("e-mail do cliente para o relatório", blank=True)

    status = models.CharField("situação", max_length=20, choices=wf.STATUS_CHOICES, default=wf.STATUS_EM_ANDAMENTO, db_index=True)
    current_step = models.CharField("etapa atual", max_length=20, choices=wf.STEP_CHOICES, default=wf.CADASTRO)

    # Antiga marcação manual: só leitura, para os atendimentos concluídos antes do QR Code.
    review_requested = models.BooleanField("avaliação solicitada ao cliente", default=False)
    review_requested_at = models.DateTimeField("avaliação solicitada em", null=True, blank=True)
    # Registra apenas que o código foi mostrado; o sistema não sabe se houve avaliação publicada.
    review_qr_presented_at = models.DateTimeField("QR Code de avaliação apresentado em", null=True, blank=True)
    review_qr_presented_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, verbose_name="QR Code apresentado por", null=True, blank=True,
        on_delete=models.SET_NULL, related_name="+",
    )

    completed_at = models.DateTimeField("concluído em", null=True, blank=True, db_index=True)
    cancelled_at = models.DateTimeField("cancelado em", null=True, blank=True)
    retention_until = models.DateTimeField("manter até", null=True, blank=True, db_index=True)
    # Gravado junto com a conclusão: se o processo cair antes do PDF, a fila de e-mails retoma.
    report_pending = models.BooleanField("relatório da finalização pendente", default=False, db_index=True)

    class Meta:
        verbose_name = "atendimento"
        verbose_name_plural = "atendimentos"
        ordering = ["-created_at"]
        indexes = [models.Index(fields=["status", "current_step"])]

    def infer_workshop_id(self):
        return self.customer.workshop_id

    # ------------------------------------------------------------------
    def save(self, *args, **kwargs):
        if self.email_opt_out:
            self.customer_email = ""
        creating = self.pk is None
        super().save(*args, **kwargs)
        if creating and not self.code:
            self.code = f"AC-{self.created_at:%Y}-{self.pk:06d}"
            super().save(update_fields=["code"])

    # ------------------------------------------------------------------
    @property
    def is_editable(self):
        return self.status == wf.STATUS_EM_ANDAMENTO

    @property
    def includes_person(self):
        return self.person_type in (PersonType.PF, PersonType.AMBOS)

    @property
    def includes_company(self):
        return self.person_type in (PersonType.PJ, PersonType.AMBOS)

    @property
    def informed_cpf(self):
        """O CPF só vale se fizer parte da modalidade deste atendimento."""
        return self.customer.cpf if self.includes_person and not self.cpf_not_informed else None

    @property
    def should_email_customer(self):
        return bool(self.customer_email) and not self.email_opt_out

    @property
    def review_qr_note(self):
        """Quando o QR Code foi apresentado (tela e PDF usam o mesmo texto).

        Não cita a conta logada: o login é da oficina e não identifica a pessoa.
        """
        if not self.review_qr_presented_at:
            return ""
        return f"Apresentado em {timezone.localtime(self.review_qr_presented_at):%d/%m/%Y às %H:%M}."

    def can_open(self, step):
        return wf.can_open(self.current_step, step, self.status)

    def progress(self):
        return wf.progress(self.current_step)

    def compute_retention_until(self):
        if not self.completed_at:
            return None
        return add_months(self.completed_at, settings.AUTOCHECK["RETENTION_MONTHS"])

    def __str__(self):
        return f"{self.code or 'Novo atendimento'} — {self.vehicle}"
