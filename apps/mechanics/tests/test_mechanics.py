"""Separação entre usuários (com login) e mecânicos (sem login)."""
from django.db import connection
from django.db.migrations.executor import MigrationExecutor
from django.test import TestCase, TransactionTestCase
from django.urls import reverse

from apps.accounts.forms import LoginForm
from apps.attendances.models import Attendance
from apps.attendances.tests.test_intake import payload
from apps.core.models import AuditLog
from apps.core.testing import default_workshop, make_attendance, make_mechanic, make_user
from apps.mechanics.models import Mechanic, name_key
from apps.mechanics.services import get_or_add


class SeparationTests(TestCase):
    def test_mechanic_has_no_credentials(self):
        fields = {f.name for f in Mechanic._meta.get_fields()}
        self.assertTrue(fields.isdisjoint({"password", "username", "last_login", "email"}))

    def test_mechanic_name_cannot_log_in(self):
        make_mechanic("Rui")
        form = LoginForm(data={"username": "Rui", "password": "qualquer-coisa-1"})
        form.request = None
        self.assertFalse(form.is_valid())


class NameRulesTests(TestCase):
    def test_key_ignores_case_accent_and_spaces(self):
        self.assertEqual(name_key("  JOÃO   da Silva "), name_key("joao DA silva"))

    def test_get_or_add_reuses_same_person(self):
        first = get_or_add("João Silva", workshop=default_workshop())
        self.assertEqual(get_or_add("  JOAO   silva ", workshop=default_workshop()).pk, first.pk)
        self.assertEqual(Mechanic.objects.count(), 1)

    def test_get_or_add_reactivates_and_audits(self):
        make_mechanic("Parado", is_active=False)
        self.assertTrue(get_or_add("parado", workshop=default_workshop()).is_active)
        self.assertTrue(AuditLog.objects.filter(action="mechanic.reactivated").exists())


class IntakeMechanicTests(TestCase):
    def setUp(self):
        self.user = make_user("ana", first_name="Ana")
        self.client.force_login(self.user)
        self.url = reverse("attendances:new")
        self.mechanic = make_mechanic("Rui")

    def _post(self, **extra):
        return self.client.post(self.url, {**payload(self.mechanic), **extra})

    def test_records_chosen_mechanic(self):
        self._post()
        self.assertEqual(Attendance.objects.get().mechanic, self.mechanic)

    def test_logged_account_cannot_be_forged_by_the_form(self):
        other = make_user("outra")
        self._post(created_by=other.pk)
        self.assertEqual(Attendance.objects.get().created_by, self.user)

    def test_adds_new_mechanic_directly_in_the_attendance(self):
        response = self._post(mechanic="", new_mechanic_name="  Carlos   Souza ")
        self.assertEqual(response.status_code, 302)
        created = Mechanic.objects.get(name="CARLOS SOUZA")
        self.assertEqual(Attendance.objects.get().mechanic, created)
        self.assertTrue(AuditLog.objects.filter(action="mechanic.created", user=self.user).exists())

    def test_typed_name_of_existing_mechanic_does_not_duplicate(self):
        self._post(mechanic="", new_mechanic_name="RUI")
        self.assertEqual(Mechanic.objects.count(), 1)
        self.assertEqual(Attendance.objects.get().mechanic, self.mechanic)

    def test_requires_a_mechanic(self):
        response = self._post(mechanic="")
        self.assertContains(response, "Selecione o mecânico responsável")
        self.assertEqual(Attendance.objects.count(), 0)

    def test_invalid_new_name_is_refused(self):
        response = self._post(mechanic="", new_mechanic_name="1")
        self.assertContains(response, "Informe o nome do mecânico")
        self.assertEqual(Attendance.objects.count(), 0)
        self.assertEqual(Mechanic.objects.count(), 1)

    def test_invalid_attendance_does_not_leave_orphan_mechanic(self):
        response = self._post(mechanic="", new_mechanic_name="Novo Nome", plate="XX")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'value="Novo Nome"')
        self.assertFalse(Mechanic.objects.filter(name_key="novo nome").exists())

    def test_list_only_offers_active_mechanics(self):
        make_mechanic("Parado", is_active=False)
        response = self.client.get(self.url)
        self.assertContains(response, "RUI")
        self.assertNotContains(response, "PARADO")

    def test_deactivated_mechanic_stays_on_old_attendance(self):
        attendance = make_attendance(mechanic=make_mechanic("Antigo", is_active=False))
        response = self.client.get(reverse("attendances:edit", args=[attendance.public_id]))
        self.assertContains(response, "ANTIGO")

    def test_summary_shows_employee_and_mechanic(self):
        self._post()
        attendance = Attendance.objects.get()
        response = self.client.get(reverse("attendances:summary", args=[attendance.public_id]))
        self.assertContains(response, "Vendedor/Atendente")
        self.assertContains(response, "ANA FUNCIONÁRIA")
        self.assertContains(response, "Mecânico responsável")
        self.assertContains(response, "RUI")


