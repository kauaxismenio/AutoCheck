from django import forms
from django.contrib.auth.forms import AuthenticationForm
from django.core.exceptions import ValidationError

from apps.core.audit import log_action

from . import throttle


class LoginForm(AuthenticationForm):
    error_messages = {
        "invalid_login": "E-mail ou senha incorretos.",
        "inactive": "Este acesso está desativado. Fale com o responsável pela plataforma.",
    }

    def __init__(self, request=None, *args, **kwargs):
        super().__init__(request, *args, **kwargs)
        self.fields["username"].label = "E-mail"
        self.fields["password"].label = "Senha"
        self.fields["username"].widget.attrs.update({"autocomplete": "username", "autocapitalize": "none", "inputmode": "email"})

    def clean(self):
        username = self.cleaned_data.get("username")
        if throttle.is_locked(username, self.request):
            raise ValidationError(
                "Muitas tentativas sem sucesso. Aguarde 15 minutos e tente de novo.", code="locked",
            )
        try:
            cleaned = super().clean()
        except ValidationError:
            throttle.register_failure(username, self.request)
            log_action("accounts.login_failed", request=self.request)
            raise
        throttle.clear(username, self.request)
        return cleaned
