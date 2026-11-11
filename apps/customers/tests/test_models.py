from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.test import TestCase

from apps.core.testing import make_customer, make_vehicle
from apps.customers.models import Customer


class CustomerTests(TestCase):
    def test_documents_and_phone_are_normalized(self):
        c = make_customer(person_type="ambos", cnpj="12.abc.345/01de-35", legal_name="Oficina X Ltda")
        c.refresh_from_db()
        self.assertEqual(c.cpf, "52998224725")
        self.assertEqual(c.cnpj, "12ABC34501DE35")
        self.assertEqual(c.phone, "81990001712")
        self.assertEqual(c.cnpj_formatted, "12.ABC.345/01DE-35")

    def test_cpf_unique_but_multiple_nulls_allowed(self):
        make_customer()
        with self.assertRaises(IntegrityError), transaction.atomic():
            make_customer(full_name="Outro")
        make_customer(person_type="pf", full_name="Sem CPF 1", cpf=None, phone="8134567890")
        make_customer(person_type="pf", full_name="Sem CPF 2", cpf=None, phone="8134567891")

    def test_full_clean_rules(self):
        c = Customer(person_type="pj", phone="81990001712")
        with self.assertRaises(ValidationError) as ctx:
            c.full_clean()
        self.assertIn("legal_name", ctx.exception.message_dict)

        c = Customer(person_type="pf", full_name="Ana", cpf="123.456.789-00", phone="81990001712")
        with self.assertRaises(ValidationError) as ctx:
            c.full_clean()
        self.assertIn("cpf", ctx.exception.message_dict)

    def test_customer_with_many_vehicles(self):
        customer = make_customer()
        make_vehicle(customer, plate="ABC-1234")
        make_vehicle(customer, plate="XYZ9K88")
        self.assertEqual(customer.vehicles.count(), 2)


class VehicleTests(TestCase):
    def test_plate_normalized_and_unique(self):
        v = make_vehicle(plate="abc-1234")
        self.assertEqual(v.plate, "ABC1234")
        self.assertEqual(v.plate_formatted, "ABC-1234")
        with self.assertRaises(IntegrityError), transaction.atomic():
            make_vehicle(customer=v.customer, plate="ABC1234")
