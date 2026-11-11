from django.test import SimpleTestCase

from apps.integrations.providers.base import NotConfigured
from apps.integrations.providers.management_system import ManagementSystemClient


class ManagementSystemTests(SimpleTestCase):
    def test_never_simulates_a_lookup(self):
        client = ManagementSystemClient()
        self.assertFalse(client.is_available)
        with self.assertRaises(NotConfigured):
            client.find_customer_by_cpf("52998224725")
