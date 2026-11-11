from django.test import TestCase
from django.urls import reverse

from apps.attendances import workflow as wf
from apps.core.audit import log_action
from apps.core.navigation import NAV_ITEMS
from apps.core.testing import make_attendance, make_user


class DashboardTests(TestCase):
    def test_counts(self):
        make_attendance()
        user = make_user("ana")
        self.client.force_login(user)
        response = self.client.get(reverse("core:home"))
        stats = response.context["stats"]
        self.assertEqual(stats["total"], 1)
        self.assertEqual(stats["in_progress"], 1)
        self.assertEqual(stats["completed"], 0)
        self.assertEqual(stats["customers"], 1)
        self.assertEqual(stats["vehicles"], 1)

    def test_cancelled_is_not_counted_as_performed(self):
        make_attendance(status=wf.STATUS_CANCELADO)
        self.client.force_login(make_user("ana"))
        self.assertEqual(self.client.get(reverse("core:home")).context["stats"]["total"], 0)

    def test_recent_activity_lists_audited_actions(self):
        att = make_attendance()
        user = make_user("ana", first_name="Ana")
        log_action("attendance.created", user=user, obj=att, attendance=att)
        self.client.force_login(user)
        self.assertContains(self.client.get(reverse("core:home")), "abriu o atendimento")

    def test_workshop_account_sees_dashboard_and_settings(self):
        self.client.force_login(make_user("func"))
        response = self.client.get(reverse("core:home"))
        self.assertContains(response, reverse("workshop:settings"))

    def test_menu_shows_settings_to_admin(self):
        self.client.force_login(make_user("chefe"))
        self.assertContains(self.client.get(reverse("core:home")), reverse("workshop:settings"))

    def test_hamburger_present(self):
        self.client.force_login(make_user("chefe"))
        self.assertContains(self.client.get(reverse("core:home")), "data-sidebar-toggle")

    def test_nav_definition_is_complete(self):
        labels = [item[0] for item in NAV_ITEMS]
        self.assertEqual(labels, ["Dashboard", "Atendimentos", "Clientes", "Veículos", "Histórico", "Pós-venda", "Configurações"])
