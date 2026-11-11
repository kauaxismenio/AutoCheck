"""Retrato canônico do atendimento no momento da assinatura.

A assinatura (ou a recusa em assinar) guarda o hash SHA-256 deste retrato.
Se qualquer dado relevante mudar depois (checklist, decisões, serviços,
fotos), o hash deixa de bater e a etapa de revisão exige nova assinatura.
"""
import hashlib
import json

from apps.core.validators.text import to_upper


def build_snapshot(attendance):
    customer, vehicle = attendance.customer, attendance.vehicle
    return {
        "attendance": attendance.code,
        "customer": {
            "id": customer.pk, "type": attendance.person_type, "name": customer.full_name,
            "legal_name": attendance.legal_name, "trade_name": attendance.trade_name,
            "cpf": attendance.informed_cpf, "cnpj": attendance.cnpj or None, "phone": customer.phone,
        },
        "vehicle": {"id": vehicle.pk, "plate": vehicle.plate, "brand": vehicle.brand, "model": vehicle.model},
        "mileage": attendance.mileage,
        "checklist": sorted(
            [i.component_name, i.result] for i in attendance.checklist_items.all()
        ),
        "tires": sorted(
            [t.position, t.condition, str(t.pressure_psi), str(t.twi_mm)]
            for t in attendance.tire_inspections.all()
        ),
        "replacements": sorted(
            [r.component_name, r.decision, r.replaced, r.part_description] for r in attendance.replacements.all()
        ),
        "services": sorted(s.description for s in attendance.services.all()),
        "photos": sorted(p.sha256 or str(p.pk) for p in attendance.photos.all()),
    }


def with_uppercase_identifiers(snapshot):
    """Retrato gravado antes da padronização em maiúsculas, na grafia atual.

    O hash registrado nunca é reescrito. Isto só evita pedir nova assinatura
    quando a única diferença é a grafia de nome, marca e modelo.
    """
    customer, vehicle = dict(snapshot.get("customer", {})), dict(snapshot.get("vehicle", {}))
    for field in ("name", "legal_name", "trade_name"):
        customer[field] = to_upper(customer.get(field))
    for field in ("brand", "model"):
        vehicle[field] = to_upper(vehicle.get(field))
    return {**snapshot, "customer": customer, "vehicle": vehicle}


def snapshot_hash(snapshot):
    payload = json.dumps(snapshot, sort_keys=True, ensure_ascii=False, separators=(",", ":"), default=str)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()
