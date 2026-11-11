"""Comando seed_demo: dados fictícios, sem tocar no que já existe e sem enviar e-mails."""
import io
import os
from unittest import mock

from django.core import mail
from django.core.management import call_command
from django.test import TestCase

from apps.accounts.models import User
from apps.attendances import workflow as wf
from apps.attendances.models import Attendance
from apps.core.management.commands.seed_demo import DEMO_LOGIN, PASSWORD_ENV
from apps.core.tenancy import workshop_scope
from apps.core.testing import make_attendance
from apps.customers.models import Customer
from apps.mailing.models import EmailDispatch
from apps.mailing.services import process_queue
from apps.reports.models import Report

DEMO_PASSWORD = "Demo-Teste-Local-2026"


def run_seed(password=DEMO_PASSWORD):
    out = io.StringIO()
    env = {PASSWORD_ENV: password} if password else {}
    with mock.patch.dict(os.environ, env, clear=False):
        if not password:
            os.environ.pop(PASSWORD_ENV, None)
        call_command("seed_demo", "--no-input", stdout=out)
    return out.getvalue()


class SeedDemoTests(TestCase):
    def test_creates_isolated_workshop_without_touching_existing_data(self):
        existing = make_attendance()
        before = (Customer.objects.count(), Attendance.objects.count(), existing.customer.full_name)

        output = run_seed()

        account = User.objects.get(username=DEMO_LOGIN)
        self.assertTrue(account.check_password(DEMO_PASSWORD))
        self.assertNotIn(DEMO_PASSWORD, output, "A senha nunca aparece na saída")
        workshop = account.workshop
        self.assertNotEqual(workshop.pk, existing.workshop_id)
        existing.refresh_from_db()
        self.assertEqual(existing.customer.full_name, before[2])
        self.assertEqual(Customer.objects.count(), before[0] + 3)
        self.assertEqual(Attendance.objects.count(), before[1] + 3)

        with workshop_scope(workshop.pk):
            demo = Attendance.objects.filter(workshop=workshop)
            self.assertEqual(demo.filter(status=wf.STATUS_CONCLUIDO).count(), 1)
            self.assertEqual(demo.filter(status=wf.STATUS_EM_ANDAMENTO).count(), 2)
            done = demo.get(status=wf.STATUS_CONCLUIDO)
            self.assertTrue(Report.objects.filter(attendance=done).exists())
            self.assertTrue(all(c.email.endswith("@example.com") for c in Customer.objects.filter(workshop=workshop)))

    def test_no_email_is_sent_even_when_the_queue_runs(self):
        run_seed()
        dispatches = EmailDispatch.objects.all()
        self.assertEqual(dispatches.count(), 2)
        self.assertFalse(dispatches.filter(next_attempt_at__isnull=False).exists())
        process_queue()
        self.assertEqual(len(mail.outbox), 0)
        self.assertFalse(EmailDispatch.objects.filter(accepted_at__isnull=False).exists())

    def test_running_twice_creates_nothing_new(self):
        run_seed()
        counts = (User.objects.count(), Customer.objects.count(), Attendance.objects.count())
        output = run_seed()
        self.assertIn("já existe", output)
        self.assertEqual(counts, (User.objects.count(), Customer.objects.count(), Attendance.objects.count()))

    def test_without_password_the_account_cannot_log_in_yet(self):
        output = run_seed(password=None)
        self.assertFalse(User.objects.get(username=DEMO_LOGIN).has_usable_password())
        self.assertIn("changepassword", output)

    def test_weak_password_is_refused_before_creating_anything(self):
        with self.assertRaises(Exception):
            run_seed(password="123")
        self.assertFalse(User.objects.filter(username=DEMO_LOGIN).exists())
