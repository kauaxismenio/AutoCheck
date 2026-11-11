"""Geração do relatório PDF com ReportLab (Python puro, funciona no Windows)."""
import io
import logging
from xml.sax.saxutils import escape

from django.utils import timezone
from PIL import Image as PILImage
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.lib.utils import ImageReader
from reportlab.pdfgen import canvas as pdf_canvas
from reportlab.platypus import (
    CondPageBreak, Image, KeepTogether, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle,
)

from apps.signatures.models import REFUSAL_TEXT

logger = logging.getLogger("autocheck.reports")

ACCENT = colors.HexColor("#f28c18")
DARK = colors.HexColor("#1f2430")
MUTED = colors.HexColor("#6b7280")
BORDER = colors.HexColor("#d9dde3")
SOFT = colors.HexColor("#f5f6f8")
OK = colors.HexColor("#1f9d55")
DANGER = colors.HexColor("#d64545")
WARN = colors.HexColor("#b7791f")

MARGIN_X = 1.6 * cm
HEADER_HEIGHT = 2.5 * cm
FOOTER_HEIGHT = 1.6 * cm
CONTENT_WIDTH = A4[0] - 2 * MARGIN_X


def _styles():
    base = getSampleStyleSheet()["Normal"]
    return {
        "body": ParagraphStyle("body", parent=base, fontName="Helvetica", fontSize=9.5, leading=13, textColor=DARK),
        "small": ParagraphStyle("small", parent=base, fontName="Helvetica", fontSize=8, leading=10.5, textColor=MUTED),
        "caption": ParagraphStyle("caption", parent=base, fontName="Helvetica", fontSize=8, leading=10, textColor=MUTED, alignment=TA_CENTER),
        "label": ParagraphStyle("label", parent=base, fontName="Helvetica-Bold", fontSize=8.5, leading=12, textColor=MUTED),
        "title": ParagraphStyle("title", parent=base, fontName="Helvetica-Bold", fontSize=17, leading=21, textColor=DARK),
        "section": ParagraphStyle("section", parent=base, fontName="Helvetica-Bold", fontSize=12, leading=15, textColor=DARK, spaceBefore=12, spaceAfter=5),
        "subsection": ParagraphStyle("subsection", parent=base, fontName="Helvetica-Bold", fontSize=10, leading=13, textColor=DARK, spaceBefore=7, spaceAfter=3),
    }


def _text(value):
    """Todo dado digitado é escapado: o Paragraph interpreta marcação XML."""
    return escape(str(value if value is not None else ""))


def _result_cell(label, kind, styles):
    color = {"ok": OK, "danger": DANGER, "warn": WARN}[kind].hexval()[2:]
    return Paragraph(f'<font color="#{color}"><b>{_text(label)}</b></font>', styles["body"])


def _open_image(file_field):
    with file_field.storage.open(file_field.name, "rb") as stored:
        return PILImage.open(io.BytesIO(stored.read()))


def _flowable_image(file_field, max_width, max_height, *, max_pixels=1100):
    """Reduz a foto e mantém a proporção, sem cortar nem distorcer."""
    try:
        with _open_image(file_field) as image:
            image.load()
            image.thumbnail((max_pixels, max_pixels), PILImage.Resampling.LANCZOS)
            width, height = image.size
            buffer = io.BytesIO()
            image.convert("RGB").save(buffer, format="JPEG", quality=72, optimize=True)
    except (OSError, ValueError) as exc:
        logger.warning("Imagem indisponível no relatório: %s", type(exc).__name__)
        return None
    buffer.seek(0)
    scale = min(max_width / width, max_height / height)
    return Image(buffer, width=width * scale, height=height * scale)


def _section(title, styles):
    return Paragraph(_text(title), styles["section"])


def _grid_style():
    return TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("LINEBELOW", (0, 0), (-1, -1), 0.4, BORDER),
        ("TOPPADDING", (0, 0), (-1, -1), 3),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
        ("LEFTPADDING", (0, 0), (-1, -1), 5),
        ("RIGHTPADDING", (0, 0), (-1, -1), 5),
    ])


