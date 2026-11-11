"""Registra no atendimento a modalidade, o CNPJ e os dados empresariais informados.

Atendimentos existentes recebem exatamente o que já mostravam, vindo do cadastro: a assinatura
continua válida e o histórico é preservado. O cadastro do cliente não é alterado.
"""
from django.db import migrations, models


def forwards(apps, schema_editor):  # noqa: ARG001
    Attendance = apps.get_model("attendances", "Attendance")
    for attendance in Attendance.objects.select_related("customer"):
        customer = attendance.customer
        Attendance.objects.filter(pk=attendance.pk).update(
            person_type=customer.person_type,
            cnpj="" if attendance.cnpj_not_informed else customer.cnpj or "",
            legal_name=customer.legal_name,
            trade_name=customer.trade_name,
            contact_person=customer.contact_person,
        )


class Migration(migrations.Migration):
    dependencies = [
        ("attendances", "0008_attendance_workshop_required"),
        ("customers", "0003_customer_workshop_required"),
    ]

    operations = [
        migrations.AddField(
            model_name="attendance",
            name="person_type",
            field=models.CharField(choices=[("pf", "CPF — Pessoa Física"), ("pj", "CNPJ — Pessoa Jurídica"), ("ambos", "Ambos")],
                                   default="pf", max_length=5, verbose_name="modalidade"),
        ),
        migrations.AddField(
            model_name="attendance",
            name="cnpj",
            field=models.CharField(blank=True, db_index=True, max_length=18, verbose_name="CNPJ informado"),
        ),
        migrations.AddField(
            model_name="attendance",
            name="legal_name",
            field=models.CharField(blank=True, max_length=200, verbose_name="razão social"),
        ),
        migrations.AddField(
            model_name="attendance",
            name="trade_name",
            field=models.CharField(blank=True, max_length=200, verbose_name="nome fantasia"),
        ),
        migrations.AddField(
            model_name="attendance",
            name="contact_person",
            field=models.CharField(blank=True, max_length=150, verbose_name="responsável"),
        ),
        migrations.RunPython(forwards, migrations.RunPython.noop),
    ]
