"""Sem perfis individuais: quem usa o acesso da oficina tem as mesmas permissões."""
from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ("workshop", "0004_assign_existing_data"),
        ("accounts", "0004_user_workshop"),
    ]

    operations = [migrations.RemoveField(model_name="user", name="role")]
