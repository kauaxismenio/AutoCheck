from django.test import TestCase
from django.urls import reverse

from apps.attendances import workflow as wf
from apps.attendances.models import Attendance
from apps.core.models import AuditLog
from apps.core.testing import make_attendance, make_customer, make_employee, make_mechanic, make_user, make_vehicle
from apps.customers.models import Customer
from apps.vehicles.models import Vehicle


def payload(mechanic, **extra):
    data = {
        "person_type": "pf", "full_name": "Maria Souza", "cpf": "529.982.247-25",
        "phone": "(81) 9 9000-1712", "email": "maria@empresa.com.br",
        "plate": "abc1d23", "brand": "Fiat", "model": "Argo", "year": "2022", "color": "Prata",
        "mileage": "45210", "mechanic": mechanic.pk, "origin": "instagram", "attendant": make_employee().pk,
    }
    data.update(extra)
    return data


class IntakeBase(TestCase):
    def setUp(self):
        self.mechanic = make_mechanic()
        self.user = make_user("ana")
        self.client.force_login(self.user)
        self.url = reverse("attendances:new")

    def post(self, **extra):
        return self.client.post(self.url, payload(self.mechanic, **extra))


class IntakeRulesTests(IntakeBase):
    def test_form_renders_cards_and_single_origin_select(self):
        response = self.client.get(self.url)
        self.assertContains(response, 'data-person-card="pf"')
        self.assertContains(response, 'data-person-card="pj"')
        self.assertContains(response, 'data-person-card="ambos"')
        self.assertContains(response, "Como conheceu nossa loja?")
        self.assertNotContains(response, 'type="radio"')
        self.assertNotContains(response, "chassi", msg_prefix="sem chassi nesta tela")
        self.assertNotContains(response, "Endereço")

    def test_requires_login(self):
        self.client.logout()
        self.assertEqual(self.client.get(self.url).status_code, 302)

    def test_creates_everything_and_advances_to_checkin(self):
        self.post()
        att = Attendance.objects.get()
        self.assertEqual(att.current_step, wf.CHECKIN)
        self.assertEqual(att.customer.cpf, "52998224725")
        self.assertEqual(att.customer.phone, "81990001712")
        self.assertEqual(att.vehicle.plate, "ABC1D23")
        self.assertEqual(att.vehicle.last_mileage, 45210)
        self.assertEqual(att.customer_email, "maria@empresa.com.br")
        self.assertEqual(att.created_by, self.user)
        self.assertEqual(att.origin, "instagram")
        self.assertTrue(AuditLog.objects.filter(action="attendance.created", attendance_id=att.pk).exists())

    def test_invalid_cpf_blocks(self):
        response = self.post(cpf="111.111.111-11")
        self.assertContains(response, "CPF inválido")
        self.assertEqual(Attendance.objects.count(), 0)
        self.assertEqual(Customer.objects.count(), 0)

    def test_cpf_opt_out_ignores_cpf_value(self):
        self.post(cpf="111.111.111-11", cpf_not_informed="on")
        att = Attendance.objects.get()
        self.assertTrue(att.cpf_not_informed)
        self.assertIsNone(att.customer.cpf)

    def test_cpf_required_without_opt_out(self):
        self.assertContains(self.post(cpf=""), "Informe o CPF")

    def test_name_required(self):
        self.assertContains(self.post(full_name=""), "Informe o nome completo")

    def test_alphanumeric_cnpj_accepted(self):
        self.post(person_type="pj", cpf="", full_name="", cnpj="12.abc.345/01de-35", legal_name="Oficina X Ltda")
        customer = Customer.objects.get()
        self.assertEqual(customer.cnpj, "12ABC34501DE35")
        self.assertEqual(customer.person_type, "pj")

    def test_invalid_cnpj_rejected(self):
        response = self.post(person_type="pj", cnpj="12.ABC.345/01DE-34", legal_name="X")
        self.assertContains(response, "CNPJ inválido")

    def test_legal_name_required_even_without_cnpj(self):
        response = self.post(person_type="pj", cnpj_not_informed="on")
        self.assertContains(response, "Informe a razão social")

    def test_cnpj_opt_out_keeps_company_fields(self):
        self.post(person_type="pj", cnpj_not_informed="on", legal_name="Oficina X", trade_name="X", contact_person="Rui")
        customer = Customer.objects.get()
        self.assertIsNone(customer.cnpj)
        self.assertEqual((customer.legal_name, customer.trade_name, customer.contact_person), ("OFICINA X", "X", "Rui"))

    def test_both_opt_outs_are_independent(self):
        self.post(person_type="ambos", cpf_not_informed="on", cnpj="12.ABC.345/01DE-35", legal_name="Y Ltda")
        att = Attendance.objects.get()
        self.assertTrue(att.cpf_not_informed)
        self.assertFalse(att.cnpj_not_informed)
        self.assertEqual(att.customer.cnpj, "12ABC34501DE35")

    def test_hidden_mode_values_do_not_block_or_persist(self):
        # Usuário digitou CNPJ inválido, depois voltou para CPF: o oculto não vale.
        self.post(person_type="pf", cnpj="XX", legal_name="Fantasma")
        customer = Customer.objects.get()
        self.assertIsNone(customer.cnpj)
        self.assertEqual(customer.legal_name, "")

    def test_phone_required_and_validated(self):
        self.assertContains(self.post(phone=""), "obrigatório")
        self.assertContains(self.post(phone="1234"), "Telefone inválido")

    def test_landline_accepted(self):
        self.post(phone="(81) 3456-7890")
        self.assertEqual(Customer.objects.get().phone, "8134567890")

    def test_email_optional_and_domain_validated(self):
        self.assertContains(self.post(email="a@b"), "e-mail")
        self.post(email="")
        self.assertEqual(Attendance.objects.get().customer_email, "")

    def test_email_opt_out_hides_and_records(self):
        self.post(email="invalido", email_opt_out="on")
        att = Attendance.objects.get()
        self.assertTrue(att.email_opt_out)
        self.assertFalse(att.should_email_customer)

    def test_email_opt_out_keeps_historic_customer_email(self):
        make_customer(email="antigo@empresa.com.br")
        self.post(email="", email_opt_out="on")
        att = Attendance.objects.get()
        self.assertEqual(att.customer.email, "antigo@empresa.com.br")
        self.assertEqual(att.customer_email, "")

    def test_plate_formats(self):
        self.post(plate="abc-1234")
        self.assertEqual(Vehicle.objects.get().plate, "ABC1234")

    def test_invalid_plate(self):
        self.assertContains(self.post(plate="AB-12"), "Placa inválida")

    def test_mileage_rejects_letters(self):
        response = self.post(mileage="12a")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(Attendance.objects.count(), 0)

    def test_origin_required(self):
        response = self.post(origin="")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(Attendance.objects.count(), 0)

    def test_inactive_mechanic_cannot_be_responsible(self):
        inactive = make_mechanic("Parado", is_active=False)
        response = self.client.post(self.url, payload(inactive))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(Attendance.objects.count(), 0)

    def test_values_survive_validation_error(self):
        response = self.post(cpf="111.111.111-11", legal_name="Guardado", full_name="Maria Souza")
        self.assertContains(response, 'value="Maria Souza"')


