from apps.attendances.models import Attendance
from apps.core.testing import make_customer

from .base import DESKTOP, PHONE, TABLET, BrowserTestCase


class ShellTests(BrowserTestCase):
    def test_login_error_and_dashboard(self):
        self.page.goto(self.url("/"))
        self.assertIn("/conta/entrar/", self.page.url)
        self.page.fill("#id_username", "chefe")
        self.page.fill("#id_password", "errada")
        self.page.click("button[type=submit]")
        self.assertIn("incorretos", self.page.inner_text(".login__card"))
        self.shot("login")
        self.login()
        self.assertIn("Atendimentos realizados", self.page.inner_text(".stats"))
        self.shot("dashboard-desktop")

    def test_desktop_menu_starts_open_and_keeps_preference(self):
        self.login()
        state = lambda: self.page.get_attribute("html", "data-sidebar")  # noqa: E731
        self.assertEqual(state(), "open")
        self.page.click("[data-sidebar-toggle]")
        self.assertEqual(state(), "closed")
        self.page.click("[data-sidebar-toggle]")
        self.assertEqual(state(), "open")
        self.page.click("[data-sidebar-toggle]")
        self.page.goto(self.url("/clientes/"))
        self.assertEqual(state(), "closed", "A preferência deve valer na próxima página")

    def test_phone_and_tablet_menu_start_closed_and_do_not_reopen(self):
        for options, name in ((PHONE, "phone"), (TABLET, "tablet")):
            page = self.new_page(options)
            self.login(page)
            state = lambda: page.get_attribute("html", "data-sidebar")  # noqa: B023,E731
            self.assertEqual(state(), "closed", name)
            page.click("[data-sidebar-toggle]")
            self.assertEqual(state(), "open", name)
            page.wait_for_timeout(300)  # fim da animação do menu
            self.assertEqual(page.eval_on_selector("#sidebar", "e => e.getBoundingClientRect().left"), 0, name)
            self.shot(f"menu-{name}", page)
            self.submit(".nav-link[href='/clientes/']", page=page)
            self.assertEqual(state(), "closed", f"{name}: não pode reabrir ao navegar")
            width = page.evaluate("document.documentElement.scrollWidth")
            self.assertLessEqual(width, options["viewport"]["width"], f"{name}: sem rolagem horizontal")
            page.context.close()


class MaskTests(BrowserTestCase):
    def setUp(self):
        super().setUp()
        self.login()
        self.page.goto(self.url("/atendimentos/novo/"))

    def _type(self, selector, text):
        self.page.fill(selector, "")
        self.page.locator(selector).press_sequentially(text)
        return self.page.input_value(selector)

    def _paste(self, selector, text):
        # Simula a colagem real: o valor entra de uma vez e dispara o evento "input".
        self.page.fill(selector, text)
        return self.page.input_value(selector)

    def test_cpf_typing_and_paste(self):
        self.assertEqual(self._type("#id_cpf", "52998224725"), "529.982.247-25")
        self.assertEqual(self._paste("#id_cpf", "529 982 247 25 abc"), "529.982.247-25")
        self.assertEqual(self._type("#id_cpf", "abc"), "")

    def test_cnpj_numeric_and_alphanumeric(self):
        self.page.click('[data-person-card="pj"]')
        self.assertEqual(self._type("#id_cnpj", "12abc34501de35"), "12.ABC.345/01DE-35")
        self.assertEqual(self._paste("#id_cnpj", "11.222.333/0001-81"), "11.222.333/0001-81")
        # Letras não são aceitas nos dígitos verificadores.
        self.assertEqual(self._type("#id_cnpj", "12ABC34501DEXY"), "12.ABC.345/01DE")

    def test_phone_mobile_and_landline(self):
        self.assertEqual(self._type("#id_phone", "81990001712"), "(81) 9 9000-1712")
        self.assertEqual(self._type("#id_phone", "8134567890"), "(81) 3456-7890")
        self.assertEqual(self._paste("#id_phone", "+55 81 99000-1712"), "(81) 9 9000-1712")
        self.assertEqual(self._type("#id_phone", "abc"), "")

    def test_plate_both_formats(self):
        self.assertEqual(self._type("#id_plate", "abc1234"), "ABC-1234")
        self.assertEqual(self._type("#id_plate", "abc1d23"), "ABC1D23")
        self.assertEqual(self._paste("#id_plate", "abc-1d23"), "ABC1D23")

    def test_mileage_only_digits(self):
        self.assertEqual(self._type("#id_mileage", "12a3b4"), "1234")

    def test_invalid_document_hint(self):
        self._type("#id_cpf", "11111111111")
        self.assertIn("inválido", self.page.inner_text(".js-cpf [data-field-hint]"))


