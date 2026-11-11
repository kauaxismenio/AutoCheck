from django.test import TestCase
from django.urls import reverse

from apps.core.testing import make_attendance, make_customer, make_user, make_vehicle
from apps.customers.models import Customer
from apps.vehicles.models import Vehicle


class CustomerViewTests(TestCase):
    def setUp(self):
        self.client.force_login(make_user("ana"))

    def test_search_by_name_document_phone_and_plate(self):
        customer = make_customer(full_name="Maria Souza")
        make_vehicle(customer, plate="ABC1D23")
        make_customer(full_name="Outro", cpf="111.444.777-35", phone="8134567890")
        for term in ("maria", "529.982.247-25", "99000", "abc1d23"):
            page = self.client.get(reverse("customers:list"), {"q": term}).context["page"]
            self.assertEqual([c.pk for c in page.object_list], [customer.pk], term)

    def test_create_normalizes(self):
        response = self.client.post(reverse("customers:create"), {
            "person_type": "pf", "full_name": "Ana", "cpf": "529.982.247-25", "phone": "(81) 3456-7890",
        })
        customer = Customer.objects.get()
        self.assertRedirects(response, reverse("customers:detail", args=[customer.pk]))
        self.assertEqual(customer.cpf, "52998224725")

    def test_duplicate_cpf_rejected_with_message(self):
        make_customer()
        response = self.client.post(reverse("customers:create"), {
            "person_type": "pf", "full_name": "Ana", "cpf": "529.982.247-25", "phone": "8134567890",
        })
        self.assertEqual(response.status_code, 200)
        self.assertEqual(Customer.objects.count(), 1)

    def test_switching_card_cannot_erase_document(self):
        customer = make_customer(person_type="ambos", cnpj="12.ABC.345/01DE-35", legal_name="Y")
        response = self.client.post(reverse("customers:edit", args=[customer.pk]), {
            "person_type": "pf", "full_name": "João", "cpf": "529.982.247-25", "phone": "81990001712",
        })
        self.assertContains(response, "Selecione")
        customer.refresh_from_db()
        self.assertEqual(customer.cnpj, "12ABC34501DE35")

    def test_workshop_account_deletes(self):
        customer = make_customer(cpf="111.444.777-35")
        self.client.force_login(make_user("oficina"))
        self.assertEqual(self.client.post(reverse("customers:delete", args=[customer.pk])).status_code, 302)
        self.assertFalse(Customer.objects.filter(pk=customer.pk).exists())

    def test_customer_with_attendance_is_protected(self):
        att = make_attendance()
        self.client.force_login(make_user("chefe"))
        self.client.post(reverse("customers:delete", args=[att.customer_id]))
        self.assertTrue(Customer.objects.filter(pk=att.customer_id).exists())

    def test_detail_lists_vehicles_and_attendances(self):
        att = make_attendance()
        response = self.client.get(reverse("customers:detail", args=[att.customer_id]))
        self.assertContains(response, att.code)
        self.assertContains(response, att.vehicle.plate_formatted)


class VehicleViewTests(TestCase):
    def setUp(self):
        self.client.force_login(make_user("ana"))

    def test_create_and_edit(self):
        customer = make_customer()
        self.client.post(reverse("vehicles:create"), {
            "customer": customer.pk, "plate": "abc-1234", "brand": "VW", "model": "Gol", "year": "2015",
        })
        vehicle = Vehicle.objects.get()
        self.assertEqual(vehicle.plate, "ABC1234")
        self.client.post(reverse("vehicles:edit", args=[vehicle.pk]), {
            "customer": customer.pk, "plate": "ABC-1234", "brand": "VW", "model": "Polo", "year": "2015",
        })
        vehicle.refresh_from_db()
        self.assertEqual(vehicle.model, "POLO")

    def test_invalid_plate_rejected(self):
        customer = make_customer()
        response = self.client.post(reverse("vehicles:create"), {"customer": customer.pk, "plate": "12", "brand": "VW", "model": "Gol"})
        self.assertContains(response, "Placa inválida")

    def test_search_by_plate(self):
        vehicle = make_vehicle()
        page = self.client.get(reverse("vehicles:list"), {"q": "abc1"}).context["page"]
        self.assertEqual(list(page.object_list), [vehicle])
