"""Definição das etapas do atendimento e regras de navegação.

Python puro: o modelo Attendance usa estas constantes e o serviço
`apps.attendances.services.workflow_guard` aplica as regras no servidor,
impedindo que alguém pule etapas alterando a URL ou o navegador.

Regras:
- As etapas seguem uma ordem fixa.
- O usuário pode abrir a etapa atual e revisitar etapas anteriores
  (enquanto o atendimento não estiver finalizado).
- Só é possível avançar uma etapa por vez, e somente quando a etapa atual
  foi validada pelo backend (cada módulo fornece seu validador).
- Atendimento finalizado ou cancelado é somente leitura.
"""

CADASTRO = "cadastro"
CHECKIN = "checkin"
CHECKLIST = "checklist"
SERVICOS = "servicos"
CHECKOUT = "checkout"
REVISAO = "revisao"
FINALIZADO = "finalizado"

STEPS = (CADASTRO, CHECKIN, CHECKLIST, SERVICOS, CHECKOUT, REVISAO, FINALIZADO)

STEP_LABELS = {
    CADASTRO: "Cliente e veículo",
    CHECKIN: "Check-in",
    CHECKLIST: "Checklist",
    SERVICOS: "Serviços e peças",
    CHECKOUT: "Check-out",
    REVISAO: "Revisão e assinatura",
    FINALIZADO: "Finalizado",
}

STEP_CHOICES = tuple((step, STEP_LABELS[step]) for step in STEPS)

# Etapas em que o usuário efetivamente trabalha (FINALIZADO é estado terminal).
WORK_STEPS = STEPS[:-1]

# Status do atendimento (independente da etapa).
STATUS_EM_ANDAMENTO = "em_andamento"
STATUS_CONCLUIDO = "concluido"
STATUS_CANCELADO = "cancelado"
STATUS_CHOICES = (
    (STATUS_EM_ANDAMENTO, "Em andamento"),
    (STATUS_CONCLUIDO, "Concluído"),
    (STATUS_CANCELADO, "Cancelado"),
)


class WorkflowError(Exception):
    """Tentativa de acessar ou avançar etapa de forma não permitida."""


def step_index(step):
    try:
        return STEPS.index(step)
    except ValueError as exc:
        raise WorkflowError(f"Etapa desconhecida: {step!r}") from exc


def next_step(step):
    index = step_index(step)
    if index >= len(STEPS) - 1:
        raise WorkflowError("O atendimento já está na última etapa.")
    return STEPS[index + 1]


def can_open(current_step, target_step, status=STATUS_EM_ANDAMENTO):
    """Pode abrir a etapa `target_step` para edição?"""
    if status != STATUS_EM_ANDAMENTO:
        return False
    if target_step == FINALIZADO:
        return False
    return step_index(target_step) <= step_index(current_step)


def ensure_can_advance(current_step, from_step, status=STATUS_EM_ANDAMENTO):
    """Valida que o avanço parte da etapa atual (sem pular etapas).

    Retorna a próxima etapa. A validação do conteúdo da etapa (fotos,
    checklist completo etc.) é responsabilidade do módulo correspondente e
    deve ser chamada ANTES deste avanço.
    """
    if status != STATUS_EM_ANDAMENTO:
        raise WorkflowError("Atendimento não está em andamento.")
    if from_step != current_step:
        raise WorkflowError(
            "Só é possível avançar a partir da etapa atual do atendimento."
        )
    return next_step(current_step)


def progress(current_step):
    """Lista para o indicador de progresso: (etapa, rótulo, estado)."""
    current = step_index(current_step)
    items = []
    for index, step in enumerate(WORK_STEPS):
        if current_step == FINALIZADO or index < current:
            state = "done"
        elif index == current:
            state = "current"
        else:
            state = "pending"
        items.append((step, STEP_LABELS[step], state))
    return items
