"""Cria uma oficina de demonstração com dados 100% fictícios.

    python manage.py seed_demo

Garantias:
- Só ACRESCENTA dados: cria uma oficina própria e nunca altera, substitui ou apaga registros existentes.
  Se a conta de demonstração já existir, nada é criado de novo.
- Nomes, documentos, telefones, placas e e-mails são inventados. Os e-mails usam o domínio reservado
  `example.com` (RFC 2606), que não entrega mensagens a ninguém.
- Nenhum e-mail é enviado: o relatório do atendimento concluído entra na fila e fica pendente.
- A senha nunca é exibida. Ela vem de AUTOCHECK_DEMO_PASSWORD ou é digitada (sem eco). Sem nenhuma das
  duas, a conta fica sem senha utilizável e o comando mostra como defini-la.
- Cada etapa do atendimento passa pelos mesmos serviços e validadores usados pelas telas.
"""
import base64
import getpass
import io
import os
import sys
import unicodedata

from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.management import call_command
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from PIL import Image, ImageDraw, ImageFont

from apps.core.tenancy import workshop_scope
from apps.core.validators.documents import _mod11_digit, calculate_cnpj_check_digits

DEMO_LOGIN = "demo@example.com"
DEMO_WORKSHOP = "Oficina Demonstração AutoCheck"
PASSWORD_ENV = "AUTOCHECK_DEMO_PASSWORD"


def fake_cpf(base9):
    """CPF com dígitos verificadores válidos, montado a partir de uma base inventada."""
    digits = [int(char) for char in base9]
    for weight_start in (10, 11):
        total = sum(value * weight for value, weight in zip(digits, range(weight_start, 1, -1)))
        digits.append(_mod11_digit(total))
    return "".join(map(str, digits))


def fake_cnpj(base12):
    return base12 + calculate_cnpj_check_digits(base12)


_FONT_CANDIDATES = ("DejaVuSans.ttf", "arial.ttf", "Arial.ttf", "LiberationSans-Regular.ttf")


def _fonts():
    """(fonte grande, fonte pequena, aceita acentos). Usa uma TrueType do sistema quando existe."""
    for name in _FONT_CANDIDATES:
        try:
            return ImageFont.truetype(name, 64), ImageFont.truetype(name, 40), True
        except OSError:
            continue
    # A fonte embutida do Pillow não tem acentos: o texto vai sem eles.
    return ImageFont.load_default(size=64), ImageFont.load_default(size=40), False


def _ascii(text):
    return unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode()


def placeholder_photo(label, color):
    """Imagem JPEG gerada na hora, com o texto "FOTO DE DEMONSTRAÇÃO"."""
    image = Image.new("RGB", (1200, 800), color)
    draw = ImageDraw.Draw(image)
    font_big, font_small, accents = _fonts()
    title = "FOTO DE DEMONSTRAÇÃO"
    if not accents:
        title, label = _ascii(title), _ascii(label)
    draw.rectangle((40, 40, 1160, 760), outline=(255, 255, 255), width=6)
    draw.text((600, 340), title, fill=(255, 255, 255), font=font_big, anchor="mm")
    draw.text((600, 440), label, fill=(255, 255, 255), font=font_small, anchor="mm")
    buffer = io.BytesIO()
    image.save(buffer, format="JPEG", quality=80)
    return SimpleUploadedFile("demo.jpg", buffer.getvalue(), content_type="image/jpeg")


