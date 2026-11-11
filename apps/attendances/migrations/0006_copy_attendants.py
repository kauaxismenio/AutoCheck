"""Atendimentos antigos: o funcionário registrado é quem os abriu.

O cadastro nasce desativado: o nome continua no histórico sem entrar na lista de
escolha. Se a pessoa for funcionária de verdade, basta reativá-la em Configurações.
"""
from django.db import migrations

from apps.core.validators.text import to_upper
from apps.mechanics.models import clean_name, name_key


def copy_attendants(apps, schema_editor):
    User = apps.get_model("accounts", "User")
    Employee = apps.get_model("employees", "Employee")
    Attendance = apps.get_model("attendances", "Attendance")

    opened_by = Attendance.objects.exclude(created_by=None).values_list("created_by_id", flat=True).distinct()
    used_keys = set()
    for user in User.objects.filter(pk__in=list(opened_by)).order_by("pk"):
        name = clean_name(f"{user.first_name} {user.last_name}") or user.username
        if name_key(name) in used_keys:  # dois homônimos continuam sendo duas pessoas
            name = f"{name} ({user.username})"
        employee = Employee.objects.create(name=to_upper(name), name_key=name_key(name), phone=user.phone, is_active=False)
        used_keys.add(employee.name_key)
        Attendance.objects.filter(created_by_id=user.pk).update(attendant=employee)


class Migration(migrations.Migration):
    dependencies = [
        ("accounts", "0003_remove_mechanic_role"),
        ("attendances", "0005_attendance_attendant"),
    ]

    operations = [migrations.RunPython(copy_attendants, migrations.RunPython.noop)]
