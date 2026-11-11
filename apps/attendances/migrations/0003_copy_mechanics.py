"""Separação de usuários e mecânicos, parte 2: cria o cadastro a partir dos usuários existentes.

Quem tinha o perfil Mecânico vira mecânico ativo. Administrador que apareceu como
responsável em atendimento antigo vira mecânico desativado: o nome continua no
histórico sem entrar na lista de escolha; se também trabalha como mecânico, basta reativá-lo.

Migração de mão única: a volta só funciona sem atendimentos (usada nos testes); com dados reais, restaure o backup do banco.
"""
from django.db import migrations
from django.db.models import Q

from apps.mechanics.models import clean_name, name_key


def _available_name(user, used_keys):
    name = clean_name(f"{user.first_name} {user.last_name}") or user.username
    if name_key(name) in used_keys:  # dois usuários homônimos continuam sendo duas pessoas
        name = f"{name} ({user.username})"
    return name


def copy_mechanics(apps, schema_editor):
    User = apps.get_model("accounts", "User")
    Mechanic = apps.get_model("mechanics", "Mechanic")
    Attendance = apps.get_model("attendances", "Attendance")

    referenced = Attendance.objects.values_list("mechanic_id", flat=True).distinct()
    used_keys = set()
    for user in User.objects.filter(Q(pk__in=list(referenced)) | Q(role="mecanico")).order_by("pk"):
        name = _available_name(user, used_keys)
        mechanic = Mechanic.objects.create(
            name=name, name_key=name_key(name), phone=user.phone,
            is_active=user.is_active and user.role == "mecanico",
        )
        used_keys.add(mechanic.name_key)
        Attendance.objects.filter(mechanic_id=user.pk).update(mechanic_ref=mechanic)


class Migration(migrations.Migration):
    dependencies = [
        ("accounts", "0002_loginattempt"),
        ("attendances", "0002_attendance_mechanic_ref"),
    ]

    operations = [migrations.RunPython(copy_mechanics, migrations.RunPython.noop)]
