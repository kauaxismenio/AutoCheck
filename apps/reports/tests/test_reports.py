import io
from datetime import timedelta

from django.core.files.storage import default_storage
from django.core.management import call_command
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone
from PIL import Image
from pypdf import PdfReader

from apps.attendances import workflow as wf
from apps.checklist.models import Result
from apps.checklist.services import save_item
from apps.core.testing import complete_through, default_workshop, make_attendance, make_customer, make_user, make_vehicle, tiny_png
from apps.photos import categories as cat
from apps.photos.models import Photo
from apps.replacements import services as rep_services
from apps.replacements.models import Decision
from apps.reports.models import Report
from apps.reports.services import ReportNotAllowed, generate_report
from apps.signatures.models import AttendanceSignature
from apps.signatures.services import register_refusal
from apps.workshop.models import WorkshopSettings


def concluded(attendance):
    type(attendance).objects.filter(pk=attendance.pk).update(
        status=wf.STATUS_CONCLUIDO, current_step=wf.FINALIZADO,
    )
    attendance.refresh_from_db()
    return attendance


def pdf_text(report):
    with default_storage.open(report.file.name, "rb") as stored:
        reader = PdfReader(io.BytesIO(stored.read()))
    return reader, "\n".join(page.extract_text() for page in reader.pages)


class ReportBase(TestCase):
    @classmethod
    def setUpTestData(cls):
        call_command("seed_checklist", verbosity=0)

    def setUp(self):
        self.user = make_user("ana")
        self.client.force_login(self.user)
        self.att = complete_through(make_attendance(), wf.REVISAO)
        register_refusal(self.att, user=self.user)
        concluded(self.att)


