"""Link de avaliação nas configurações e geração do QR Code."""
import io
from unittest import skipUnless

from django.test import TestCase
from django.urls import reverse
from PIL import Image

from apps.core.models import AuditLog
from apps.core.testing import default_workshop, make_user
from apps.workshop.models import WorkshopSettings
from apps.workshop.review_qr import build_png

try:
    import cv2
    import numpy
except ImportError:  # dependência só de desenvolvimento
    cv2 = None

LINK = "https://g.page/r/CaBcDeFgHiJkEBM/review"


def read_qr(png_bytes):
    """Lê a imagem com um decodificador independente, como faria a câmera de um celular."""
    image = cv2.imdecode(numpy.frombuffer(png_bytes, dtype=numpy.uint8), cv2.IMREAD_COLOR)
    return cv2.QRCodeDetector().detectAndDecode(image)[0]


class QrGenerationTests(TestCase):
    def test_png_is_valid_and_large_enough_to_print(self):
        image = Image.open(io.BytesIO(build_png(LINK)))
        self.assertEqual(image.format, "PNG")
        self.assertEqual(image.width, image.height)
        self.assertGreaterEqual(image.width, 400)

    @skipUnless(cv2, "opencv não instalado (requirements/development.txt)")
    def test_generated_code_decodes_to_the_exact_link(self):
        for link in (LINK, "https://search.google.com/local/writereview?placeid=ChIJN1t_tDeuEmsRUsoyG83frY4",
                     "https://www.google.com/maps/place/x?" + "a" * 300):
            self.assertEqual(read_qr(build_png(link)), link)


class ReviewLinkViewTests(TestCase):
    def setUp(self):
        self.admin = make_user("chefe")
        self.employee = make_user("func")
        self.settings_url = reverse("workshop:settings")
        self.save_url = reverse("workshop:review_link")
        self.qr_url = reverse("workshop:review_qr")
        self.download_url = reverse("workshop:review_qr_download")
        self.client.force_login(self.admin)

    def _set_link(self, link=LINK):
        WorkshopSettings.objects.update_or_create(pk=default_workshop().pk, defaults={"google_review_url": link})

    def test_field_shows_on_settings_without_preview_until_saved(self):
        response = self.client.get(self.settings_url)
        self.assertContains(response, "LINK DE AVALIAÇÃO DA OFICINA NO GOOGLE")
        self.assertNotContains(response, self.qr_url)
        self.assertEqual(self.client.get(self.qr_url).status_code, 404)
        self.assertEqual(self.client.get(self.download_url).status_code, 404)

    def test_save_generates_preview_and_download(self):
        response = self.client.post(self.save_url, {"google_review_url": LINK}, follow=True)
        self.assertRedirects(response, self.settings_url)
        self.assertContains(response, "Link de avaliação salvo.")
        self.assertContains(response, self.qr_url)
        self.assertContains(response, self.download_url)
        self.assertContains(response, LINK)
        self.assertTrue(AuditLog.objects.filter(action="workshop.review_link_updated").exists())

        preview = self.client.get(self.qr_url)
        self.assertEqual(preview["Content-Type"], "image/png")
        self.assertNotIn("Content-Disposition", preview)
        self.assertIn("no-store", preview["Cache-Control"])

        download = self.client.get(self.download_url)
        self.assertEqual(download["Content-Type"], "image/png")
        self.assertEqual(download["Content-Disposition"], 'attachment; filename="qrcode-avaliacao-google.png"')
        self.assertEqual(Image.open(io.BytesIO(download.content)).format, "PNG")

    @skipUnless(cv2, "opencv não instalado (requirements/development.txt)")
    def test_changing_the_link_changes_the_code(self):
        self._set_link()
        self.assertEqual(read_qr(self.client.get(self.qr_url).content), LINK)
        other = "https://g.page/r/OutroCodigo/review"
        self.client.post(self.save_url, {"google_review_url": other})
        self.assertEqual(read_qr(self.client.get(self.qr_url).content), other)

    def test_invalid_links_are_refused_and_keep_the_saved_one(self):
        self._set_link()
        for bad in ("http://g.page/r/x/review", "https://example.com/review", "https://google.com.golpe.com/x",
                    "https://google.com@golpe.com/x", "javascript:alert(1)", "https://g.page/"):
            response = self.client.post(self.save_url, {"google_review_url": bad})
            self.assertEqual(response.status_code, 200, bad)
            self.assertContains(response, "field__error")
            self.assertEqual(default_workshop().google_review_url, LINK, bad)

    def test_blank_link_removes_the_code(self):
        self._set_link()
        response = self.client.post(self.save_url, {"google_review_url": ""}, follow=True)
        self.assertContains(response, "Link de avaliação removido.")
        self.assertEqual(self.client.get(self.qr_url).status_code, 404)

    def test_platform_owner_does_not_reach_workshop_settings(self):
        from apps.core.testing import make_owner

        self.client.force_login(make_owner())
        response = self.client.post(self.save_url, {"google_review_url": "https://g.page/r/outro/review"})
        self.assertRedirects(response, reverse("platform_admin:list"))

    def test_get_does_not_change_the_link(self):
        self.assertEqual(self.client.get(self.save_url).status_code, 405)

    def test_saving_the_link_preserves_existing_settings(self):
        WorkshopSettings.objects.update_or_create(pk=default_workshop().pk, defaults={
            "name": "Oficina Boa", "report_email": "dono@oficinaboa.com.br", "address": "Rua A, 10",
            "phone": "8134567890", "cnpj": "12ABC34501DE35",
        })
        self.client.post(self.save_url, {"google_review_url": LINK})
        workshop = default_workshop()
        self.assertEqual((workshop.name, workshop.report_email, workshop.address, workshop.phone, workshop.cnpj),
                         ("OFICINA BOA", "dono@oficinaboa.com.br", "Rua A, 10", "8134567890", "12ABC34501DE35"))
        self.assertEqual(workshop.google_review_url, LINK)

    def test_saving_workshop_data_preserves_the_link(self):
        self._set_link()
        response = self.client.post(self.settings_url, {
            "name": "Oficina Nova", "cnpj": "", "phone": "", "address": "", "report_email": "novo@oficinaboa.com.br",
        })
        self.assertRedirects(response, self.settings_url)
        workshop = default_workshop()
        self.assertEqual(workshop.report_email, "novo@oficinaboa.com.br")
        self.assertEqual(workshop.google_review_url, LINK)

    def test_existing_sections_remain_and_there_is_no_branch_management(self):
        self._set_link()
        response = self.client.get(self.settings_url)
        for text in ("Dados da oficina", "E-mail do responsável", "Serviço de e-mail", "Enviar e-mail de teste ao responsável",
                     "Alterar senha", "Gerenciar vendedores/atendentes", "Gerenciar mecânicos", "BrasilAPI"):
            self.assertContains(response, text)
        content = response.content.decode().lower()
        for forbidden in ("filial", "filiais", "unidade"):
            self.assertNotIn(forbidden, content)
        self.assertEqual(content.count('name="report_email"'), 1)
