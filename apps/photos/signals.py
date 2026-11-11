"""Remove o arquivo físico quando o registro da foto é excluído."""
from django.db.models.signals import post_delete
from django.dispatch import receiver

from apps.core.file_cleanup import delete_file_after_commit

from .models import Photo


@receiver(post_delete, sender=Photo)
def delete_photo_file(sender, instance, **kwargs):  # noqa: ARG001
    delete_file_after_commit(instance.image)
