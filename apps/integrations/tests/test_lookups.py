"""As respostas HTTP da BrasilAPI são substituídas por dublês SOMENTE nos testes.

O comportamento real do serviço foi conferido com consulta verdadeira (ver
docstring de providers/brasilapi.py) e pelo teste de integração opcional abaixo.
"""
import os
from unittest import mock, skipUnless

import requests
from django.test import SimpleTestCase, TestCase
from django.urls import reverse

from apps.core.testing import make_customer, make_user, make_vehicle
from apps.integrations.models import ExternalCallLog
from apps.integrations.providers.base import InvalidResponse, NotFound, Unavailable
from apps.integrations.providers.brasilapi import BrasilAPIClient

CNPJ = "12ABC34501DE35"


def fake_response(status=200, payload=None, json_error=False):
    response = mock.Mock(status_code=status)
    if json_error:
        response.json.side_effect = ValueError()
    else:
        response.json.return_value = payload
    return response


class BrasilAPIClientTests(SimpleTestCase):
    def _find(self, **kwargs):
        with mock.patch("requests.get", **kwargs) as patched:
            result = BrasilAPIClient().find_company(CNPJ)
        return result, patched

    def test_success_maps_fields_and_keeps_alphanumeric_in_url(self):
        result, patched = self._find(return_value=fake_response(payload={"razao_social": "Oficina X", "nome_fantasia": None}))
        self.assertEqual((result.legal_name, result.trade_name), ("Oficina X", ""))
        self.assertTrue(patched.call_args.args[0].endswith(f"/cnpj/v1/{CNPJ}"))
        self.assertIn("timeout", patched.call_args.kwargs)

    def test_not_found(self):
        with self.assertRaises(NotFound):
            self._find(return_value=fake_response(404))

    def test_server_error_is_unavailable(self):
        with self.assertRaises(Unavailable):
            self._find(return_value=fake_response(500))

    def test_connection_failure_is_unavailable(self):
        for error in (requests.ConnectionError(), requests.Timeout()):
            with self.assertRaises(Unavailable):
                self._find(side_effect=error)

    def test_incomplete_response(self):
        with self.assertRaises(InvalidResponse):
            self._find(return_value=fake_response(payload={"razao_social": ""}))

    def test_invalid_json(self):
        with self.assertRaises(InvalidResponse):
            self._find(return_value=fake_response(json_error=True))


class LookupViewTests(TestCase):
    def setUp(self):
        self.client.force_login(make_user("ana"))

    def test_requires_login(self):
        self.client.logout()
        self.assertEqual(self.client.get(reverse("integrations:cnpj"), {"cnpj": CNPJ}).status_code, 302)

    def test_invalid_cnpj_never_calls_service(self):
        with mock.patch("requests.get") as patched:
            response = self.client.get(reverse("integrations:cnpj"), {"cnpj": "12.ABC.345/01DE-34"})
        self.assertEqual(response.status_code, 400)
        patched.assert_not_called()

    def test_cnpj_found_is_logged_without_document(self):
        with mock.patch("requests.get", return_value=fake_response(payload={"razao_social": "Oficina X", "nome_fantasia": "X"})):
            response = self.client.get(reverse("integrations:cnpj"), {"cnpj": "12.ABC.345/01DE-35"})
        self.assertEqual(response.json()["legal_name"], "Oficina X")
        log = ExternalCallLog.objects.get()
        self.assertTrue(log.success)
        self.assertNotIn(CNPJ, log.query_hash)

    def test_cnpj_failures_return_friendly_message(self):
        for status, code in ((404, 404), (500, 503)):
            with mock.patch("requests.get", return_value=fake_response(status)):
                response = self.client.get(reverse("integrations:cnpj"), {"cnpj": CNPJ})
            self.assertEqual(response.status_code, code)
            self.assertIn("manual", response.json()["message"].lower())

    def test_cnpj_in_customer_history_still_uses_only_brasilapi(self):
        make_customer(person_type="ambos", full_name="Pessoa Do Historico", cnpj=CNPJ, legal_name="Razão Antiga",
                      trade_name="Fantasia Antiga", email="historico@empresa.com.br")
        answer = {"razao_social": "Razão Da Consulta", "nome_fantasia": "Fantasia Da Consulta"}
        with mock.patch("requests.get", return_value=fake_response(payload=answer)) as patched:
            data = self.client.get(reverse("integrations:cnpj"), {"cnpj": CNPJ}).json()
        patched.assert_called_once()
        self.assertEqual((data["legal_name"], data["trade_name"]), ("Razão Da Consulta", "Fantasia Da Consulta"))
        for field in ("full_name", "phone", "email", "cpf", "contact_person"):
            self.assertNotIn(field, data)

    def test_cpf_with_cnpj_history_returns_only_personal_data(self):
        make_customer(person_type="ambos", full_name="Maria", cnpj=CNPJ, legal_name="Razão Antiga",
                      trade_name="Fantasia Antiga", contact_person="Rui")
        with mock.patch("requests.get") as patched:
            response = self.client.get(reverse("integrations:cpf"), {"cpf": "529.982.247-25"})
        data = response.json()
        patched.assert_not_called()
        self.assertEqual(data["full_name"], "MARIA")
        for field in ("cnpj", "legal_name", "trade_name", "contact_person"):
            self.assertNotIn(field, data)
        for leaked in (CNPJ, "RAZÃO ANTIGA", "FANTASIA ANTIGA", "Rui"):
            self.assertNotIn(leaked, response.content.decode())

    def test_cpf_local_match(self):
        make_customer(full_name="Maria")
        response = self.client.get(reverse("integrations:cpf"), {"cpf": "529.982.247-25"})
        self.assertEqual(response.json()["full_name"], "MARIA")

    def test_cpf_unknown_is_not_simulated(self):
        response = self.client.get(reverse("integrations:cpf"), {"cpf": "529.982.247-25"})
        data = response.json()
        self.assertFalse(data["found"])
        self.assertEqual(data["code"], "nao_configurado")

    def test_plate_lookup(self):
        make_vehicle(plate="ABC1D23", brand="Fiat")
        data = self.client.get(reverse("integrations:plate"), {"placa": "abc1d23"}).json()
        self.assertTrue(data["found"])
        self.assertEqual(data["brand"], "FIAT")
        self.assertFalse(self.client.get(reverse("integrations:plate"), {"placa": "XYZ9K88"}).json()["found"])


@skipUnless(os.environ.get("RUN_REAL_API") == "1", "Consulta real: defina RUN_REAL_API=1")
class BrasilAPIRealTests(SimpleTestCase):
    def test_public_company(self):
        company = BrasilAPIClient().find_company("00000000000191")
        self.assertIn("BANCO DO BRASIL", company.legal_name)

    def test_alphanumeric_format_is_understood(self):
        with self.assertRaises(NotFound):
            BrasilAPIClient().find_company(CNPJ)
