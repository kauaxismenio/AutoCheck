"""Oficinas e suas contas de acesso. Só a administração da plataforma chama estas funções."""
import secrets

from django.contrib.auth import get_user_model
from django.db import transaction

from apps.workshop.models import WorkshopSettings


def normalize_login(email):
    return (email or "").strip().lower()


def generate_password():
    return secrets.token_urlsafe(12)


def login_account(workshop):
    """A conta ativa da oficina. Contas individuais antigas ficam desativadas, só para o histórico."""
    return next((user for user in workshop.accounts.all() if user.is_active), None)


def login_in_use(email, *, except_account=None):
    users = get_user_model().objects.filter(username=normalize_login(email))
    if except_account is not None:
        users = users.exclude(pk=except_account.pk)
    return users.exists()


def _create_account(workshop, email, password):
    email = normalize_login(email)
    user = get_user_model()(username=email, email=email, workshop=workshop)
    user.set_password(password)
    user.save()
    return user


@transaction.atomic
def create_workshop(name, email, password=None):
    """Devolve a oficina e a senha gerada (None se a senha foi informada)."""
    workshop = WorkshopSettings.objects.create(name=name)
    generated = None if password else generate_password()
    _create_account(workshop, email, password or generated)
    return workshop, generated


@transaction.atomic
def update_login(workshop, email):
    """Altera o e-mail de acesso. Oficina sem conta recebe uma, com a senha gerada devolvida."""
    account = login_account(workshop)
    if account is None:
        generated = generate_password()
        _create_account(workshop, email, generated)
        return generated
    email = normalize_login(email)
    account.username = account.email = email
    account.save(update_fields=["username", "email"])
    return None


def reset_password(account):
    password = generate_password()
    account.set_password(password)
    account.save(update_fields=["password"])
    return password
