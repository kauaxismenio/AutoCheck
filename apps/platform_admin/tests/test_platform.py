"""Proprietário da plataforma: cadastra oficinas; a oficina entra com o próprio e-mail e senha."""
from django.db import connection
from django.db.migrations.executor import MigrationExecutor
from django.test import TestCase, TransactionTestCase
from django.urls import reverse

from apps.accounts.models import User
from apps.core.models import AuditLog
from apps.core.testing import PASSWORD, make_attendance, make_customer, make_owner, make_user, make_workshop
from apps.platform_admin import services
from apps.workshop.models import WorkshopSettings

LOGIN = "/conta/entrar/"


class OwnerAreaTests(TestCase):
    def setUp(self):
        self.owner = make_owner()
        self.client.force_login(self.owner)

    def _create(self, **extra):
        return self.client.post(reverse("platform_admin:create"), {"name": "oficina modelo centro", "login_email": "Contato@OficinaModelo.example.com", **extra})

    def test_creates_workshop_with_generated_password_shown_once(self):
        response = self._create()
        self.assertContains(response, "Anote agora")
        self.assertIn("no-store", response["Cache-Control"])
        workshop = WorkshopSettings.objects.get(name="OFICINA MODELO CENTRO")
        account = workshop.accounts.get()
        self.assertEqual((account.username, account.email), ("contato@oficinamodelo.example.com", "contato@oficinamodelo.example.com"))
        self.assertFalse(account.is_staff or account.is_superuser)
        password = response.context["password"]
        self.assertGreaterEqual(len(password), 16)
        self.assertTrue(account.check_password(password))
        self.assertTrue(self.client.login(username="contato@oficinamodelo.example.com", password=password))

    def test_password_is_not_recorded(self):
        response = self._create()
        password = response.context["password"]
        for entry in AuditLog.objects.all():
            self.assertNotIn(password, str(entry.details))
        self.assertNotIn(password, self.client.get(reverse("platform_admin:list")).content.decode())

    def test_weak_initial_password_is_refused(self):
        response = self._create(password="123456")
        self.assertEqual(response.status_code, 200)
        self.assertFalse(WorkshopSettings.objects.exists())

    def test_strong_typed_password_is_accepted_and_not_echoed(self):
        response = self._create(password="Pneu-Forte-Modelo-88")
        self.assertRedirects(response, reverse("platform_admin:list"))
        self.assertTrue(User.objects.get(username="contato@oficinamodelo.example.com").check_password("Pneu-Forte-Modelo-88"))

    def test_duplicate_login_is_refused(self):
        self._create()
        response = self._create(name="Outra")
        self.assertContains(response, "já é o acesso de outra conta")
        self.assertEqual(WorkshopSettings.objects.count(), 1)

    def test_list_counts_workshops_without_client_data(self):
        shop = make_workshop("Oficina Um")
        make_workshop("Oficina Dois", is_active=False)
        make_user("um@oficina.com.br", workshop=shop, email="um@oficina.com.br")
        customer = make_customer(workshop=shop, full_name="Cliente Sigiloso")
        from apps.core.testing import make_vehicle

        make_attendance(vehicle=make_vehicle(customer))
        response = self.client.get(reverse("platform_admin:list"))
        self.assertEqual(response.context["stats"]["total"], 2)
        self.assertEqual(response.context["stats"]["active"], 1)
        self.assertContains(response, "OFICINA UM")
        self.assertContains(response, "um@oficina.com.br")
        self.assertEqual(next(w for w in response.context["workshops"] if w.pk == shop.pk).attendance_count, 1)
        self.assertNotContains(response, "CLIENTE SIGILOSO")

    def test_existing_workshop_without_account_gets_one(self):
        shop = make_workshop("Antiga")
        response = self.client.post(reverse("platform_admin:edit", args=[shop.pk]), {"name": "Antiga", "login_email": "antiga@oficina.com.br", "is_active": "on"})
        self.assertContains(response, "Anote agora")
        self.assertTrue(shop.accounts.get().check_password(response.context["password"]))

    def test_reset_password_replaces_the_old_one(self):
        shop = make_workshop("Oficina")
        account = make_user("a@oficina.com.br", workshop=shop, email="a@oficina.com.br")
        response = self.client.post(reverse("platform_admin:reset_password", args=[shop.pk]))
        account.refresh_from_db()
        self.assertFalse(account.check_password(PASSWORD))
        self.assertTrue(account.check_password(response.context["password"]))

    def test_changing_email_changes_the_login(self):
        shop = make_workshop("Oficina")
        make_user("a@oficina.com.br", workshop=shop, email="a@oficina.com.br")
        self.client.post(reverse("platform_admin:edit", args=[shop.pk]), {"name": "Oficina", "login_email": "b@oficina.com.br", "is_active": "on"})
        self.assertEqual(self.client.logout(), None)
        self.assertTrue(self.client.login(username="b@oficina.com.br", password=PASSWORD))

    def test_owner_is_sent_away_from_workshop_data(self):
        for url in (reverse("core:home"), reverse("attendances:list"), reverse("customers:list"), reverse("workshop:settings")):
            self.assertRedirects(self.client.get(url), reverse("platform_admin:list"))

    def test_owner_menu_only_has_workshops(self):
        items = self.client.get(reverse("platform_admin:list")).context["nav_items"]
        self.assertEqual([item["label"] for item in items], ["Oficinas"])


