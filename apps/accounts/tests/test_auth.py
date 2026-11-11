from django.test import TestCase
from django.urls import reverse

from apps.accounts import throttle
from apps.accounts.models import LoginAttempt, User
from apps.core.models import AuditLog
from apps.core.testing import make_user


class LoginTests(TestCase):
    def setUp(self):
        self.user = make_user("ana")
        self.url = reverse("accounts:login")

    def _login(self, password="senha-forte-123"):
        return self.client.post(self.url, {"username": "ana", "password": password})

    def test_login_page_renders(self):
        response = self.client.get(self.url)
        self.assertContains(response, "Entrar")

    def test_success_redirects_to_dashboard_and_audits(self):
        response = self._login()
        self.assertRedirects(response, reverse("core:home"))
        self.assertTrue(AuditLog.objects.filter(action="accounts.login", user=self.user).exists())

    def test_wrong_password_shows_message(self):
        self.assertContains(self._login("errada"), "E-mail ou senha incorretos")
        self.assertEqual(LoginAttempt.objects.count(), 1)

    def test_lockout_blocks_even_the_correct_password(self):
        for _ in range(throttle.MAX_FAILURES):
            self._login("errada")
        response = self._login()
        self.assertContains(response, "Muitas tentativas")
        self.assertNotIn("_auth_user_id", self.client.session)

    def test_success_clears_failures(self):
        self._login("errada")
        self._login()
        self.assertEqual(LoginAttempt.objects.count(), 0)

    def test_logout_requires_post(self):
        self.client.force_login(self.user)
        self.assertEqual(self.client.get(reverse("accounts:logout")).status_code, 405)
        self.assertEqual(self.client.post(reverse("accounts:logout")).status_code, 302)
        self.assertNotIn("_auth_user_id", self.client.session)


class OwnPasswordTests(TestCase):
    def test_change_own_password(self):
        employee = make_user("func")
        self.client.force_login(employee)
        response = self.client.post(reverse("accounts:change_password"), {
            "old_password": "senha-forte-123", "new_password1": "Outra-Forte-88", "new_password2": "Outra-Forte-88",
        })
        self.assertRedirects(response, reverse("core:home"))
        employee.refresh_from_db()
        self.assertTrue(employee.check_password("Outra-Forte-88"))

    def test_user_management_routes_no_longer_exist(self):
        self.client.force_login(make_user("func"))
        self.assertEqual(self.client.get("/conta/usuarios/").status_code, 404)