class GenerationTests(ReportBase):
    def test_contains_required_content_in_every_section(self):
        workshop = default_workshop()
        workshop.name = "Oficina Boa"
        workshop.cnpj = "12ABC34501DE35"
        workshop.save()
        reader, text = pdf_text(generate_report(self.att, user=self.user))
        for expected in ("OFICINA BOA", "12.ABC.345/01DE-35", self.att.code, "JOÃO DA SILVA", "529.982.247-25",
                         "ABC1D23", "FIAT", "45.210 km", "Fotografias de entrada", "Frente do veículo", "Checklist",
                         "Suspensão", "Pastilhas dianteiras", "Dianteiro direito", "32.0 PSI",
                         "Recomendações, autorizações e recusas", "Serviços executados", "Fotografias de saída",
                         "Traseira com placa visível", "CLIENTE NÃO ACEITOU ASSINAR",
                         "optou por não registrar sua assinatura digital"):
            self.assertIn(expected, text, expected)
        self.assertGreaterEqual(len(reader.pages), 2)

    def test_pagination_header_and_footer_on_all_pages(self):
        reader, _ = pdf_text(generate_report(self.att))
        total = len(reader.pages)
        for number, page in enumerate(reader.pages, start=1):
            content = page.extract_text()
            self.assertIn(f"Página {number} de {total}", content)
            self.assertIn(self.att.code, content)
            self.assertIn("Gerado pelo AutoCheck", content)

    def test_recommendations_decisions_and_part_photos(self):
        items = list(self.att.checklist_items.select_related("attendance")[:2])
        type(self.att).objects.filter(pk=self.att.pk).update(status=wf.STATUS_EM_ANDAMENTO, current_step=wf.SERVICOS)
        self.att.refresh_from_db()
        for item in items:
            save_item(item, result=Result.SUBSTITUIR)
        authorized, refused = self.att.replacements.order_by("id")
        rep_services.register_decision(authorized, Decision.AUTORIZADO)
        rep_services.register_decision(refused, Decision.NAO_AUTORIZADO)
        for phase in (cat.PHASE_PART_OLD, cat.PHASE_PART_NEW):
            Photo.objects.create(attendance=self.att, phase=phase, replacement=authorized, image=tiny_png())
        rep_services.confirm_replacement(authorized, part_description="Marca X")
        rep_services.add_manual_service(self.att, "Alinhamento")
        concluded(self.att)

        _, text = pdf_text(generate_report(self.att))
        self.assertIn("Autorizada e substituída", text)
        self.assertIn("Recusada pelo cliente", text)
        self.assertIn("Marca X", text)
        self.assertIn("Peça antiga", text)
        self.assertIn("Peça nova", text)
        self.assertIn(f"Substituição: {authorized.component_name}", text)
        self.assertIn("Alinhamento", text)

    def test_signature_image_is_embedded(self):
        import base64

        from apps.signatures.services import register_signature

        AttendanceSignature.objects.all().delete()
        self.att = type(self.att).objects.get(pk=self.att.pk)
        image = Image.new("RGBA", (300, 100), (0, 0, 0, 0))
        image.paste((0, 0, 0, 255), (10, 40, 290, 60))
        buffer = io.BytesIO()
        image.save(buffer, format="PNG")
        register_signature(self.att, "data:image/png;base64," + base64.b64encode(buffer.getvalue()).decode())
        self.att = type(self.att).objects.get(pk=self.att.pk)
        report = generate_report(self.att)
        reader, text = pdf_text(report)
        self.assertNotIn("NÃO ACEITOU", text)
        self.assertEqual(report.signature_sha256, self.att.signature.snapshot_sha256)
        signature_page = next(p for p in reader.pages if "Assinatura do cliente" in p.extract_text())
        self.assertGreaterEqual(len(signature_page.images), 1)

    def test_user_text_with_markup_is_safe(self):
        customer = make_customer(full_name="Ana & <b>Filhos</b> <script>", cpf="111.444.777-35")
        att = make_attendance(vehicle=make_vehicle(customer, plate="XYZ9K88"), mechanic=self.att.mechanic)
        complete_through(att, wf.REVISAO)
        register_refusal(att)
        concluded(att)
        _, text = pdf_text(generate_report(att))
        self.assertIn("ANA & <B>FILHOS</B> <SCRIPT>", " ".join(text.split()))

    def test_missing_photo_file_does_not_break_report(self):
        photo = self.att.photos.first()
        default_storage.delete(photo.image.name)
        _, text = pdf_text(generate_report(self.att))
        self.assertIn("Foto indisponível", text)

    def test_logo_with_transparency_rendered(self):
        workshop = default_workshop()
        image = Image.new("RGBA", (200, 80), (242, 140, 24, 128))
        buffer = io.BytesIO()
        image.save(buffer, format="PNG")
        from django.core.files.base import ContentFile

        workshop.logo.save("logo.png", ContentFile(buffer.getvalue()), save=True)
        report = generate_report(self.att)
        self.assertGreater(report.size_bytes, 0)

    def test_versions_increment_and_keep_hash(self):
        first = generate_report(self.att)
        second = generate_report(self.att)
        self.assertEqual((first.version, second.version), (1, 2))
        self.assertEqual(len(first.sha256), 64)
        self.assertEqual(Report.objects.count(), 2)
        self.assertNotEqual(first.file.name, second.file.name)

    def test_not_allowed_before_completion(self):
        other = make_attendance(vehicle=make_vehicle(self.att.customer, plate="XYZ9K88"), mechanic=self.att.mechanic)
        with self.assertRaises(ReportNotAllowed):
            generate_report(other)


class AccessTests(ReportBase):
    def test_download_requires_login_and_matching_attendance(self):
        report = generate_report(self.att)
        url = reverse("reports:download", args=[self.att.public_id, report.pk])
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Content-Type"], "application/pdf")
        self.assertIn(report.download_name, response["Content-Disposition"])
        response.close()
        other = make_attendance(vehicle=make_vehicle(self.att.customer, plate="XYZ9K88"), mechanic=self.att.mechanic)
        self.assertEqual(self.client.get(reverse("reports:download", args=[other.public_id, report.pk])).status_code, 404)
        self.client.logout()
        self.assertEqual(self.client.get(url).status_code, 302)

    def test_generate_view_creates_new_version(self):
        url = reverse("reports:generate", args=[self.att.public_id])
        self.client.post(url)
        self.client.post(url)
        self.assertEqual(Report.objects.filter(attendance=self.att).count(), 1, "Duplo clique não cria outra versão")
        Report.objects.filter(attendance=self.att).update(generated_at=timezone.now() - timedelta(minutes=2))
        self.client.post(url)
        self.assertEqual(Report.objects.filter(attendance=self.att).count(), 2)

    def test_summary_panel_shows_download(self):
        report = generate_report(self.att)
        response = self.client.get(reverse("attendances:summary", args=[self.att.public_id]))
        self.assertContains(response, reverse("reports:download", args=[self.att.public_id, report.pk]))
