from django.db.models.signals import post_delete
from django.dispatch import receiver

from apps.core.file_cleanup import delete_file_after_commit

from .models import Report


@receiver(post_delete, sender=Report)
def delete_report_file(sender, instance, **kwargs):  # noqa: ARG001
    delete_file_after_commit(instance.file)
