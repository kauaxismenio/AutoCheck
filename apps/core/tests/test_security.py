"""Varredura de segurança: novas rotas entram sozinhas nestas verificações."""
import uuid
from unittest import mock

from django.test import RequestFactory, TestCase, override_settings
from django.urls import URLPattern, URLResolver, get_resolver, reverse

from apps.core.audit import client_ip
from apps.core.middleware import CONTENT_SECURITY_POLICY
from apps.core.testing import make_attendance, make_user

# Únicas rotas acessíveis sem login, cada uma com o seu motivo.
PUBLIC = {
    "core:health",        # monitoramento; não expõe dados
    "core:manifest",      # instalação do PWA
    "core:sw",            # service worker
    "core:offline",       # página "sem conexão"
    "accounts:login",
}
PLATFORM_ONLY = {
    "platform_admin:list": [], "platform_admin:create": [], "platform_admin:edit": [1], "platform_admin:reset_password": [1],
}


def walk(patterns, namespace=""):
    for pattern in patterns:
        if isinstance(pattern, URLResolver):
            if pattern.namespace == "admin":
                continue
            child = f"{namespace}{pattern.namespace}:" if pattern.namespace else namespace
            yield from walk(pattern.url_patterns, child)
        elif isinstance(pattern, URLPattern) and pattern.name:
            yield f"{namespace}{pattern.name}", pattern


def fake_kwargs(pattern):
    kwargs = {}
    for name, converter in pattern.pattern.converters.items():
        kwargs[name] = uuid.uuid4() if type(converter).__name__ == "UUIDConverter" else 1
    return kwargs


class AnonymousAccessTests(TestCase):
    def test_every_route_requires_login_except_declared_public_ones(self):
        routes = list(walk(get_resolver().url_patterns))
        self.assertGreater(len(routes), 30)
        login_url = reverse("accounts:login")
        for name, pattern in routes:
            if name in PUBLIC or name == "accounts:logout":
                continue
            url = reverse(name, kwargs=fake_kwargs(pattern))
            for method in ("get", "post"):
                response = getattr(self.client, method)(url)
                self.assertEqual(response.status_code, 302, f"{method} {name}")
                self.assertTrue(response["Location"].startswith(login_url), f"{method} {name}")

    def test_public_routes_expose_no_personal_data(self):
        attendance = make_attendance()
        for name in PUBLIC:
            response = self.client.get(reverse(name))
            self.assertEqual(response.status_code, 200, name)
            content = response.content.decode()
            self.assertNotIn(attendance.customer.full_name, content, name)
            self.assertNotIn(attendance.vehicle.plate, content, name)


class RolePermissionTests(TestCase):
    def test_platform_routes_refuse_workshop_accounts(self):
        self.client.force_login(make_user("func"))
        for name, args in PLATFORM_ONLY.items():
            self.assertEqual(self.client.post(reverse(name, args=args)).status_code, 403, name)

    def test_regular_user_cannot_enter_django_admin(self):
        self.client.force_login(make_user("func"))
        response = self.client.get("/admin/")
        self.assertEqual(response.status_code, 302)
        self.assertIn("/admin/login/", response["Location"])


class HeaderTests(TestCase):
    def test_security_headers_present(self):
        response = self.client.get(reverse("accounts:login"))
        self.assertEqual(response["Content-Security-Policy"], CONTENT_SECURITY_POLICY)
        self.assertIn("camera=(self)", response["Permissions-Policy"])
        self.assertEqual(response["X-Frame-Options"], "DENY")
        self.assertEqual(response["X-Content-Type-Options"], "nosniff")
        self.assertEqual(response["Referrer-Policy"], "same-origin")

    def test_csp_blocks_inline_and_external_code(self):
        self.assertIn("script-src 'self'", CONTENT_SECURITY_POLICY)
        self.assertNotIn("unsafe-inline", CONTENT_SECURITY_POLICY)
        self.assertNotIn("unsafe-eval", CONTENT_SECURITY_POLICY)

    def test_templates_have_no_inline_script_or_style(self):
        from pathlib import Path

        from django.conf import settings

        for path in Path(settings.BASE_DIR, "templates").rglob("*.html"):
            content = path.read_text(encoding="utf-8")
            self.assertNotRegex(content, r"<script(?![^>]*\bsrc=)", str(path))
            self.assertNotRegex(content, r"\son[a-z]+=\"", str(path))
            self.assertNotRegex(content, r"\sstyle=\"", str(path))


