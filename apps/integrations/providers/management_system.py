"""Integração com o sistema de gestão da oficina — AGUARDANDO DOCUMENTAÇÃO.

Nenhum endpoint, parâmetro ou formato foi inventado. Enquanto a documentação
e as credenciais não forem fornecidas, todas as operações levantam
`NotConfigured`, e o AutoCheck funciona normalmente com cadastro manual.

Quando a documentação chegar, implementar aqui (e somente aqui):
- `find_customer_by_cpf(cpf) -> PersonData`
- `find_vehicles(customer_external_id) -> list` (se a API suportar)
- `push_attendance(attendance)` (se a API permitir envio/sincronização)
Configuração esperada por variáveis de ambiente: MANAGEMENT_API_BASE_URL,
MANAGEMENT_API_TOKEN, MANAGEMENT_API_TIMEOUT (nomes provisórios, ajustáveis
conforme o método de autenticação documentado).
"""
from django.conf import settings

from .base import NotConfigured


class ManagementSystemClient:
    provider = "sistema_gestao"

    def __init__(self, base_url=None, token=None, timeout=None):
        cfg = settings.AUTOCHECK
        self.base_url = base_url if base_url is not None else cfg["MANAGEMENT_API_BASE_URL"]
        self.token = token if token is not None else cfg["MANAGEMENT_API_TOKEN"]
        self.timeout = timeout or cfg["MANAGEMENT_API_TIMEOUT"]

    @property
    def is_available(self):
        """Só ficará True quando a integração real for implementada."""
        return False

    def _not_implemented(self):
        raise NotConfigured(
            "Integração com o sistema de gestão aguardando documentação técnica e credenciais."
        )

    def find_customer_by_cpf(self, cpf):  # noqa: ARG002
        self._not_implemented()

    def find_vehicles(self, customer_external_id):  # noqa: ARG002
        self._not_implemented()

    def push_attendance(self, attendance):  # noqa: ARG002
        self._not_implemented()
