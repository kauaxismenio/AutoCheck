"""Oficinas independentes, parte 3: oficina obrigatória e unicidade dentro de cada oficina."""
import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("workshop", "0004_assign_existing_data"),
        ("customers", "0002_customer_workshop"),
    ]

    operations = [
        migrations.AlterField(
            model_name="customer",
            name="workshop",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.PROTECT, related_name="%(class)ss",
                to="workshop.workshopsettings", verbose_name="oficina",
            ),
        ),
        migrations.RemoveConstraint(model_name="customer", name="uniq_customer_cpf"),
        migrations.RemoveConstraint(model_name="customer", name="uniq_customer_cnpj"),
        migrations.AddConstraint(
            model_name="customer",
            constraint=models.UniqueConstraint(condition=models.Q(("cpf__isnull", False)), fields=("workshop", "cpf"), name="uniq_customer_workshop_cpf"),
        ),
        migrations.AddConstraint(
            model_name="customer",
            constraint=models.UniqueConstraint(condition=models.Q(("cnpj__isnull", False)), fields=("workshop", "cnpj"), name="uniq_customer_workshop_cnpj"),
        ),
    ]
