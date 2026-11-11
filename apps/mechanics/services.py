from apps.core.audit import log_action

from .models import Mechanic, clean_name, name_key


def get_or_add(name, *, workshop, user=None, request=None):
    """Mecânico informado no atendimento: reaproveita o cadastro de mesmo nome, nunca duplica."""
    name = clean_name(name)
    mechanic, created = Mechanic.objects.get_or_create(workshop=workshop, name_key=name_key(name), defaults={"name": name})
    if created:
        log_action("mechanic.created", request=request, user=user, obj=mechanic)
    elif not mechanic.is_active:
        mechanic.is_active = True
        mechanic.save(update_fields=["is_active", "updated_at"])
        log_action("mechanic.reactivated", request=request, user=user, obj=mechanic)
    return mechanic
