"""Separação de usuários e mecânicos, parte 3, e registro da apresentação do QR Code de avaliação."""
import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("attendances", "0003_copy_mechanics"),
    ]

    operations = [
        migrations.RemoveField(model_name="attendance", name="mechanic"),
        migrations.RenameField(model_name="attendance", old_name="mechanic_ref", new_name="mechanic"),
        migrations.AlterField(
            model_name="attendance",
            name="mechanic",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.PROTECT, related_name="attendances", to="mechanics.mechanic",
                verbose_name="mecânico responsável",
            ),
        ),
        migrations.AlterField(
            model_name="attendance",
            name="created_by",
            field=models.ForeignKey(
                null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="attendances_created",
                to=settings.AUTH_USER_MODEL, verbose_name="funcionário do atendimento",
            ),
        ),
        migrations.AddField(
            model_name="attendance",
            name="review_qr_presented_at",
            field=models.DateTimeField(blank=True, null=True, verbose_name="QR Code de avaliação apresentado em"),
        ),
        migrations.AddField(
            model_name="attendance",
            name="review_qr_presented_by",
            field=models.ForeignKey(
                blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="+",
                to=settings.AUTH_USER_MODEL, verbose_name="QR Code apresentado por",
            ),
        ),
    ]