def _photo_rows(entries, styles, columns=2):
    """`entries`: lista de (arquivo, legenda). Devolve uma tabela por linha de fotos,
    para que nenhuma linha seja cortada entre páginas."""
    gap = 0.3 * cm
    cell_width = (CONTENT_WIDTH - gap * (columns - 1)) / columns
    max_height = 6.6 * cm if columns == 2 else 5 * cm
    cells = []
    for file_field, caption in entries:
        image = _flowable_image(file_field, cell_width - 0.2 * cm, max_height)
        content = image if image is not None else Paragraph("Foto indisponível", styles["caption"])
        cells.append([content, Spacer(1, 2), Paragraph(_text(caption), styles["caption"])])
    tables = []
    for start in range(0, len(cells), columns):
        row = cells[start:start + columns]
        row += [""] * (columns - len(row))
        table = Table([row], colWidths=[cell_width + gap] * columns, hAlign="LEFT")
        table.setStyle(TableStyle([
            ("ALIGN", (0, 0), (-1, -1), "CENTER"), ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("LEFTPADDING", (0, 0), (-1, -1), 0), ("RIGHTPADDING", (0, 0), (-1, -1), gap),
            ("TOPPADDING", (0, 0), (-1, -1), 3), ("BOTTOMPADDING", (0, 0), (-1, -1), 7),
        ]))
        tables.append(table)
    return tables


def _photo_section(heading, entries, styles, columns=2):
    """Mantém o título junto da primeira linha de fotos, sem título sozinho no fim da página."""
    rows = _photo_rows(entries, styles, columns)
    if not rows:
        return [KeepTogether([heading, Paragraph("Sem fotografias.", styles["small"])])]
    return [KeepTogether([heading, rows[0]]), *rows[1:]]


def _key_values(rows, styles, width):
    data = [[Paragraph(_text(label), styles["label"]), Paragraph(_text(value), styles["body"])] for label, value in rows]
    table = Table(data, colWidths=[width * 0.38, width * 0.62])
    table.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "TOP"), ("TOPPADDING", (0, 0), (-1, -1), 1.5), ("BOTTOMPADDING", (0, 0), (-1, -1), 1.5),
        ("LEFTPADDING", (0, 0), (-1, -1), 0), ("RIGHTPADDING", (0, 0), (-1, -1), 4),
    ]))
    return table


def _identification(summary, styles):
    half = (CONTENT_WIDTH - 0.6 * cm) / 2
    left = [Paragraph("Cliente", styles["subsection"]), _key_values(summary["customer_rows"], styles, half - 0.5 * cm)]
    right = [Paragraph("Veículo", styles["subsection"]), _key_values(summary["vehicle_rows"], styles, half - 0.5 * cm)]
    table = Table([[left, right]], colWidths=[half + 0.3 * cm, half + 0.3 * cm])
    table.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "TOP"), ("BOX", (0, 0), (0, 0), 0.5, BORDER), ("BOX", (1, 0), (1, 0), 0.5, BORDER),
        ("LEFTPADDING", (0, 0), (-1, -1), 8), ("RIGHTPADDING", (0, 0), (-1, -1), 8), ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
    ]))
    return table


def _checklist(summary, styles):
    story = []
    for group in summary["checklist"]:
        rows = []
        for item in group["items"]:
            name = _text(item["name"])
            if item["notes"]:
                name += f'<br/><font size="8" color="#6b7280">{_text(item["notes"])}</font>'
            rows.append([Paragraph(name, styles["body"]),
                         _result_cell(item["label"], "ok" if item["is_ok"] else "danger" if item["result"] else "warn", styles)])
        table = Table(rows, colWidths=[CONTENT_WIDTH * 0.76, CONTENT_WIDTH * 0.24])
        table.setStyle(_grid_style())
        heading = Paragraph(_text(group["name"]), styles["subsection"])
        story.append(KeepTogether([heading, table]) if len(rows) <= 12 else heading)
        if len(rows) > 12:
            story.append(table)
    return story


def _tires(summary, styles):
    header = [Paragraph(f"<b>{title}</b>", styles["small"]) for title in ("Posição", "Calibragem", "TWI", "Avaliação")]
    rows = [header]
    for tire in summary["tires"]:
        rows.append([
            Paragraph(_text(tire["label"]), styles["body"]),
            Paragraph(f'{_text(tire["psi"])} PSI' if tire["psi"] is not None else "—", styles["body"]),
            Paragraph(f'{_text(tire["twi"])} mm' if tire["twi"] is not None else "—", styles["body"]),
            _result_cell(tire["condition"], "ok" if tire["is_ok"] else "danger" if tire["result"] else "warn", styles),
        ])
    table = Table(rows, colWidths=[CONTENT_WIDTH * 0.40, CONTENT_WIDTH * 0.18, CONTENT_WIDTH * 0.18, CONTENT_WIDTH * 0.24], repeatRows=1)
    table.setStyle(_grid_style())
    photos = [(photo.image, f'Pneu: {tire["label"]}') for tire in summary["tires"] for photo in tire["photos"]]
    story = [KeepTogether([Paragraph("Pneus", styles["subsection"]), table])]
    if photos:
        story += [Spacer(1, 4), *_photo_rows(photos, styles, columns=3)]
    return story