class CardTests(BrowserTestCase):
    def setUp(self):
        super().setUp()
        self.login()
        self.page.goto(self.url("/atendimentos/novo/"))

    def test_cards_switch_fields_and_keep_values(self):
        pf, pj = self.page.locator("#id_full_name"), self.page.locator("#id_legal_name")
        self.assertTrue(pf.is_visible())
        self.assertFalse(pj.is_visible())
        self.page.fill("#id_full_name", "Maria Souza")
        self.page.click('[data-person-card="pj"]')
        self.assertFalse(pf.is_visible())
        self.assertTrue(pj.is_visible())
        self.assertEqual(self.page.get_attribute('[data-person-card="pj"]', "aria-pressed"), "true")
        self.assertEqual(self.page.get_attribute('[data-person-card="pf"]', "aria-pressed"), "false")
        self.page.fill("#id_legal_name", "Oficina X")
        self.page.click('[data-person-card="ambos"]')
        self.assertTrue(pf.is_visible() and pj.is_visible())
        self.assertEqual(self.page.input_value("#id_full_name"), "MARIA SOUZA")
        self.assertEqual(self.page.input_value("#id_legal_name"), "OFICINA X")
        self.shot("intake-ambos")

    def test_active_card_is_orange_with_a_single_mark(self):
        self.page.click('[data-person-card="pj"]')
        visible_marks = self.page.locator(".choice-card__mark:visible")
        self.assertEqual(visible_marks.count(), 1)
        self.page.wait_for_timeout(300)  # fim da transição de cor
        color = self.page.eval_on_selector('[data-person-card="pj"]', "e => getComputedStyle(e).borderTopColor")
        self.assertEqual(color, "rgb(242, 140, 24)")

    def test_opt_outs_hide_only_their_field_and_keep_value(self):
        self.page.fill("#id_cpf", "52998224725")
        self.page.check("#id_cpf_not_informed")
        self.assertFalse(self.page.locator("#id_cpf").is_visible())
        self.page.uncheck("#id_cpf_not_informed")
        self.assertEqual(self.page.input_value("#id_cpf"), "529.982.247-25")

        self.page.click('[data-person-card="pj"]')
        self.page.check("#id_cnpj_not_informed")
        self.assertFalse(self.page.locator("#id_cnpj").is_visible())
        self.assertTrue(self.page.locator("#id_legal_name").is_visible())

        self.page.check("#id_email_opt_out")
        self.assertFalse(self.page.locator("#id_email").is_visible())
        self.page.uncheck("#id_email_opt_out")
        self.assertTrue(self.page.locator("#id_email").is_visible())


