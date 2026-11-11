from apps.attendances import workflow as wf
from apps.attendances.models import Attendance
from apps.signatures.models import AttendanceSignature

from .base import BrowserTestCase
from .helpers import advance_to_review, draw_signature, open_intake


class SignatureTests(BrowserTestCase):
    def setUp(self):
        super().setUp()
        self.login()
        open_intake(self)
        advance_to_review(self, bad_component="Pastilhas dianteiras")

    def test_requires_signature_then_signs_with_pointer(self):
        self.assertIn("Pastilhas dianteiras", self.page.inner_text("main"))
        self.assertIn("Recusada", self.page.inner_text("main"))
        self.submit("[data-step-submit]")
        self.assertIn("Colete a assinatura", self.page.inner_text(".errors-box"))
        self.assertEqual(Attendance.objects.get().status, wf.STATUS_EM_ANDAMENTO)

        draw_signature(self.page)
        self.shot("review-signed")
        self.submit("[data-step-submit]")
        self.assertIn("/resumo/", self.page.url, self.page.inner_text("main")[:600])

        att = Attendance.objects.get()
        self.assertEqual(att.status, wf.STATUS_CONCLUIDO)
        self.assertFalse(AttendanceSignature.objects.get().refused)
        image = self.page.locator(".signature-saved")
        image.wait_for()
        self.assertGreater(image.evaluate("img => img.naturalWidth"), 0)
        self.shot("attendance-completed")

    def test_clear_button_removes_drawing(self):
        draw_signature(self.page)
        self.page.click("[data-signature-clear]")
        self.submit("[data-step-submit]")
        self.assertIn("Colete a assinatura", self.page.inner_text(".errors-box"))
        self.assertFalse(AttendanceSignature.objects.exists())

    def test_refusal_hides_pad_and_shows_official_text(self):
        self.page.check("[data-signature-refused]")
        self.assertFalse(self.page.locator("[data-signature-canvas]").is_visible())
        self.assertIn("optou por não registrar", self.page.inner_text("[data-refusal-text]"))
        self.submit("[data-step-submit]")
        self.assertIn("/resumo/", self.page.url, self.page.inner_text("main")[:600])
        self.assertTrue(AttendanceSignature.objects.get().refused)
        self.assertIn("optou por não registrar", self.page.inner_text("main"))
