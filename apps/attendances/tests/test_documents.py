"""CPF e CNPJ são independentes: um nunca é buscado ou preenchido a partir do outro."""
import importlib
import io
from unittest import mock

from django.apps import apps as django_apps
from django.test import TestCase
from django.urls import reverse
from pypdf import PdfReader

from apps.attendances import workflow as wf
from apps.attendances.models import Attendance
from apps.attendances.summary import build_summary
from apps.core.testing import make_attendance, make_customer, make_employee, make_mechanic, make_user, make_vehicle, make_workshop
from apps.customers.models import Customer
from apps.reports.services import generate_report
from apps.signatures.services import register_refusal
from apps.signatures.snapshot import build_snapshot

CPF = "529.982.247-25"
CPF_RAW = "52998224725"
OLD_CNPJ = "12ABC34501DE35"
OLD_CNPJ_MASKED = "12.ABC.345/01DE-35"
NEW_CNPJ = "00.000.000/0001-91"
NEW_CNPJ_RAW = "00000000000191"
OLD_COMPANY = "RAZAO HISTORICA LTDA"
OLD_TRADE = "FANTASIA HISTORICA"


def pdf_text(report):
    with report.file.open("rb") as stored:
        reader = PdfReader(io.BytesIO(stored.read()))
    return "\n".join(page.extract_text() for page in reader.pages)


class DocumentBase(TestCase):
    def setUp(self):
        self.user = make_user("oficina")
        self.client.force_login(self.user)
        self.mechanic = make_mechanic()
        self.attendant = make_employee()
        self.url = reverse("attendances:new")

    def history(self, **extra):
        """Cliente cujo CPF já ficou ligado a um CNPJ no cadastro."""
        data = {"person_type": "ambos", "full_name": "Maria Souza", "cnpj": OLD_CNPJ, "legal_name": OLD_COMPANY,
                "trade_name": OLD_TRADE, "contact_person": "Rui Antigo"}
        data.update(extra)
        return make_customer(**data)

    def payload(self, **extra):
        data = {"person_type": "pf", "full_name": "Maria Souza", "cpf": CPF, "phone": "(81) 9 9000-1712",
                "plate": "abc1d23", "brand": "Fiat", "model": "Argo", "mileage": "45210", "mechanic": self.mechanic.pk,
                "origin": "instagram", "attendant": self.attendant.pk}
        data.update(extra)
        return data

    def open_attendance(self, **extra):
        response = self.client.post(self.url, self.payload(**extra))
        self.assertEqual(response.status_code, 302, getattr(response, "context", None) and response.context["form"].errors)
        return Attendance.objects.order_by("-pk").first()

    def customer_rows(self, attendance):
        return dict(build_summary(attendance)["customer_rows"])

    def concluded_pdf(self, attendance):
        Attendance.objects.filter(pk=attendance.pk).update(status=wf.STATUS_CONCLUIDO, current_step=wf.FINALIZADO)
        attendance.refresh_from_db()
        return pdf_text(generate_report(attendance))


