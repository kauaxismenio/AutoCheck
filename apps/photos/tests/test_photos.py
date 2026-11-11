import io

from django.core.files.storage import default_storage
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.urls import reverse
from PIL import Image

from apps.attendances import services as att_services
from apps.attendances import workflow as wf
from apps.core.testing import make_attendance, make_user, make_vehicle, tiny_png
from apps.photos import categories as cat
from apps.photos.models import Photo


def jpeg_with_exif():
    image = Image.new("RGB", (3000, 1500), (10, 20, 30))
    exif = image.getexif()
    exif[0x010F] = "Fabricante Secreto"
    buffer = io.BytesIO()
    image.save(buffer, format="JPEG", exif=exif)
    return SimpleUploadedFile("foto.jpg", buffer.getvalue(), content_type="image/jpeg")


class PhotoBase(TestCase):
    def setUp(self):
        self.user = make_user("ana")
        self.client.force_login(self.user)
        self.att = make_attendance()
        att_services.advance(self.att, wf.CADASTRO)

    def upload(self, att=None, **extra):
        att = att or self.att
        data = {"phase": cat.PHASE_CHECKIN, "category": cat.FRENTE, "image": tiny_png()}
        data.update(extra)
        return self.client.post(reverse("photos:upload", args=[att.public_id]), data)


class UploadTests(PhotoBase):
    def test_upload_returns_urls_and_processes_image(self):
        response = self.upload()
        self.assertEqual(response.status_code, 201)
        photo = Photo.objects.get()
        self.assertEqual(photo.taken_by, self.user)
        self.assertEqual(len(photo.sha256), 64)
        self.assertGreater(photo.size_bytes, 0)
        self.assertTrue(photo.image.name.endswith(".jpg"))
        self.assertEqual(response.json()["id"], photo.pk)

    def test_exif_removed_and_image_resized(self):
        self.upload(image=jpeg_with_exif())
        photo = Photo.objects.get()
        with default_storage.open(photo.image.name) as stored, Image.open(stored) as image:
            self.assertEqual(max(image.size), 2000)
            self.assertEqual(len(image.getexif()), 0)

    def test_fake_image_rejected(self):
        fake = SimpleUploadedFile("foto.jpg", b"<script>alert(1)</script>", content_type="image/jpeg")
        response = self.upload(image=fake)
        self.assertEqual(response.status_code, 400)
        self.assertEqual(Photo.objects.count(), 0)

    @override_settings(MAX_PHOTO_UPLOAD_BYTES=10)
    def test_too_large_rejected(self):
        response = self.upload()
        self.assertEqual(response.status_code, 400)
        self.assertIn("grande", response.json()["error"])

    def test_category_must_belong_to_phase(self):
        self.assertEqual(self.upload(category=cat.TRASEIRA_PLACA).status_code, 400)

    def test_multiple_photos_per_category(self):
        self.upload(category=cat.AVARIAS)
        self.upload(category=cat.AVARIAS)
        self.assertEqual(Photo.objects.filter(category=cat.AVARIAS).count(), 2)

    def test_cannot_upload_to_future_step(self):
        response = self.upload(phase=cat.PHASE_CHECKOUT, category=cat.FRENTE)
        self.assertEqual(response.status_code, 403)

    def test_cannot_upload_to_completed_attendance(self):
        type(self.att).objects.filter(pk=self.att.pk).update(status=wf.STATUS_CONCLUIDO)
        self.assertEqual(self.upload().status_code, 403)

    def test_target_of_other_attendance_rejected(self):
        from apps.checklist.services import ensure_initialized

        other = make_attendance(vehicle=make_vehicle(self.att.customer, plate="XYZ9K88"), mechanic=self.att.mechanic)
        ensure_initialized(other)
        type(self.att).objects.filter(pk=self.att.pk).update(current_step=wf.CHECKLIST)
        self.att.refresh_from_db()
        foreign = other.tire_inspections.first()
        response = self.upload(phase=cat.PHASE_TIRE, category=cat.GERAL, target=foreign.pk)
        self.assertEqual(response.status_code, 400)

    def test_requires_login(self):
        self.client.logout()
        self.assertEqual(self.upload().status_code, 302)

    def test_csrf_enforced(self):
        client = self.client_class(enforce_csrf_checks=True)
        client.force_login(self.user)
        response = client.post(reverse("photos:upload", args=[self.att.public_id]),
                               {"phase": cat.PHASE_CHECKIN, "category": cat.FRENTE, "image": tiny_png()})
        self.assertEqual(response.status_code, 403)


