"""Base dos testes em navegador real (Playwright + Edge ou Chrome já instalado).

Não rodam por padrão. Para executar:
    $env:RUN_E2E="1"; python manage.py test e2e --settings=config.settings.test
Capturas de tela ficam em e2e/_shots (fora do git).
"""
import os
import tempfile
import time
from pathlib import Path
from unittest import skipUnless

from django.contrib.staticfiles.testing import StaticLiveServerTestCase

from apps.core.testing import make_employee, make_mechanic, make_user

RUN = os.environ.get("RUN_E2E") == "1"
SHOTS = Path(__file__).resolve().parent / "_shots"
PASSWORD = "senha-forte-123"
DESKTOP = {"viewport": {"width": 1366, "height": 850}}
TABLET = {"viewport": {"width": 800, "height": 1280}, "has_touch": True, "is_mobile": True}
PHONE = {"viewport": {"width": 390, "height": 844}, "has_touch": True, "is_mobile": True}


@skipUnless(RUN, "Testes em navegador: defina RUN_E2E=1")
class BrowserTestCase(StaticLiveServerTestCase):
    @classmethod
    def setUpClass(cls):
        os.environ["DJANGO_ALLOW_ASYNC_UNSAFE"] = "true"  # Playwright síncrono usa um laço de eventos
        super().setUpClass()
        from playwright.sync_api import sync_playwright

        cls.playwright = sync_playwright().start()
        cls.browser = cls.playwright.chromium.launch(channel=os.environ.get("E2E_CHANNEL", "msedge"), headless=True)

    @classmethod
    def tearDownClass(cls):
        cls.browser.close()
        cls.playwright.stop()
        super().tearDownClass()

    def setUp(self):
        from django.core.management import call_command

        call_command("seed_checklist", verbosity=0, stdout=open(os.devnull, "w"))  # noqa: SIM115
        self.admin = make_user("chefe", first_name="Dono")
        self.mechanic = make_mechanic("Rui")
        self.employee = make_user("func", first_name="Ana")
        self.attendant = make_employee("Ana")
        self.browser_errors = []
        self.page = self.new_page(DESKTOP)

    def tearDown(self):
        self.page.context.close()
        self.assertEqual(self.browser_errors, [], "Erros no console do navegador")

    def new_page(self, options):
        context = self.browser.new_context(**options, locale="pt-BR")
        page = context.new_page()
        page.set_default_timeout(15000)
        page.on("pageerror", lambda error: self.browser_errors.append(str(error)))

        def on_console(message):
            # 4xx de consultas e validações são respostas esperadas, não falhas de script.
            if message.type == "error" and "Failed to load resource" not in message.text:
                self.browser_errors.append(message.text)

        page.on("console", on_console)
        return page

    def url(self, path):
        return f"{self.live_server_url}{path}"

    def submit(self, target="button.btn--lg", page=None):
        """Clica e espera a nova página: só depois disso o servidor terminou de gravar."""
        from playwright.sync_api import TimeoutError as PlaywrightTimeout

        page = page or self.page
        locator = page.locator(target) if isinstance(target, str) else target
        started = time.monotonic()
        try:
            with page.expect_navigation():
                locator.click()
        except PlaywrightTimeout as exc:
            self.shot(f"timeout-{self._testMethodName}", page)
            raise AssertionError(
                f"Sem navegação após {time.monotonic() - started:.1f}s. URL: {page.url}\n"
                f"Tela: {page.inner_text('body')[:900]}"
            ) from exc

    def login(self, page=None, username="chefe"):
        page = page or self.page
        page.goto(self.url("/conta/entrar/"))
        page.fill("#id_username", username)
        page.fill("#id_password", PASSWORD)
        self.submit("button[type=submit]", page=page)
        assert page.url == self.url("/"), page.url

    def wait_true(self, expression, page=None, timeout=20):
        """Espera uma expressão JS ficar verdadeira. O wait_for_function do Playwright usa
        eval, bloqueado pela CSP do sistema, que não deve ser afrouxada nos testes."""
        page = page or self.page
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            if page.evaluate(expression):
                return
            page.wait_for_timeout(100)
        raise AssertionError(f"Condição não atendida em {timeout}s: {expression}")

    def assert_no_overflow(self, page, width, label):
        offenders = page.evaluate(
            """(limit) => [...document.querySelectorAll('body *')]
                 .filter(e => e.getBoundingClientRect().right > limit + 1 && !e.closest('.steps, .table-wrap, .sidebar'))
                 .slice(0, 6).map(e => e.tagName + '.' + e.className + ' #' + e.id + ' ' + Math.round(e.getBoundingClientRect().right))""",
            width,
        )
        scroll_width = page.evaluate("document.documentElement.scrollWidth")
        self.assertLessEqual(scroll_width, width, f"{label}: {offenders}")

    def shot(self, name, page=None):
        SHOTS.mkdir(exist_ok=True)
        (page or self.page).screenshot(path=str(SHOTS / f"{name}.png"), full_page=True)

    @staticmethod
    def temp_image(color=(242, 140, 24)):
        from PIL import Image

        handle = tempfile.NamedTemporaryFile(suffix=".jpg", delete=False)
        handle.close()
        Image.new("RGB", (1024, 768), color).save(handle.name, "JPEG")
        return handle.name
