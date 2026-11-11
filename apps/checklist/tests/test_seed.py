from django.core.management import call_command
from django.test import TestCase

from apps.checklist.catalog import CATALOG
from apps.checklist.models import ChecklistCategory, ChecklistComponent


class SeedChecklistTests(TestCase):
    def test_seed_is_idempotent(self):
        call_command("seed_checklist", verbosity=0)
        call_command("seed_checklist", verbosity=0)
        self.assertEqual(ChecklistCategory.objects.count(), len(CATALOG))
        self.assertEqual(ChecklistComponent.objects.count(), sum(len(c[2]) for c in CATALOG))

    def test_catalog_codes_unique(self):
        codes = [code for _, _, comps in CATALOG for code, _ in comps]
        self.assertEqual(len(codes), len(set(codes)))
