"""Oficinas independentes, parte 3: oficina obrigatória e unicidade dentro de cada oficina."""
import apps.employees.models
import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("workshop", "0004_assign_existing_data"),
        ("employees", "0002_employee_workshop"),
    ]

    operations = [
        migrations.AlterField(
            model_name="employee",
            name="workshop",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.PROTECT, related_name="%(class)ss",
                to="workshop.workshopsettings", verbose_name="oficina",
            ),
        ),
        migrations.AlterField(
            model_name="employee",
            name="name_key",
            field=models.CharField(editable=False, max_length=120),
        ),
        migrations.AddConstraint(
            model_name="employee",
            constraint=models.UniqueConstraint(fields=("workshop", "name_key"), name="uniq_employee_name_per_workshop"),
        ),
        migrations.RemoveField(model_name="employee", name="phone"),
        migrations.AlterField(
            model_name="employee",
            name="name",
            field=models.CharField(max_length=120, validators=[apps.employees.models.validate_employee_name], verbose_name="nome completo"),
        ),
        migrations.AlterModelOptions(
            name="employee",
            options={"ordering": ["name"], "verbose_name": "vendedor/atendente", "verbose_name_plural": "vendedores/atendentes"},
        ),
    ]
