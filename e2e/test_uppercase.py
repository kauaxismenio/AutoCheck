"""Maiúsculas no navegador real: digitação, colagem, depois de salvar e na consulta."""
from apps.core.testing import default_workshop
from apps.attendances.models import Attendance
from apps.mechanics.models import Mechanic
from apps.workshop.models import WorkshopSettings

from .base import BrowserTestCase


class UppercaseBrowserTests(BrowserTestCase):
    def setUp(self):
        super().setUp()
        self.login()
        self.page.goto(self.url("/atendimentos/novo/"))

    def _paste(self, selector, text):
        """Colagem de verdade: passa pela área de transferência e pelo Ctrl+V."""
        self.page.context.grant_permissions(["clipboard-read", "clipboard-write"], origin=self.url("/").rstrip("/"))
        self.page.evaluate("text => navigator.clipboard.writeText(text)", text)
        self.page.focus(selector)
        self.page.keyboard.press("Control+V")

    def test_converts_while_typing(self):
        self.page.click("#id_full_name")
        self.page.keyboard.type("maria")
        self.assertEqual(self.page.input_value("#id_full_name"), "MARIA")
        self.page.keyboard.type(" joão ção")
        self.assertEqual(self.page.input_value("#id_full_name"), "MARIA JOÃO ÇÃO")

    def test_typing_in_the_middle_keeps_cursor_position(self):
        self.page.click("#id_brand")
        self.page.keyboard.type("fiat")
        for _ in range(2):
            self.page.keyboard.press("ArrowLeft")
        self.page.keyboard.type("xy")
        self.assertEqual(self.page.input_value("#id_brand"), "FIXYAT")

    def test_converts_after_paste(self):
        self._paste("#id_model", "argo 1.3 drive")
        self.assertEqual(self.page.input_value("#id_model"), "ARGO 1.3 DRIVE")
        self._paste("#id_color", "Vermelhão")
        self.assertEqual(self.page.input_value("#id_color"), "VERMELHÃO")
        self._paste("#id_plate", "abc-1d23")
        self.assertEqual(self.page.input_value("#id_plate"), "ABC1D23")

    def test_email_is_not_converted(self):
        self.page.click("#id_email")
        self.page.keyboard.type("Maria.Souza@empresa.com.br")
        self.assertEqual(self.page.input_value("#id_email"), "Maria.Souza@empresa.com.br")

    def test_saved_and_consulted_in_upper(self):
        self.page.select_option("#id_attendant", label="ANA")
        self.page.fill("#id_full_name", "maria conceição")
        self.page.fill("#id_cpf", "52998224725")
        self.page.fill("#id_phone", "81990001712")
        self.page.fill("#id_email", "Maria.Souza@empresa.com.br")
        self.page.fill("#id_plate", "abc1d23")
        self.page.fill("#id_brand", "fiat")
        self.page.fill("#id_model", "argo")
        self.page.fill("#id_color", "branca")
        self.page.fill("#id_mileage", "45210")
        self.page.click("[data-mechanic-toggle]")
        self.page.click("#id_new_mechanic_name")
        self.page.keyboard.type("josé carlos")
        self.assertEqual(self.page.input_value("#id_new_mechanic_name"), "JOSÉ CARLOS")
        self.page.select_option("#id_origin", "instagram")
        self.submit()
        self.assertIn("/check-in/", self.page.url, self.page.inner_text("main")[:600])

        attendance = Attendance.objects.get()
        self.assertEqual(attendance.customer.full_name, "MARIA CONCEIÇÃO")
        self.assertEqual(attendance.customer_email, "Maria.Souza@empresa.com.br")
        self.assertEqual(attendance.vehicle.brand, "FIAT")
        self.assertTrue(Mechanic.objects.filter(name="JOSÉ CARLOS").exists())

        self.page.goto(self.url(f"/clientes/{attendance.customer_id}/"))
        self.assertIn("MARIA CONCEIÇÃO", self.page.inner_text("main"))
        self.page.goto(self.url(f"/veiculos/{attendance.vehicle_id}/"))
        self.assertIn("FIAT", self.page.inner_text("main"))
        self.page.goto(self.url("/atendimentos/"))
        self.assertIn("MARIA CONCEIÇÃO", self.page.inner_text("main"))
        self.shot("uppercase-list")

    def test_settings_name_upper_and_email_kept(self):
        self.page.goto(self.url("/configuracoes/"))
        self.page.fill("#id_name", "")
        self.page.click("#id_name")
        self.page.keyboard.type("oficina exemplo ltda")
        self.assertEqual(self.page.input_value("#id_name"), "OFICINA EXEMPLO LTDA")
        self.page.fill("#id_report_email", "Dono@oficinaboa.com.br")
        self.submit("form.form-grid button[type=submit]")
        workshop = default_workshop()
        self.assertEqual(workshop.name, "OFICINA EXEMPLO LTDA")
        self.assertEqual(workshop.report_email, "Dono@oficinaboa.com.br")
        self.assertEqual(self.page.input_value("#id_name"), "OFICINA EXEMPLO LTDA")
