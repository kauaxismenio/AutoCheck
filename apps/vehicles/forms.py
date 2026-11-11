from django import forms
from django.core.exceptions import ValidationError

from apps.core.django_validators import validate_plate
from apps.core.forms import mark_uppercase
from apps.core.validators.plate import format_plate, normalize_plate

from apps.customers.models import Customer

from .models import Vehicle

PLATE_WIDGET = forms.TextInput(attrs={"data-mask": "plate", "autocapitalize": "characters", "autocomplete": "off"})


class VehicleForm(forms.ModelForm):
    plate = forms.CharField(label="Placa", max_length=8, widget=PLATE_WIDGET)
    year = forms.IntegerField(label="Ano", required=False, min_value=1900, max_value=2100,
                              widget=forms.TextInput(attrs={"data-mask": "number", "inputmode": "numeric", "maxlength": "4"}))

    class Meta:
        model = Vehicle
        fields = ["customer", "plate", "brand", "model", "year", "color", "chassis"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.use_required_attribute = False
        mark_uppercase(self, "brand", "model", "color")
        # A lista é montada aqui, na requisição: a declarada na classe não teria o filtro da oficina.
        self.fields["customer"].queryset = Customer.objects.all()
        if self.instance.pk:
            self.initial["plate"] = format_plate(self.instance.plate)

    def clean_plate(self):
        value = self.cleaned_data["plate"]
        try:
            validate_plate(value)
        except ValidationError as exc:
            raise ValidationError(exc.messages) from exc
        plate = normalize_plate(value)
        if Vehicle.objects.filter(plate=plate).exclude(pk=self.instance.pk).exists():
            raise ValidationError("Já existe um veículo com esta placa.")
        return plate