class CpfWithCnpjHistoryTests(DocumentBase):
    """O caso central: CPF com histórico de CNPJ nunca recupera esse CNPJ."""

    def assert_no_company_data(self, attendance):
        self.assertEqual((attendance.cnpj, attendance.legal_name, attendance.trade_name, attendance.contact_person),
                         ("", "", "", ""))

    def test_pf_attendance_does_not_inherit_the_cnpj(self):
        self.history()
        attendance = self.open_attendance()
        self.assert_no_company_data(attendance)
        rows = self.customer_rows(attendance)
        self.assertEqual(rows["CPF"], "529.982.247-25")
        for label in ("CNPJ", "Razão Social", "Nome Fantasia", "Responsável"):
            self.assertNotIn(label, rows)

    def test_review_screen_does_not_show_the_cnpj(self):
        self.history()
        attendance = self.open_attendance()
        response = self.client.get(reverse("attendances:summary", args=[attendance.public_id]))
        for leaked in (OLD_CNPJ, OLD_CNPJ_MASKED, OLD_COMPANY, OLD_TRADE, "Rui Antigo"):
            self.assertNotContains(response, leaked)

    def test_pdf_does_not_show_the_cnpj(self):
        self.history()
        text = self.concluded_pdf(self.open_attendance())
        self.assertIn("529.982.247-25", text)
        for leaked in (OLD_CNPJ_MASKED, OLD_COMPANY, OLD_TRADE, "Rui Antigo"):
            self.assertNotIn(leaked, text)

    def test_edit_form_does_not_bring_the_cnpj(self):
        self.history()
        attendance = self.open_attendance()
        response = self.client.get(reverse("attendances:edit", args=[attendance.public_id]))
        for leaked in (OLD_CNPJ_MASKED, OLD_COMPANY, OLD_TRADE):
            self.assertNotContains(response, leaked)

    def test_ambos_without_typing_the_cnpj_is_not_filled_from_history(self):
        self.history()
        response = self.client.post(self.url, self.payload(person_type="ambos", legal_name="Digitada Ltda"))
        self.assertContains(response, "Informe o CNPJ")
        self.assertEqual(Attendance.objects.count(), 0)

    def test_ambos_uses_only_the_typed_cnpj(self):
        customer = self.history()
        attendance = self.open_attendance(person_type="ambos", cnpj=NEW_CNPJ, legal_name="Banco Digitado", trade_name="BD")
        self.assertEqual(attendance.customer, customer)
        self.assertEqual((attendance.cnpj, attendance.legal_name, attendance.trade_name), (NEW_CNPJ_RAW, "BANCO DIGITADO", "BD"))
        rows = self.customer_rows(attendance)
        self.assertEqual(rows["CNPJ"], NEW_CNPJ)
        self.assertEqual(rows["Razão Social"], "BANCO DIGITADO")
        text = self.concluded_pdf(attendance)
        self.assertIn(NEW_CNPJ, text)
        for leaked in (OLD_CNPJ_MASKED, OLD_COMPANY, OLD_TRADE):
            self.assertNotIn(leaked, text)

    def test_ambos_with_cnpj_not_informed_shows_no_historic_cnpj(self):
        self.history()
        attendance = self.open_attendance(person_type="ambos", cnpj_not_informed="on", legal_name="Digitada Ltda")
        self.assertEqual(attendance.cnpj, "")
        self.assertEqual(self.customer_rows(attendance)["CNPJ"], "Cliente não informou")

    def test_history_is_not_erased_or_changed(self):
        customer = self.history()
        self.open_attendance()
        self.open_attendance(person_type="ambos", cnpj=NEW_CNPJ, legal_name="Outra Ltda", mileage="50000")
        customer.refresh_from_db()
        self.assertEqual((customer.cnpj, customer.legal_name, customer.trade_name, customer.person_type),
                         (OLD_CNPJ, OLD_COMPANY, OLD_TRADE, "ambos"))


class NoNewAssociationTests(DocumentBase):
    def test_ambos_does_not_link_cnpj_to_the_cpf_record(self):
        attendance = self.open_attendance(person_type="ambos", cnpj=NEW_CNPJ, legal_name="Banco Ltda", trade_name="Banco")
        customer = attendance.customer
        self.assertEqual(customer.cpf, CPF_RAW)
        self.assertIsNone(customer.cnpj)
        self.assertEqual((customer.legal_name, customer.trade_name, customer.person_type), ("", "", "pf"))
        self.assertEqual(attendance.cnpj, NEW_CNPJ_RAW)

    def test_next_visit_with_same_cpf_does_not_recover_the_previous_cnpj(self):
        self.open_attendance(person_type="ambos", cnpj=NEW_CNPJ, legal_name="Banco Ltda")
        second = self.open_attendance(mileage="50000")
        self.assertEqual(second.cnpj, "")
        self.assertNotIn("CNPJ", self.customer_rows(second))
        self.assertEqual(Customer.objects.count(), 1)

    def test_same_cpf_can_inform_different_cnpjs_per_attendance(self):
        first = self.open_attendance(person_type="ambos", cnpj=NEW_CNPJ, legal_name="Banco Ltda")
        second = self.open_attendance(person_type="ambos", cnpj=OLD_CNPJ_MASKED, legal_name="Outra Ltda", mileage="50000")
        first.refresh_from_db()
        self.assertEqual((first.cnpj, first.legal_name), (NEW_CNPJ_RAW, "BANCO LTDA"))
        self.assertEqual((second.cnpj, second.legal_name), (OLD_CNPJ, "OUTRA LTDA"))


