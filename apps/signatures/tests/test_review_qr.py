"""Seção do QR Code na revisão: exibe, registra a apresentação e nunca afirma que houve avaliação."""
import io

from django.core.management import call_command
from django.test import TestCase
from django.urls import reverse
from pypdf import PdfReader

from apps.attendances import workflow as wf
from apps.core.models import AuditLog
from apps.core.testing import complete_through, default_workshop, make_attendance, make_employee, make_user
from apps.reports.services import generate_report
from apps.signatures.models import AttendanceSignature
from apps.signatures.services import register_refusal
from apps.signatures.tests.test_step import signature_data_url
from apps.workshop.models import WorkshopSettings

LINK = "https://g.page/r/CaBcDeFgHiJkEBM/review"


class ReviewQrBase(TestCase):
    @classmethod
    def setUpTestData(cls):
        call_command("seed_checklist", verbosity=0)

    def setUp(self):
        self.user = make_user("ana", first_name="Ana")
        self.client.force_login(self.user)
        self.att = complete_through(make_attendance(), wf.REVISAO)
        self.step_url = reverse("signatures:step", args=[self.att.public_id])
        self.action_url = reverse("signatures:review_qr", args=[self.att.public_id])
        WorkshopSettings.objects.update_or_create(
            pk=default_workshop().pk, defaults={"name": "Oficina Boa", "google_review_url": LINK},
        )

    def present(self, action="present", **headers):
        return self.client.post(self.action_url, {"action": action}, **headers)

    def present_json(self, action="present"):
        return self.present(action, headers={"Accept": "application/json"})


class ReviewSectionTests(ReviewQrBase):
    def test_shows_code_invitation_guidance_and_action(self):
        response = self.client.get(self.step_url)
        self.assertContains(response, reverse("workshop:review_qr"))
        self.assertContains(response, "Como foi sua experiência na OFICINA BOA?")
        self.assertContains(response, "Aponte para o código")
        self.assertContains(response, "QR CODE APRESENTADO AO CLIENTE")

    def test_old_checkbox_is_gone(self):
        response = self.client.get(self.step_url)
        self.assertNotContains(response, 'name="review_requested"')
        self.assertNotContains(response, "AVALIAÇÃO SOLICITADA AO CLIENTE")

    def test_does_not_open_google_nor_expose_the_link(self):
        self.assertNotContains(self.client.get(self.step_url), LINK)

    def test_without_link_shows_notice_and_no_action(self):
        WorkshopSettings.objects.filter(pk=default_workshop().pk).update(google_review_url="")
        response = self.client.get(self.step_url)
        self.assertContains(response, "ainda não foi configurado")
        self.assertNotContains(response, "QR CODE APRESENTADO AO CLIENTE")
        self.assertNotContains(response, reverse("workshop:review_qr"))

    def test_shortcut_to_settings_when_not_configured(self):
        WorkshopSettings.objects.filter(pk=default_workshop().pk).update(google_review_url="")
        self.assertContains(self.client.get(self.step_url), "Configurar agora")