class WorkshopLoginTests(TestCase):
    def setUp(self):
        self.shop = make_workshop("Oficina Boa")
        self.account = make_user("contato@oficinaboa.com.br", workshop=self.shop, email="contato@oficinaboa.com.br")

    def _login(self, email="contato@oficinaboa.com.br", password=PASSWORD):
        return self.client.post(LOGIN, {"username": email, "password": password})

    def test_logs_in_with_email_ignoring_case(self):
        self.assertRedirects(self._login("Contato@OficinaBoa.com.br "), reverse("core:home"))

    def test_login_page_asks_for_email(self):
        response = self.client.get(LOGIN)
        self.assertContains(response, "E-mail")
        self.assertNotContains(response, "cadastre-se")

    def test_wrong_password_is_refused(self):
        self.assertContains(self._login(password="senha-errada-1"), "E-mail ou senha incorretos")

    def test_workshop_sees_dashboard_and_settings(self):
        self._login()
        self.assertContains(self.client.get(reverse("core:home")), "OFICINA BOA")
        self.assertEqual(self.client.get(reverse("workshop:settings")).status_code, 200)

    def test_workshop_cannot_enter_platform_or_django_admin(self):
        self._login()
        for name, args in (("platform_admin:list", []), ("platform_admin:create", []), ("platform_admin:edit", [self.shop.pk])):
            self.assertEqual(self.client.get(reverse(name, args=args)).status_code, 403, name)
        self.assertIn("/admin/login/", self.client.get("/admin/")["Location"])

    def test_deactivating_blocks_login_and_ends_open_sessions(self):
        self._login()
        WorkshopSettings.objects.filter(pk=self.shop.pk).update(is_active=False)
        self.assertEqual(self.client.get(reverse("core:home")).status_code, 302)
        self.assertContains(self._login(), "E-mail ou senha incorretos")

    def test_account_without_workshop_cannot_log_in(self):
        User.objects.create_user(username="solta@oficina.com.br", password=PASSWORD)
        self.assertContains(self._login("solta@oficina.com.br"), "E-mail ou senha incorretos")

    def test_no_public_signup_route(self):
        self.assertEqual(self.client.get(reverse("platform_admin:create")).status_code, 302)
        for path in ("/cadastro/", "/conta/cadastro/", "/conta/registrar/", "/oficinas/nova/"):
            self.assertEqual(self.client.get(path).status_code, 404, path)


class ServiceTests(TestCase):
    def test_generated_passwords_are_unique(self):
        self.assertNotEqual(services.generate_password(), services.generate_password())


class ExistingDataMigrationTests(TransactionTestCase):
    """Roda a conversão de verdade sobre dados do formato anterior."""

    BEFORE = [("workshop", "0003_workshopsettings_is_active"), ("accounts", "0004_user_workshop"),
              ("customers", "0002_customer_workshop"), ("vehicles", "0002_vehicle_workshop"),
              ("attendances", "0007_attendance_workshop"), ("mechanics", "0003_mechanic_workshop"),
              ("employees", "0002_employee_workshop")]
    AFTER = [("workshop", "0004_assign_existing_data")]

    def tearDown(self):
        executor = MigrationExecutor(connection)
        executor.migrate(executor.loader.graph.leaf_nodes())

    def test_existing_data_goes_to_the_existing_workshop_and_nothing_is_lost(self):
        executor = MigrationExecutor(connection)
        executor.migrate(self.BEFORE)
        old = executor.loader.project_state(self.BEFORE).apps
        shop = old.get_model("workshop", "WorkshopSettings").objects.create(name="MINHA OFICINA", report_email="dono@x.com.br")
        OldUser = old.get_model("accounts", "User")
        owner = OldUser.objects.create(username="dono", is_superuser=True, is_staff=True, password="x")
        seller = OldUser.objects.create(username="ana", role="vendedor", password="x")
        customer = old.get_model("customers", "Customer").objects.create(person_type="pf", full_name="C", phone="81990001712", cpf="52998224725")
        vehicle = old.get_model("vehicles", "Vehicle").objects.create(customer=customer, plate="ABC1D23", brand="F", model="A")
        mechanic = old.get_model("mechanics", "Mechanic").objects.create(name="RUI", name_key="rui")
        employee = old.get_model("employees", "Employee").objects.create(name="ANA", name_key="ana")
        attendance = old.get_model("attendances", "Attendance").objects.create(
            customer=customer, vehicle=vehicle, mechanic=mechanic, attendant=employee, created_by=seller, mileage=1, origin="outro", code="A1",
        )

        executor = MigrationExecutor(connection)
        executor.migrate(self.AFTER)
        new = executor.loader.project_state(self.AFTER).apps
        for app_label, name, pk in (("customers", "Customer", customer.pk), ("vehicles", "Vehicle", vehicle.pk), ("attendances", "Attendance", attendance.pk),
                                    ("mechanics", "Mechanic", mechanic.pk), ("employees", "Employee", employee.pk)):
            self.assertEqual(new.get_model(app_label, name).objects.get(pk=pk).workshop_id, shop.pk, name)
        NewUser = new.get_model("accounts", "User")
        self.assertIsNone(NewUser.objects.get(pk=owner.pk).workshop_id, "o proprietário não pertence a uma oficina")
        self.assertTrue(NewUser.objects.get(pk=owner.pk).is_active)
        got = NewUser.objects.get(pk=seller.pk)
        self.assertEqual(got.workshop_id, shop.pk)
        self.assertFalse(got.is_active, "login individual antigo deixa de valer")
        self.assertEqual(new.get_model("workshop", "WorkshopSettings").objects.get(pk=shop.pk).report_email, "dono@x.com.br")
