from apps.attendances import workflow as wf
from apps.attendances.models import Attendance
from apps.photos.models import Photo

from .base import PHONE, BrowserTestCase
from .helpers import open_intake, upload_all_required


class CheckinTests(BrowserTestCase):
    def setUp(self):
        super().setUp()
        self.login()
        open_intake(self)

    def test_blocks_then_advances_with_preview_and_delete(self):
        self.page.click("button.btn--lg")
        self.page.wait_for_selector(".errors-box")
        self.assertIn("Falta a foto", self.page.inner_text(".errors-box"))
        self.assertEqual(Attendance.objects.get().current_step, wf.CHECKIN)

        upload_all_required(self)
        first = self.page.locator("[data-photo-slot][data-required]").first
        self.assertEqual(first.locator("[data-photo-badge]").inner_text(), "Enviada")
        natural_width = first.locator("img").evaluate("img => img.complete ? img.naturalWidth : -1")
        self.assertNotEqual(natural_width, 0, "A pré-visualização precisa carregar")
        self.shot("checkin-photos")

        self.page.on("dialog", lambda dialog: dialog.accept())
        first.locator("[data-photo-remove]").click()
        first.locator("[data-photo-thumb]").wait_for(state="detached")
        self.assertEqual(first.locator("[data-photo-badge]").inner_text(), "Obrigatória")
        self.assertEqual(Photo.objects.count(), 4)

        first.locator("[data-photo-input]").set_input_files(self.temp_image())
        first.locator("[data-photo-thumb]").first.wait_for()
        self.submit()
        self.assertEqual(Attendance.objects.get().current_step, wf.CHECKLIST)

    def test_invalid_file_shows_error(self):
        import tempfile

        handle = tempfile.NamedTemporaryFile(suffix=".jpg", delete=False)
        handle.write(b"nao sou imagem")
        handle.close()
        slot = self.page.locator("[data-photo-slot]").first
        slot.locator("[data-photo-input]").set_input_files(handle.name)
        slot.locator(".photo-status.is-error").wait_for()
        self.assertIn("imagem", slot.locator(".photo-status").inner_text())

    def test_phone_layout(self):
        page = self.new_page(PHONE)
        self.login(page)
        page.goto(self.page.url)
        self.assertLessEqual(page.evaluate("document.documentElement.scrollWidth"), 390)
        self.shot("checkin-phone", page)
        page.context.close()
