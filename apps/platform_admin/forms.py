from django import forms
from django.contrib.auth.password_validation import validate_password

from apps.core.django_validators import validate_email_address
from apps.core.forms import mark_uppercase
from apps.workshop.models import WorkshopSettings

from . import services


class _LoginEmailMixin:
    account = None

    def clean_login_email(self):
        email = services.normalize_login(self.cleaned_data["login_email"])
        validate_email_address(email)
        if services.login_in_use(email, except_account=self.account):
            raise forms.ValidationError("Este e-mail já é o acesso de outra conta.")
        return email


class WorkshopCreateForm(_LoginEmailMixin, forms.Form):
    name = forms.CharField(label="Nome da oficina", max_length=150)
    login_email = forms.CharField(label="E-mail de acesso", max_length=150,
                                  widget=forms.EmailInput(attrs={"autocomplete": "off"}))
    password = forms.CharField(label="Senha inicial", required=False, strip=False,
                               help_text="Deixe em branco para o sistema gerar uma senha segura.",
                               widget=forms.PasswordInput(attrs={"autocomplete": "new-password"}))

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.use_required_attribute = False
        mark_uppercase(self, "name")

    def clean_password(self):
        password = self.cleaned_data.get("password")
        if password:
            validate_password(password)
        return password


class WorkshopEditForm(_LoginEmailMixin, forms.ModelForm):
    login_email = forms.CharField(label="E-mail de acesso", max_length=150,
                                  widget=forms.EmailInput(attrs={"autocomplete": "off"}))

    class Meta:
        model = WorkshopSettings
        fields = ["name", "login_email", "is_active"]
        labels = {"is_active": "Oficina ativa (pode acessar o sistema)"}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.use_required_attribute = False
        mark_uppercase(self, "name")
        self.account = services.login_account(self.instance)
        if self.account is not None:
            self.fields["login_email"].initial = self.account.email
