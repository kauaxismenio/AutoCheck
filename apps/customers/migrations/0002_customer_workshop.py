"""Oficinas independentes, parte 1: campo provisório, preenchido em workshop.0004."""
import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("workshop", "0003_workshopsettings_is_active"),
        ("customers", "0001_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="customer",
            name="workshop",
            field=models.ForeignKey(
                null=True, on_delete=django.db.models.deletion.PROTECT, related_name="customers",
                to="workshop.workshopsettings", verbose_name="oficina",
            ),
        ),
    ]
