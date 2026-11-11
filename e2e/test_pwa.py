from .base import PHONE, TABLET, BrowserTestCase
from .helpers import open_intake, upload_all_required


class PwaBrowserTests(BrowserTestCase):
    def test_service_worker_activates_and_keeps_private_data_out_of_cache(self):
        self.login()
        open_intake(self)
        upload_all_required(self)
        photo = self.page.locator("[data-photo-thumb] img").first.get_attribute("src")
        self.page.goto(self.url(photo))
        self.page.goto(self.url("/atendimentos/"))
        state = self.page.evaluate("navigator.serviceWorker.ready.then(r => r.active.state)")
        self.assertIn(state, ("activating", "activated"))
        self.page.reload()
        self.wait_true("navigator.serviceWorker.controller !== null")
        cached = self.page.evaluate("""async () => {
            const urls = [];
            for (const name of await caches.keys()) {
                for (const request of await (await caches.open(name)).keys()) urls.push(new URL(request.url).pathname);
            }
            return urls;
        }""")
        self.assertTrue(cached)
        for path in cached:
            self.assertTrue(path.startswith("/static/") or path == "/sem-conexao/", path)

    def test_offline_shows_friendly_page(self):
        self.login()
        self.page.evaluate("navigator.serviceWorker.ready.then(() => true)")
        self.page.reload()
        self.wait_true("navigator.serviceWorker.controller !== null")
        self.page.context.set_offline(True)
        self.page.goto(self.url("/clientes/"))
        self.assertIn("Sem conexão", self.page.inner_text("main"))
        self.shot("offline")
        self.page.context.set_offline(False)

    def test_manifest_is_linked_and_served(self):
        self.page.goto(self.url("/conta/entrar/"))
        href = self.page.get_attribute('link[rel="manifest"]', "href")
        data = self.page.request.get(self.url(href)).json()
        self.assertEqual(data["display"], "standalone")
        for icon in data["icons"]:
            self.assertEqual(self.page.request.get(self.url(icon["src"])).status, 200, icon["src"])


class ResponsiveSweepTests(BrowserTestCase):
    """Sem rolagem horizontal nas telas principais, no celular e no tablet."""

    def test_no_horizontal_overflow(self):
        paths = ["/", "/atendimentos/", "/atendimentos/novo/", "/atendimentos/historico/", "/clientes/", "/veiculos/",
                 "/pos-venda/", "/configuracoes/", "/conta/usuarios/", "/conta/minha-senha/"]
        for options, name in ((PHONE, "celular"), (TABLET, "tablet")):
            page = self.new_page(options)
            self.login(page)
            for path in paths:
                page.goto(self.url(path))
                self.assert_no_overflow(page, options["viewport"]["width"], f"{name} {path}")
            page.context.close()
