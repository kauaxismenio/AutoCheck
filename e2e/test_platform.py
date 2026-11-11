"""Fluxo real no navegador: o proprietário cria a oficina, que entra por e-mail e não vê a outra."""
from apps.core.testing import PASSWORD, make_customer, make_owner, make_workshop

from .base import PHONE, BrowserTestCase


class PlatformBrowserTests(BrowserTestCase):
    def setUp(self):
        super().setUp()
        make_owner("proprietario")

    def _sign_in(self, page, username, password):
        page.goto(self.url("/conta/entrar/"))
        page.fill("#id_username", username)
        page.fill("#id_password", password)
        self.submit("button[type=submit]", page=page)

    def test_owner_creates_workshop_and_workshop_logs_in_isolated(self):
        make_customer(workshop=make_workshop("Oficina Rival"), full_name="Cliente Rival")

        self._sign_in(self.page, "proprietario", PASSWORD)
        self.assertIn("/plataforma/", self.page.url)
        self.assertEqual(self.page.locator(".nav-link").count(), 1)
        self.submit(self.page.get_by_role("link", name="+ Nova oficina"))
        self.page.click("#id_name")
        self.page.keyboard.type("oficina modelo centro")
        self.assertEqual(self.page.input_value("#id_name"), "OFICINA MODELO CENTRO")
        self.page.fill("#id_login_email", "contato@oficinamodelo.example.com")
        self.shot("platform-new-workshop")
        self.submit("form.form-grid button[type=submit]")
        password = self.page.inner_text("[data-generated-password]")
        self.shot("platform-credentials")
        self.submit(self.page.get_by_role("link", name="Voltar às oficinas"))
        self.assertIn("OFICINA MODELO CENTRO", self.page.inner_text("main"))
        self.shot("platform-list")

        workshop_page = self.browser.new_context(locale="pt-BR").new_page()
        self._sign_in(workshop_page, "Contato@OficinaModelo.example.com", password)
        self.assertEqual(workshop_page.url, self.url("/"))
        self.assertIn("OFICINA MODELO CENTRO", workshop_page.inner_text("main"))
        workshop_page.goto(self.url("/clientes/"))
        self.assertNotIn("CLIENTE RIVAL", workshop_page.inner_text("main"))
        self.assertEqual(workshop_page.goto(self.url("/plataforma/")).status, 403)
        self.assertEqual(workshop_page.goto(self.url("/configuracoes/")).status, 200)
        self.shot("workshop-settings", page=workshop_page)
        workshop_page.context.close()

    def test_platform_list_fits_phone(self):
        page = self.new_page(PHONE)
        self._sign_in(page, "proprietario", PASSWORD)
        self.assertFalse(page.evaluate("document.documentElement.scrollWidth > document.documentElement.clientWidth"))
        page.context.close()
