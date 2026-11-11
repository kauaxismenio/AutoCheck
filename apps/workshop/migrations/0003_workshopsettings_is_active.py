from django.db import migrations, models


class Migration(migrations.Migration):
    """Cada registro passa a ser uma oficina independente."""

    dependencies = [("workshop", "0002_workshopsettings_google_review_url")]

    operations = [
        migrations.AddField(
            model_name="workshopsettings",
            name="is_active",
            field=models.BooleanField(default=True, verbose_name="oficina ativa"),
        ),
        migrations.AlterModelOptions(
            name="workshopsettings",
            options={"verbose_name": "oficina", "verbose_name_plural": "oficinas"},
        ),
    ]
