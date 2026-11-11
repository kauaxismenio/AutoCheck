"""Oficinas independentes, parte 2: todo dado existente passa a pertencer à oficina já cadastrada.

Nenhum registro é apagado. Contas individuais antigas (não proprietárias) ficam desativadas,
sem perder o histórico: o acesso da oficina é criado na administração da plataforma.
"""
from django.db import migrations

OWNED = (("customers", "Customer"), ("vehicles", "Vehicle"), ("attendances", "Attendance"),
         ("mechanics", "Mechanic"), ("employees", "Employee"))


def assign_existing_data(apps, schema_editor):
    workshops = apps.get_model("workshop", "WorkshopSettings").objects
    models = [apps.get_model(app_label, name) for app_label, name in OWNED]
    accounts = apps.get_model("accounts", "User").objects.filter(is_superuser=False)
    if not accounts.exists() and not any(model.objects.exists() for model in models):
        return
    workshop = workshops.order_by("pk").first() or workshops.create(name="MINHA OFICINA")
    for model in models:
        model.objects.filter(workshop=None).update(workshop=workshop)
    accounts.update(workshop=workshop, is_active=False)


class Migration(migrations.Migration):
    dependencies = [
        ("workshop", "0003_workshopsettings_is_active"),
        ("accounts", "0004_user_workshop"),
        ("customers", "0002_customer_workshop"),
        ("vehicles", "0002_vehicle_workshop"),
        ("attendances", "0007_attendance_workshop"),
        ("mechanics", "0003_mechanic_workshop"),
        ("employees", "0002_employee_workshop"),
    ]

    operations = [migrations.RunPython(assign_existing_data, migrations.RunPython.noop)]