def drawn_signature():
    image = Image.new("RGBA", (600, 200), (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)
    points = [(40, 150), (90, 60), (130, 140), (180, 70), (230, 150), (300, 90), (360, 130), (430, 80), (540, 120)]
    draw.line(points, fill=(20, 30, 60, 255), width=5, joint="curve")
    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    return "data:image/png;base64," + base64.b64encode(buffer.getvalue()).decode()


class Command(BaseCommand):
    help = "Cria uma oficina de demonstração com clientes, veículos e atendimentos fictícios (não apaga nada)."

    def add_arguments(self, parser):
        parser.add_argument("--no-input", action="store_true", help="Não pergunta a senha (útil em scripts).")

    # ------------------------------------------------------------------ senha
    def _password(self, interactive):
        password = os.environ.get(PASSWORD_ENV, "")
        if password:
            return password
        if not interactive or not sys.stdin.isatty():
            return None
        while True:
            first = getpass.getpass("Senha da conta de demonstração (Enter para definir depois): ")
            if not first:
                return None
            if first != getpass.getpass("Repita a senha: "):
                self.stderr.write("As senhas não conferem.")
                continue
            return first

    def _apply_password(self, user, password):
        if password is None:
            user.set_unusable_password()
            return False
        try:
            validate_password(password, user)
        except ValidationError as exc:
            raise CommandError("Senha recusada: " + " ".join(exc.messages)) from exc
        user.set_password(password)
        return True

    # ------------------------------------------------------------------ dados
    def handle(self, *args, **options):
        User = get_user_model()
        if User.objects.filter(username=DEMO_LOGIN).exists():
            self.stdout.write(self.style.WARNING(
                f"A conta {DEMO_LOGIN} já existe; nada foi criado nem alterado.\n"
                f"Para trocar a senha: python manage.py changepassword {DEMO_LOGIN}"))
            return

        password = self._password(interactive=not options["no_input"])
        call_command("seed_checklist", verbosity=0)  # catálogo global; só cria o que faltar

        with transaction.atomic():
            from apps.workshop.models import WorkshopSettings

            workshop = WorkshopSettings.objects.create(
                name=DEMO_WORKSHOP, phone="(11) 3000-0000", address="Rua Fictícia, 123 — Bairro Exemplo",
                report_email="oficina-demo@example.com", google_review_url="https://g.page/r/demonstracao/review",
            )
            user = User(username=DEMO_LOGIN, email=DEMO_LOGIN, workshop=workshop)
            has_password = self._apply_password(user, password)
            user.save()
            with workshop_scope(workshop.pk):
                summary = self._populate(workshop, user)

        self.stdout.write(self.style.SUCCESS(f"Oficina de demonstração criada: {summary}."))
        self.stdout.write(f"Login: {DEMO_LOGIN}")
        if has_password:
            self.stdout.write("Senha: a que você definiu (não é exibida).")
        else:
            self.stdout.write(self.style.WARNING(
                f"A conta ainda não tem senha. Defina com: python manage.py changepassword {DEMO_LOGIN}"))
        self.stdout.write("Nenhum e-mail foi enviado: o relatório do atendimento concluído ficou na fila, pendente.")

    def _populate(self, workshop, user):
        from apps.customers.models import Customer
        from apps.employees.models import Employee
        from apps.mechanics.models import Mechanic, name_key
        from apps.vehicles.models import Vehicle

        def team(model, name):
            return model.objects.create(workshop=workshop, name=name, name_key=name_key(name))

        mechanic = team(Mechanic, "Rafael Exemplo")
        team(Mechanic, "Lucas Fictício")
        attendant = team(Employee, "Paula Demonstração")

        def customer(**data):
            obj = Customer(workshop=workshop, **data)
            obj.full_clean()
            obj.save()
            return obj

        def vehicle(owner, **data):
            obj = Vehicle(workshop=workshop, customer=owner, **data)
            obj.full_clean()
            obj.save()
            return obj

        ana = customer(person_type="pf", full_name="Ana Exemplo da Silva", cpf=fake_cpf("100200300"),
                       phone="(11) 9 9000-0001", email="ana.exemplo@example.com")
        bruno = customer(person_type="pf", full_name="Bruno Fictício Lima", cpf=fake_cpf("400500600"),
                         phone="(11) 9 9000-0002", email="bruno.ficticio@example.com")
        company = customer(person_type="pj", cnpj=fake_cnpj("998877660001"),
                           legal_name="Transportes Exemplo Ltda", trade_name="Exemplo Log",
                           contact_person="Carla Modelo", phone="(11) 3000-0003", email="frota@example.com")

        car_ana = vehicle(ana, plate="DEM1A23", brand="Fiat", model="Argo", year=2021, color="Prata")
        car_bruno = vehicle(bruno, plate="DEM2B34", brand="Volkswagen", model="Polo", year=2020, color="Branco")
        truck = vehicle(company, plate="DEM3C45", brand="Renault", model="Master", year=2019, color="Branco")

        common = {"workshop": workshop, "mechanic": mechanic, "attendant": attendant, "created_by": user}
        done = self._attendance(bruno, car_bruno, 58210, "google", common)
        self._finish(done, user)
        in_progress = self._attendance(ana, car_ana, 32740, "instagram", common)
        self._through_checkin(in_progress, user)
        self._attendance(company, truck, 140500, "indicacao", common, person_type="pj", cnpj=company.cnpj,
                         legal_name=company.legal_name, trade_name=company.trade_name,
                         contact_person=company.contact_person)
        return "3 clientes, 3 veículos, 3 atendimentos (1 concluído com PDF, 2 em andamento)"

    # ------------------------------------------------------- atendimentos
    def _attendance(self, customer, vehicle, mileage, origin, common, **extra):
        from apps.attendances import services, workflow as wf
        from apps.attendances.models import Attendance

        attendance = Attendance.objects.create(
            customer=customer, vehicle=vehicle, mileage=mileage, origin=origin,
            customer_email=customer.email, **common, **extra,
        )
        return services.advance(attendance, wf.CADASTRO, user=common["created_by"])

    def _photos(self, attendance, phase, categories, user, color):
        from apps.photos import categories as cat
        from apps.photos.services import save_photo

        for category in categories:
            save_photo(attendance, phase=phase, category=category, user=user,
                       uploaded=placeholder_photo(cat.CATEGORY_LABELS[category], color))

    def _through_checkin(self, attendance, user):
        from apps.attendances import services, workflow as wf
        from apps.photos import categories as cat

        self._photos(attendance, cat.PHASE_CHECKIN, cat.CHECKIN_REQUIRED, user, (52, 84, 122))
        return services.advance(attendance, wf.CHECKIN, user=user)

    def _finish(self, attendance, user):
        from apps.attendances import services, workflow as wf
        from apps.checklist.models import Result
        from apps.checklist.services import ensure_initialized, save_item
        from apps.mailing.services import issue_report
        from apps.photos import categories as cat
        from apps.replacements.models import Decision
        from apps.replacements.services import add_manual_service, register_decision
        from apps.signatures.services import register_signature, set_review_qr_presented
        from apps.tires.services import save_tire

        self._through_checkin(attendance, user)

        ensure_initialized(attendance)
        items = list(attendance.checklist_items.select_related("attendance").order_by("pk"))
        for index, item in enumerate(items):
            # Um item recomendado para troca (o cliente recusa); o restante OK.
            save_item(item, result=Result.SUBSTITUIR if index == 0 else Result.OK, user=user)
        for tire in attendance.tire_inspections.select_related("attendance"):
            save_tire(tire, condition=Result.OK, pressure="32", user=user)
        services.advance(attendance, wf.CHECKLIST, user=user)

        for replacement in attendance.replacements.all():
            register_decision(replacement, Decision.NAO_AUTORIZADO, user=user)
        add_manual_service(attendance, "Alinhamento e balanceamento", user=user)
        services.advance(attendance, wf.SERVICOS, user=user)

        self._photos(attendance, cat.PHASE_CHECKOUT, cat.CHECKOUT_REQUIRED, user, (46, 110, 78))
        services.advance(attendance, wf.CHECKOUT, user=user)

        set_review_qr_presented(attendance, True, user=user)
        register_signature(attendance, drawn_signature(), user=user)
        services.advance(attendance, wf.REVISAO, user=user)

        # Gera o PDF e grava os registros de envio; send_report não é chamado, então nada sai agora.
        attendance.refresh_from_db()
        report = issue_report(attendance, user=user)
        # Fora da fila automática: mesmo com SMTP configurado, o trabalhador não envia estes e-mails.
        # Ficam pendentes e só saem por "Reenviar" na tela, por decisão de quem testa.
        report.email_dispatches.update(next_attempt_at=None)
