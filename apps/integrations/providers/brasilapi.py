"""Consulta de CNPJ na BrasilAPI (gratuita, sem credencial), sempre pelo backend.

Compatibilidade verificada com consulta real em 06/11/2026: CNPJ numérico retorna
dados; `12ABC34501DE35` (exemplo da Receita) é aceito e responde 404 "não encontrado",
ou seja, o formato alfanumérico não é recusado pelo serviço.
"""
import requests
from django.conf import settings

from .base import CompanyData, InvalidResponse, NotFound, Unavailable


class BrasilAPIClient:
    provider = "brasilapi"

    def __init__(self, base_url=None, timeout=None):
        cfg = settings.AUTOCHECK
        self.base_url = (base_url or cfg["BRASILAPI_BASE_URL"]).rstrip("/")
        self.timeout = timeout or cfg["BRASILAPI_TIMEOUT"]
        self.last_status = None

    def find_company(self, cnpj):
        """`cnpj` já validado e normalizado. Levanta um dos erros de providers.base."""
        self.last_status = None
        try:
            response = requests.get(
                f"{self.base_url}/cnpj/v1/{cnpj}", timeout=self.timeout,
                headers={"User-Agent": "AutoCheck/1.0", "Accept": "application/json"},
            )
        except requests.RequestException as exc:
            raise Unavailable(str(type(exc).__name__)) from exc

        self.last_status = response.status_code
        if response.status_code in (400, 404):
            raise NotFound()
        if response.status_code != 200:
            raise Unavailable(f"HTTP {response.status_code}")
        try:
            payload = response.json()
        except ValueError as exc:
            raise InvalidResponse("JSON inválido") from exc
        if not isinstance(payload, dict):
            raise InvalidResponse("Formato inesperado")

        legal_name = (payload.get("razao_social") or "").strip()
        if not legal_name:
            raise InvalidResponse("Resposta sem razão social")
        return CompanyData(
            cnpj=cnpj, legal_name=legal_name,
            trade_name=(payload.get("nome_fantasia") or "").strip(), source=self.provider,
        )
