from django.contrib.auth.models import AnonymousUser
from django.core.exceptions import ValidationError
from django.test import RequestFactory, TestCase

from apps.core.audit import log_action
from apps.core.django_validators import validate_cnpj, validate_cpf, validate_phone, validate_plate
from apps.core.models import AuditLog
from apps.core.storage import PrivateMediaStorage
from apps.core.testing import make_user


class BackendValidatorTests(TestCase):
    def test_validators_accept_masked_values(self):
        validate_cpf("529.982.247-25")
        validate_cnpj("12.ABC.345/01DE-35")
        validate_phone("(81) 9 9000-1712")
        validate_plate("ABC-1234")

    def test_validators_reject(self):
        for validator, value in ((validate_cpf, "111.111.111-11"), (validate_cnpj, "12.ABC.345/01DE-34"),
                                 (validate_phone, "1234"), (validate_plate, "AB-12")):
            with self.assertRaises(ValidationError):
                validator(value)


class PermissionTests(TestCase):
    def test_superuser_is_platform_owner_without_workshop(self):
        from apps.core.testing import make_owner

        owner = make_owner()
        self.assertTrue(owner.is_superuser)
        self.assertIsNone(owner.workshop_id)


class PrivateStorageTests(TestCase):
    def test_no_public_url(self):
        self.assertEqual(PrivateMediaStorage().url("qualquer.jpg"), "")


class AuditTests(TestCase):
    def test_log_action(self):
        user = make_user()
        request = RequestFactory().get("/", REMOTE_ADDR="10.0.0.5")
        request.user = user
        log_action("teste.acao", request=request, obj=user, extra="x")
        entry = AuditLog.objects.get()
        self.assertEqual(entry.user, user)
        self.assertEqual(entry.ip_address, "10.0.0.5")
        self.assertEqual(entry.details, {"extra": "x"})


class HealthViewTests(TestCase):
    def test_health(self):
        response = self.client.get("/saude/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["database"], True)

    def test_home_requires_login(self):
        response = self.client.get("/")
        self.assertEqual(response.status_code, 302)