def _decision_cell(row, styles):
    if row["replaced"]:
        return _result_cell("Autorizada e substituída", "ok", styles)
    if row["decision"] == "autorizado":
        return _result_cell("Autorizada", "warn", styles)
    if row["decision"] == "nao_autorizado":
        return _result_cell("Recusada pelo cliente", "danger", styles)
    return _result_cell("Aguardando decisão", "warn", styles)


def _recommendations(summary, styles):
    if not summary["recommended"]:
        return [Paragraph("Nenhuma substituição foi recomendada neste atendimento.", styles["body"])]
    rows = [[Paragraph("<b>Componente</b>", styles["small"]), Paragraph("<b>Autorização</b>", styles["small"])]]
    for row in summary["recommended"]:
        name = _text(row["name"])
        if row["part"]:
            name += f'<br/><font size="8" color="#6b7280">Peça: {_text(row["part"])}</font>'
        rows.append([Paragraph(name, styles["body"]), _decision_cell(row, styles)])
    table = Table(rows, colWidths=[CONTENT_WIDTH * 0.64, CONTENT_WIDTH * 0.36], repeatRows=1)
    table.setStyle(_grid_style())
    return [table]


def _services(summary, styles):
    if not summary["services"]:
        return [Paragraph("Nenhum serviço registrado.", styles["body"])]
    rows = [[Paragraph(_text(s.description), styles["body"]),
             Paragraph(_text(timezone.localtime(s.performed_at).strftime("%d/%m/%Y %H:%M") if s.performed_at else ""), styles["small"])]
            for s in summary["services"]]
    table = Table(rows, colWidths=[CONTENT_WIDTH * 0.76, CONTENT_WIDTH * 0.24])
    table.setStyle(_grid_style())
    return [table]


def _part_photos(summary, styles):
    story = []
    for row in summary["authorized"]:
        entries = [(p.image, "Peça antiga") for p in row["old_photos"]] + [(p.image, "Peça nova") for p in row["new_photos"]]
        if entries:
            story += _photo_section(Paragraph(_text(row["name"]), styles["subsection"]), entries, styles)
    return story


def _signature(attendance, styles):
    signature = getattr(attendance, "signature", None)
    if signature is None:
        return [Paragraph("Assinatura não registrada.", styles["body"])]
    when = timezone.localtime(signature.created_at).strftime("%d/%m/%Y às %H:%M")
    if signature.refused:
        content = [Paragraph("<b>CLIENTE NÃO ACEITOU ASSINAR</b>", styles["body"]), Spacer(1, 3),
                   Paragraph(_text(REFUSAL_TEXT), styles["body"])]
    else:
        image = _flowable_image(signature.image, 9 * cm, 3.4 * cm, max_pixels=1000)
        content = [image if image is not None else Paragraph("Imagem da assinatura indisponível.", styles["body"])]
    content += [Spacer(1, 4),
                Paragraph(f"Registrado em {when}. Versão assinada (SHA-256): {_text(signature.snapshot_sha256)}", styles["small"])]
    if attendance.review_qr_presented_at:
        content += [Spacer(1, 2), Paragraph(
            f"QR Code de avaliação apresentado ao cliente. {_text(attendance.review_qr_note)}", styles["small"])]
    elif attendance.review_requested:
        content += [Spacer(1, 2), Paragraph("Avaliação solicitada ao cliente.", styles["small"])]
    return content


