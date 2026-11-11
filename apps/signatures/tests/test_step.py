import base64
import io

from django.core.exceptions import ValidationError
from django.core.files.storage import default_storage
from django.core.management import call_command
from django.test import SimpleTestCase, TestCase
from django.urls import reverse
from PIL import Image, ImageDraw

from apps.attendances import workflow as wf
from apps.core.testing import complete_through, make_attendance, make_user, tiny_png
from apps.photos import categories as cat
from apps.photos.models import Photo
from apps.signatures.models import AttendanceSignature
from apps.signatures.services import decode_signature


def signature_data_url(blank=False, format_name="PNG"):
    image = Image.new("RGBA", (400, 150), (0, 0, 0, 0))
    if not blank:
        ImageDraw.Draw(image).line([(10, 10), (390, 140)], fill=(0, 0, 0, 255), width=4)
    buffer = io.BytesIO()
    image.convert("RGB").save(buffer, format=format_name) if format_name != "PNG" else image.save(buffer, format="PNG")
    return "data:image/png;base64," + base64.b64encode(buffer.getvalue()).decode()


class DecodeTests(SimpleTestCase):
    def test_valid_signature_flattened_on_white(self):
        content = decode_signature(signature_data_url())
        with Image.open(io.BytesIO(content.read())) as image:
            self.assertEqual(image.mode, "RGB")
            self.assertEqual(image.getpixel((399, 0)), (255, 255, 255))

    def test_rejects_blank_garbage_and_wrong_formats(self):
        for value in (signature_data_url(blank=True), "", "texto", "data:image/png;base64,@@@",
                      "data:image/png;base64,bmFvIHNvdSBpbWFnZW0=", signature_data_url(format_name="JPEG"),
                      "data:text/html;base64,PHNjcmlwdD4="):
            with self.assertRaises(ValidationError):
                decode_signature(value)

    def test_rejects_oversized(self):
        with self.assertRaises(ValidationError):
            decode_signature("data:image/png;base64," + "A" * 3_000_001)


class StepBase(TestCase):
    @classmethod
    def setUpTestData(cls):
        call_command("seed_checklist", verbosity=0)

    def setUp(self):
        self.user = make_user("ana")
        self.client.force_login(self.user)
        self.att = complete_through(make_attendance(), wf.REVISAO)
        self.url = reverse("signatures:step", args=[self.att.public_id])

    def sign(self, **extra):
        return self.client.post(self.url, {"signature_data": signature_data_url(), **extra})


class ReviewStepTests(StepBase):
    def test_page_has_summary_and_required_options(self):
        response = self.client.get(self.url)
        self.assertContains(response, self.att.vehicle.plate_formatted)
        self.assertContains(response, "CLIENTE NÃO ACEITOU ASSINAR")
        self.assertContains(response, "Serviços realizados")
        self.assertNotContains(response, "google.com")

    def test_blocked_before_step(self):
        type(self.att).objects.filter(pk=self.att.pk).update(current_step=wf.CHECKOUT)
        self.assertEqual(self.client.get(self.url).status_code, 403)
        self.assertEqual(self.sign().status_code, 403)
        self.assertFalse(AttendanceSignature.objects.exists())

    def test_cannot_finish_without_signature_or_refusal(self):
        response = self.client.post(self.url)
        self.assertContains(response, "Colete a assinatura")
        self.att.refresh_from_db()
        self.assertEqual(self.att.status, wf.STATUS_EM_ANDAMENTO)

    def test_blank_signature_rejected(self):
        response = self.client.post(self.url, {"signature_data": signature_data_url(blank=True)})
        self.assertContains(response, "em branco")
        self.assertFalse(AttendanceSignature.objects.exists())

    def test_signature_finishes_and_binds_to_version(self):
        response = self.sign()
        self.assertRedirects(response, reverse("attendances:summary", args=[self.att.public_id]))
        self.att.refresh_from_db()
        self.assertEqual(self.att.status, wf.STATUS_CONCLUIDO)
        self.assertEqual(self.att.current_step, wf.FINALIZADO)
        self.assertIsNotNone(self.att.completed_at)
        self.assertEqual(self.att.retention_until, self.att.compute_retention_until())
        signature = self.att.signature
        self.assertFalse(signature.refused)
        self.assertEqual(signature.registered_by, self.user)
        self.assertTrue(signature.matches_current_version())
        self.assertEqual(len(signature.snapshot_sha256), 64)

    def test_refusal_finishes_with_official_text(self):
        self.client.post(self.url, {"refused": "on", "signature_data": signature_data_url()})
        self.att.refresh_from_db()
        self.assertEqual(self.att.status, wf.STATUS_CONCLUIDO)
        signature = self.att.signature
        self.assertTrue(signature.refused)
        self.assertFalse(signature.image)
        response = self.client.get(reverse("attendances:summary", args=[self.att.public_id]))
        self.assertContains(response, "O cliente optou por não registrar sua assinatura digital.")

    def test_signature_file_is_protected(self):
        self.sign()
        url = reverse("signatures:file", args=[self.att.public_id])
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        response.close()
        self.client.logout()
        self.assertEqual(self.client.get(url).status_code, 302)

    def test_completed_attendance_is_read_only(self):
        self.sign()
        self.assertEqual(self.client.get(self.url).status_code, 403)
        self.assertEqual(self.client.get(reverse("checklist:step", args=[self.att.public_id])).status_code, 403)


class VersionBindingTests(StepBase):
    def _stale_signature(self):
        signature = AttendanceSignature(attendance=self.att, refused=True, registered_by=self.user)
        signature.bind_to_current_version()
        signature.save()
        return signature

    def test_change_after_signature_requires_new_signature(self):
        signature = self._stale_signature()
        Photo.objects.create(attendance=self.att, phase=cat.PHASE_CHECKIN, category=cat.AVARIAS, image=tiny_png(), sha256="nova")
        self.assertFalse(signature.matches_current_version())
        response = self.client.post(self.url)
        # Recusa antiga desmarcada e nada novo: precisa coletar de novo.
        self.assertContains(response, "Colete a assinatura")
        self.att.refresh_from_db()
        self.assertEqual(self.att.status, wf.STATUS_EM_ANDAMENTO)

    def test_new_signature_replaces_old_file(self):
        self.client.post(self.url, {"signature_data": signature_data_url(), "refused": ""})
        first = AttendanceSignature.objects.get()
        name = first.image.name
        type(self.att).objects.filter(pk=self.att.pk).update(status=wf.STATUS_EM_ANDAMENTO, current_step=wf.REVISAO)
        with self.captureOnCommitCallbacks(execute=True):
            self.sign()
        second = AttendanceSignature.objects.get()
        self.assertNotEqual(second.image.name, name)
        self.assertFalse(default_storage.exists(name))

    def test_failed_finish_does_not_keep_partial_state(self):
        Photo.objects.filter(attendance=self.att, phase=cat.PHASE_CHECKOUT).delete()
        response = self.sign()
        self.assertContains(response, "Falta a foto")
        self.assertFalse(AttendanceSignature.objects.exists())