class PresentationRecordTests(ReviewQrBase):
    def test_nothing_recorded_until_the_action(self):
        self.client.get(self.step_url)
        self.client.post(self.step_url, {"signature_data": signature_data_url()})
        self.att.refresh_from_db()
        self.assertEqual(self.att.status, wf.STATUS_CONCLUIDO, "o QR Code não é obrigatório para concluir")
        self.assertIsNone(self.att.review_qr_presented_at)

    def test_records_when_and_who_and_audits(self):
        response = self.present_json()
        data = response.json()
        self.assertTrue(data["presented"])
        self.assertIn("Apresentado em", data["note"])
        self.assertNotIn(" por ", data["note"], "o login é da oficina e não identifica a pessoa")
        self.att.refresh_from_db()
        self.assertIsNotNone(self.att.review_qr_presented_at)
        self.assertEqual(self.att.review_qr_presented_by, self.user)
        self.assertTrue(AuditLog.objects.filter(action="attendance.review_qr_presented", attendance_id=self.att.pk).exists())

    def test_without_js_redirects_back_showing_record(self):
        response = self.client.post(self.action_url, {"action": "present"}, follow=True)
        self.assertRedirects(response, self.step_url)
        self.assertContains(response, "QR Code apresentado ao cliente")
        self.assertContains(response, "Apresentado em")

    def test_repeating_keeps_first_record(self):
        self.present_json()
        self.att.refresh_from_db()
        first = self.att.review_qr_presented_at
        self.client.force_login(make_user("outra"))
        self.present_json()
        self.att.refresh_from_db()
        self.assertEqual(self.att.review_qr_presented_at, first)
        self.assertEqual(self.att.review_qr_presented_by, self.user)
        self.assertEqual(AuditLog.objects.filter(action="attendance.review_qr_presented").count(), 1)

    def test_undo_clears_and_audits(self):
        self.present_json()
        data = self.present_json("clear").json()
        self.assertFalse(data["presented"])
        self.att.refresh_from_db()
        self.assertIsNone(self.att.review_qr_presented_at)
        self.assertIsNone(self.att.review_qr_presented_by)
        self.assertTrue(AuditLog.objects.filter(action="attendance.review_qr_cleared").exists())

    def test_refused_when_link_is_not_configured(self):
        WorkshopSettings.objects.filter(pk=default_workshop().pk).update(google_review_url="")
        response = self.present_json()
        self.assertEqual(response.status_code, 400)
        self.assertIn("não está configurado", response.json()["error"])
        self.att.refresh_from_db()
        self.assertIsNone(self.att.review_qr_presented_at)

    def test_blocked_before_review_step(self):
        type(self.att).objects.filter(pk=self.att.pk).update(current_step=wf.CHECKOUT)
        self.assertEqual(self.present_json().status_code, 403)
        self.att.refresh_from_db()
        self.assertIsNone(self.att.review_qr_presented_at)

    def test_blocked_after_conclusion(self):
        self.client.post(self.step_url, {"signature_data": signature_data_url()})
        self.assertEqual(self.present_json().status_code, 403)

    def test_get_changes_nothing(self):
        self.assertEqual(self.client.get(self.action_url).status_code, 405)

    def test_presenting_does_not_invalidate_the_signature(self):
        self.client.post(self.step_url, {"refused": ""})
        register_refusal(self.att, user=self.user)
        self.present_json()
        self.assertTrue(AttendanceSignature.objects.get(attendance=self.att).matches_current_version())


class RecordWordingTests(ReviewQrBase):
    FORBIDDEN = ("avaliação publicada", "avaliação realizada", "cliente avaliou", "avaliou a oficina")

    def _finish(self):
        self.present_json()
        self.client.post(self.step_url, {"signature_data": signature_data_url()})
        self.att.refresh_from_db()

    def test_screens_state_only_the_presentation(self):
        response = self.client.get(self.step_url)
        self.assertContains(response, "Não confirma que uma avaliação foi publicada")
        self._finish()
        summary = self.client.get(reverse("attendances:summary", args=[self.att.public_id]))
        self.assertContains(summary, "QR Code de avaliação apresentado ao cliente")
        self.assertContains(summary, "Apresentado em")
        content = summary.content.decode().lower()
        for text in self.FORBIDDEN:
            self.assertNotIn(text, content)

    def _pdf_text(self):
        report = generate_report(self.att, user=self.user)
        with report.file.open("rb") as stored:
            reader = PdfReader(io.BytesIO(stored.read()))
        return " ".join(" ".join(page.extract_text().split()) for page in reader.pages)

    def test_pdf_records_presentation_employee_and_mechanic(self):
        self._finish()
        type(self.att).objects.filter(pk=self.att.pk).update(attendant=make_employee("Ana Souza"))
        self.att.refresh_from_db()
        text = self._pdf_text()
        self.assertIn("QR Code de avaliação apresentado ao cliente", text)
        self.assertIn("Vendedor/Atendente", text)
        self.assertIn("ANA SOUZA", text)
        self.assertIn(self.att.mechanic.name, text)
        for forbidden in self.FORBIDDEN:
            self.assertNotIn(forbidden, text.lower())

    def test_old_attendance_keeps_old_wording(self):
        self.client.post(self.step_url, {"signature_data": signature_data_url()})
        type(self.att).objects.filter(pk=self.att.pk).update(review_requested=True)
        self.att.refresh_from_db()
        summary = self.client.get(reverse("attendances:summary", args=[self.att.public_id]))
        self.assertContains(summary, "Avaliação solicitada ao cliente")
        self.assertNotContains(summary, "QR Code de avaliação apresentado")
        self.assertIn("Avaliação solicitada ao cliente", self._pdf_text())