class CnpjOnlyTests(DocumentBase):
    def test_cnpj_held_by_person_does_not_show_or_link_that_cpf(self):
        person = self.history()
        attendance = self.open_attendance(person_type="pj", full_name="", cpf="", cnpj=OLD_CNPJ_MASKED, legal_name="Digitada Ltda")
        self.assertNotEqual(attendance.customer, person)
        self.assertIsNone(attendance.customer.cpf)
        self.assertEqual(attendance.cnpj, OLD_CNPJ)
        rows = self.customer_rows(attendance)
        self.assertNotIn("CPF", rows)
        self.assertNotIn("Nome", rows)
        self.assertEqual(rows["Razão Social"], "DIGITADA LTDA")
        person.refresh_from_db()
        self.assertEqual(person.cnpj, OLD_CNPJ)
        self.assertNotIn("529.982.247-25", self.concluded_pdf(attendance))

    def test_company_record_is_reused_by_its_cnpj(self):
        company = make_customer(person_type="pj", full_name="", cpf=None, cnpj=OLD_CNPJ, legal_name="Empresa Ltda")
        attendance = self.open_attendance(person_type="pj", full_name="", cpf="", cnpj=OLD_CNPJ_MASKED, legal_name="Empresa Ltda")
        self.assertEqual(attendance.customer, company)

    def test_new_company_is_registered_without_any_cpf(self):
        attendance = self.open_attendance(person_type="pj", full_name="", cpf="", cnpj=NEW_CNPJ, legal_name="Nova Ltda")
        self.assertIsNone(attendance.customer.cpf)
        self.assertEqual(attendance.customer.cnpj, NEW_CNPJ_RAW)
        self.assertEqual(attendance.customer.person_type, "pj")


class ModalityGateTests(DocumentBase):
    def test_cnpj_mode_on_vehicle_owner_with_cpf_does_not_show_that_cpf(self):
        owner = make_customer(full_name="Maria Souza", phone="81990001712")
        make_vehicle(owner, plate="ABC1D23")
        attendance = self.open_attendance(person_type="pj", full_name="", cpf="", cnpj_not_informed="on", legal_name="Digitada Ltda")
        self.assertEqual(attendance.customer, owner, "Sem documento, mesma placa e telefone: mantém o dono do veículo")
        self.assertIsNone(attendance.informed_cpf)
        rows = self.customer_rows(attendance)
        self.assertNotIn("CPF", rows)
        self.assertNotIn("Nome", rows)
        owner.refresh_from_db()
        self.assertEqual(owner.legal_name, "", "Cliente com CPF não recebe dados empresariais")

    def test_cpf_mode_never_shows_company_fields_even_if_present(self):
        attendance = make_attendance(person_type="pf", cnpj=OLD_CNPJ, legal_name=OLD_COMPANY, trade_name=OLD_TRADE, contact_person="Rui")
        rows = self.customer_rows(attendance)
        for label in ("CNPJ", "Razão Social", "Nome Fantasia", "Responsável"):
            self.assertNotIn(label, rows)


