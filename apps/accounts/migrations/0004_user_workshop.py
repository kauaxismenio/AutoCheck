"""A conta de acesso pertence a uma oficina; o proprietário da plataforma não tem oficina."""
import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("workshop", "0003_workshopsettings_is_active"),
        ("accounts", "0003_remove_mechanic_role"),
    ]

    operations = [
        migrations.AddField(
            model_name="user",
            name="workshop",
            field=models.ForeignKey(
                blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="accounts",
                to="workshop.workshopsettings", verbose_name="oficina",
            ),
        ),
    ]
