"""Resumo organizado do atendimento, usado na tela de revisão, na consulta e no PDF."""
from itertools import groupby

from apps.checklist.models import Result
from apps.core.validators.documents import format_cnpj
from apps.photos import categories as cat
from apps.replacements.models import Decision


def _identification(attendance):
    customer, vehicle = attendance.customer, attendance.vehicle
    customer_rows = []
    # Somente o que foi informado neste atendimento, nunca o histórico do cadastro.
    if attendance.includes_person:
        if customer.full_name:
            customer_rows.append(("Nome", customer.full_name))
        if attendance.cpf_not_informed:
            customer_rows.append(("CPF", "Cliente não informou"))
        elif attendance.informed_cpf:
            customer_rows.append(("CPF", customer.cpf_formatted))
    if attendance.includes_company:
        if attendance.legal_name:
            customer_rows.append(("Razão Social", attendance.legal_name))
        if attendance.trade_name:
            customer_rows.append(("Nome Fantasia", attendance.trade_name))
        if attendance.contact_person:
            customer_rows.append(("Responsável", attendance.contact_person))
        if attendance.cnpj_not_informed:
            customer_rows.append(("CNPJ", "Cliente não informou"))
        elif attendance.cnpj:
            customer_rows.append(("CNPJ", format_cnpj(attendance.cnpj)))
    customer_rows.append(("Telefone", customer.phone_formatted))
    customer_rows.append(("E-mail", "Cliente optou por não informar" if attendance.email_opt_out
                          else attendance.customer_email or "Não informado"))
    vehicle_rows = [
        ("Placa", vehicle.plate_formatted), ("Marca", vehicle.brand), ("Modelo", vehicle.model),
        ("Ano", vehicle.year or "—"), ("Cor", vehicle.color or "—"),
        ("Quilometragem", f"{attendance.mileage:,} km".replace(",", ".")),
        ("Vendedor/Atendente", attendance.attendant.name if attendance.attendant else "—"),
        ("Mecânico responsável", attendance.mechanic.name),
        ("Como conheceu a loja", attendance.get_origin_display()),
    ]
    return customer_rows, vehicle_rows


def _photo_groups(photos, phase):
    order = {cat.PHASE_CHECKIN: cat.CHECKIN_REQUIRED + cat.CHECKIN_OPTIONAL,
             cat.PHASE_CHECKOUT: cat.CHECKOUT_REQUIRED}[phase]
    rank = {category: index for index, category in enumerate(order)}
    selected = sorted((p for p in photos if p.phase == phase), key=lambda p: rank.get(p.category, 99))
    return [{"photo": p, "label": cat.CATEGORY_LABELS.get(p.category, "")} for p in selected]


def _checklist(attendance):
    items = attendance.checklist_items.prefetch_related("photos").order_by("order")
    groups = []
    for name, rows in groupby(items, key=lambda item: item.category_name):
        groups.append({"name": name, "items": [
            {"name": i.component_name, "result": i.result, "label": i.get_result_display() or "Pendente",
             "is_ok": i.result == Result.OK, "notes": i.notes, "photos": list(i.photos.all())}
            for i in rows
        ]})
    return groups


def _tires(attendance):
    return [
        {"label": t.get_position_display(), "result": t.condition, "condition": t.get_condition_display() or "Pendente",
         "is_ok": t.condition == Result.OK, "psi": t.pressure_psi, "twi": t.twi_mm, "notes": t.notes,
         "photos": list(t.photos.all())}
        for t in attendance.tire_inspections.prefetch_related("photos").order_by("id")
    ]


def _replacements(attendance):
    rows = []
    for r in attendance.replacements.prefetch_related("photos"):
        photos = list(r.photos.all())
        rows.append({
            "name": r.component_name, "part": r.part_description, "decision": r.decision,
            "decision_label": r.get_decision_display(), "replaced": r.replaced, "decided_at": r.decided_at,
            "old_photos": [p for p in photos if p.phase == cat.PHASE_PART_OLD],
            "new_photos": [p for p in photos if p.phase == cat.PHASE_PART_NEW],
        })
    return rows


def build_summary(attendance):
    customer_rows, vehicle_rows = _identification(attendance)
    photos = list(attendance.photos.all())
    replacements = _replacements(attendance)
    return {
        "customer_rows": customer_rows,
        "vehicle_rows": vehicle_rows,
        "checkin_photos": _photo_groups(photos, cat.PHASE_CHECKIN),
        "checkout_photos": _photo_groups(photos, cat.PHASE_CHECKOUT),
        "checklist": _checklist(attendance),
        "tires": _tires(attendance),
        "recommended": replacements,
        "authorized": [r for r in replacements if r["decision"] == Decision.AUTORIZADO],
        "refused": [r for r in replacements if r["decision"] == Decision.NAO_AUTORIZADO],
        "pending": [r for r in replacements if r["decision"] == Decision.AGUARDANDO],
        "services": list(attendance.services.select_related("performed_by")),
    }