class EditKeepsDocumentsApartTests(DocumentBase):
    def _edit(self, attendance, **extra):
        response = self.client.post(reverse("attendances:edit", args=[attendance.public_id]), self.payload(**extra))
        self.assertEqual(response.status_code, 302)
        attendance.refresh_from_db()
        return attendance

    def test_changing_from_cpf_to_cnpj_does_not_link_them(self):
        attendance = self.open_attendance()
        person = attendance.customer
        self._edit(attendance, person_type="pj", full_name="", cpf="", cnpj=NEW_CNPJ, legal_name="Empresa Ltda")
        self.assertNotEqual(attendance.customer, person)
        person.refresh_from_db()
        self.assertIsNone(person.cnpj)
        self.assertEqual(person.cpf, CPF_RAW)

    def test_adding_cpf_to_cnpj_attendance_does_not_link_them(self):
        attendance = self.open_attendance(person_type="pj", full_name="", cpf="", cnpj=NEW_CNPJ, legal_name="Empresa Ltda")
        company = attendance.customer
        self._edit(attendance, person_type="ambos", cnpj=NEW_CNPJ, legal_name="Empresa Ltda")
        self.assertNotEqual(attendance.customer, company)
        self.assertEqual(attendance.cnpj, NEW_CNPJ_RAW)
        company.refresh_from_db()
        self.assertIsNone(company.cpf)
        self.assertIsNone(attendance.customer.cnpj)

    def test_edit_form_keeps_what_was_informed(self):
        attendance = self.open_attendance(person_type="ambos", cnpj=NEW_CNPJ, legal_name="Empresa Ltda", trade_name="Emp")
        response = self.client.get(reverse("attendances:edit", args=[attendance.public_id]))
        self.assertContains(response, NEW_CNPJ)
        self.assertContains(response, "EMPRESA LTDA")

    def test_switching_to_pf_clears_company_data_of_the_attendance(self):
        attendance = self.open_attendance(person_type="ambos", cnpj=NEW_CNPJ, legal_name="Empresa Ltda")
        self._edit(attendance)
        self.assertEqual((attendance.person_type, attendance.cnpj, attendance.legal_name), ("pf", "", ""))


class SearchTests(DocumentBase):
    def _results(self, term):
        response = self.client.get(reverse("attendances:list"), {"q": term})
        return list(response.context["page"].object_list)

    def test_finds_attendance_by_the_informed_cnpj_only(self):
        with_cnpj = self.open_attendance(person_type="ambos", cnpj=NEW_CNPJ, legal_name="Banco Ltda")
        without = self.open_attendance(mileage="50000")
        self.assertEqual(self._results(NEW_CNPJ), [with_cnpj])
        self.assertEqual(self._results(NEW_CNPJ_RAW), [with_cnpj])
        self.assertEqual(self._results("Banco Ltda"), [with_cnpj])
        self.assertNotIn(without, self._results(NEW_CNPJ))

    def test_cnpj_search_finds_the_attendance_without_linking_it_to_the_cpf_record(self):
        with_cnpj = self.open_attendance(person_type="ambos", cnpj=NEW_CNPJ, legal_name="Banco Ltda", trade_name="Banco")
        same_cpf_without_cnpj = self.open_attendance(mileage="50000")
        person = with_cnpj.customer
        self.assertEqual(same_cpf_without_cnpj.customer, person)

        for term in (NEW_CNPJ, NEW_CNPJ_RAW):
            self.assertEqual(self._results(term), [with_cnpj])
        history = self.client.get(reverse("attendances:history"), {"q": NEW_CNPJ})
        self.assertEqual(history.status_code, 200)

        person.refresh_from_db()
        self.assertEqual((person.cpf, person.cnpj, person.legal_name, person.trade_name, person.person_type),
                         (CPF_RAW, None, "", "", "pf"))
        self.assertFalse(Customer.objects.filter(cnpj=NEW_CNPJ_RAW).exists())
        customers = reverse("customers:list")
        self.assertNotContains(self.client.get(customers, {"q": NEW_CNPJ}), "MARIA SOUZA")
        self.assertContains(self.client.get(customers, {"q": CPF}), "MARIA SOUZA")

    def test_history_screen_finds_completed_attendance_by_the_informed_cnpj(self):
        with_cnpj = self.open_attendance(person_type="ambos", cnpj=NEW_CNPJ, legal_name="Banco Ltda")
        without = self.open_attendance(mileage="50000")
        Attendance.objects.filter(pk__in=[with_cnpj.pk, without.pk]).update(status=wf.STATUS_CONCLUIDO, current_step=wf.FINALIZADO)
        response = self.client.get(reverse("attendances:history"), {"q": NEW_CNPJ})
        self.assertEqual(list(response.context["page"].object_list), [with_cnpj])

    def test_historic_cnpj_of_the_customer_does_not_find_other_attendances(self):
        self.history()
        attendance = self.open_attendance()
        self.assertNotIn(attendance, self._results(OLD_CNPJ_MASKED))
        self.assertNotIn(attendance, self._results(OLD_COMPANY))
        self.assertIn(attendance, self._results(CPF))

    def test_search_is_limited_to_the_workshop(self):
        self.open_attendance(person_type="ambos", cnpj=NEW_CNPJ, legal_name="Banco Ltda")
        other = make_workshop("Oficina Dois")
        self.client.force_login(make_user("dois@oficina.com.br", workshop=other))
        self.assertEqual(self._results(NEW_CNPJ), [])


