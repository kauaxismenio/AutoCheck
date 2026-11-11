from django import forms
from django.core.exceptions import ValidationError

from apps.core.forms import mark_uppercase
from apps.core.images import process_upload

from .models import WorkshopSettings


class ReviewLinkForm(forms.ModelForm):
    """Formulário próprio: salvar o link não reenvia nem revalida os dados da oficina."""

    google_review_url = forms.URLField(
        label="LINK DE AVALIAÇÃO DA OFICINA NO GOOGLE", required=False, max_length=500, assume_scheme="https",
        help_text="Copie o link em \"Pedir avaliações\" no Perfil da Empresa no Google. Deixe em branco para remover o QR Code.",
        widget=forms.URLInput(attrs={"inputmode": "url", "autocomplete": "off", "placeholder": "https://g.page/r/.../review"}),
    )

    class Meta:
        model = WorkshopSettings
        fields = ["google_review_url"]


class WorkshopSettingsForm(forms.ModelForm):
    # Aceita o valor com máscara; o modelo normaliza ao salvar.
    logo = forms.ImageField(label="Logotipo", required=False, widget=forms.ClearableFileInput)

    class Meta:
        model = WorkshopSettings
        fields = ["name", "logo", "cnpj", "phone", "address", "report_email"]
        widgets = {
            "cnpj": forms.TextInput(attrs={"data-mask": "cnpj", "autocapitalize": "characters"}),
            "phone": forms.TextInput(attrs={"data-mask": "phone", "inputmode": "tel"}),
            "report_email": forms.EmailInput(attrs={"autocomplete": "email"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        mark_uppercase(self, "name")
        self._previous_logo_name = self.instance.logo.name if self.instance.logo else ""
        self.initial["cnpj"] = self._formatted(self.instance.cnpj, "cnpj")
        self.initial["phone"] = self._formatted(self.instance.phone, "phone")

    @staticmethod
    def _formatted(value, kind):
        from apps.core.validators.documents import format_cnpj
        from apps.core.validators.phone import format_phone

        if not value:
            return ""
        return format_cnpj(value) if kind == "cnpj" else format_phone(value)

    def clean_logo(self):
        logo = self.cleaned_data.get("logo")
        # False = "limpar"; arquivo sem content_type = o logotipo já salvo.
        if not logo or not hasattr(logo, "content_type"):
            return logo
        try:
            return process_upload(logo, max_side=800, keep_alpha=True).content
        except ValidationError as exc:
            raise ValidationError(exc.messages) from exc

    def save(self, commit=True):
        from django.core.files.storage import default_storage
        from django.db import transaction

        instance = super().save(commit=commit)
        previous = self._previous_logo_name
        current = instance.logo.name if instance.logo else ""
        if commit and previous and previous != current:
            transaction.on_commit(lambda: default_storage.delete(previous))
        return instance
