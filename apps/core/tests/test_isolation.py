"""Isolamento entre oficinas: novas rotas entram sozinhas nesta varredura."""
from django.core import mail
from django.core.management import call_command
from django.test import TestCase
from django.urls import get_resolver, reverse

from apps.attendances import workflow as wf
from apps.attendances.models import Attendance
from apps.attendances.services import advance
from apps.attendances.tests.test_intake import payload
from apps.core.testing import (
    complete_through, make_attendance, make_customer, make_employee, make_mechanic, make_user, make_vehicle, make_workshop,
)
from apps.core.tests.test_security import PUBLIC, walk
from apps.customers.models import Customer
from apps.mechanics.models import Mechanic
from apps.photos.models import Photo
from apps.replacements.services import add_manual_service
from apps.reports.models import Report
from apps.reports.services import generate_report
from apps.services.models import ServiceRecord
from apps.signatures.services import register_signature
from apps.signatures.tests.test_step import signature_data_url
from apps.vehicles.models import Vehicle
from apps.workshop.models import WorkshopSettings


class TwoWorkshops(TestCase):
    @classmethod
    def setUpTestData(cls):
        call_command("seed_checklist", verbosity=0)
        cls.shop_a = make_workshop("Oficina Alfa", report_email="alfa@oficina.com.br")
        cls.shop_b = make_workshop("Oficina Beta", report_email="beta@oficina.com.br",
                                   google_review_url="https://g.page/r/BetaSecreto/review")
        cls.user_a = make_user("alfa@oficina.com.br", workshop=cls.shop_a)
        cls.user_b = make_user("beta@oficina.com.br", workshop=cls.shop_b)
        cls.customer_b = make_customer(workshop=cls.shop_b, full_name="Cliente Da Beta", cpf="111.444.777-35", email="cliente@beta.com.br")
        cls.vehicle_b = make_vehicle(cls.customer_b, plate="BET4A56", brand="Marcabeta", model="Modelobeta")
        cls.mechanic_b = make_mechanic("Mecanico Beta", workshop=cls.shop_b)
        cls.employee_b = make_employee("Vendedor Beta", workshop=cls.shop_b)
        cls.attendance_b = complete_through(
            make_attendance(vehicle=cls.vehicle_b, mechanic=cls.mechanic_b, attendant=cls.employee_b), wf.REVISAO,
        )
        cls.service_b = add_manual_service(cls.attendance_b, "Servico Beta") or ServiceRecord.objects.filter(attendance=cls.attendance_b).first()
        register_signature(cls.attendance_b, signature_data_url(), user=cls.user_b)
        advance(cls.attendance_b, wf.REVISAO, user=cls.user_b)
        cls.attendance_b.refresh_from_db()
        cls.report_b = generate_report(cls.attendance_b)
        cls.photo_b = Photo.objects.filter(attendance=cls.attendance_b).first()

    def setUp(self):
        self.client.force_login(self.user_a)


class RouteSweepTests(TwoWorkshops):
    PK_BY_NAMESPACE = {
        "customers": "customer_b", "vehicles": "vehicle_b", "mechanics": "mechanic_b", "employees": "employee_b",
        "photos": "photo_b", "reports": "report_b", "replacements": "service_b",
    }
    # Rotas com identificador da oficina. A plataforma tem a própria proteção, testada em test_security.
    SKIP_NAMESPACES = ("platform_admin:",)

    def _routes(self):
        for name, pattern in walk(get_resolver().url_patterns):
            if name in PUBLIC or name.startswith(self.SKIP_NAMESPACES) or not pattern.pattern.converters:
                continue
            kwargs = {}
            for key, converter in pattern.pattern.converters.items():
                if type(converter).__name__ == "UUIDConverter":
                    kwargs[key] = self.attendance_b.public_id
                else:
                    kwargs[key] = getattr(self, self.PK_BY_NAMESPACE[name.split(":")[0]]).pk
            yield name, reverse(name, kwargs=kwargs)

    def test_every_route_with_identifier_refuses_other_workshop(self):
        routes = list(self._routes())
        self.assertGreater(len(routes), 20)
        for name, url in routes:
            for method in ("get", "post"):
                status = getattr(self.client, method)(url).status_code
                # 404 e não 403: para a outra oficina, o registro simplesmente não existe.
                self.assertIn(status, (404, 405), f"{method} {name} devolveu {status}")

    def test_the_same_identifiers_work_for_their_own_workshop(self):
        """Prova que a varredura acima usa identificadores válidos, e não uma recusa por dado inexistente."""
        self.client.force_login(self.user_b)
        not_found = [name for name, url in self._routes() if self.client.get(url).status_code == 404]
        self.assertEqual(not_found, [])

    def test_nothing_of_the_other_workshop_changed(self):
        for name, url in self._routes():
            self.client.post(url, {"action": "present", "description": "Invadido", "decision": "autorizado", "name": "Invadido", "is_active": "on"})
        self.customer_b.refresh_from_db()
        self.attendance_b.refresh_from_db()
        self.assertEqual(self.customer_b.full_name, "CLIENTE DA BETA")
        self.assertIsNone(self.attendance_b.review_qr_presented_at)
        self.assertEqual(self.attendance_b.status, wf.STATUS_CONCLUIDO)
        self.assertTrue(Customer.objects.filter(pk=self.customer_b.pk).exists())
        self.assertTrue(Vehicle.objects.filter(pk=self.vehicle_b.pk).exists())
        self.assertFalse(Mechanic.objects.filter(name="INVADIDO").exists())
        self.assertEqual(len(mail.outbox), 0)


