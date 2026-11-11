"""Link, QR Code e mecânico novo em navegador real: imagem carregada, download e assinatura preservada."""
from apps.core.testing import default_workshop
from apps.attendances.models import Attendance
from apps.mechanics.models import Mechanic
from apps.signatures.models import AttendanceSignature
from apps.workshop.models import WorkshopSettings
from apps.workshop.tests.test_review_link import cv2, read_qr

from .base import PHONE, TABLET, BrowserTestCase
from .helpers import advance_to_review, draw_signature, open_intake

LINK = "https://g.page/r/CaBcDeFgHiJkEBM/review"


class ReviewQrBrowserTests(BrowserTestCase):
    def setUp(self):
        super().setUp()
        self.login()

    def _no_horizontal_scroll(self, page):
        self.assertFalse(page.evaluate("document.documentElement.scrollWidth > document.documentElement.clientWidth"))

    def _image_ok(self, page, selector=".qr-image"):
        image = page.locator(selector)
        image.wait_for()
        image.scroll_into_view_if_needed()
        page.wait_for_function("s => { const i = document.querySelector(s); return i.complete && i.naturalWidth > 0; }", arg=selector)
        self.assertGreater(image.evaluate("i => i.naturalWidth"), 400)

    def test_settings_save_preview_and_download(self):
        self.page.goto(self.url("/configuracoes/"))
        heights = self.page.evaluate("""() => [document.querySelector('#id_google_review_url'), document.querySelector('#id_name')]
            .map(field => field.getBoundingClientRect().height)""")
        self.assertEqual(heights[0], heights[1], "o campo do link segue o padrão dos demais")
        self.page.fill("#id_google_review_url", "http://site-qualquer.com/x")
        self.submit("#avaliacao-google button[type=submit]")
        self.assertIn("link oficial", self.page.inner_text("#avaliacao-google"))
        self.assertEqual(default_workshop().google_review_url, "")

        self.page.fill("#id_google_review_url", LINK)
        self.submit("#avaliacao-google button[type=submit]")
        self.assertEqual(default_workshop().google_review_url, LINK)
        self._image_ok(self.page)
        self.shot("settings-review-qr")

        with self.page.expect_download() as info:
            self.page.click("text=Baixar QR Code (PNG)")
        download = info.value
        self.assertEqual(download.suggested_filename, "qrcode-avaliacao-google.png")
        with open(download.path(), "rb") as stream:
            data = stream.read()
        self.assertEqual(data[:8], b"\x89PNG\r\n\x1a\n")
        if cv2:
            self.assertEqual(read_qr(data), LINK)

        for options in (PHONE, TABLET):
            page = self.new_page(options)
            self.login(page)
            page.goto(self.url("/configuracoes/"))
            self._image_ok(page)
            self._no_horizontal_scroll(page)
            page.context.close()

    def test_review_action_keeps_drawn_signature_and_finishes(self):
        WorkshopSettings.objects.update_or_create(pk=default_workshop().pk, defaults={"google_review_url": LINK})
        open_intake(self)
        advance_to_review(self)
        self._image_ok(self.page)
        self.assertEqual(self.page.locator("input[name=review_requested]").count(), 0)
        self.shot("review-qr-section")

        # A barra superior é fixa: partindo do topo, a área de assinatura não fica escondida atrás dela.
        self.page.evaluate("window.scrollTo(0, 0)")
        draw_signature(self.page)
        before = self.page.evaluate("document.querySelector('[data-signature-canvas]').toDataURL()")
        blank = self.page.evaluate("""() => {
            const source = document.querySelector('[data-signature-canvas]');
            const empty = document.createElement('canvas');
            empty.width = source.width; empty.height = source.height;
            return empty.toDataURL();
        }""")
        self.assertNotEqual(before, blank, "a assinatura precisa ter sido desenhada de verdade")
        self.page.click("text=QR CODE APRESENTADO AO CLIENTE")
        self.page.locator("[data-review-qr-done]").wait_for(state="visible")
        self.assertIn("Apresentado em", self.page.inner_text("[data-review-qr-done]"))
        self.assertTrue(Attendance.objects.get().review_qr_presented_at)
        self.assertEqual(before, self.page.evaluate("document.querySelector('[data-signature-canvas]').toDataURL()"),
                         "registrar o QR Code não pode apagar a assinatura")
        self.shot("review-qr-presented")

        self.page.click("[data-review-qr-done] button")
        self.page.locator("[data-review-qr-pending]").wait_for(state="visible")
        self.assertIsNone(Attendance.objects.get().review_qr_presented_at)
        self.page.click("text=QR CODE APRESENTADO AO CLIENTE")
        self.page.locator("[data-review-qr-done]").wait_for(state="visible")

        self.submit("[data-step-submit]")
        self.assertIn("/resumo/", self.page.url, self.page.inner_text(".errors-box") if self.page.locator(".errors-box").count() else "sem caixa de erro")
        self.assertIn("QR Code de avaliação apresentado ao cliente", self.page.inner_text("main"))
        self.assertFalse(AttendanceSignature.objects.get().refused)

    def test_review_section_fits_small_screens(self):
        WorkshopSettings.objects.update_or_create(pk=default_workshop().pk, defaults={"google_review_url": LINK})
        open_intake(self)
        advance_to_review(self)
        review_url = self.page.url
        for options in (PHONE, TABLET):
            page = self.new_page(options)
            self.login(page)
            page.goto(review_url)
            self._image_ok(page)
            self._no_horizontal_scroll(page)
            fits = page.evaluate("""() => {
                const box = document.querySelector('.review-qr').getBoundingClientRect();
                const button = document.querySelector('[data-review-qr-pending] button').getBoundingClientRect();
                return button.left >= box.left && button.right <= box.right;
            }""")
            self.assertTrue(fits, "o botão precisa caber dentro da seção")
            if options is PHONE:
                self.shot("review-qr-phone", page=page)
            page.context.close()


