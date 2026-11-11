from apps.attendances import workflow as wf
from apps.attendances.models import Attendance
from apps.checklist.models import ChecklistItem
from apps.replacements.models import PartReplacement

from .base import PHONE, BrowserTestCase
from .helpers import evaluate_all, open_intake, upload_all_required, wait_saved


class ChecklistTests(BrowserTestCase):
    def setUp(self):
        super().setUp()
        self.login()
        open_intake(self)
        upload_all_required(self)
        self.submit()
        self.assertIn("/checklist/", self.page.url)

    def test_autosave_survives_reload_and_updates_progress(self):
        row = self.page.locator(".check-row[data-check-item]").first
        row.locator(".evaluate label", has_text="SUBSTITUIR").click()
        wait_saved(self.page)
        self.assertEqual(self.page.inner_text("[data-check-done]"), "1")
        self.assertEqual(PartReplacement.objects.count(), 1)

        self.page.reload()
        self.assertEqual(self.page.inner_text("[data-check-done]"), "1")
        checked = self.page.locator(".check-row[data-check-item]").first.locator(".evaluate__bad input")
        self.assertTrue(checked.is_checked())

    def test_blocks_pending_then_advances(self):
        self.submit()
        self.assertIn("sem avaliação", self.page.inner_text(".errors-box"))

        evaluate_all(self.page, bad_component="Pastilhas dianteiras", bad_tire="Estepe", image=self.temp_image())
        self.assertEqual(self.page.inner_text("[data-check-done]"), "52")
        self.shot("checklist-done")
        self.submit()
        self.assertEqual(Attendance.objects.get().current_step, wf.SERVICOS)
        self.assertEqual(
            sorted(PartReplacement.objects.values_list("component_name", flat=True)),
            ["Pastilhas dianteiras", "Pneu estepe"],
        )
        self.assertEqual(ChecklistItem.objects.exclude(result="").count(), 47)

    def test_tire_photo_slot_only_when_replacing(self):
        tire = self.page.locator(".tire-card").first
        slot = tire.locator("[data-tire-photo]")
        self.assertFalse(slot.is_visible())
        tire.locator(".evaluate label", has_text="SUBSTITUIR").click()
        self.assertTrue(slot.is_visible())
        tire.locator(".evaluate label", has_text="OK").click()
        self.assertFalse(slot.is_visible())
        wait_saved(self.page)

    def test_selected_buttons_are_green_and_red(self):
        row = self.page.locator(".check-row[data-check-item]").first
        row.locator(".evaluate label", has_text="OK").click()
        self.page.wait_for_timeout(100)
        green = row.locator(".evaluate__ok").evaluate("e => getComputedStyle(e).backgroundColor")
        self.assertEqual(green, "rgb(31, 157, 85)")
        row.locator(".evaluate label", has_text="SUBSTITUIR").click()
        self.page.wait_for_timeout(100)
        red = row.locator(".evaluate__bad").evaluate("e => getComputedStyle(e).backgroundColor")
        self.assertEqual(red, "rgb(214, 69, 69)")
        wait_saved(self.page)

    def test_phone_layout(self):
        page = self.new_page(PHONE)
        self.login(page)
        page.goto(self.page.url)
        self.assertLessEqual(page.evaluate("document.documentElement.scrollWidth"), 390)
        self.shot("checklist-phone", page)
        page.context.close()
