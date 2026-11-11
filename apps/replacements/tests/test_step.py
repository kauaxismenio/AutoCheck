from django.core.management import call_command
from django.test import TestCase
from django.urls import reverse

from apps.attendances import workflow as wf
from apps.checklist import services as checklist
from apps.checklist.models import Result
from apps.core.testing import default_workshop, complete_through, make_attendance, make_user, make_vehicle, tiny_png
from apps.photos import categories as cat
from apps.photos.models import Photo
from apps.replacements.models import Decision
from apps.services.models import ServiceRecord


class ServiceStepBase(TestCase):
    @classmethod
    def setUpTestData(cls):
        call_command("seed_checklist", verbosity=0)

    def setUp(self):
        self.user = make_user("ana")
        self.client.force_login(self.user)
        self.att = complete_through(make_attendance(), wf.SERVICOS)
        self.item = self.att.checklist_items.select_related("attendance").first()
        checklist.save_item(self.item, result=Result.SUBSTITUIR)
        self.rep = self.att.replacements.get()
        self.step_url = reverse("replacements:step", args=[self.att.public_id])

    def decide(self, decision):
        return self.client.post(reverse("replacements:decision", args=[self.att.public_id, self.rep.pk]), {"decision": decision})

    def upload(self, phase):
        return self.client.post(reverse("photos:upload", args=[self.att.public_id]),
                                {"phase": phase, "category": cat.GERAL, "target": self.rep.pk, "image": tiny_png()})

    def confirm(self, **data):
        return self.client.post(reverse("replacements:confirm", args=[self.att.public_id, self.rep.pk]), data)


class DecisionTests(ServiceStepBase):
    def test_page_lists_component_without_retyping_name(self):
        response = self.client.get(self.step_url)
        self.assertContains(response, self.item.component_name)
        self.assertContains(response, "Aguardando decisão")
        self.assertNotContains(response, 'name="component_name"')

    def test_waiting_blocks_advance(self):
        response = self.client.post(self.step_url)
        self.assertContains(response, "registre a decisão")
        self.att.refresh_from_db()
        self.assertEqual(self.att.current_step, wf.SERVICOS)

    def test_refusal_needs_no_photos_and_advances(self):
        self.decide(Decision.NAO_AUTORIZADO)
        self.rep.refresh_from_db()
        self.assertEqual(self.rep.decision, Decision.NAO_AUTORIZADO)
        self.assertEqual(self.rep.decision_registered_by, self.user)
        self.assertIsNotNone(self.rep.decided_at)
        self.assertEqual(self.client.post(self.step_url).status_code, 302)
        self.att.refresh_from_db()
        self.assertEqual(self.att.current_step, wf.CHECKOUT)
        self.assertFalse(ServiceRecord.objects.exists())

    def test_authorized_requires_both_photos_and_confirmation(self):
        self.decide(Decision.AUTORIZADO)
        response = self.client.post(self.step_url)
        self.assertContains(response, "peça antiga")
        self.assertContains(response, "peça nova")
        self.assertContains(response, "confirme a substituição")

    def test_confirm_needs_photos(self):
        self.decide(Decision.AUTORIZADO)
        self.upload(cat.PHASE_PART_OLD)
        self.confirm()
        self.rep.refresh_from_db()
        self.assertFalse(self.rep.replaced)

    def test_full_authorized_flow_creates_linked_service(self):
        self.decide(Decision.AUTORIZADO)
        self.assertEqual(self.upload(cat.PHASE_PART_OLD).status_code, 201)
        self.assertEqual(self.upload(cat.PHASE_PART_NEW).status_code, 201)
        self.confirm(part_description="Marca X, código 123")
        self.rep.refresh_from_db()
        self.assertTrue(self.rep.replaced)
        self.assertEqual(self.rep.part_description, "Marca X, código 123")
        service = ServiceRecord.objects.get()
        self.assertEqual(service.replacement, self.rep)
        self.assertIn(self.item.component_name, service.description)
        part_photos = Photo.objects.filter(phase__in=(cat.PHASE_PART_OLD, cat.PHASE_PART_NEW))
        self.assertEqual({p.replacement_id for p in part_photos}, {self.rep.pk})
        self.assertEqual(self.client.post(self.step_url).status_code, 302)

    def test_confirm_twice_keeps_one_service(self):
        self.decide(Decision.AUTORIZADO)
        self.upload(cat.PHASE_PART_OLD)
        self.upload(cat.PHASE_PART_NEW)
        self.confirm()
        self.confirm()
        self.assertEqual(ServiceRecord.objects.count(), 1)

    def test_photo_upload_rejected_without_authorization(self):
        self.assertEqual(self.upload(cat.PHASE_PART_OLD).status_code, 400)

    def test_deleting_part_photo_undoes_replacement(self):
        self.decide(Decision.AUTORIZADO)
        self.upload(cat.PHASE_PART_OLD)
        self.upload(cat.PHASE_PART_NEW)
        self.confirm()
        photo = Photo.objects.filter(phase=cat.PHASE_PART_OLD).get()
        self.client.post(reverse("photos:delete", args=[self.att.public_id, photo.pk]))
        self.rep.refresh_from_db()
        self.assertFalse(self.rep.replaced)
        self.assertFalse(ServiceRecord.objects.exists())

    def test_changing_decision_clears_execution_and_photos(self):
        self.decide(Decision.AUTORIZADO)
        self.upload(cat.PHASE_PART_OLD)
        self.upload(cat.PHASE_PART_NEW)
        self.confirm()
        self.decide(Decision.NAO_AUTORIZADO)
        self.rep.refresh_from_db()
        self.assertFalse(self.rep.replaced)
        self.assertFalse(self.rep.photos.exists())
        self.assertFalse(ServiceRecord.objects.exists())

    def test_reset_decision_allows_item_back_to_ok(self):
        self.decide(Decision.NAO_AUTORIZADO)
        self.decide(Decision.AGUARDANDO)
        self.item.refresh_from_db()
        checklist.save_item(self.item, result=Result.OK)
        self.assertFalse(self.att.replacements.exists())

    def test_invalid_decision_ignored(self):
        self.decide("talvez")
        self.rep.refresh_from_db()
        self.assertEqual(self.rep.decision, Decision.AGUARDANDO)

    def test_replacement_of_other_attendance_is_404(self):
        other = make_attendance(vehicle=make_vehicle(self.att.customer, plate="XYZ9K88"), mechanic=self.att.mechanic)
        type(other).objects.filter(pk=other.pk).update(current_step=wf.SERVICOS)
        response = self.client.post(reverse("replacements:decision", args=[other.public_id, self.rep.pk]),
                                    {"decision": Decision.AUTORIZADO})
        self.assertEqual(response.status_code, 404)

    def test_blocked_before_step_and_after_completion(self):
        type(self.att).objects.filter(pk=self.att.pk).update(current_step=wf.CHECKLIST)
        self.assertEqual(self.client.get(self.step_url).status_code, 403)
        self.assertEqual(self.decide(Decision.AUTORIZADO).status_code, 403)
        type(self.att).objects.filter(pk=self.att.pk).update(current_step=wf.FINALIZADO, status=wf.STATUS_CONCLUIDO)
        self.assertEqual(self.decide(Decision.AUTORIZADO).status_code, 403)


