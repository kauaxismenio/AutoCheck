"""Formulário único de cadastro: cliente, contato, veículo e origem do atendimento."""
from django import forms
from django.db.models import Q
from django.utils import timezone

from apps.core.django_validators import validate_cnpj, validate_cpf, validate_plate
from apps.core.forms import mark_uppercase
from apps.core.validators.documents import format_cnpj, format_cpf, normalize_cnpj, normalize_cpf
from apps.core.validators.phone import format_phone
from apps.core.validators.plate import format_plate, normalize_plate
from apps.customers.forms import CNPJ_WIDGET, CPF_WIDGET, PHONE_WIDGET, clean_contact, clean_document
from apps.customers.models import PersonType
from apps.employees.models import Employee
from apps.mechanics.models import Mechanic, clean_name, validate_mechanic_name
from apps.vehicles.forms import PLATE_WIDGET

from .models import Origin


class IntakeForm(forms.Form):
    attendant = forms.ModelChoiceField(label="Vendedor/Atendente", queryset=Employee.objects.none(),
                                       empty_label="Selecione...",
                                       error_messages={"required": "Selecione o vendedor/atendente."})
    person_type = forms.ChoiceField(choices=PersonType.choices, widget=forms.HiddenInput, initial=PersonType.PF)
    # Pessoa física
    full_name = forms.CharField(label="Nome completo", required=False, max_length=150)
    cpf = forms.CharField(label="CPF", required=False, max_length=14, widget=CPF_WIDGET)
    cpf_not_informed = forms.BooleanField(label="Cliente não deseja informar CPF", required=False)
    # Pessoa jurídica
    cnpj = forms.CharField(label="CNPJ", required=False, max_length=18, widget=CNPJ_WIDGET)
    cnpj_not_informed = forms.BooleanField(label="Cliente não sabe ou não deseja informar CNPJ", required=False)
    legal_name = forms.CharField(label="Razão Social", required=False, max_length=200)
    trade_name = forms.CharField(label="Nome Fantasia", required=False, max_length=200)
    contact_person = forms.CharField(label="Responsável", required=False, max_length=150)
    # Contato
    phone = forms.CharField(label="Telefone", max_length=20, widget=PHONE_WIDGET)
    email = forms.CharField(label="E-mail", required=False, max_length=254,
                            widget=forms.EmailInput(attrs={"autocomplete": "off"}))
    email_opt_out = forms.BooleanField(label="Cliente não deseja informar e-mail ou receber o relatório", required=False)
    # Veículo
    plate = forms.CharField(label="Placa", max_length=8, widget=PLATE_WIDGET)
    brand = forms.CharField(label="Marca", max_length=60)
    model = forms.CharField(label="Modelo", max_length=80)
    year = forms.IntegerField(label="Ano", required=False, min_value=1900,
                              widget=forms.TextInput(attrs={"data-mask": "number", "inputmode": "numeric", "maxlength": "4"}))
    color = forms.CharField(label="Cor", required=False, max_length=40)
    mileage = forms.IntegerField(label="Quilometragem", min_value=0, max_value=3_000_000,
                                 widget=forms.TextInput(attrs={"data-mask": "number", "inputmode": "numeric", "maxlength": "7"}))
    mechanic = forms.ModelChoiceField(label="Mecânico responsável", queryset=Mechanic.objects.none(), required=False,
                                      empty_label="Selecione...")
    new_mechanic_name = forms.CharField(label="Nome do novo mecânico", required=False, max_length=120,
                                        validators=[validate_mechanic_name])
    # Origem
    origin = forms.ChoiceField(label="Como conheceu nossa loja?",
                               choices=[("", "Selecione...")] + list(Origin.choices))

    def __init__(self, *args, attendance=None, **kwargs):
        self.attendance = attendance
        if attendance is not None:
            kwargs.setdefault("initial", self._initial_from(attendance))
        super().__init__(*args, **kwargs)
        self.use_required_attribute = False
        mark_uppercase(self, "full_name", "legal_name", "trade_name", "brand", "model", "color", "new_mechanic_name")
        eligible = Q(is_active=True)
        if attendance is not None:
            eligible |= Q(pk=attendance.mechanic_id)  # mantém o mecânico mesmo se foi desativado
        self.fields["mechanic"].queryset = Mechanic.objects.filter(eligible)
        eligible_attendants = Q(is_active=True)
        if attendance is not None:
            eligible_attendants |= Q(pk=attendance.attendant_id)  # mantém o funcionário mesmo se foi desativado
        self.fields["attendant"].queryset = Employee.objects.filter(eligible_attendants)
        if attendance is not None and attendance.attendant_id:
            # Escolhido no início, permanece responsável até a finalização; o servidor ignora outro valor.
            self.fields["attendant"].disabled = True

    @staticmethod
    def _initial_from(att):
        customer, vehicle = att.customer, att.vehicle
        return {
            "attendant": att.attendant_id,
            "person_type": att.person_type, "full_name": customer.full_name,
            "cpf": format_cpf(att.informed_cpf) if att.informed_cpf else "",
            "cpf_not_informed": att.cpf_not_informed,
            "cnpj": format_cnpj(att.cnpj) if att.cnpj else "",
            "cnpj_not_informed": att.cnpj_not_informed, "legal_name": att.legal_name,
            "trade_name": att.trade_name, "contact_person": att.contact_person,
            "phone": format_phone(customer.phone), "email": att.customer_email, "email_opt_out": att.email_opt_out,
            "plate": format_plate(vehicle.plate), "brand": vehicle.brand, "model": vehicle.model,
            "year": vehicle.year, "color": vehicle.color, "mileage": att.mileage,
            "mechanic": att.mechanic_id, "origin": att.origin,
        }

    # ------------------------------------------------------------------
    def clean_plate(self):
        value = self.cleaned_data["plate"]
        validate_plate(value)
        return normalize_plate(value)

    def clean_year(self):
        year = self.cleaned_data.get("year")
        if year and year > timezone.localdate().year + 1:
            raise forms.ValidationError("Ano do veículo inválido.")
        return year

    def clean(self):
        cleaned = super().clean()
        kind = cleaned.get("person_type")
        self._clean_person(cleaned, kind)
        self._clean_company(cleaned, kind)
        if cleaned.get("email_opt_out"):
            cleaned["email"] = ""
        clean_contact(self, cleaned)
        self._clean_mechanic(cleaned)
        return cleaned

    def _clean_mechanic(self, cleaned):
        cleaned["new_mechanic_name"] = clean_name(cleaned.get("new_mechanic_name"))
        if cleaned.get("mechanic") or cleaned["new_mechanic_name"]:
            return
        if not self.has_error("mechanic") and not self.has_error("new_mechanic_name"):
            self.add_error("mechanic", "Selecione o mecânico responsável ou adicione um novo.")

    def _clean_person(self, cleaned, kind):
        if kind not in (PersonType.PF, PersonType.AMBOS):
            # Valor digitado em campo oculto não pode valer (nem bloquear).
            cleaned.update(full_name="", cpf=None, cpf_not_informed=False)
            return
        if not cleaned.get("full_name", "").strip():
            self.add_error("full_name", "Informe o nome completo.")
        if cleaned.get("cpf_not_informed"):
            cleaned["cpf"] = None
        elif not cleaned.get("cpf"):
            self.add_error("cpf", "Informe o CPF ou marque que o cliente não deseja informar.")
        else:
            clean_document(self, cleaned, "cpf", validate_cpf, normalize_cpf)

    def _clean_company(self, cleaned, kind):
        if kind not in (PersonType.PJ, PersonType.AMBOS):
            cleaned.update(cnpj=None, cnpj_not_informed=False, legal_name="", trade_name="", contact_person="")
            return
        if not cleaned.get("legal_name", "").strip():
            self.add_error("legal_name", "Informe a razão social.")
        if cleaned.get("cnpj_not_informed"):
            cleaned["cnpj"] = None
        elif not cleaned.get("cnpj"):
            self.add_error("cnpj", "Informe o CNPJ ou marque que o cliente não sabe/não deseja informar.")
        else:
            clean_document(self, cleaned, "cnpj", validate_cnpj, normalize_cnpj)