class ProxyIpTests(TestCase):
    def _request(self):
        return RequestFactory().get("/", REMOTE_ADDR="10.0.0.5", HTTP_X_FORWARDED_FOR="1.2.3.4")

    def test_forged_header_ignored_by_default(self):
        self.assertEqual(client_ip(self._request()), "10.0.0.5")

    def test_header_used_only_when_enabled(self):
        from django.conf import settings

        with override_settings(AUTOCHECK={**settings.AUTOCHECK, "TRUST_PROXY_HEADERS": True}):
            self.assertEqual(client_ip(self._request()), "1.2.3.4")


class ErrorPageTests(TestCase):
    def test_404_is_friendly(self):
        response = self.client.get("/nao-existe/")
        self.assertEqual(response.status_code, 404)
        self.assertContains(response, "Página não encontrada", status_code=404)

    def test_403_is_friendly(self):
        self.client.force_login(make_user("func"))
        self.assertContains(self.client.get(reverse("platform_admin:list")), "Acesso negado", status_code=403)

    def test_500_hides_internal_details(self):
        self.client.force_login(make_user("func"))
        self.client.raise_request_exception = False
        with mock.patch("apps.core.views.recent_activity", side_effect=RuntimeError("segredo-interno")):
            response = self.client.get(reverse("core:home"))
        self.assertEqual(response.status_code, 500)
        self.assertContains(response, "Algo deu errado", status_code=500)
        self.assertNotContains(response, "segredo-interno", status_code=500)


class PwaTests(TestCase):
    def test_manifest_is_installable(self):
        response = self.client.get(reverse("core:manifest"))
        self.assertEqual(response["Content-Type"], "application/manifest+json")
        data = response.json()
        self.assertEqual(data["display"], "standalone")
        self.assertEqual(data["start_url"], "/")
        sizes = {icon["sizes"] for icon in data["icons"]}
        self.assertLessEqual({"192x192", "512x512"}, sizes)
        self.assertTrue(any(icon["purpose"] == "maskable" for icon in data["icons"]))

    def test_icons_exist(self):
        from django.contrib.staticfiles import finders

        for name in ("icon-192.png", "icon-512.png", "maskable-512.png"):
            self.assertIsNotNone(finders.find(f"img/icons/{name}"), name)

    def test_service_worker_scope_and_no_private_caching(self):
        response = self.client.get(reverse("core:sw"))
        self.assertIn("text/javascript", response["Content-Type"])
        self.assertEqual(response["Service-Worker-Allowed"], "/")
        self.assertIn("no-cache", response["Cache-Control"])
        content = response.content.decode()
        self.assertNotIn("/atendimentos", content)
        self.assertNotIn("/fotos", content)
        self.assertIn("/sem-conexao/", content)

    def test_service_worker_works_with_hashed_static_storage(self):
        """Regressão: em produção o armazenamento com hash recusa static("") e o worker dava erro 500."""

        def strict_static(path):
            if not path:
                raise ValueError("Missing staticfiles manifest entry for ''")
            return f"/static/{path}"

        with mock.patch("apps.core.pwa.static", side_effect=strict_static):
            response = self.client.get(reverse("core:sw"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'STATIC_PREFIX = "/static/"')

    def test_pages_link_manifest_and_register_worker(self):
        response = self.client.get(reverse("accounts:login"))
        self.assertContains(response, 'rel="manifest"')
        self.assertContains(response, 'data-sw-url="/sw.js"')