class ManualServiceTests(ServiceStepBase):
    def test_add_and_delete_manual_service(self):
        self.client.post(reverse("replacements:add_service", args=[self.att.public_id]), {"description": "Alinhamento"})
        service = ServiceRecord.objects.get()
        self.assertEqual(service.description, "Alinhamento")
        self.assertEqual(service.performed_by, self.user)
        self.client.post(reverse("replacements:delete_service", args=[self.att.public_id, service.pk]))
        self.assertFalse(ServiceRecord.objects.exists())

    def test_empty_description_rejected(self):
        self.client.post(reverse("replacements:add_service", args=[self.att.public_id]), {"description": "  "})
        self.assertFalse(ServiceRecord.objects.exists())

    def test_linked_service_cannot_be_deleted_directly(self):
        self.decide(Decision.AUTORIZADO)
        self.upload(cat.PHASE_PART_OLD)
        self.upload(cat.PHASE_PART_NEW)
        self.confirm()
        service = ServiceRecord.objects.get()
        response = self.client.post(reverse("replacements:delete_service", args=[self.att.public_id, service.pk]))
        self.assertEqual(response.status_code, 404)
        self.assertTrue(ServiceRecord.objects.exists())


class ServiceIdentificationTests(TestCase):
    def test_shows_workshop_name_and_not_the_logged_account(self):
        from apps.replacements.services import add_manual_service
        from apps.workshop.models import WorkshopSettings

        WorkshopSettings.objects.filter(pk=default_workshop().pk).update(name="OFICINA TESTE")
        user = make_user("oficina", first_name="Nome Da Conta Logada")
        self.client.force_login(user)
        attendance = complete_through(make_attendance(), wf.SERVICOS)
        add_manual_service(attendance, "Alinhamento", user=user)
        response = self.client.get(reverse("replacements:step", args=[attendance.public_id]))
        self.assertContains(response, "— OFICINA TESTE")
        self.assertNotContains(response, "NOME DA CONTA LOGADA")

