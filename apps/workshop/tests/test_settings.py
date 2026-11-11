from django.core.files.storage import default_storage
from django.test import TestCase, override_settings
from django.urls import reverse

from apps.core.testing import default_workshop, make_user, tiny_png
from apps.workshop.models import WorkshopSettings


class SettingsTests(TestCase):
    def setUp(self):
        self.admin = make_user("chefe")
        self.url = reverse("workshop:settings")

    def _payload(self, **extra):
        data = {"name": "Oficina Boa", "cnpj": "12.ABC.345/01DE-35", "phone": "(81) 3456-7890",
                "address": "Rua A, 10", "report_email": "dono@oficinaboa.com.br"}
        data.update(extra)
        return data

    def test_workshop_account_can_open(self):
        self.client.force_login(make_user("func"))
        self.assertEqual(self.client.get(self.url).status_code, 200)

    def test_save_normalizes_and_audits(self):
        self.client.force_login(self.admin)
        response = self.client.post(self.url, self._payload())
        self.assertRedirects(response, self.url)
        workshop = default_workshop()
        self.assertEqual(workshop.cnpj, "12ABC34501DE35")
        self.assertEqual(workshop.phone, "8134567890")
        self.assertEqual(workshop.report_email, "dono@oficinaboa.com.br")

    def test_invalid_cnpj_rejected(self):
        self.client.force_login(self.admin)
        response = self.client.post(self.url, self._payload(cnpj="12.ABC.345/01DE-34"))
        self.assertContains(response, "CNPJ inválido")

    def test_logo_is_private_and_replaced(self):
        self.client.force_login(self.admin)
        self.client.post(self.url, {**self._payload(), "logo": tiny_png("logo.png")})
        workshop = default_workshop()
        first = workshop.logo.name
        self.assertTrue(first)
        response = self.client.get(reverse("workshop:logo"))
        self.assertEqual(response.status_code, 200)
        response.close()  # no Windows, arquivo aberto não pode ser apagado

        self.client.logout()
        self.assertEqual(self.client.get(reverse("workshop:logo")).status_code, 302)

        self.client.force_login(self.admin)
        with self.captureOnCommitCallbacks(execute=True):
            self.client.post(self.url, {**self._payload(), "logo": tiny_png("novo.png")})
        workshop.refresh_from_db()
        self.assertNotEqual(workshop.logo.name, first)
        self.assertFalse(default_storage.exists(first))

    def test_fake_image_rejected(self):
        from django.core.files.uploadedfile import SimpleUploadedFile

        self.client.force_login(self.admin)
        fake = SimpleUploadedFile("logo.png", b"nao sou imagem", content_type="image/png")
        response = self.client.post(self.url, {**self._payload(), "logo": fake})
        self.assertEqual(response.status_code, 200)
        self.assertFalse(default_workshop().logo)

    @override_settings(EMAIL_HOST_PASSWORD="segredo-que-nao-pode-vazar")
    def test_smtp_password_is_never_rendered(self):
        self.client.force_login(self.admin)
        self.assertNotContains(self.client.get(self.url), "segredo-que-nao-pode-vazar")