class IntakeReuseTests(IntakeBase):
    def test_existing_customer_found_by_cpf(self):
        customer = make_customer(full_name="Antigo Nome", email="velho@empresa.com.br")
        self.post(email="")
        self.assertEqual(Customer.objects.count(), 1)
        customer.refresh_from_db()
        self.assertEqual(customer.full_name, "MARIA SOUZA")
        self.assertEqual(customer.email, "velho@empresa.com.br")

    def test_customer_can_have_many_vehicles(self):
        self.post()
        self.post(plate="XYZ9K88")
        self.assertEqual(Customer.objects.count(), 1)
        self.assertEqual(Vehicle.objects.count(), 2)
        self.assertEqual(Attendance.objects.count(), 2)

    def test_vehicle_can_have_many_attendances(self):
        self.post()
        self.post(mileage="50000")
        self.assertEqual(Vehicle.objects.count(), 1)
        self.assertEqual(Vehicle.objects.get().last_mileage, 50000)
        self.assertEqual(Attendance.objects.count(), 2)

    def test_owner_change_preserves_old_attendance(self):
        self.post()
        first = Attendance.objects.get()
        self.post(cpf="111.444.777-35", full_name="Novo Dono")
        vehicle = Vehicle.objects.get()
        self.assertEqual(vehicle.customer.full_name, "NOVO DONO")
        first.refresh_from_db()
        self.assertEqual(first.customer.full_name, "MARIA SOUZA")

    def test_pf_visit_does_not_erase_company_document(self):
        customer = make_customer(person_type="ambos", cnpj="12.ABC.345/01DE-35", legal_name="Y Ltda")
        self.post(person_type="pf")
        customer.refresh_from_db()
        self.assertEqual(customer.cnpj, "12ABC34501DE35")
        self.assertEqual(customer.person_type, "ambos")

    def test_cpf_and_cnpj_of_different_records_do_not_conflict(self):
        person = make_customer()
        company = make_customer(person_type="pj", cpf=None, cnpj="12.ABC.345/01DE-35", legal_name="Z Ltda")
        self.post(person_type="ambos", cnpj="12.ABC.345/01DE-35", legal_name="Z Ltda")
        attendance = Attendance.objects.get()
        self.assertEqual(attendance.customer, person)
        self.assertEqual(attendance.cnpj, "12ABC34501DE35")
        person.refresh_from_db()
        company.refresh_from_db()
        self.assertIsNone(person.cnpj)
        self.assertIsNone(company.cpf)

    def test_no_document_same_phone_reuses_vehicle_owner(self):
        owner = make_customer(cpf=None, phone="81990001712")
        make_vehicle(owner)
        self.post(cpf="", cpf_not_informed="on")
        self.assertEqual(Customer.objects.count(), 1)

    def test_no_document_other_phone_creates_customer(self):
        owner = make_customer(cpf=None, phone="81990001799")
        make_vehicle(owner)
        self.post(cpf="", cpf_not_informed="on")
        self.assertEqual(Customer.objects.count(), 2)


