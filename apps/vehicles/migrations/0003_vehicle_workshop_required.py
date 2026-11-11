"""Oficinas independentes, parte 3: oficina obrigatória e unicidade dentro de cada oficina."""
import apps.core.django_validators
import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("workshop", "0004_assign_existing_data"),
        ("vehicles", "0002_vehicle_workshop"),
    ]

    operations = [
        migrations.AlterField(
            model_name="vehicle",
            name="workshop",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.PROTECT, related_name="%(class)ss",
                to="workshop.workshopsettings", verbose_name="oficina",
            ),
        ),
        migrations.AlterField(
            model_name="vehicle",
            name="plate",
            field=models.CharField(max_length=8, validators=[apps.core.django_validators.validate_plate], verbose_name="placa"),
        ),
        migrations.AddConstraint(
            model_name="vehicle",
            constraint=models.UniqueConstraint(fields=("workshop", "plate"), name="uniq_vehicle_workshop_plate"),
        ),
    ]
