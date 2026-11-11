"""Vendedor/Atendente: cadastrado em Configurações e escolhido ao iniciar o atendimento."""
import io

from django.core.management import call_command
from django.db import connection
from django.db.migrations.executor import MigrationExecutor
from django.test import TestCase, TransactionTestCase
from django.urls import reverse
from pypdf import PdfReader

from apps.attendances import workflow as wf
from apps.attendances.models import Attendance
from apps.attendances.step_validators import validate_cadastro
from apps.attendances.tests.test_intake import payload
from apps.core.models import AuditLog
from apps.core.testing import complete_through, make_attendance, make_employee, make_mechanic, make_user
from apps.employees.models import Employee
from apps.reports.services import generate_report
from apps.signatures.tests.test_step import signature_data_url


class ManagementTests(TestCase):
    def setUp(self):
        self.client.force_login(make_user("oficina"))

    def test_settings_links_to_the_register(self):
        self.assertContains(self.client.get(reverse("workshop:settings")), reverse("employees:list"))

    def test_create_edit_and_deactivate(self):
        response = self.client.post(reverse("employees:create"), {"name": "ana souza", "is_active": "on"}, follow=True)
        self.assertContains(response, "ANA SOUZA")
        employee = Employee.objects.get()
        self.assertEqual(employee.name, "ANA SOUZA")
        self.assertTrue(AuditLog.objects.filter(action="employee.created").exists())

        self.client.post(reverse("employees:edit", args=[employee.pk]), {"name": "Ana Lima"})
        employee.refresh_from_db()
        self.assertEqual(employee.name, "ANA LIMA")
        self.assertFalse(employee.is_active)

    def test_duplicate_name_is_refused(self):
        make_employee("João")
        response = self.client.post(reverse("employees:create"), {"name": "JOAO", "is_active": "on"})
        self.assertContains(response, "Já existe um vendedor/atendente")
        self.assertEqual(Employee.objects.count(), 1)

    def test_invalid_name_is_refused(self):
        response = self.client.post(reverse("employees:create"), {"name": "1", "is_active": "on"})
        self.assertContains(response, "Informe o nome completo")

    def test_register_only_has_name_and_status(self):
        response = self.client.get(reverse("employees:create"))
        self.assertContains(response, 'name="name"')
        self.assertContains(response, 'name="is_active"')
        for field in ("phone", "email", "password", "username"):
            self.assertNotContains(response, f'name="{field}"')

    def test_has_no_credentials(self):
        fields = {f.name for f in Employee._meta.get_fields()}
        self.assertTrue(fields.isdisjoint({"password", "username", "last_login", "email", "phone"}))

    def test_same_name_can_be_employee_and_mechanic(self):
        make_mechanic("Rui")
        response = self.client.post(reverse("employees:create"), {"name": "Rui", "is_active": "on"})
        self.assertEqual(response.status_code, 302)

    def test_workshop_account_manages(self):
        self.client.force_login(make_user("func"))
        self.assertEqual(self.client.get(reverse("employees:list")).status_code, 200)


class IntakeAttendantTests(TestCase):
    def setUp(self):
        self.login_user = make_user("oficina", first_name="Oficina")
        self.client.force_login(self.login_user)
        self.url = reverse("attendances:new")
        self.mechanic = make_mechanic("Rui")
        self.ana = make_employee("Ana Souza")
        self.bia = make_employee("Bia Lima")

    def _post(self, **extra):
        return self.client.post(self.url, {**payload(self.mechanic), "attendant": self.ana.pk, **extra})

    def test_field_comes_before_customer_data(self):
        content = self.client.get(self.url).content.decode()
        self.assertLess(content.index('name="attendant"'), content.index('name="full_name"'))

    def test_chosen_employee_is_recorded_apart_from_login(self):
        self._post(attendant=self.bia.pk)
        attendance = Attendance.objects.get()
        self.assertEqual(attendance.attendant, self.bia)
        self.assertEqual(attendance.created_by, self.login_user)

    def test_employee_is_required(self):
        response = self._post(attendant="")
        self.assertContains(response, "Selecione o vendedor/atendente")
        self.assertEqual(Attendance.objects.count(), 0)

    def test_inactive_employee_is_refused_and_not_listed(self):
        inactive = make_employee("Parado", is_active=False)
        self.assertNotContains(self.client.get(self.url), "PARADO")
        self.assertEqual(self._post(attendant=inactive.pk).status_code, 200)
        self.assertEqual(Attendance.objects.count(), 0)

    def test_unknown_employee_id_is_refused(self):
        response = self._post(attendant=999999)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(Attendance.objects.count(), 0)

    def test_empty_register_guides_to_settings(self):
        Employee.objects.all().delete()
        response = self.client.get(self.url)
        self.assertContains(response, "Nenhum vendedor/atendente cadastrado")
        self.assertContains(response, reverse("employees:create"))

    def test_employee_stays_responsible_until_the_end(self):
        self._post()
        attendance = Attendance.objects.get()
        edit_url = reverse("attendances:edit", args=[attendance.public_id])
        self.assertRegex(self.client.get(edit_url).content.decode(), r'<select name="attendant"[^>]*disabled')
        self.client.post(edit_url, {**payload(self.mechanic), "attendant": self.bia.pk})
        attendance.refresh_from_db()
        self.assertEqual(attendance.attendant, self.ana)

    def test_mechanic_stays_at_end_of_first_step_with_vehicle_data(self):
        content = self.client.get(self.url).content.decode()
        order = [content.index(f'name="{name}"') for name in ("attendant", "full_name", "plate", "mileage", "mechanic", "origin")]
        self.assertEqual(order, sorted(order))

    def test_deactivated_employee_stays_on_open_attendance(self):
        attendance = make_attendance(attendant=make_employee("Antiga", is_active=False))
        self.assertContains(self.client.get(reverse("attendances:edit", args=[attendance.public_id])), "ANTIGA")

    def test_server_refuses_to_advance_without_employee(self):
        attendance = make_attendance()
        Attendance.objects.filter(pk=attendance.pk).update(attendant=None)
        attendance.refresh_from_db()
        self.assertIn("Selecione o vendedor/atendente.", validate_cadastro(attendance))


class ConsultationTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        call_command("seed_checklist", verbosity=0)

    def test_summary_and_pdf_show_employee_not_login(self):
        login = make_user("oficina", first_name="Conta da Oficina")
        self.client.force_login(login)
        attendance = complete_through(make_attendance(attendant=make_employee("Ana Souza"), mechanic=make_mechanic("Rui"),
                                                      created_by=login), wf.REVISAO)
        self.client.post(reverse("signatures:step", args=[attendance.public_id]), {"signature_data": signature_data_url()})
        attendance.refresh_from_db()
        response = self.client.get(reverse("attendances:summary", args=[attendance.public_id]))
        self.assertContains(response, "ANA SOUZA")
        self.assertContains(response, "RUI")

        with generate_report(attendance, user=login).file.open("rb") as stored:
            text = " ".join(" ".join(p.extract_text().split()) for p in PdfReader(io.BytesIO(stored.read())).pages)
        self.assertIn("Vendedor/Atendente", text)
        self.assertIn("ANA SOUZA", text)
        self.assertNotIn("CONTA DA OFICINA", text)


class MigrationTests(TransactionTestCase):
    BEFORE = [("attendances", "0004_attendance_mechanic_and_review_qr"), ("accounts", "0003_remove_mechanic_role"),
              ("customers", "0001_initial"), ("vehicles", "0001_initial"), ("mechanics", "0001_initial")]
    AFTER = [("attendances", "0006_copy_attendants")]

    def tearDown(self):
        executor = MigrationExecutor(connection)
        executor.migrate(executor.loader.graph.leaf_nodes())

    def test_old_attendances_keep_who_opened_them_as_inactive_employee(self):
        executor = MigrationExecutor(connection)
        executor.migrate(self.BEFORE)
        old = executor.loader.project_state(self.BEFORE).apps
        User = old.get_model("accounts", "User")
        first = User.objects.create(username="ana", first_name="Ana", last_name="Lima", password="x")
        twin = User.objects.create(username="ana2", first_name="Ana", last_name="Lima", password="x")
        customer = old.get_model("customers", "Customer").objects.create(person_type="pf", full_name="C", phone="81990001712")
        vehicle = old.get_model("vehicles", "Vehicle").objects.create(customer=customer, plate="ABC1D23", brand="F", model="A")
        mechanic = old.get_model("mechanics", "Mechanic").objects.create(name="RUI", name_key="rui")
        OldAttendance = old.get_model("attendances", "Attendance")
        common = {"customer": customer, "vehicle": vehicle, "mechanic": mechanic, "mileage": 1, "origin": "outro"}
        by_first = OldAttendance.objects.create(created_by=first, code="A1", **common)
        by_twin = OldAttendance.objects.create(created_by=twin, code="A2", **common)
        no_owner = OldAttendance.objects.create(created_by=None, code="A3", **common)

        executor = MigrationExecutor(connection)
        executor.migrate(self.AFTER)
        new = executor.loader.project_state(self.AFTER).apps
        NewAttendance = new.get_model("attendances", "Attendance")
        got = NewAttendance.objects.get(pk=by_first.pk)
        self.assertEqual(got.attendant.name, "ANA LIMA")
        self.assertFalse(got.attendant.is_active)
        self.assertEqual(got.created_by_id, first.pk)
        self.assertEqual(NewAttendance.objects.get(pk=by_twin.pk).attendant.name, "ANA LIMA (ANA2)")
        self.assertIsNone(NewAttendance.objects.get(pk=no_owner.pk).attendant_id)
