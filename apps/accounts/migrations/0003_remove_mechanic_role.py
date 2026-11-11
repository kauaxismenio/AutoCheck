"""Mecânico deixa de ser usuário: perde o acesso e passa a existir só em mechanics.Mechanic.

A conta antiga é mantida desativada e sem senha, porque atendimentos e a auditoria
podem apontar para ela. Depende da cópia feita em attendances.0003.
"""
from django.contrib.auth.hashers import make_password
from django.db import migrations, models


def revoke_mechanic_logins(apps, schema_editor):
    User = apps.get_model("accounts", "User")
    User.objects.filter(role="mecanico").update(role="atendente", is_active=False, password=make_password(None))


class Migration(migrations.Migration):
    dependencies = [
        ("accounts", "0002_loginattempt"),
        ("attendances", "0003_copy_mechanics"),
    ]

    operations = [
        migrations.RunPython(revoke_mechanic_logins, migrations.RunPython.noop),
        migrations.AlterField(
            model_name="user",
            name="role",
            field=models.CharField(
                choices=[("admin", "Administrador"), ("vendedor", "Vendedor"), ("atendente", "Atendente")],
                default="atendente", max_length=20, verbose_name="perfil",
            ),
        ),
    ]
