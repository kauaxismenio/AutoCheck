"""Funcionário no navegador real: cadastro em Configurações e escolha ao iniciar o atendimento."""
from apps.attendances.models import Attendance
from apps.employees.models import Employee

from .base import PHONE, BrowserTestCase
from .helpers import open_intake


class EmployeeBrowserTests(BrowserTestCase):
    def setUp(self):
        super().setUp()
        self.login()

    def test_add_in_settings_then_select_at_attendance_start(self):
        self.page.goto(self.url("/configuracoes/"))
        self.submit(self.page.get_by_role("link", name="Gerenciar vendedores/atendentes"))
        self.submit(self.page.get_by_role("link", name="Novo vendedor/atendente"))
        self.page.click("#id_name")
        self.page.keyboard.type("bia lima")
        self.assertEqual(self.page.input_value("#id_name"), "BIA LIMA")
        self.submit("form.form-grid button[type=submit]")
        self.assertIn("BIA LIMA", self.page.inner_text("main"))
        self.shot("employees-list")

        open_intake(self, attendant="BIA LIMA")
        attendance = Attendance.objects.get()
        self.assertEqual(attendance.attendant, Employee.objects.get(name="BIA LIMA"))
        self.assertEqual(attendance.created_by, self.admin)

    def test_field_is_first_on_the_page_and_required(self):
        self.page.goto(self.url("/atendimentos/novo/"))
        positions = self.page.evaluate("""() => ['#id_attendant', '#id_full_name']
            .map(s => document.querySelector(s).getBoundingClientRect().top)""")
        self.assertLess(positions[0], positions[1])
        self.shot("intake-attendant")
        self.submit()
        self.assertIn("Selecione o vendedor/atendente", self.page.inner_text("main"))
        self.assertEqual(Attendance.objects.count(), 0)

    def test_empty_register_points_to_settings(self):
        Employee.objects.all().delete()
        self.page.goto(self.url("/atendimentos/novo/"))
        self.assertIn("Nenhum vendedor/atendente cadastrado", self.page.inner_text("main"))
        self.submit(self.page.get_by_role("link", name="Cadastrar vendedor/atendente"))
        self.assertIn("/funcionarios/novo/", self.page.url)

    def test_register_fits_phone(self):
        page = self.new_page(PHONE)
        self.login(page)
        page.goto(self.url("/funcionarios/"))
        self.assertIn("ANA", page.inner_text("main"))
        self.assertFalse(page.evaluate("document.documentElement.scrollWidth > document.documentElement.clientWidth"))
        page.context.close()
