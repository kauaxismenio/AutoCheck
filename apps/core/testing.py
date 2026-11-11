"""Fábricas simples para testes (sem dependências externas)."""
import io

from django.core.files.uploadedfile import SimpleUploadedFile

PASSWORD = "senha-forte-123"


def default_workshop():
    from apps.workshop.models import WorkshopSettings

    return WorkshopSettings.objects.order_by("pk").first() or WorkshopSettings.objects.create(name="Oficina dos Testes")


def make_workshop(name="Outra Oficina", **extra):
    from apps.workshop.models import WorkshopSettings

    return WorkshopSettings.objects.create(name=name, **extra)


def make_user(username="funcionario", workshop=None, **extra):
    """Conta de acesso de uma oficina."""
    from apps.accounts.models import User

    return User.objects.create_user(username=username, password=PASSWORD, workshop=workshop or default_workshop(), **extra)


def make_owner(username="proprietario"):
    """Proprietário da plataforma: superusuário sem oficina."""
    from apps.accounts.models import User

    return User.objects.create_superuser(username=username, password=PASSWORD)


def make_mechanic(name="Rui Mecânico", workshop=None, **extra):
    from apps.mechanics.models import Mechanic, name_key

    return Mechanic.objects.get_or_create(workshop=workshop or default_workshop(), name_key=name_key(name),
                                          defaults={"name": name, **extra})[0]


def make_employee(name="Ana Funcionária", workshop=None, **extra):
    from apps.employees.models import Employee
    from apps.mechanics.models import name_key

    return Employee.objects.get_or_create(workshop=workshop or default_workshop(), name_key=name_key(name),
                                          defaults={"name": name, **extra})[0]


def make_customer(workshop=None, **extra):
    from apps.customers.models import Customer

    data = {"person_type": "pf", "full_name": "João da Silva", "cpf": "529.982.247-25", "phone": "(81) 9 9000-1712"}
    data.update(extra)
    return Customer.objects.create(workshop=workshop or default_workshop(), **data)


def make_vehicle(customer=None, **extra):
    from apps.vehicles.models import Vehicle

    data = {"customer": customer or make_customer(), "plate": "abc1d23", "brand": "Fiat", "model": "Argo", "year": 2022}
    data.update(extra)
    return Vehicle.objects.create(**data)


def make_attendance(**extra):
    from apps.attendances.models import Attendance

    vehicle = extra.pop("vehicle", None) or make_vehicle()
    customer = vehicle.customer
    workshop = customer.workshop
    data = {
        "customer": customer, "vehicle": vehicle,
        "person_type": customer.person_type, "cnpj": customer.cnpj or "", "legal_name": customer.legal_name,
        "trade_name": customer.trade_name, "contact_person": customer.contact_person,
        "attendant": extra.pop("attendant", None) or make_employee(workshop=workshop),
        "mechanic": extra.pop("mechanic", None) or make_mechanic(workshop=workshop),
        "mileage": 45210, "origin": "instagram",
    }
    data.update(extra)
    return Attendance.objects.create(**data)


def complete_through(attendance, step):
    """Preenche dados válidos de todas as etapas anteriores a `step` e posiciona o atendimento nela."""
    from apps.attendances import workflow as wf
    from apps.checklist.models import Result
    from apps.checklist.services import ensure_initialized, save_item
    from apps.photos import categories as cat
    from apps.photos.models import Photo
    from apps.tires.services import save_tire

    index = wf.step_index(step)
    if index > wf.step_index(wf.CHECKIN):
        for category in cat.CHECKIN_REQUIRED:
            Photo.objects.create(attendance=attendance, phase=cat.PHASE_CHECKIN, category=category, image=tiny_png(),
                                 sha256=f"in-{category}")
    if index > wf.step_index(wf.CHECKLIST):
        ensure_initialized(attendance)
        for item in attendance.checklist_items.select_related("attendance"):
            save_item(item, result=Result.OK)
        for tire in attendance.tire_inspections.select_related("attendance"):
            save_tire(tire, condition=Result.OK, pressure="32")
    if index > wf.step_index(wf.CHECKOUT):
        for category in cat.CHECKOUT_REQUIRED:
            Photo.objects.create(attendance=attendance, phase=cat.PHASE_CHECKOUT, category=category, image=tiny_png(),
                                 sha256=f"out-{category}")
    type(attendance).objects.filter(pk=attendance.pk).update(current_step=step)
    attendance.refresh_from_db()
    return attendance


def tiny_png(name="foto.png"):
    from PIL import Image

    buffer = io.BytesIO()
    Image.new("RGB", (4, 4), (242, 140, 24)).save(buffer, format="PNG")
    return SimpleUploadedFile(name, buffer.getvalue(), content_type="image/png")
