"""Padronização em maiúsculas: gravação, consulta, PDF, dados antigos e campos que não mudam."""
import io
import unittest

from django.core.management import call_command
from django.db import connection
from django.db.migrations.executor import MigrationExecutor
from django.test import TestCase, TransactionTestCase
from django.urls import reverse
from pypdf import PdfReader

from apps.attendances import workflow as wf
from apps.attendances.models import Attendance
from apps.attendances.tests.test_intake import payload
from apps.core.testing import complete_through, default_workshop, make_attendance, make_customer, make_employee, make_mechanic, make_owner, make_user, make_vehicle
from apps.core.validators.text import to_upper
from apps.customers.models import Customer
from apps.mechanics.models import Mechanic
from apps.reports.services import generate_report
from apps.signatures.models import AttendanceSignature
from apps.signatures.tests.test_step import signature_data_url
from apps.vehicles.models import Vehicle
from apps.workshop.models import WorkshopSettings


class ToUpperTests(unittest.TestCase):
    def test_examples(self):
        for raw, expected in (("maria de souza", "MARIA DE SOUZA"), ("Fiat", "FIAT"), ("Argo", "ARGO"),
                              ("Vermelha", "VERMELHA"), ("João Silva", "JOÃO SILVA"),
                              ("Oficina Exemplo LTDA", "OFICINA EXEMPLO LTDA")):
            self.assertEqual(to_upper(raw), expected)

    def test_keeps_accents_numbers_and_punctuation(self):
        self.assertEqual(to_upper("coração ção à é ü & cia. nº 2 - s/a"), "CORAÇÃO ÇÃO À É Ü & CIA. Nº 2 - S/A")
        self.assertEqual(to_upper("208 gt 1.6"), "208 GT 1.6")

    def test_empty_values(self):
        self.assertEqual(to_upper(""), "")
        self.assertEqual(to_upper(None), "")


class ModelStandardTests(TestCase):
    """Vale para qualquer caminho de gravação, inclusive sem passar pelo navegador."""

    def test_customer(self):
        customer = make_customer(full_name="joão silva", legal_name="Auto Peças ação ltda", trade_name="peça boa",
                                 contact_person="Dona Ana", email="Joao.Silva@Empresa.com.br", person_type="ambos",
                                 address="Rua das Flores, 10")
        customer.refresh_from_db()
        self.assertEqual((customer.full_name, customer.legal_name, customer.trade_name),
                         ("JOÃO SILVA", "AUTO PEÇAS AÇÃO LTDA", "PEÇA BOA"))
        self.assertEqual(customer.address, "Rua das Flores, 10")
        self.assertEqual(customer.contact_person, "Dona Ana")
        self.assertTrue(customer.email.startswith("Joao.Silva@"), "e-mail mantém a grafia da parte local")

    def test_vehicle(self):
        vehicle = make_vehicle(brand="Fiat", model="Argo 1.3 drive", color="Vermelha", plate="abc1d23")
        vehicle.refresh_from_db()
        self.assertEqual((vehicle.brand, vehicle.model, vehicle.color, vehicle.plate),
                         ("FIAT", "ARGO 1.3 DRIVE", "VERMELHA", "ABC1D23"))

    def test_mechanic(self):
        self.assertEqual(make_mechanic("joão  silva").name, "JOÃO SILVA")

    def test_user_names_upper_but_login_data_untouched(self):
        user = make_user("Maria.Souza", first_name="maria", last_name="souza", email="Maria@Oficina.com.br")
        user.refresh_from_db()
        self.assertEqual(user.get_full_name(), "MARIA SOUZA")
        self.assertEqual(user.username, "Maria.Souza")
        self.assertTrue(user.email.startswith("Maria@"))
        self.assertTrue(user.check_password("senha-forte-123"))

    def test_owner_without_name_displays_login_in_upper_only_on_screen(self):
        owner = make_owner("maria")
        self.assertEqual(owner.display_name, "MARIA")
        self.assertEqual(owner.username, "maria")

    def test_workshop_account_displays_the_workshop_name(self):
        account = make_user("contato@oficina.com.br")
        self.assertEqual(account.display_name, account.workshop.name)

    def test_login_still_uses_original_username(self):
        make_user("Maria.Souza", first_name="maria")
        self.assertTrue(self.client.login(username="Maria.Souza", password="senha-forte-123"))
        self.assertFalse(self.client.login(username="MARIA.SOUZA", password="senha-forte-123"))

    def test_workshop_name_only(self):
        workshop = default_workshop()
        workshop.name = "Oficina Exemplo LTDA"
        workshop.report_email = "Dono@OficinaBoa.com.br"
        workshop.google_review_url = "https://g.page/r/CaBcDeF/review"
        workshop.save()
        workshop.refresh_from_db()
        self.assertEqual(workshop.name, "OFICINA EXEMPLO LTDA")
        self.assertEqual(workshop.google_review_url, "https://g.page/r/CaBcDeF/review")
        self.assertIn("Dono", workshop.report_email)
        self.assertEqual(WorkshopSettings.objects.count(), 1)


