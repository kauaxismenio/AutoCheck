from django import forms

from apps.core.django_validators import validate_phone
from apps.core.forms import mark_uppercase
from apps.core.validators.phone import format_phone, normalize_phone

from .models import Mechanic, name_key


class TeamMemberForm(forms.ModelForm):
    """Base dos cadastros de mecânicos e de vendedores/atendentes."""

    duplicate_message = ""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.use_required_attribute = False
        mark_uppercase(self, "name")

    def clean_name(self):
        name = self.cleaned_data["name"]
        same_name = self._meta.model.objects.filter(name_key=name_key(name)).exclude(pk=self.instance.pk)
        if same_name.exists():
            raise forms.ValidationError(self.duplicate_message)
        return name


class MechanicForm(TeamMemberForm):
    duplicate_message = "Já existe um mecânico com este nome."
    phone = forms.CharField(label="Telefone", required=False, max_length=20,
                            widget=forms.TextInput(attrs={"data-mask": "phone", "inputmode": "tel"}))

    class Meta:
        model = Mechanic
        fields = ["name", "phone", "is_active"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.initial["phone"] = format_phone(self.instance.phone) if self.instance.phone else ""

    def clean_phone(self):
        value = self.cleaned_data.get("phone", "")
        if not value:
            return ""
        validate_phone(value)
        return normalize_phone(value)