class SignatureTests(DocumentBase):
    def test_later_change_in_customer_company_data_does_not_invalidate_signature(self):
        attendance = self.open_attendance()
        signature = register_refusal(attendance, user=self.user)
        Customer.objects.filter(pk=attendance.customer_id).update(cnpj=OLD_CNPJ, legal_name=OLD_COMPANY, person_type="ambos")
        attendance = Attendance.objects.get(pk=attendance.pk)
        signature.attendance = attendance
        self.assertTrue(signature.matches_current_version())
        self.assertIsNone(build_snapshot(attendance)["customer"]["cnpj"])


class LegacyAttendanceMigrationTests(TestCase):
    """Atendimento anterior à correção: mantém o que mostrava, com a mesma assinatura."""

    def _migrate(self):
        module = importlib.import_module("apps.attendances.migrations.0010_documentos_no_atendimento")
        module.forwards(django_apps, None)

    def _legacy(self, customer, **extra):
        attendance = make_attendance(vehicle=make_vehicle(customer), **extra)
        Attendance.objects.filter(pk=attendance.pk).update(person_type="pf", cnpj="", legal_name="", trade_name="", contact_person="")
        return attendance

    def test_copies_what_the_attendance_showed_and_keeps_the_hash(self):
        customer = make_customer(person_type="ambos", full_name="Maria", cnpj=OLD_CNPJ, legal_name="Empresa Ltda",
                                 trade_name="Empresa", contact_person="Rui")
        attendance = self._legacy(customer)
        before = {"id": customer.pk, "type": "ambos", "name": "MARIA", "legal_name": "EMPRESA LTDA", "trade_name": "EMPRESA",
                  "cpf": CPF_RAW, "cnpj": OLD_CNPJ, "phone": customer.phone}
        self._migrate()
        attendance.refresh_from_db()
        self.assertEqual(build_snapshot(attendance)["customer"], before)
        self.assertEqual((attendance.cnpj, attendance.contact_person), (OLD_CNPJ, "Rui"))
        customer.refresh_from_db()
        self.assertEqual(customer.cnpj, OLD_CNPJ)

    def test_respects_not_informed_marks(self):
        customer = make_customer(person_type="ambos", full_name="Maria", cnpj=OLD_CNPJ, legal_name="Empresa Ltda")
        attendance = self._legacy(customer, cnpj_not_informed=True)
        self._migrate()
        attendance.refresh_from_db()
        self.assertEqual(attendance.cnpj, "")
        self.assertIsNone(build_snapshot(attendance)["customer"]["cnpj"])


class NoExternalCallFromCpfTests(DocumentBase):
    def test_typing_cpf_never_calls_brasilapi(self):
        self.history()
        with mock.patch("requests.get") as patched:
            self.client.get(reverse("integrations:cpf"), {"cpf": CPF})
        patched.assert_not_called()

    def test_saving_attendance_never_calls_brasilapi(self):
        with mock.patch("requests.get") as patched:
            self.open_attendance(person_type="ambos", cnpj=NEW_CNPJ, legal_name="Banco Ltda")
        patched.assert_not_called()
