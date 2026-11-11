"""Carrega/atualiza o catálogo do checklist de forma idempotente."""
from django.core.management.base import BaseCommand
from django.db import transaction

from apps.checklist.catalog import CATALOG
from apps.checklist.models import ChecklistCategory, ChecklistComponent


class Command(BaseCommand):
    help = "Cria ou atualiza as categorias e componentes do checklist (não apaga nada)."

    @transaction.atomic
    def handle(self, *args, **options):
        created = updated = 0
        for cat_order, (cat_code, cat_name, components) in enumerate(CATALOG, start=1):
            category, _ = ChecklistCategory.objects.update_or_create(
                code=cat_code, defaults={"name": cat_name, "order": cat_order},
            )
            for comp_order, (comp_code, comp_name) in enumerate(components, start=1):
                _, was_created = ChecklistComponent.objects.update_or_create(
                    code=comp_code,
                    defaults={"category": category, "name": comp_name, "order": comp_order},
                )
                created += was_created
                updated += not was_created
        self.stdout.write(self.style.SUCCESS(
            f"Checklist: {created} componente(s) criado(s), {updated} atualizado(s)."
        ))
