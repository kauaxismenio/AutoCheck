from django import forms
from django.core.exceptions import ValidationError

from apps.core.django_validators import validate_cnpj, validate_cpf, validate_email_address, validate_phone
from apps.core.forms import mark_uppercase
from apps.core.validators.documents import format_cnpj, format_cpf, normalize_cnpj, normalize_cpf
from apps.core.validators.email import normalize_email
from apps.core.validators.phone import format_phone, normalize_phone

from .models import Customer, PersonType

CPF_WIDGET = forms.TextInput(attrs={"data-mask": "cpf", "inputmode": "numeric", "autocomplete": "off"})
CNPJ_WIDGET = forms.TextInput(attrs={"data-mask": "cnpj", "autocapitalize": "characters", "autocomplete": "off"})
PHONE_WIDGET = forms.TextInput(attrs={"data-mask": "phone", "inputmode": "tel", "autocomplete": "off"})


def clean_contact(form, cleaned):
    """Telefone e e-mail: regras comuns ao cadastro avulso e ao atendimento."""
    phone = cleaned.get("phone")
    if phone:
        try:
            validate_phone(phone)
            cleaned["phone"] = normalize_phone(phone)
        except ValidationError as exc:
            form.add_error("phone", exc)
    email = cleaned.get("email")
    if email:
        try:
            validate_email_address(email)
            cleaned["email"] = normalize_email(email)
        except ValidationError as exc:
            form.add_error("email", exc)


def clean_document(form, cleaned, field, validator, normalizer):
    value = cleaned.get(field)
    if not value:
        cleaned[field] = None
        return
    try:
        validator(value)
        cleaned[field] = normalizer(value)
    except ValidationError as exc:
        form.add_error(field, exc)


class CustomerForm(forms.ModelForm):
    person_type = forms.ChoiceField(choices=PersonType.choices, widget=forms.HiddenInput, initial=PersonType.PF)
    cpf = forms.CharField(label="CPF", required=False, max_length=14, widget=CPF_WIDGET)
    cnpj = forms.CharField(label="CNPJ", required=False, max_length=18, widget=CNPJ_WIDGET)
    phone = forms.CharField(label="Telefone", max_length=20, widget=PHONE_WIDGET)
    email = forms.CharField(label="E-mail", required=False, max_length=254,
                            widget=forms.EmailInput(attrs={"autocomplete": "off"}))

    class Meta:
        model = Customer
        fields = ["person_type", "full_name", "cpf", "cnpj", "legal_name", "trade_name", "contact_person",
                  "phone", "email", "address"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.use_required_attribute = False
        mark_uppercase(self, "full_name", "legal_name", "trade_name")
        if self.instance.pk:
            self.initial["cpf"] = format_cpf(self.instance.cpf) if self.instance.cpf else ""
            self.initial["cnpj"] = format_cnpj(self.instance.cnpj) if self.instance.cnpj else ""
            self.initial["phone"] = format_phone(self.instance.phone)

    def clean(self):
        cleaned = super().clean()
        kind = cleaned.get("person_type")
        if kind == PersonType.PF:
            # Cliente que já tem CNPJ não perde o dado por uma troca de cartão.
            if self.instance.cnpj:
                self.add_error("person_type", "Este cliente tem CNPJ cadastrado. Selecione 'Ambos'.")
            cleaned["cnpj"] = None
        elif kind == PersonType.PJ:
            if self.instance.cpf:
                self.add_error("person_type", "Este cliente tem CPF cadastrado. Selecione 'Ambos'.")
            cleaned["cpf"] = None
        clean_document(self, cleaned, "cpf", validate_cpf, normalize_cpf)
        clean_document(self, cleaned, "cnpj", validate_cnpj, normalize_cnpj)
        clean_contact(self, cleaned)
        self._check_unique_document(cleaned, "cpf", "CPF")
        self._check_unique_document(cleaned, "cnpj", "CNPJ")
        return cleaned

    def _check_unique_document(self, cleaned, field, label):
        value = cleaned.get(field)
        if value and Customer.objects.filter(**{field: value}).exclude(pk=self.instance.pk).exists():
            self.add_error(field, f"Já existe um cliente com este {label}.")
