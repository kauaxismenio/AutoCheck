from django.core.management import call_command
from django.test import TestCase
from django.urls import reverse

from apps.attendances import services as att_services
from apps.attendances import workflow as wf
from apps.checklist import services
from apps.checklist.models import Result
from apps.core.testing import make_attendance, make_user, make_vehicle, tiny_png
from apps.photos import categories as cat
from apps.photos.models import Photo
from apps.replacements.models import Decision, PartReplacement
from apps.tires.models import TirePosition


def at_step(att, step):
    type(att).objects.filter(pk=att.pk).update(current_step=step)
    att.refresh_from_db()
    return att


def add_required_checkin_photos(att):
    for category in cat.CHECKIN_REQUIRED:
        Photo.objects.create(attendance=att, phase=cat.PHASE_CHECKIN, category=category, image=tiny_png())


def fill_all(att, psi="32", result=Result.OK):
    services.ensure_initialized(att)
    data = {}
    for item in att.checklist_items.all():
        data[f"item-{item.pk}"] = result
    for tire in att.tire_inspections.all():
        data[f"tire-{tire.pk}-condition"] = result
        data[f"tire-{tire.pk}-psi"] = psi
    return data


class ChecklistBase(TestCase):
    @classmethod
    def setUpTestData(cls):
        call_command("seed_checklist", verbosity=0)

    def setUp(self):
        self.user = make_user("ana")
        self.client.force_login(self.user)
        self.att = make_attendance()
        at_step(self.att, wf.CHECKLIST)
        add_required_checkin_photos(self.att)
        self.url = reverse("checklist:step", args=[self.att.public_id])
        self.autosave_url = reverse("checklist:autosave", args=[self.att.public_id])


class InitializationTests(ChecklistBase):
    def test_creates_items_and_five_tires_once(self):
        self.client.get(self.url)
        self.client.get(self.url)
        self.assertEqual(self.att.checklist_items.count(), 47)
        self.assertEqual({t.position for t in self.att.tire_inspections.all()}, set(TirePosition.values))
        self.assertEqual(self.att.tire_inspections.count(), 5)

    def test_page_lists_categories_and_has_no_not_checked_option(self):
        response = self.client.get(self.url)
        for name in ("Suspensão", "Freios", "Lubrificantes", "Filtros", "Iluminação", "Componentes elétricos", "Pneus"):
            self.assertContains(response, name)
        self.assertNotContains(response, "Não verificado")

    def test_blocked_before_step(self):
        at_step(self.att, wf.CHECKIN)
        self.assertEqual(self.client.get(self.url).status_code, 403)
        self.assertEqual(self.client.post(self.autosave_url, {"kind": "item", "id": "1"}).status_code, 403)

    def test_snapshot_of_names_survives_catalog_rename(self):
        services.ensure_initialized(self.att)
        item = self.att.checklist_items.first()
        component = item.component
        original = item.component_name
        component.name = "Nome novo"
        component.save()
        item.refresh_from_db()
        self.assertEqual(item.component_name, original)


class AdvanceTests(ChecklistBase):
    def test_cannot_advance_with_pending_item(self):
        data = fill_all(self.att)
        first = self.att.checklist_items.first()
        del data[f"item-{first.pk}"]
        response = self.client.post(self.url, data)
        self.assertContains(response, "sem avaliação")
        self.att.refresh_from_db()
        self.assertEqual(self.att.current_step, wf.CHECKLIST)

    def test_cannot_advance_without_psi(self):
        response = self.client.post(self.url, fill_all(self.att, psi=""))
        self.assertContains(response, "calibragem")

    def test_all_ok_advances_without_twi_or_photo(self):
        response = self.client.post(self.url, fill_all(self.att))
        self.assertEqual(response.status_code, 302)
        self.att.refresh_from_db()
        self.assertEqual(self.att.current_step, wf.SERVICOS)
        self.assertEqual(PartReplacement.objects.count(), 0)

    def test_bad_tire_requires_photo(self):
        data = fill_all(self.att)
        tire = self.att.tire_inspections.get(position="dd")
        data[f"tire-{tire.pk}-condition"] = Result.SUBSTITUIR
        self.assertContains(self.client.post(self.url, data), "foto obrigatória")
        Photo.objects.create(attendance=self.att, phase=cat.PHASE_TIRE, tire_inspection=tire, image=tiny_png())
        self.assertEqual(self.client.post(self.url, data).status_code, 302)

    def test_invalid_psi_rejected(self):
        for value in ("abc", "999", "-5", "NaN", "Infinity"):
            data = fill_all(self.att, psi=value)
            response = self.client.post(self.url, data)
            self.assertEqual(response.status_code, 200, value)
            self.att.refresh_from_db()
            self.assertEqual(self.att.current_step, wf.CHECKLIST, value)

    def test_comma_decimal_accepted(self):
        self.client.post(self.url, fill_all(self.att, psi="32,5"))
        self.assertEqual(str(self.att.tire_inspections.first().pressure_psi), "32.5")

    def test_invalid_result_rejected(self):
        data = fill_all(self.att)
        first = self.att.checklist_items.first()
        data[f"item-{first.pk}"] = "nao_verificado"
        response = self.client.post(self.url, data)
        self.assertContains(response, "Avaliação inválida")


