"""Leva os envios automáticos existentes para a chave atendimento + versão + endereço.

Sem isso, um envio antigo seria tratado como inexistente e poderia ser repetido.
Nenhum registro é apagado. Os pendentes antigos continuam sem `next_attempt_at`:
a fila automática não os envia, para clientes antigos não receberem relatórios de surpresa.
"""
import hashlib

from django.db import migrations


def _new_key(row):
    address = hashlib.sha256(row.recipient_email.strip().lower().encode()).hexdigest()
    return f"auto:{row.attendance_id}:v{row.report.version}:{address}"


def forwards(apps, schema_editor):  # noqa: ARG001
    EmailDispatch = apps.get_model("mailing", "EmailDispatch")
    seen = set(EmailDispatch.objects.exclude(idempotency_key__startswith="auto:").values_list("idempotency_key", flat=True))
    for row in EmailDispatch.objects.filter(is_manual_resend=False).select_related("report").order_by("pk"):
        key = _new_key(row)
        if key in seen:
            continue  # oficina e cliente com o mesmo endereço: o segundo registro mantém a chave antiga
        seen.add(key)
        EmailDispatch.objects.filter(pk=row.pk).update(idempotency_key=key)


def backwards(apps, schema_editor):  # noqa: ARG001
    EmailDispatch = apps.get_model("mailing", "EmailDispatch")
    for row in EmailDispatch.objects.filter(is_manual_resend=False, idempotency_key__startswith="auto:"):
        EmailDispatch.objects.filter(pk=row.pk).update(
            idempotency_key=f"auto:{row.report_id}:{row.recipient_type}:{row.recipient_email.lower()}",
        )


class Migration(migrations.Migration):
    dependencies = [
        ("mailing", "0002_envio_automatico"),
    ]

    operations = [
        migrations.RunPython(forwards, backwards),
    ]
