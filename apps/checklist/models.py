"""Catálogo de componentes e avaliações do checklist por atendimento."""
from django.conf import settings
from django.db import models

from apps.core.tenancy import AttendanceScopedManager
from apps.core.models import TimeStampedModel


class Result(models.TextChoices):
    """Avaliação obrigatória. Não existe 'Não verificado'.

    O valor vazio ("") significa apenas que o item ainda não foi avaliado e
    bloqueia o avanço da etapa.
    """

    OK = "ok", "OK"
    SUBSTITUIR = "substituir", "SUBSTITUIR"


class ChecklistCategory(models.Model):
    code = models.SlugField("código", max_length=40, unique=True)
    name = models.CharField("nome", max_length=80)
    order = models.PositiveSmallIntegerField("ordem", default=0)
    active = models.BooleanField("ativa", default=True)

    class Meta:
        verbose_name = "categoria do checklist"
        verbose_name_plural = "categorias do checklist"
        ordering = ["order", "name"]

    def __str__(self):
        return self.name


class ChecklistComponent(models.Model):
    category = models.ForeignKey(ChecklistCategory, verbose_name="categoria", on_delete=models.PROTECT, related_name="components")
    code = models.SlugField("código", max_length=60, unique=True)
    name = models.CharField("componente", max_length=120)
    order = models.PositiveSmallIntegerField("ordem", default=0)
    active = models.BooleanField("ativo", default=True)

    class Meta:
        verbose_name = "componente do checklist"
        verbose_name_plural = "componentes do checklist"
        ordering = ["category__order", "order", "name"]

    def __str__(self):
        return f"{self.category.name} — {self.name}"


class ChecklistItem(TimeStampedModel):
    """Avaliação de um componente em um atendimento.

    Nome do componente e da categoria são copiados no momento da criação, para
    que o histórico e o PDF não mudem se o catálogo for editado depois.
    """

    attendance = models.ForeignKey("attendances.Attendance", on_delete=models.CASCADE, related_name="checklist_items")
    component = models.ForeignKey(ChecklistComponent, on_delete=models.PROTECT, related_name="items")
    category_name = models.CharField("categoria", max_length=80)
    component_name = models.CharField("componente", max_length=120)
    order = models.PositiveIntegerField("ordem", default=0)
    result = models.CharField("avaliação", max_length=12, choices=Result.choices, blank=True)
    notes = models.TextField("observações", blank=True)
    evaluated_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="+")
    evaluated_at = models.DateTimeField("avaliado em", null=True, blank=True)

    objects = AttendanceScopedManager()

    class Meta:
        verbose_name = "item do checklist"
        verbose_name_plural = "itens do checklist"
        ordering = ["order"]
        constraints = [
            models.UniqueConstraint(fields=["attendance", "component"], name="uniq_checklist_item_per_attendance"),
        ]

    def __str__(self):
        return f"{self.component_name}: {self.get_result_display() or 'pendente'}"
