"""Separação de usuários e mecânicos, parte 1: coluna provisória para o novo cadastro."""
import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("mechanics", "0001_initial"),
        ("attendances", "0001_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="attendance",
            name="mechanic_ref",
            field=models.ForeignKey(
                null=True, on_delete=django.db.models.deletion.PROTECT, related_name="+", to="mechanics.mechanic",
            ),
        ),
    ]