class IntakeEditTests(IntakeBase):
    def setUp(self):
        super().setUp()
        self.post()
        self.att = Attendance.objects.get()
        self.edit_url = reverse("attendances:edit", args=[self.att.public_id])

    def test_edit_form_prefilled_and_correction_saved(self):
        self.assertContains(self.client.get(self.edit_url), "ABC1D23")
        self.client.post(self.edit_url, payload(self.mechanic, mileage="46000", full_name="Maria S."))
        self.att.refresh_from_db()
        self.assertEqual(self.att.mileage, 46000)
        self.assertEqual(self.att.customer.full_name, "MARIA S.")
        self.assertEqual(self.att.current_step, wf.CHECKIN)

    def test_plate_typo_fixed_in_place_when_no_other_attendance(self):
        self.client.post(self.edit_url, payload(self.mechanic, plate="XYZ9K88"))
        self.assertEqual(Vehicle.objects.get().plate, "XYZ9K88")

    def test_plate_change_creates_vehicle_when_history_exists(self):
        self.post(mileage="50000")
        self.client.post(self.edit_url, payload(self.mechanic, plate="XYZ9K88"))
        self.assertEqual(Vehicle.objects.count(), 2)

    def test_cannot_edit_after_completion(self):
        Attendance.objects.filter(pk=self.att.pk).update(status=wf.STATUS_CONCLUIDO)
        self.assertEqual(self.client.get(self.edit_url).status_code, 403)

    def test_detail_redirects_to_open_step_or_summary(self):
        self.assertEqual(self.client.get(reverse("attendances:detail", args=[self.att.public_id])).status_code, 302)
        Attendance.objects.filter(pk=self.att.pk).update(status=wf.STATUS_CONCLUIDO, current_step=wf.FINALIZADO)
        response = self.client.get(reverse("attendances:detail", args=[self.att.public_id]))
        self.assertRedirects(response, reverse("attendances:summary", args=[self.att.public_id]))


class CancelTests(TestCase):
    def setUp(self):
        self.att = make_attendance()
        self.url = reverse("attendances:cancel", args=[self.att.public_id])

    def test_workshop_account_cancels(self):
        self.client.force_login(make_user("oficina"))
        response = self.client.post(self.url)
        self.assertEqual(response.status_code, 302)
        self.att.refresh_from_db()
        self.assertEqual(self.att.status, wf.STATUS_CANCELADO)

    def test_cancel_sets_retention_and_blocks_steps(self):
        self.client.force_login(make_user("chefe"))
        self.client.post(self.url)
        self.att.refresh_from_db()
        self.assertEqual(self.att.status, wf.STATUS_CANCELADO)
        self.assertIsNotNone(self.att.retention_until)
        self.assertEqual(self.client.get(reverse("attendances:edit", args=[self.att.public_id])).status_code, 403)
