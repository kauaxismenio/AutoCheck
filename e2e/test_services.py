from apps.attendances import workflow as wf
from apps.attendances.models import Attendance
from apps.replacements.models import PartReplacement
from apps.services.models import ServiceRecord

from .base import BrowserTestCase
from .helpers import evaluate_all, open_intake, upload_all_required


class ServicesStepTests(BrowserTestCase):
    def setUp(self):
        super().setUp()
        self.login()
        open_intake(self)
        upload_all_required(self)
        self.submit()
        evaluate_all(self.page, bad_component="Pastilhas dianteiras", bad_tire="Estepe", image=self.temp_image())
        self.submit()
        self.assertIn("/servicos/", self.page.url)

    def _card(self, name):
        return self.page.locator(".part-card", has_text=name)

    def test_decisions_photos_and_advance(self):
        self.assertEqual(self.page.locator(".part-card").count(), 2)
        self.submit("[data-step-submit]")
        self.assertIn("registre a decisão", self.page.inner_text(".errors-box"))

        # Peça autorizada: exige as duas fotos.
        self.submit(self._card("Pastilhas dianteiras").get_by_role("button", name="Cliente autorizou"))
        self.submit(self._card("Pastilhas dianteiras").get_by_role("button", name="Confirmar substituição realizada"))
        self.assertIn("foto da peça", self.page.inner_text(".messages"))

        card = self._card("Pastilhas dianteiras")
        image = self.temp_image()
        for label in ("Peça antiga", "Peça nova"):
            slot = card.locator("[data-photo-slot]", has_text=label)
            slot.locator("[data-photo-input]").set_input_files(image)
            slot.locator("[data-photo-thumb]").first.wait_for()
        card.locator("input[name=part_description]").fill("Marca X")
        self.shot("services-authorized")
        self.submit(card.get_by_role("button", name="Confirmar substituição realizada"))
        self.assertTrue(PartReplacement.objects.get(component_name="Pastilhas dianteiras").replaced)

        # Pneu recusado: sem fotos.
        self.submit(self._card("Pneu estepe").get_by_role("button", name="Cliente não autorizou"))
        self.assertIn("Recusa registrada", self._card("Pneu estepe").inner_text())

        self.page.fill("#service-description", "Alinhamento")
        self.submit(self.page.get_by_role("button", name="Adicionar serviço"))
        self.assertEqual(ServiceRecord.objects.count(), 2)
        self.shot("services-done")

        self.submit("[data-step-submit]")
        self.assertIn("/check-out/", self.page.url)
        self.assertEqual(Attendance.objects.get().current_step, wf.CHECKOUT)
