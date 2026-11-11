"""Funcionário do atendimento passa a ser escolhido; created_by volta a ser só a conta que abriu."""
import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("employees", "0001_initial"),
        ("attendances", "0004_attendance_mechanic_and_review_qr"),
    ]

    operations = [
        migrations.AddField(
            model_name="attendance",
            name="attendant",
            field=models.ForeignKey(
                null=True, on_delete=django.db.models.deletion.PROTECT, related_name="attendances",
                to="employees.employee", verbose_name="funcionário do atendimento",
            ),
        ),
        migrations.AlterField(
            model_name="attendance",
            name="created_by",
            field=models.ForeignKey(
                null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="attendances_created",
                to=settings.AUTH_USER_MODEL, verbose_name="aberto por",
            ),
        ),
    ]
