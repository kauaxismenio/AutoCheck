"""Login por e-mail. A conta da oficina usa o e-mail, em minúsculas, como nome de acesso."""
from django.contrib.auth.backends import ModelBackend


class WorkshopAccountBackend(ModelBackend):
    def authenticate(self, request, username=None, password=None, **kwargs):
        if username and "@" in username:
            username = username.strip().lower()
        return super().authenticate(request, username=username, password=password, **kwargs)

    def user_can_authenticate(self, user):
        """Vale também para sessões abertas: desativar a oficina encerra o acesso na hora."""
        if not super().user_can_authenticate(user):
            return False
        if user.is_superuser:
            return True
        return user.workshop_id is not None and user.workshop.is_active
