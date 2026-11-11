"""Atendimento completo pelo navegador, do login ao PDF baixado e ao e-mail registrado."""
import io
import tempfile

from django.core import mail
from PIL import Image, ImageDraw
from pypdf import PdfReader

from apps.attendances import workflow as wf
from apps.attendances.models import Attendance
from apps.mailing.models import EmailDispatch
from apps.reports.models import Report

from .base import SHOTS, BrowserTestCase
from .helpers import draw_signature, evaluate_all, open_intake, wait_saved


def sample_image(label, size, color):
    """Foto de teste com formato variado, para conferir proporção e cortes no PDF."""
    image = Image.new("RGB", size, color)
    draw = ImageDraw.Draw(image)
    draw.rectangle([10, 10, size[0] - 10, size[1] - 10], outline=(255, 255, 255), width=8)
    draw.line([(0, 0), size], fill=(255, 255, 255), width=4)
    draw.line([(0, size[1]), (size[0], 0)], fill=(255, 255, 255), width=4)
    draw.text((30, 30), label, fill=(255, 255, 255))
    handle = tempfile.NamedTemporaryFile(suffix=".jpg", delete=False)
    handle.close()
    image.save(handle.name, "JPEG")
    return handle.name


class FullFlowTests(BrowserTestCase):
    def _upload_slots(self, images):
        slots = self.page.locator("[data-photo-slot][data-required]")
        for index in range(slots.count()):
            slot = slots.nth(index)
            slot.locator("[data-photo-input]").set_input_files(images[index % len(images)])
            slot.locator("[data-photo-thumb]").first.wait_for()

    def test_complete_attendance_generates_pdf_and_sends_email(self):
        landscape = sample_image("Paisagem", (1600, 900), (60, 90, 140))
        portrait = sample_image("Retrato", (900, 1600), (140, 70, 60))
        square = sample_image("Quadrada", (1000, 1000), (60, 130, 90))
        images = [landscape, portrait, square]

        self.login()
        # Configuração real pela tela do administrador.
        self.page.goto(self.url("/configuracoes/"))
        self.page.fill("#id_name", "Oficina Teste & Filhos")
        self.page.fill("#id_cnpj", "12abc34501de35")
        self.page.fill("#id_phone", "8134567890")
        self.page.fill("#id_address", "Rua das Oficinas, 100, Cidade Exemplo - SP")
        self.page.fill("#id_report_email", "dono@oficinaboa.com.br")
        self.page.set_input_files("#id_logo", sample_image("Logo", (600, 240), (242, 140, 24)))
        self.submit("form.card button[type=submit]")
        self.assertIn("Configurações salvas", self.page.inner_text(".messages"))

        open_intake(self)
        self._upload_slots(images)
        extra = self.page.locator("[data-photo-slot]", has_text="Avarias")
        extra.locator("[data-photo-input]").set_input_files(square)
        extra.locator("[data-photo-thumb]").first.wait_for()
        self.submit()

        evaluate_all(self.page, bad_component="Pastilhas dianteiras", bad_tire="Estepe", image=portrait)
        note_row = self.page.locator(".check-row", has_text="Óleo do motor")
        note_row.locator("summary").click()
        note_row.locator("textarea").fill("Nível no mínimo & cor escura <ver>")
        note_row.locator("textarea").blur()
        wait_saved(self.page)
        self.submit()

        card = self.page.locator(".part-card", has_text="Pastilhas dianteiras")
        self.submit(card.get_by_role("button", name="Cliente autorizou"))
        card = self.page.locator(".part-card", has_text="Pastilhas dianteiras")
        for label, image in (("Peça antiga", landscape), ("Peça nova", portrait)):
            slot = card.locator("[data-photo-slot]", has_text=label)
            slot.locator("[data-photo-input]").set_input_files(image)
            slot.locator("[data-photo-thumb]").first.wait_for()
        card.locator("input[name=part_description]").fill("Marca X, código 123")
        self.submit(card.get_by_role("button", name="Confirmar substituição realizada"))
        self.submit(self.page.locator(".part-card", has_text="Pneu estepe").get_by_role("button", name="Cliente não autorizou"))
        self.page.fill("#service-description", "Alinhamento e balanceamento")
        self.submit(self.page.get_by_role("button", name="Adicionar serviço"))
        self.submit("[data-step-submit]")

        self._upload_slots(images)
        self.submit()
        self.assertIn("/revisao/", self.page.url)
        self.shot("review-page")

        draw_signature(self.page)
        self.submit("[data-step-submit]")
        self.assertIn("/resumo/", self.page.url, self.page.inner_text("main")[:800])

        attendance = Attendance.objects.get()
        self.assertEqual(attendance.status, wf.STATUS_CONCLUIDO)
        self.assertEqual(Report.objects.count(), 1)
        self.assertEqual({m.to[0] for m in mail.outbox}, {"dono@oficinaboa.com.br", "cliente@empresa.com.br"})
        self.assertTrue(all(d.is_confirmed for d in EmailDispatch.objects.all()))
        self.assertIn("aceito pelo servidor", self.page.inner_text(".messages"))
        self.shot("completed-with-report")

        with self.page.expect_download() as download:
            self.page.get_by_role("link", name="Baixar relatório PDF").click()
        path = download.value.path()
        with open(path, "rb") as stream:
            data = stream.read()
        self.assertTrue(data.startswith(b"%PDF"))
        text = "\n".join(page.extract_text() for page in PdfReader(io.BytesIO(data)).pages)
        for expected in ("OFICINA TESTE & FILHOS", "MARIA SOUZA", "Autorizada e substituída", "Recusada pelo cliente",
                         "Marca X, código 123", "Alinhamento e balanceamento", "Nível no mínimo & cor escura <ver>"):
            self.assertIn(expected, text)
        self._render_pdf(data)

    @staticmethod
    def _render_pdf(data):
        import pypdfium2

        SHOTS.mkdir(exist_ok=True)
        (SHOTS / "relatorio.pdf").write_bytes(data)
        document = pypdfium2.PdfDocument(data)
        for index in range(len(document)):
            document[index].render(scale=1.1).to_pil().save(SHOTS / f"pdf-{index + 1}.png")
        document.close()
