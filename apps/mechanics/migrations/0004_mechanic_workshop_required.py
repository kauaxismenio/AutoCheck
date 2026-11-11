"""Oficinas independentes, parte 3: oficina obrigatória e unicidade dentro de cada oficina."""
import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("workshop", "0004_assign_existing_data"),
        ("mechanics", "0003_mechanic_workshop"),
    ]

    operations = [
        migrations.AlterField(
            model_name="mechanic",
            name="workshop",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.PROTECT, related_name="%(class)ss",
                to="workshop.workshopsettings", verbose_name="oficina",
            ),
        ),
        migrations.AlterField(
            model_name="mechanic",
            name="name_key",
            field=models.CharField(editable=False, max_length=120),
        ),
        migrations.AddConstraint(
            model_name="mechanic",
            constraint=models.UniqueConstraint(fields=("workshop", "name_key"), name="uniq_mechanic_name_per_workshop"),
        ),
    ]