class FormInputTests(TestCase):
    MARK = 'data-mask="upper"'

    def setUp(self):
        self.client.force_login(make_user("chefe"))

    def _field_html(self, url, name):
        import re

        match = re.search(rf'<input[^>]*name="{name}"[^>]*>', self.client.get(url).content.decode())
        self.assertIsNotNone(match, name)
        return match.group(0)

    def test_required_fields_are_marked(self):
        customer = make_customer()
        pages = {
            reverse("attendances:new"): ("full_name", "legal_name", "trade_name", "brand", "model", "color", "new_mechanic_name"),
            reverse("customers:edit", args=[customer.pk]): ("full_name", "legal_name", "trade_name"),
            reverse("vehicles:create"): ("brand", "model", "color"),
            reverse("mechanics:create"): ("name",),
            reverse("employees:create"): ("name",),
            reverse("workshop:settings"): ("name",),
        }
        for url, names in pages.items():
            for name in names:
                self.assertIn(self.MARK, self._field_html(url, name), f"{url} {name}")

    def test_case_sensitive_fields_are_not_marked(self):
        pages = {
            reverse("attendances:new"): ("email",),
            reverse("accounts:login"): (),
            reverse("workshop:settings"): ("report_email", "google_review_url"),
        }
        for url, names in pages.items():
            for name in names:
                self.assertNotIn("upper", self._field_html(url, name), f"{url} {name}")


class IntakeToConsultationTests(TestCase):
    """Do formulário até as consultas e o PDF."""

    @classmethod
    def setUpTestData(cls):
        call_command("seed_checklist", verbosity=0)

    def setUp(self):
        self.user = make_user("ana", first_name="ana", last_name="souza")
        self.client.force_login(self.user)
        data = payload(make_mechanic("rui melo"), full_name="joão coração", brand="Citroën", model="c3 aircross",
                       color="Vermelha", plate="abc1d23", email="Cliente.Teste@Empresa.com.br")
        data["attendant"] = make_employee("ana souza").pk
        self.assertEqual(self.client.post(reverse("attendances:new"), data).status_code, 302)
        self.att = Attendance.objects.get()

    def test_saved_in_upper_and_email_untouched(self):
        self.assertEqual(self.att.customer.full_name, "JOÃO CORAÇÃO")
        self.assertEqual(self.att.vehicle.brand, "CITROËN")
        self.assertEqual(self.att.vehicle.model, "C3 AIRCROSS")
        self.assertEqual(self.att.vehicle.color, "VERMELHA")
        self.assertEqual(self.att.vehicle.plate, "ABC1D23")
        self.assertEqual(self.att.customer_email, "Cliente.Teste@empresa.com.br")

    def test_reopened_forms_and_detail_screens_show_upper(self):
        self.assertContains(self.client.get(reverse("attendances:edit", args=[self.att.public_id])), 'value="JOÃO CORAÇÃO"')
        for url in (reverse("customers:detail", args=[self.att.customer.pk]),
                    reverse("attendances:list")):
            response = self.client.get(url)
            self.assertEqual(response.status_code, 200, url)
            self.assertContains(response, "JOÃO CORAÇÃO")
            self.assertNotContains(response, "João Coração")
        self.assertContains(self.client.get(reverse("vehicles:detail", args=[self.att.vehicle.pk])), "CITROËN")

    def test_search_in_lower_case_finds_upper_case_with_accent(self):
        for url in (reverse("customers:list"), reverse("attendances:list"), reverse("vehicles:list")):
            self.assertContains(self.client.get(url, {"q": "joão cora"}), "JOÃO CORAÇÃO", msg_prefix=url)
        self.assertContains(self.client.get(reverse("vehicles:list"), {"q": "citroën"}), "CITROËN")

    def test_pdf_in_upper_keeping_accents(self):
        complete_through(self.att, wf.REVISAO)
        self.assertEqual(self.client.post(reverse("signatures:step", args=[self.att.public_id]),
                                          {"signature_data": signature_data_url()}).status_code, 302)
        self.att.refresh_from_db()
        self.assertContains(self.client.get(reverse("attendances:history")), "JOÃO CORAÇÃO")
        report = generate_report(self.att, user=self.user)
        with report.file.open("rb") as stored:
            text = " ".join(page.extract_text() for page in PdfReader(io.BytesIO(stored.read())).pages)
        for value in ("JOÃO CORAÇÃO", "CITROËN", "C3 AIRCROSS", "VERMELHA", "RUI MELO", "ANA SOUZA"):
            self.assertIn(value, text)
        for value in ("João Coração", "Citroën", "Rui Melo", "Ana Souza"):
            self.assertNotIn(value, text)
        self.assertIn("Cliente.Teste@empresa.com.br", text)