class IntakeNewMechanicBrowserTests(BrowserTestCase):
    def setUp(self):
        super().setUp()
        self.login()

    def _fill(self):
        self.page.goto(self.url("/atendimentos/novo/"))
        self.page.select_option("#id_attendant", label="ANA")
        self.page.fill("#id_full_name", "Maria Souza")
        self.page.fill("#id_cpf", "52998224725")
        self.page.fill("#id_phone", "81990001712")
        self.page.fill("#id_email", "cliente@empresa.com.br")
        self.page.fill("#id_plate", "abc1d23")
        self.page.fill("#id_brand", "Fiat")
        self.page.fill("#id_model", "Argo")
        self.page.fill("#id_mileage", "45210")
        self.page.select_option("#id_origin", "instagram")

    def test_adds_mechanic_from_the_attendance(self):
        self._fill()
        self.assertFalse(self.page.is_visible("#id_new_mechanic_name"))
        self.page.click("[data-mechanic-toggle]")
        self.assertTrue(self.page.is_visible("#id_new_mechanic_name"))
        self.shot("intake-new-mechanic")
        self.page.fill("#id_new_mechanic_name", "Carlos Souza")
        self.submit()
        self.assertIn("/check-in/", self.page.url, self.page.inner_text("main")[:600])
        attendance = Attendance.objects.get()
        self.assertEqual(attendance.mechanic, Mechanic.objects.get(name="CARLOS SOUZA"))
        self.assertEqual(attendance.created_by, self.admin)

    def test_back_to_list_discards_typed_name(self):
        self._fill()
        self.page.click("[data-mechanic-toggle]")
        self.page.fill("#id_new_mechanic_name", "Desisti")
        self.page.click("[data-mechanic-toggle]")
        self.assertFalse(self.page.is_visible("#id_new_mechanic_name"))
        self.page.select_option("#id_mechanic", label="RUI")
        self.submit()
        self.assertEqual(Attendance.objects.get().mechanic, self.mechanic)
        self.assertFalse(Mechanic.objects.filter(name="DESISTI").exists())

    def test_empty_register_opens_name_field_directly(self):
        Mechanic.objects.all().delete()
        self._fill()
        self.assertTrue(self.page.is_visible("#id_new_mechanic_name"))
        self.assertFalse(self.page.is_visible("#id_mechanic"))
