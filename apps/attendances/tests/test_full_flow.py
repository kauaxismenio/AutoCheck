"""Integração: um atendimento inteiro pelas views, tentando furar o fluxo em cada etapa."""
import base64
import io

from django.core import mail
from django.core.management import call_command
from django.test import TestCase
from django.urls import reverse
from PIL import Image, ImageDraw

from apps.attendances import workflow as wf
from apps.attendances.models import Attendance
from apps.core.models import AuditLog
from apps.core.testing import default_workshop, make_employee, make_mechanic, make_user, tiny_png
from apps.mailing.models import EmailDispatch
from apps.mailing.services import mandatory_emails_confirmed
from apps.photos import categories as cat
from apps.replacements.models import Decision
from apps.reports.models import Report
from apps.workshop.models import WorkshopSettings


def signature():
    image = Image.new("RGBA", (400, 150), (0, 0, 0, 0))
    ImageDraw.Draw(image).line([(10, 10), (390, 140)], fill=(0, 0, 0, 255), width=4)
    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    return "data:image/png;base64," + base64.b64encode(buffer.getvalue()).decode()


class FullFlowTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        call_command("seed_checklist", verbosity=0)

    def setUp(self):
        self.mechanic = make_mechanic()
        self.client.force_login(make_user("ana"))
        workshop = default_workshop()
        workshop.report_email = "dono@oficinaboa.com.br"
        workshop.save()

    def _url(self, name, *args):
        return reverse(name, args=[self.att.public_id, *args])

    def _assert_future_steps_blocked(self, *names):
        for name in names:
            self.assertEqual(self.client.get(self._url(name)).status_code, 403, name)
            self.assertEqual(self.client.post(self._url(name)).status_code, 403, name)

    def _upload(self, phase, category=cat.GERAL, target=""):
        response = self.client.post(self._url("photos:upload"), {"phase": phase, "category": category, "target": target, "image": tiny_png()})
        self.assertEqual(response.status_code, 201, response.content)

    def _step(self):
        self.att.refresh_from_db()
        return self.att.current_step

    def test_complete_attendance(self):
        # 1. Cadastro
        response = self.client.post(reverse("attendances:new"), {
            "person_type": "ambos", "full_name": "Maria Souza", "cpf": "529.982.247-25", "cnpj": "12.ABC.345/01DE-35",
            "legal_name": "Souza Ltda", "phone": "(81) 9 9000-1712", "email": "maria@empresa.com.br", "plate": "ABC1D23",
            "brand": "Fiat", "model": "Argo", "year": "2022", "color": "Prata", "mileage": "45210",
            "mechanic": self.mechanic.pk, "origin": "google", "attendant": make_employee().pk,
        })
        self.assertEqual(response.status_code, 302)
        self.att = Attendance.objects.get()
        self.assertEqual(self._step(), wf.CHECKIN)
        self._assert_future_steps_blocked("checklist:step", "replacements:step", "photos:checkout", "signatures:step")

        # 2. Check-in: não avança sem as fotos
        self.client.post(self._url("photos:checkin"))
        self.assertEqual(self._step(), wf.CHECKIN)
        for category in cat.CHECKIN_REQUIRED:
            self._upload(cat.PHASE_CHECKIN, category)
        self.client.post(self._url("photos:checkin"))
        self.assertEqual(self._step(), wf.CHECKLIST)
        self._assert_future_steps_blocked("replacements:step", "photos:checkout", "signatures:step")

        # 3. Checklist: dois componentes e um pneu a substituir
        self.client.get(self._url("checklist:step"))
        items = list(self.att.checklist_items.all())
        tires = list(self.att.tire_inspections.all())
        data = {f"item-{item.pk}": "ok" for item in items}
        data[f"item-{items[0].pk}"] = "substituir"
        data[f"item-{items[1].pk}"] = "substituir"
        for tire in tires:
            data[f"tire-{tire.pk}-condition"] = "ok"
            data[f"tire-{tire.pk}-psi"] = "32"
        data[f"tire-{tires[0].pk}-condition"] = "substituir"
        response = self.client.post(self._url("checklist:step"), data)
        self.assertContains(response, "foto obrigatória")
        self._upload(cat.PHASE_TIRE, target=tires[0].pk)
        self.client.post(self._url("checklist:step"), data)
        self.assertEqual(self._step(), wf.SERVICOS)
        self.assertEqual(self.att.replacements.count(), 3)

        # 4. Serviços: um autorizado e dois recusados
        replacements = list(self.att.replacements.order_by("id"))
        self.client.post(self._url("replacements:step"))
        self.assertEqual(self._step(), wf.SERVICOS)
        self.client.post(self._url("replacements:decision", replacements[0].pk), {"decision": Decision.AUTORIZADO})
        for replacement in replacements[1:]:
            self.client.post(self._url("replacements:decision", replacement.pk), {"decision": Decision.NAO_AUTORIZADO})
        self.client.post(self._url("replacements:step"))
        self.assertEqual(self._step(), wf.SERVICOS, "Sem as fotos da peça não avança")
        self._upload(cat.PHASE_PART_OLD, target=replacements[0].pk)
        self._upload(cat.PHASE_PART_NEW, target=replacements[0].pk)
        self.client.post(self._url("replacements:confirm", replacements[0].pk), {"part_description": "Marca X"})
        self.client.post(self._url("replacements:add_service"), {"description": "Alinhamento"})
        self.client.post(self._url("replacements:step"))
        self.assertEqual(self._step(), wf.CHECKOUT)

        # 5. Check-out
        self.client.post(self._url("photos:checkout"))
        self.assertEqual(self._step(), wf.CHECKOUT)
        for category in cat.CHECKOUT_REQUIRED:
            self._upload(cat.PHASE_CHECKOUT, category)
        self.client.post(self._url("photos:checkout"))
        self.assertEqual(self._step(), wf.REVISAO)

        # 6. Revisão: conclui com assinatura, gera o PDF e envia os e-mails
        self.assertEqual(self.client.post(self._url("reports:generate"), follow=True).status_code, 200)
        self.assertEqual(Report.objects.count(), 0, "Sem relatório antes de concluir")
        self.client.post(self._url("signatures:step"))
        self.assertEqual(self._step(), wf.REVISAO)
        WorkshopSettings.objects.filter(pk=default_workshop().pk).update(google_review_url="https://g.page/r/oficina/review")
        self.client.post(self._url("signatures:review_qr"), {"action": "present"})
        response = self.client.post(self._url("signatures:step"), {"signature_data": signature()}, follow=True)
        self.assertContains(response, "Atendimento concluído")
        self.att.refresh_from_db()
        self.assertEqual(self.att.status, wf.STATUS_CONCLUIDO)
        self.assertIsNotNone(self.att.review_qr_presented_at)
        self.assertIsNotNone(self.att.retention_until)

        report = Report.objects.get()
        self.assertTrue(report.signature_sha256)
        self.assertEqual({m.to[0] for m in mail.outbox}, {"dono@oficinaboa.com.br", "maria@empresa.com.br"})
        self.assertEqual(EmailDispatch.objects.filter(status="enviado").count(), 2)
        self.assertTrue(mandatory_emails_confirmed(self.att))

        # Depois de concluído: somente leitura
        self._assert_future_steps_blocked("attendances:edit", "photos:checkin", "checklist:step", "replacements:step",
                                          "photos:checkout", "signatures:step")
        self.assertEqual(self.client.get(self._url("attendances:summary")).status_code, 200)

        # A trilha de auditoria registra as passagens, sem dados pessoais
        actions = set(AuditLog.objects.filter(attendance_id=self.att.pk).values_list("action", flat=True))
        self.assertLessEqual({"attendance.created", "attendance.step_advanced", "attendance.completed",
                              "signature.registered", "report.generated"}, actions)
        audit_text = " ".join(str(entry.details) for entry in AuditLog.objects.all())
        self.assertNotIn("52998224725", audit_text)
        self.assertNotIn("Maria Souza", audit_text)