class _NumberedCanvas(pdf_canvas.Canvas):
    """Conhece o total de páginas para escrever 'Página X de Y'."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._saved_states = []

    def showPage(self):  # noqa: N802 — nome definido pelo ReportLab
        self._saved_states.append(dict(self.__dict__))
        self._startPage()

    def save(self):
        total = len(self._saved_states)
        for state in self._saved_states:
            self.__dict__.update(state)
            self.setFont("Helvetica", 8)
            self.setFillColor(MUTED)
            self.drawRightString(A4[0] - MARGIN_X, 0.85 * cm, f"Página {self._pageNumber} de {total}")
            super().showPage()
        super().save()


def _page_decorator(attendance, workshop, generated_at):
    logo = None
    if workshop.logo:
        try:
            with _open_image(workshop.logo) as source:
                source.load()
                buffer = io.BytesIO()
                source.convert("RGBA").save(buffer, format="PNG")
            buffer.seek(0)
            logo = ImageReader(buffer)
        except (OSError, ValueError) as exc:
            logger.warning("Logotipo indisponível no relatório: %s", type(exc).__name__)

    contact = " · ".join(part for part in (
        workshop.cnpj and _formatted_cnpj(workshop.cnpj), workshop.phone and _formatted_phone(workshop.phone), workshop.address,
    ) if part)

    def draw(canvas, doc):  # noqa: ARG001
        width, height = A4
        canvas.saveState()
        top = height - 1.0 * cm
        left = MARGIN_X
        if logo is not None:
            image_width, image_height = logo.getSize()
            scale = min(2.6 * cm / image_width, 1.25 * cm / image_height)
            canvas.drawImage(logo, MARGIN_X, top - image_height * scale, image_width * scale, image_height * scale, mask="auto")
            left = MARGIN_X + image_width * scale + 0.3 * cm
        canvas.setFillColor(DARK)
        canvas.setFont("Helvetica-Bold", 11)
        canvas.drawString(left, top - 0.4 * cm, workshop.name[:60])
        canvas.setFont("Helvetica", 7.5)
        canvas.setFillColor(MUTED)
        canvas.drawString(left, top - 0.85 * cm, contact[:105])
        canvas.setFont("Helvetica-Bold", 9)
        canvas.setFillColor(DARK)
        canvas.drawRightString(width - MARGIN_X, top - 0.4 * cm, attendance.code or "")
        canvas.setFont("Helvetica", 7.5)
        canvas.setFillColor(MUTED)
        canvas.drawRightString(width - MARGIN_X, top - 0.85 * cm, "Relatório de atendimento")
        canvas.setStrokeColor(ACCENT)
        canvas.setLineWidth(1.6)
        canvas.line(MARGIN_X, height - HEADER_HEIGHT + 0.25 * cm, width - MARGIN_X, height - HEADER_HEIGHT + 0.25 * cm)
        canvas.setStrokeColor(BORDER)
        canvas.setLineWidth(0.5)
        canvas.line(MARGIN_X, FOOTER_HEIGHT - 0.25 * cm, width - MARGIN_X, FOOTER_HEIGHT - 0.25 * cm)
        canvas.setFont("Helvetica", 7.5)
        canvas.drawString(MARGIN_X, 0.85 * cm, f"Gerado pelo AutoCheck em {generated_at}")
        canvas.restoreState()

    return draw


def _formatted_cnpj(value):
    from apps.core.validators.documents import format_cnpj

    return f"CNPJ {format_cnpj(value)}"


def _formatted_phone(value):
    from apps.core.validators.phone import format_phone

    return format_phone(value)


def build_pdf(attendance, summary, workshop, *, version=1):
    styles = _styles()
    generated_at = timezone.localtime().strftime("%d/%m/%Y às %H:%M")
    buffer = io.BytesIO()
    document = SimpleDocTemplate(
        buffer, pagesize=A4, leftMargin=MARGIN_X, rightMargin=MARGIN_X,
        topMargin=HEADER_HEIGHT + 0.1 * cm, bottomMargin=FOOTER_HEIGHT + 0.1 * cm,
        title=f"Relatório {attendance.code}", author=workshop.name, subject="Relatório de atendimento AutoCheck",
    )
    completed = attendance.completed_at or timezone.now()
    story = [
        Paragraph("Relatório de inspeção e atendimento", styles["title"]),
        Paragraph(
            f"Atendimento <b>{_text(attendance.code)}</b> · Concluído em "
            f"{timezone.localtime(completed).strftime('%d/%m/%Y às %H:%M')} · Versão {version}",
            styles["small"],
        ),
        Spacer(1, 8),
        _identification(summary, styles),
        *_photo_section(_section("Fotografias de entrada", styles),
                        [(e["photo"].image, e["label"]) for e in summary["checkin_photos"]], styles),
        _section("Checklist", styles),
        *_checklist(summary, styles),
        *_tires(summary, styles),
        _section("Recomendações, autorizações e recusas", styles),
        *_recommendations(summary, styles),
        _section("Serviços executados", styles),
        *_services(summary, styles),
    ]
    part_photos = _part_photos(summary, styles)
    if part_photos:
        story += [CondPageBreak(9 * cm), _section("Peças substituídas: antigas e novas", styles), *part_photos]
    story += [
        *_photo_section(_section("Fotografias de saída", styles),
                        [(e["photo"].image, e["label"]) for e in summary["checkout_photos"]], styles),
        KeepTogether([_section("Assinatura do cliente", styles), *_signature(attendance, styles)]),
    ]
    decorate = _page_decorator(attendance, workshop, generated_at)
    document.build(story, onFirstPage=decorate, onLaterPages=decorate, canvasmaker=_NumberedCanvas)
    return buffer.getvalue()
