"""Categorias de fotografia e regras de obrigatoriedade (Python puro)."""

# Fases em que a foto foi tirada
PHASE_CHECKIN = "checkin"
PHASE_CHECKOUT = "checkout"
PHASE_COMPONENT = "componente"   # foto opcional de item do checklist
PHASE_TIRE = "pneu"              # obrigatória se o pneu precisar de substituição
PHASE_PART_OLD = "peca_antiga"   # obrigatória se a substituição foi autorizada
PHASE_PART_NEW = "peca_nova"     # obrigatória se a substituição foi autorizada

PHASE_CHOICES = (
    (PHASE_CHECKIN, "Entrada (check-in)"),
    (PHASE_CHECKOUT, "Saída (check-out)"),
    (PHASE_COMPONENT, "Componente do checklist"),
    (PHASE_TIRE, "Pneu"),
    (PHASE_PART_OLD, "Peça antiga"),
    (PHASE_PART_NEW, "Peça nova"),
)

# Categorias (posição/tipo da foto)
FRENTE = "frente"
LATERAL_DIREITA = "lateral_direita"
LATERAL_ESQUERDA = "lateral_esquerda"
TRASEIRA = "traseira"
TRASEIRA_PLACA = "traseira_placa"
PAINEL = "painel"
ARRANHOES = "arranhoes"
AVARIAS = "avarias"
DANOS = "danos"
DETALHES = "detalhes"
GERAL = "geral"

CATEGORY_LABELS = {
    FRENTE: "Frente do veículo",
    LATERAL_DIREITA: "Lateral direita",
    LATERAL_ESQUERDA: "Lateral esquerda",
    TRASEIRA: "Traseira",
    TRASEIRA_PLACA: "Traseira com placa visível",
    PAINEL: "Painel (quilometragem)",
    ARRANHOES: "Arranhões",
    AVARIAS: "Avarias",
    DANOS: "Danos existentes",
    DETALHES: "Detalhes específicos",
    GERAL: "Geral",
}
CATEGORY_CHOICES = tuple(CATEGORY_LABELS.items())

CHECKIN_REQUIRED = (FRENTE, LATERAL_DIREITA, LATERAL_ESQUERDA, TRASEIRA, PAINEL)
CHECKIN_OPTIONAL = (ARRANHOES, AVARIAS, DANOS, DETALHES)
CHECKOUT_REQUIRED = (FRENTE, LATERAL_DIREITA, LATERAL_ESQUERDA, TRASEIRA_PLACA, PAINEL)

ALLOWED_CATEGORIES = {
    PHASE_CHECKIN: CHECKIN_REQUIRED + CHECKIN_OPTIONAL,
    PHASE_CHECKOUT: CHECKOUT_REQUIRED,
    PHASE_COMPONENT: (GERAL,),
    PHASE_TIRE: (GERAL,),
    PHASE_PART_OLD: (GERAL,),
    PHASE_PART_NEW: (GERAL,),
}


def missing_required(phase, present_categories):
    """Categorias obrigatórias ainda sem foto, na ordem de exibição."""
    required = {PHASE_CHECKIN: CHECKIN_REQUIRED, PHASE_CHECKOUT: CHECKOUT_REQUIRED}.get(phase, ())
    present = set(present_categories)
    return [category for category in required if category not in present]


def is_category_allowed(phase, category):
    return category in ALLOWED_CATEGORIES.get(phase, ())
