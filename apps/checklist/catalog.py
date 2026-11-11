"""Catálogo inicial do checklist (carregado por `python manage.py seed_checklist`).

PROVISÓRIO: as referências visuais do WSmart ainda não foram enviadas. Esta
lista cobre as categorias exigidas na especificação e será ajustada quando as
capturas chegarem. Pneus são avaliados no módulo próprio (apps.tires).
"""

CATALOG = [
    ("suspensao", "Suspensão", [
        ("amortecedores-dianteiros", "Amortecedores dianteiros"),
        ("amortecedores-traseiros", "Amortecedores traseiros"),
        ("molas", "Molas"),
        ("coxins-batentes", "Coxins e batentes"),
        ("bandejas-bucha", "Bandejas e buchas"),
        ("pivos", "Pivôs"),
        ("bieletas", "Bieletas"),
        ("terminais-direcao", "Terminais de direção"),
        ("barras-axiais", "Barras axiais"),
        ("rolamentos-roda", "Rolamentos de roda"),
    ]),
    ("freios", "Freios", [
        ("pastilhas-dianteiras", "Pastilhas dianteiras"),
        ("discos-dianteiros", "Discos dianteiros"),
        ("freio-traseiro-lonas-pastilhas", "Lonas/pastilhas traseiras"),
        ("tambores-discos-traseiros", "Tambores/discos traseiros"),
        ("fluido-freio", "Fluido de freio"),
        ("flexiveis-freio", "Flexíveis de freio"),
        ("freio-estacionamento", "Freio de estacionamento"),
    ]),
    ("lubrificantes", "Lubrificantes e fluidos", [
        ("oleo-motor", "Óleo do motor"),
        ("oleo-cambio", "Óleo do câmbio"),
        ("fluido-direcao", "Fluido da direção hidráulica"),
        ("liquido-arrefecimento", "Líquido de arrefecimento"),
    ]),
    ("filtros", "Filtros", [
        ("filtro-oleo", "Filtro de óleo"),
        ("filtro-ar-motor", "Filtro de ar do motor"),
        ("filtro-combustivel", "Filtro de combustível"),
        ("filtro-cabine", "Filtro de cabine (ar-condicionado)"),
    ]),
    ("iluminacao", "Iluminação", [
        ("farol-baixo", "Farol baixo"),
        ("farol-alto", "Farol alto"),
        ("lanternas", "Lanternas"),
        ("luz-freio", "Luzes de freio"),
        ("setas", "Setas e pisca-alerta"),
        ("luz-re", "Luz de ré"),
        ("luz-placa", "Luz de placa"),
        ("farol-neblina", "Faróis de neblina"),
    ]),
    ("eletrica", "Componentes elétricos", [
        ("bateria", "Bateria"),
        ("alternador", "Alternador"),
        ("motor-partida", "Motor de partida"),
        ("buzina", "Buzina"),
        ("limpadores", "Palhetas e limpadores"),
        ("luzes-painel", "Luzes de advertência do painel"),
    ]),
    ("motor-transmissao", "Motor e transmissão", [
        ("correia-dentada", "Correia dentada"),
        ("correia-acessorios", "Correia de acessórios"),
        ("velas-ignicao", "Velas de ignição"),
        ("mangueiras", "Mangueiras"),
        ("radiador", "Radiador"),
        ("embreagem", "Embreagem"),
        ("homocineticas-coifas", "Homocinéticas e coifas"),
        ("escapamento", "Escapamento"),
    ]),
]
