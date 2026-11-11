"""Contratos comuns das integrações externas.

Os resultados usam tipos simples (dataclasses) para que views e formulários
não dependam do formato de resposta de cada fornecedor.
"""
from dataclasses import dataclass, field


class IntegrationError(Exception):
    """Erro genérico de integração. `code` é exibível ao usuário de forma amigável."""

    code = "erro"
    user_message = "Não foi possível consultar o serviço agora. Preencha manualmente."


class NotConfigured(IntegrationError):
    code = "nao_configurado"
    user_message = "Integração ainda não configurada. Preencha os dados manualmente."


class NotFound(IntegrationError):
    code = "nao_encontrado"
    user_message = "Cadastro não encontrado. Preencha os dados manualmente."


class Unavailable(IntegrationError):
    code = "indisponivel"
    user_message = "Serviço de consulta indisponível no momento. Preencha manualmente."


class InvalidResponse(IntegrationError):
    code = "resposta_invalida"
    user_message = "O serviço retornou dados incompletos. Confira e complete manualmente."


@dataclass
class CompanyData:
    cnpj: str
    legal_name: str = ""
    trade_name: str = ""
    source: str = ""


@dataclass
class PersonData:
    cpf: str
    full_name: str = ""
    phone: str = ""
    email: str = ""
    external_id: str = ""
    vehicles: list = field(default_factory=list)
    source: str = ""
