"""Converte para maiúsculas os registros já existentes. Só dados; nenhuma coluna muda.

`updated_at` não é tocado: é uma padronização de grafia, não uma edição do cadastro.
"""
from django.db import migrations

from apps.core.validators.text import to_upper

FIELDS = (
    ("customers", "Customer", ("full_name", "legal_name", "trade_name")),
    ("vehicles", "Vehicle", ("brand", "model", "color")),
    ("mechanics", "Mechanic", ("name",)),
    ("accounts", "User", ("first_name", "last_name")),
    ("workshop", "WorkshopSettings", ("name",)),
)


def uppercase_existing(apps, schema_editor):
    for app_label, model_name, fields in FIELDS:
        model = apps.get_model(app_label, model_name)
        changed = []
        for obj in model.objects.only("pk", *fields).iterator():
            before = [getattr(obj, field) for field in fields]
            after = [to_upper(value) for value in before]
            if before != after:
                for field, value in zip(fields, after):
                    setattr(obj, field, value)
                changed.append(obj)
        if changed:
            model.objects.bulk_update(changed, fields, batch_size=200)


class Migration(migrations.Migration):
    dependencies = [
        ("core", "0001_initial"),
        ("customers", "0001_initial"),
        ("vehicles", "0001_initial"),
        ("mechanics", "0001_initial"),
        ("accounts", "0003_remove_mechanic_role"),
        ("workshop", "0002_workshopsettings_google_review_url"),
    ]

    operations = [migrations.RunPython(uppercase_existing, migrations.RunPython.noop)]
