"""Oficinas independentes, parte 3: oficina obrigatória e unicidade dentro de cada oficina."""
import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("workshop", "0004_assign_existing_data"),
        ("attendances", "0007_attendance_workshop"),
    ]

    operations = [
        migrations.AlterField(
            model_name="attendance",
            name="workshop",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.PROTECT, related_name="%(class)ss",
                to="workshop.workshopsettings", verbose_name="oficina",
            ),
        ),
        migrations.AlterField(
            model_name="attendance",
            name="attendant",
            field=models.ForeignKey(
                null=True, on_delete=django.db.models.deletion.PROTECT, related_name="attendances",
                to="employees.employee", verbose_name="vendedor/atendente",
            ),
        ),
    ]