class RecommendationTests(ChecklistBase):
    def setUp(self):
        super().setUp()
        services.ensure_initialized(self.att)
        self.item = self.att.checklist_items.select_related("attendance").first()

    def _autosave(self, **data):
        return self.client.post(self.autosave_url, {"kind": "item", "id": self.item.pk, **data})

    def test_substituir_creates_recommendation_with_component_name(self):
        self.assertEqual(self._autosave(result="substituir").status_code, 200)
        replacement = PartReplacement.objects.get()
        self.assertEqual(replacement.component_name, self.item.component_name)
        self.assertEqual(replacement.decision, Decision.AGUARDANDO)
        self.item.refresh_from_db()
        self.assertEqual(self.item.evaluated_by, self.user)

    def test_back_to_ok_removes_recommendation_without_decision(self):
        self._autosave(result="substituir")
        self._autosave(result="ok")
        self.assertEqual(PartReplacement.objects.count(), 0)

    def test_back_to_ok_blocked_after_customer_decision(self):
        self._autosave(result="substituir")
        PartReplacement.objects.update(decision=Decision.NAO_AUTORIZADO)
        response = self._autosave(result="ok")
        self.assertEqual(response.status_code, 400)
        self.assertIn("decisão", response.json()["error"])
        self.item.refresh_from_db()
        self.assertEqual(self.item.result, Result.SUBSTITUIR)
        self.assertEqual(PartReplacement.objects.count(), 1)

    def test_bad_tire_creates_named_recommendation(self):
        tire = self.att.tire_inspections.get(position="estepe")
        self.client.post(self.autosave_url, {"kind": "tire", "id": tire.pk, "condition": "substituir", "psi": "30", "twi": ""})
        self.assertEqual(PartReplacement.objects.get().component_name, "Pneu estepe")

    def test_item_of_other_attendance_not_found(self):
        other = make_attendance(vehicle=make_vehicle(self.att.customer, plate="XYZ9K88"), mechanic=self.att.mechanic)
        services.ensure_initialized(other)
        foreign = other.checklist_items.first()
        response = self.client.post(self.autosave_url, {"kind": "item", "id": foreign.pk, "result": "ok"})
        self.assertEqual(response.status_code, 404)
        foreign.refresh_from_db()
        self.assertEqual(foreign.result, "")

    def test_notes_are_saved_and_optional(self):
        self._autosave(result="ok", notes="  folga leve ")
        self.item.refresh_from_db()
        self.assertEqual(self.item.notes, "folga leve")


class RevisitTests(ChecklistBase):
    def test_new_recommendation_after_services_blocks_later_advance(self):
        """Marcar SUBSTITUIR voltando de uma etapa à frente não pode escapar da decisão."""
        self.client.post(self.url, fill_all(self.att))
        self.att.refresh_from_db()
        att_services.advance(self.att, wf.SERVICOS)
        self.assertEqual(self.att.current_step, wf.CHECKOUT)

        item = self.att.checklist_items.select_related("attendance").first()
        self.client.post(self.autosave_url, {"kind": "item", "id": item.pk, "result": "substituir"})
        for category in cat.CHECKOUT_REQUIRED:
            Photo.objects.create(attendance=self.att, phase=cat.PHASE_CHECKOUT, category=category, image=tiny_png())
        with self.assertRaises(att_services.StepIncomplete) as ctx:
            att_services.advance(self.att, wf.CHECKOUT)
        self.assertIn("registre a decisão", ctx.exception.errors[0])
