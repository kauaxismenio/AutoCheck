"""Une os dois caminhos independentes de migração. Não altera nada no banco."""
from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ("attendances", "0009_envio_automatico"),
        ("attendances", "0010_documentos_no_atendimento"),
    ]

    operations = []