class ManagementTests(TestCase):
    def setUp(self):
        self.client.force_login(make_user("chefe"))

    def test_create_edit_and_deactivate(self):
        self.client.post(reverse("mechanics:create"), {"name": "Rui", "phone": "(81) 9 9000-1712", "is_active": "on"})
        mechanic = Mechanic.objects.get()
        self.assertEqual(mechanic.phone, "81990001712")
        self.assertContains(self.client.get(reverse("mechanics:list")), "RUI")

        self.client.post(reverse("mechanics:edit", args=[mechanic.pk]), {"name": "Rui Melo", "phone": ""})
        mechanic.refresh_from_db()
        self.assertEqual(mechanic.name, "RUI MELO")
        self.assertFalse(mechanic.is_active)

    def test_duplicate_name_is_refused(self):
        make_mechanic("João")
        response = self.client.post(reverse("mechanics:create"), {"name": "JOAO", "phone": "", "is_active": "on"})
        self.assertContains(response, "Já existe um mecânico")
        self.assertEqual(Mechanic.objects.count(), 1)

    def test_editing_keeps_own_name_valid(self):
        mechanic = make_mechanic("João")
        response = self.client.post(reverse("mechanics:edit", args=[mechanic.pk]), {"name": "JOÃO", "phone": "", "is_active": "on"})
        self.assertEqual(response.status_code, 302)

    def test_invalid_phone_is_refused(self):
        response = self.client.post(reverse("mechanics:create"), {"name": "Rui", "phone": "123", "is_active": "on"})
        self.assertContains(response, "Telefone inválido")

    def test_mechanic_in_use_cannot_be_deleted_from_database(self):
        from django.db.models import ProtectedError

        attendance = make_attendance()
        with self.assertRaises(ProtectedError):
            attendance.mechanic.delete()


class MigrationTests(TransactionTestCase):
    """Roda a conversão de verdade sobre dados no formato antigo."""

    BEFORE = [("attendances", "0001_initial"), ("accounts", "0002_loginattempt"), ("customers", "0001_initial"),
              ("vehicles", "0001_initial")]
    AFTER = [("attendances", "0004_attendance_mechanic_and_review_qr"), ("accounts", "0003_remove_mechanic_role")]

    def tearDown(self):
        executor = MigrationExecutor(connection)
        executor.migrate(executor.loader.graph.leaf_nodes())

    def test_converts_users_into_mechanics(self):
        executor = MigrationExecutor(connection)
        executor.migrate(self.BEFORE)
        old = executor.loader.project_state(self.BEFORE).apps
        OldUser = old.get_model("accounts", "User")
        common = {"password": "x"}
        mech = OldUser.objects.create(username="rui", first_name="Rui", last_name="Melo", role="mecanico", phone="81990001712", **common)
        idle = OldUser.objects.create(username="zeca", first_name="Rui", last_name="Melo", role="mecanico", **common)
        gone = OldUser.objects.create(username="ex", role="mecanico", is_active=False, **common)
        boss = OldUser.objects.create(username="dono", first_name="Dona", role="admin", **common)
        desk = OldUser.objects.create(username="ana", role="atendente", **common)
        customer = old.get_model("customers", "Customer").objects.create(person_type="pf", full_name="C", phone="81990001712")
        vehicle = old.get_model("vehicles", "Vehicle").objects.create(customer=customer, plate="ABC1D23", brand="F", model="A")
        OldAttendance = old.get_model("attendances", "Attendance")
        common_att = {"customer": customer, "vehicle": vehicle, "mileage": 1, "origin": "outro"}
        by_mech = OldAttendance.objects.create(mechanic=mech, created_by=desk, code="A1", **common_att)
        by_boss = OldAttendance.objects.create(mechanic=boss, created_by=boss, code="A2", **common_att)

        executor = MigrationExecutor(connection)
        executor.migrate(self.AFTER)
        new = executor.loader.project_state(self.AFTER).apps
        NewMechanic = new.get_model("mechanics", "Mechanic")
        NewAttendance = new.get_model("attendances", "Attendance")
        NewUser = new.get_model("accounts", "User")

        self.assertEqual(NewAttendance.objects.get(pk=by_mech.pk).mechanic.name, "Rui Melo")
        self.assertEqual(NewAttendance.objects.get(pk=by_mech.pk).mechanic.phone, "81990001712")
        self.assertEqual(NewAttendance.objects.get(pk=by_mech.pk).created_by_id, desk.pk)
        self.assertTrue(NewMechanic.objects.get(name="Rui Melo").is_active)
        self.assertTrue(NewMechanic.objects.get(name="Rui Melo (zeca)").is_active, "homônimo não é fundido")
        self.assertFalse(NewMechanic.objects.get(name="ex").is_active, "conta desativada continua desativada")
        self.assertFalse(NewMechanic.objects.get(name="Dona").is_active, "administrador fica só no histórico")
        self.assertEqual(NewAttendance.objects.get(pk=by_boss.pk).mechanic.name, "Dona")

        for username in ("rui", "zeca", "ex"):
            user = NewUser.objects.get(username=username)
            self.assertFalse(user.is_active, username)
            self.assertEqual(user.role, "atendente", username)
            self.assertTrue(user.password.startswith("!"), f"{username} continua com senha utilizável")
        self.assertEqual(NewUser.objects.get(username="dono").role, "admin")
        self.assertTrue(NewUser.objects.get(username="dono").is_active)
        self.assertEqual(NewUser.objects.get(username="dono").password, "x")
        self.assertTrue(NewUser.objects.get(username="ana").is_active)
        self.assertEqual(idle.pk, NewUser.objects.get(username="zeca").pk)