class SignatureCompatibilityTests(TestCase):
    """Padronizar a grafia não pode exigir nova assinatura nem trocar o hash já registrado."""

    @classmethod
    def setUpTestData(cls):
        call_command("seed_checklist", verbosity=0)

    def _signed_before_standard(self):
        att = complete_through(make_attendance(), wf.REVISAO)
        Customer.objects.filter(pk=att.customer_id).update(full_name="João da Silva")
        Vehicle.objects.filter(pk=att.vehicle_id).update(brand="Fiat", model="Argo")
        att = Attendance.objects.get(pk=att.pk)
        signature = AttendanceSignature(attendance=att, refused=True)
        signature.bind_to_current_version()
        signature.save()
        # O que a migração de dados faz.
        Customer.objects.filter(pk=att.customer_id).update(full_name="JOÃO DA SILVA")
        Vehicle.objects.filter(pk=att.vehicle_id).update(brand="FIAT", model="ARGO")
        return AttendanceSignature.objects.get(pk=signature.pk)

    def test_old_signature_still_valid_and_hash_unchanged(self):
        signature = self._signed_before_standard()
        stored = signature.snapshot_sha256
        self.assertTrue(signature.matches_current_version())
        self.assertEqual(AttendanceSignature.objects.get(pk=signature.pk).snapshot_sha256, stored)

    def test_real_change_still_requires_new_signature(self):
        signature = self._signed_before_standard()
        Customer.objects.filter(pk=signature.attendance.customer_id).update(full_name="OUTRA PESSOA")
        self.assertFalse(AttendanceSignature.objects.get(pk=signature.pk).matches_current_version())
        Customer.objects.filter(pk=signature.attendance.customer_id).update(full_name="JOÃO DA SILVA")
        Vehicle.objects.filter(pk=signature.attendance.vehicle_id).update(model="MOBI")
        self.assertFalse(AttendanceSignature.objects.get(pk=signature.pk).matches_current_version())

    def test_new_signature_matches_directly(self):
        att = complete_through(make_attendance(), wf.REVISAO)
        signature = AttendanceSignature(attendance=att, refused=True)
        signature.bind_to_current_version()
        signature.save()
        self.assertTrue(AttendanceSignature.objects.get(pk=signature.pk).matches_current_version())


class DataMigrationTests(TransactionTestCase):
    BEFORE = [("core", "0001_initial"), ("accounts", "0003_remove_mechanic_role"), ("customers", "0001_initial"),
              ("vehicles", "0001_initial"), ("mechanics", "0001_initial"),
              ("workshop", "0002_workshopsettings_google_review_url")]
    AFTER = [("core", "0002_uppercase_identifiers")]

    def tearDown(self):
        executor = MigrationExecutor(connection)
        executor.migrate(executor.loader.graph.leaf_nodes())

    def test_converts_existing_rows_without_touching_other_columns(self):
        executor = MigrationExecutor(connection)
        executor.migrate(self.BEFORE)
        old = executor.loader.project_state(self.BEFORE).apps
        customer = old.get_model("customers", "Customer").objects.create(
            person_type="ambos", full_name="joão", legal_name="ação ltda", trade_name="peça", contact_person="Dona Ana",
            phone="81990001712", email="Maria@empresa.com.br", address="Rua A",
        )
        OldVehicle = old.get_model("vehicles", "Vehicle")
        vehicle = OldVehicle.objects.create(customer=customer, plate="ABC1D23", brand="Fiat", model="Argo", color="")
        stamp = OldVehicle.objects.get(pk=vehicle.pk).updated_at
        mechanic = old.get_model("mechanics", "Mechanic").objects.create(name="Rui", name_key="rui")
        user = old.get_model("accounts", "User").objects.create(username="Ana.Souza", first_name="ana", email="Ana@x.com", password="hash")
        old.get_model("workshop", "WorkshopSettings").objects.create(pk=1, name="Minha Oficina", report_email="Dono@x.com",
                                                                     google_review_url="https://g.page/r/AbC/review")

        executor = MigrationExecutor(connection)
        executor.migrate(self.AFTER)
        new = executor.loader.project_state(self.AFTER).apps
        got = new.get_model("customers", "Customer").objects.get(pk=customer.pk)
        self.assertEqual((got.full_name, got.legal_name, got.trade_name), ("JOÃO", "AÇÃO LTDA", "PEÇA"))
        self.assertEqual((got.contact_person, got.email, got.address), ("Dona Ana", "Maria@empresa.com.br", "Rua A"))
        got_vehicle = new.get_model("vehicles", "Vehicle").objects.get(pk=vehicle.pk)
        self.assertEqual((got_vehicle.brand, got_vehicle.model), ("FIAT", "ARGO"))
        self.assertEqual(got_vehicle.updated_at, stamp)
        got_mechanic = new.get_model("mechanics", "Mechanic").objects.get(pk=mechanic.pk)
        self.assertEqual((got_mechanic.name, got_mechanic.name_key), ("RUI", "rui"))
        got_user = new.get_model("accounts", "User").objects.get(pk=user.pk)
        self.assertEqual((got_user.first_name, got_user.username, got_user.email, got_user.password),
                         ("ANA", "Ana.Souza", "Ana@x.com", "hash"))
        got_shop = new.get_model("workshop", "WorkshopSettings").objects.get(pk=1)
        self.assertEqual((got_shop.name, got_shop.report_email, got_shop.google_review_url),
                         ("MINHA OFICINA", "Dono@x.com", "https://g.page/r/AbC/review"))
        self.assertEqual(Mechanic._meta.db_table, "mechanics_mechanic")