class ListingTests(TwoWorkshops):
    SECRETS = ("CLIENTE DA BETA", "BET4A56", "BET-4A56", "MARCABETA", "MODELOBETA", "MECANICO BETA", "VENDEDOR BETA", "OFICINA BETA")

    def test_lists_and_dashboard_show_nothing_of_the_other_workshop(self):
        for url_name in ("core:home", "attendances:list", "attendances:history", "attendances:new", "customers:list", "vehicles:list",
                         "vehicles:create", "aftersales:list", "mechanics:list", "employees:list", "workshop:settings"):
            content = self.client.get(reverse(url_name)).content.decode()
            for secret in self.SECRETS:
                self.assertNotIn(secret, content, f"{url_name}: {secret}")

    def test_search_does_not_cross_workshops(self):
        for url_name in ("customers:list", "vehicles:list", "attendances:list", "attendances:history", "aftersales:list"):
            for term in ("Cliente Da Beta", "BET4A56", "11144477735"):
                self.assertNotContains(self.client.get(reverse(url_name), {"q": term}), "CLIENTE DA BETA", msg_prefix=url_name)

    def test_lookups_do_not_reveal_the_other_workshop(self):
        cpf = self.client.get(reverse("integrations:cpf"), {"cpf": "111.444.777-35"})
        plate = self.client.get(reverse("integrations:plate"), {"plate": "BET4A56"})
        self.assertNotIn("BETA", cpf.content.decode())
        self.assertNotIn("BETA", plate.content.decode())

    def test_recent_activity_is_separate(self):
        from apps.core.audit import log_action

        log_action("attendance.created", user=self.user_b, obj=self.attendance_b, attendance=self.attendance_b)
        self.assertNotContains(self.client.get(reverse("core:home")), self.attendance_b.code)

    def test_workshop_files_and_settings_are_separate(self):
        self.assertEqual(self.client.get(reverse("workshop:review_qr")).status_code, 404, "A não tem link; não pode ver o de B")
        self.assertNotContains(self.client.get(reverse("workshop:settings")), "BetaSecreto")
        self.client.post(reverse("workshop:settings"), {"name": "Alfa Nova", "report_email": "novo@alfa.com.br"})
        self.shop_b.refresh_from_db()
        self.assertEqual((self.shop_b.name, self.shop_b.report_email), ("OFICINA BETA", "beta@oficina.com.br"))
        self.assertEqual(WorkshopSettings.objects.get(pk=self.shop_a.pk).name, "ALFA NOVA")


class OwnDataTests(TwoWorkshops):
    def _intake(self, **extra):
        data = {**payload(make_mechanic("Rui", workshop=self.shop_a)), "attendant": make_employee("Ana", workshop=self.shop_a).pk, **extra}
        return self.client.post(reverse("attendances:new"), data)

    def test_same_cpf_and_plate_are_separate_records_in_each_workshop(self):
        response = self._intake(cpf="111.444.777-35", plate="BET4A56", full_name="Cliente Da Alfa")
        self.assertEqual(response.status_code, 302)
        created = Attendance.objects.exclude(pk=self.attendance_b.pk).get()
        self.assertEqual(created.workshop, self.shop_a)
        self.assertEqual(created.customer.workshop, self.shop_a)
        self.assertEqual(created.vehicle.workshop, self.shop_a)
        self.assertNotEqual(created.customer_id, self.customer_b.pk)
        self.assertNotEqual(created.vehicle_id, self.vehicle_b.pk)
        self.customer_b.refresh_from_db()
        self.assertEqual(self.customer_b.full_name, "CLIENTE DA BETA")

    def test_cannot_use_mechanic_or_employee_of_other_workshop(self):
        for field, value in (("mechanic", self.mechanic_b.pk), ("attendant", self.employee_b.pk)):
            response = self._intake(**{field: value})
            self.assertEqual(response.status_code, 200, field)
        self.assertEqual(Attendance.objects.exclude(pk=self.attendance_b.pk).count(), 0)

    def test_vehicle_form_cannot_attach_to_customer_of_other_workshop(self):
        response = self.client.post(reverse("vehicles:create"), {"customer": self.customer_b.pk, "plate": "XYZ9K88", "brand": "A", "model": "B"})
        self.assertEqual(response.status_code, 200)
        self.assertFalse(Vehicle.objects.filter(plate="XYZ9K88").exists())

    def test_new_records_belong_to_the_logged_workshop(self):
        self.client.post(reverse("mechanics:create"), {"name": "Novo", "phone": "", "is_active": "on"})
        self.client.post(reverse("employees:create"), {"name": "Nova", "is_active": "on"})
        self.client.post(reverse("customers:create"), {"person_type": "pf", "full_name": "Novo Cliente", "cpf": "529.982.247-25", "phone": "8134567890"})
        self.assertEqual(Mechanic.objects.get(name="NOVO").workshop, self.shop_a)
        self.assertEqual(self.shop_a.employees.get(name="NOVA").workshop, self.shop_a)
        self.assertEqual(Customer.objects.get(full_name="NOVO CLIENTE").workshop, self.shop_a)

    def test_same_mechanic_name_allowed_in_each_workshop(self):
        response = self.client.post(reverse("mechanics:create"), {"name": "Mecanico Beta", "phone": "", "is_active": "on"})
        self.assertEqual(response.status_code, 302)

    def test_report_uses_the_data_of_its_own_workshop(self):
        self.assertEqual(Report.objects.filter(attendance=self.attendance_b).count(), 1)
        self.assertEqual(self.report_b.attendance.workshop, self.shop_b)