class IntakeFlowTests(BrowserTestCase):
    def setUp(self):
        super().setUp()
        self.login()
        self.page.goto(self.url("/atendimentos/novo/"))

    def _fill_common(self):
        self.page.select_option("#id_attendant", label="ANA")
        self.page.fill("#id_phone", "81990001712")
        self.page.fill("#id_plate", "abc1d23")
        self.page.fill("#id_brand", "Fiat")
        self.page.fill("#id_model", "Argo")
        self.page.fill("#id_mileage", "45210")
        self.page.select_option("#id_mechanic", label="RUI")
        self.page.select_option("#id_origin", "instagram")

    def test_hidden_invalid_field_does_not_block_submit(self):
        self.page.click('[data-person-card="pj"]')
        self.page.fill("#id_cnpj", "11111")
        self.page.click('[data-person-card="pf"]')
        self.page.fill("#id_full_name", "Maria Souza")
        self.page.fill("#id_cpf", "52998224725")
        self._fill_common()
        self.submit()
        att = Attendance.objects.get()
        self.assertEqual(att.customer.full_name, "MARIA SOUZA")
        self.assertIsNone(att.customer.cnpj)

    def test_server_error_keeps_card_and_values(self):
        self.page.click('[data-person-card="ambos"]')
        self.page.fill("#id_full_name", "Maria")
        self.page.click("button.btn--lg")
        self.page.wait_for_selector(".field__error")
        self.assertEqual(self.page.get_attribute('[data-person-card="ambos"]', "aria-pressed"), "true")
        self.assertEqual(self.page.input_value("#id_full_name"), "MARIA")

    def test_real_brasilapi_fills_company_and_stays_editable(self):
        """Consulta REAL à BrasilAPI, com CNPJ público do Banco do Brasil."""
        self.page.click('[data-person-card="pj"]')
        self.page.locator("#id_cnpj").press_sequentially("00000000000191")
        self.wait_true("document.querySelector('#id_legal_name').value !== ''")
        self.assertIn("BANCO DO BRASIL", self.page.input_value("#id_legal_name"))
        self.page.fill("#id_legal_name", "Editado à mão")
        self.assertEqual(self.page.input_value("#id_legal_name"), "EDITADO À MÃO")
        self.shot("intake-cnpj")

    def test_cpf_with_cnpj_history_never_fills_company_fields(self):
        """No modo Ambos, o CPF só traz dados pessoais. A empresa vem da consulta REAL do CNPJ digitado."""
        make_customer(person_type="ambos", full_name="Maria Historico", cnpj="12ABC34501DE35",
                      legal_name="Razão Antiga", trade_name="Fantasia Antiga", contact_person="Rui")
        self.page.click('[data-person-card="ambos"]')
        self.page.locator("#id_cpf").press_sequentially("52998224725")
        self.wait_true("document.querySelector('#id_full_name').value !== ''")
        self.assertEqual(self.page.input_value("#id_full_name"), "MARIA HISTORICO")
        for selector in ("#id_cnpj", "#id_legal_name", "#id_trade_name"):
            self.assertEqual(self.page.input_value(selector), "", selector)
        self.page.locator("#id_cnpj").press_sequentially("00000000000191")
        self.wait_true("document.querySelector('#id_legal_name').value !== ''")
        self.assertIn("BANCO DO BRASIL", self.page.input_value("#id_legal_name"))
        self.assertEqual(self.page.input_value("#id_full_name"), "MARIA HISTORICO")

    def test_unknown_cnpj_allows_manual_entry(self):
        """Consulta REAL com CNPJ de formato válido sem cadastro."""
        self.page.click('[data-person-card="pj"]')
        self.page.locator("#id_cnpj").press_sequentially("12ABC34501DE35")
        hint = self.page.locator(".js-cnpj [data-field-hint]")
        self.wait_true("document.querySelector('.js-cnpj [data-field-hint]').textContent.includes('manual')")
        self.assertIn("manual", hint.inner_text())
        self.page.fill("#id_legal_name", "Empresa Nova Ltda")
        self._fill_common()
        self.submit()
        self.assertEqual(Attendance.objects.get().customer.cnpj, "12ABC34501DE35")

    def test_phone_layout(self):
        page = self.new_page(DESKTOP | PHONE)
        self.login(page)
        page.goto(self.url("/atendimentos/novo/"))
        self.assertLessEqual(page.evaluate("document.documentElement.scrollWidth"), 390)
        self.shot("intake-phone", page)
        page.context.close()
