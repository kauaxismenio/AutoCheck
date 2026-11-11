import apps.core.django_validators
import apps.employees.models
from django.db import migrations, models


class Migration(migrations.Migration):
    initial = True

    dependencies = []

    operations = [
        migrations.CreateModel(
            name="Employee",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("created_at", models.DateTimeField(auto_now_add=True, verbose_name="criado em")),
                ("updated_at", models.DateTimeField(auto_now=True, verbose_name="atualizado em")),
                ("name_key", models.CharField(editable=False, max_length=120, unique=True)),
                ("phone", models.CharField(blank=True, max_length=11, validators=[apps.core.django_validators.validate_phone], verbose_name="telefone")),
                ("is_active", models.BooleanField(db_index=True, default=True, verbose_name="ativo")),
                ("name", models.CharField(max_length=120, validators=[apps.employees.models.validate_employee_name], verbose_name="nome")),
            ],
            options={"verbose_name": "funcionário", "verbose_name_plural": "funcionários", "ordering": ["name"]},
        ),
    ]
