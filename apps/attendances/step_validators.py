"""Validadores de conclusão de cada etapa (regras de negócio no backend).

Cada função recebe o atendimento e devolve uma lista de mensagens de erro.
Lista vazia = etapa pode ser concluída. As telas de cada etapa (Etapas 3 a 8
do plano) usam estes mesmos validadores para mostrar o que falta.
"""
from apps.photos import categories as photo_cat

from . import workflow as wf


def validate_cadastro(att):
    errors = []
    if att.attendant_id is None:
        errors.append("Selecione o vendedor/atendente.")
    customer = att.customer
    if att.includes_person:
        if not customer.full_name:
            errors.append("Informe o nome completo do cliente.")
        if not att.cpf_not_informed and not customer.cpf:
            errors.append("Informe o CPF ou marque que o cliente não deseja informar.")
    if att.includes_company:
        if not att.legal_name:
            errors.append("Informe a razão social.")
        if not att.cnpj_not_informed and not att.cnpj:
            errors.append("Informe o CNPJ ou marque que o cliente não sabe/não deseja informar.")
    if not customer.phone:
        errors.append("Informe o telefone do cliente.")
    if att.mileage is None:
        errors.append("Informe a quilometragem.")
    if not att.origin:
        errors.append("Selecione como o cliente conheceu a loja.")
    return errors


def _photo_errors(att, phase):
    present = att.photos.filter(phase=phase).values_list("category", flat=True)
    missing = photo_cat.missing_required(phase, present)
    return [f"Falta a foto: {photo_cat.CATEGORY_LABELS[c]}." for c in missing]


def validate_checkin(att):
    return _photo_errors(att, photo_cat.PHASE_CHECKIN)


def validate_checklist(att):
    from apps.checklist.models import Result
    from apps.tires.models import TirePosition

    errors = []
    items = att.checklist_items.all()
    if not items.exists():
        errors.append("O checklist ainda não foi iniciado.")
    pending = items.filter(result="").count()
    if pending:
        errors.append(f"{pending} item(ns) do checklist sem avaliação (OK ou SUBSTITUIR).")

    tires = {t.position: t for t in att.tire_inspections.all()}
    for position, label in TirePosition.choices:
        tire = tires.get(position)
        if tire is None or not tire.condition:
            errors.append(f"Pneu {label}: informe a condição.")
            continue
        if tire.pressure_psi is None:
            errors.append(f"Pneu {label}: informe a calibragem (PSI).")
        if tire.condition == Result.SUBSTITUIR and not tire.photos.exists():
            errors.append(f"Pneu {label}: foto obrigatória para pneu a substituir.")
    return errors


def validate_servicos(att):
    from apps.replacements.models import Decision

    errors = []
    for rep in att.replacements.all():
        if rep.decision == Decision.AGUARDANDO:
            errors.append(f"{rep.component_name}: registre a decisão do cliente.")
        elif rep.decision == Decision.AUTORIZADO:
            phases = set(rep.photos.values_list("phase", flat=True))
            if photo_cat.PHASE_PART_OLD not in phases:
                errors.append(f"{rep.component_name}: falta a foto da peça antiga.")
            if photo_cat.PHASE_PART_NEW not in phases:
                errors.append(f"{rep.component_name}: falta a foto da peça nova.")
            if not rep.replaced:
                errors.append(f"{rep.component_name}: confirme a substituição realizada.")
    return errors


def validate_checkout(att):
    return _photo_errors(att, photo_cat.PHASE_CHECKOUT)


def validate_revisao(att):
    signature = getattr(att, "signature", None)
    if signature is None:
        return ["Colete a assinatura do cliente ou registre que ele não aceitou assinar."]
    if not signature.matches_current_version():
        return ["O atendimento mudou depois da assinatura. Colete a assinatura novamente."]
    return []


VALIDATORS = {
    wf.CADASTRO: validate_cadastro,
    wf.CHECKIN: validate_checkin,
    wf.CHECKLIST: validate_checklist,
    wf.SERVICOS: validate_servicos,
    wf.CHECKOUT: validate_checkout,
    wf.REVISAO: validate_revisao,
}