class AccessTests(PhotoBase):
    def _photo(self):
        self.upload()
        return Photo.objects.get()

    def test_file_requires_login(self):
        photo = self._photo()
        url = reverse("photos:file", args=[self.att.public_id, photo.pk])
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Cache-Control"], "private, no-store")
        response.close()
        self.client.logout()
        self.assertEqual(self.client.get(url).status_code, 302)

    def test_file_not_served_under_other_attendance(self):
        photo = self._photo()
        other = make_attendance(vehicle=make_vehicle(self.att.customer, plate="XYZ9K88"), mechanic=self.att.mechanic)
        self.assertEqual(self.client.get(reverse("photos:file", args=[other.public_id, photo.pk])).status_code, 404)

    def test_no_public_media_url(self):
        photo = self._photo()
        self.assertEqual(self.client.get(f"/media/{photo.image.name}").status_code, 404)
        self.assertEqual(self.client.get(f"/{photo.image.name}").status_code, 404)

    def test_delete_removes_file_after_commit(self):
        photo = self._photo()
        name = photo.image.name
        with self.captureOnCommitCallbacks(execute=True):
            response = self.client.post(reverse("photos:delete", args=[self.att.public_id, photo.pk]))
        self.assertEqual(response.status_code, 200)
        self.assertFalse(Photo.objects.exists())
        self.assertFalse(default_storage.exists(name))

    def test_delete_blocked_after_completion(self):
        photo = self._photo()
        type(self.att).objects.filter(pk=self.att.pk).update(status=wf.STATUS_CONCLUIDO)
        response = self.client.post(reverse("photos:delete", args=[self.att.public_id, photo.pk]))
        self.assertEqual(response.status_code, 403)
        self.assertTrue(Photo.objects.exists())


class CheckinStepTests(PhotoBase):
    def setUp(self):
        super().setUp()
        self.url = reverse("photos:checkin", args=[self.att.public_id])

    def test_page_shows_summary_and_slots_without_notes_field(self):
        response = self.client.get(self.url)
        self.assertContains(response, self.att.vehicle.plate_formatted)
        for label in ("Frente do veículo", "Lateral direita", "Lateral esquerda", "Traseira", "Painel"):
            self.assertContains(response, label)
        self.assertContains(response, 'capture="environment"')
        self.assertNotContains(response, "<textarea")

    def test_cannot_advance_without_five_photos(self):
        for category in cat.CHECKIN_REQUIRED[:4]:
            self.upload(category=category)
        response = self.client.post(self.url)
        self.assertContains(response, "Falta a foto")
        self.att.refresh_from_db()
        self.assertEqual(self.att.current_step, wf.CHECKIN)

    def test_optional_photos_do_not_replace_required(self):
        for category in cat.CHECKIN_OPTIONAL:
            self.upload(category=category)
        self.assertContains(self.client.post(self.url), "Falta a foto")

    def test_advances_with_required_photos(self):
        for category in cat.CHECKIN_REQUIRED:
            self.upload(category=category)
        response = self.client.post(self.url)
        self.assertEqual(response.status_code, 302)
        self.att.refresh_from_db()
        self.assertEqual(self.att.current_step, wf.CHECKLIST)

    def test_step_blocked_before_intake(self):
        att = make_attendance(vehicle=make_vehicle(self.att.customer, plate="XYZ9K88"), mechanic=self.att.mechanic)
        self.assertEqual(self.client.get(reverse("photos:checkin", args=[att.public_id])).status_code, 403)
        self.assertEqual(self.client.get(reverse("photos:checkout", args=[self.att.public_id])).status_code, 403)

    def test_cannot_jump_by_posting_future_step(self):
        self.client.post(reverse("photos:checkout", args=[self.att.public_id]))
        self.att.refresh_from_db()
        self.assertEqual(self.att.current_step, wf.CHECKIN)
