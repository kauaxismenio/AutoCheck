"""Envio automático na finalização, fila persistente, duplicidade, falhas e reenvio."""
import asyncio
import io
import logging
import smtplib
import socket
from datetime import timedelta
from unittest import mock

from aiosmtpd.controller import Controller
from django.core import mail
from django.core.mail.backends.locmem import EmailBackend as LocMemBackend
from django.core.management import call_command
from django.db import connection
from django.db.migrations.executor import MigrationExecutor
from django.test import TestCase, TransactionTestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from apps.attendances import workflow as wf
from apps.attendances.models import Attendance
from apps.core.testing import (
    complete_through,
    default_workshop,
    make_attendance,
    make_customer,
    make_user,
    make_vehicle,
    make_workshop,
)
from apps.mailing import services
from apps.mailing.models import DispatchStatus, EmailDispatch
from apps.mailing.tests.test_mailing import SMTP, FailingBackend, free_port
from apps.reports.models import Report
from apps.reports.services import generate_report

OFICINA = "dono@oficinaboa.com.br"
CLIENTE = "cliente@empresa.com.br"
SECRET = "senha-de-aplicativo-secreta"


class _FailsForCustomer(LocMemBackend):
    error = smtplib.SMTPDataError(451, b"tente mais tarde")

    def send_messages(self, messages):
        if messages[0].to == [CLIENTE]:
            raise self.error
        return super().send_messages(messages)


class CustomerTemporaryFailure(_FailsForCustomer):
    pass


class CustomerPermanentFailure(_FailsForCustomer):
    error = smtplib.SMTPRecipientsRefused({CLIENTE: (550, b"caixa inexistente")})


class CustomerConnectionLost(_FailsForCustomer):
    error = smtplib.SMTPServerDisconnected("Connection unexpectedly closed: timed out")


class CustomerTimeout(_FailsForCustomer):
    error = TimeoutError("timed out")


class AuthFailure(LocMemBackend):
    def open(self):
        raise smtplib.SMTPAuthenticationError(535, f"Bad credentials {SECRET}".encode())


class LeakyFailure(LocMemBackend):
    def open(self):
        raise OSError(f"falha ao usar {SECRET}")


def backend(cls):
    return override_settings(EMAIL_BACKEND=f"{__name__}.{cls.__name__}")


class FlowBase(TestCase):
    @classmethod
    def setUpTestData(cls):
        call_command("seed_checklist", verbosity=0)

    def setUp(self):
        self.user = make_user("oficina")
        self.client.force_login(self.user)
        self.workshop = default_workshop()
        self.workshop.report_email = OFICINA
        self.workshop.save()

    def ready(self, **extra):
        extra.setdefault("customer_email", CLIENTE)
        return complete_through(make_attendance(**extra), wf.REVISAO)

    def finalize(self, attendance):
        return self.client.post(reverse("signatures:step", args=[attendance.public_id]), {"refused": "on"}, follow=True)

    def worker(self):
        output = io.StringIO()
        call_command("process_email_queue", stdout=output)
        return output.getvalue()

    def make_due(self, **filters):
        EmailDispatch.objects.filter(next_attempt_at__isnull=False, **filters).update(
            next_attempt_at=timezone.now() - timedelta(seconds=1),
        )

    def age_completion(self, attendance):
        Attendance.objects.filter(pk=attendance.pk).update(completed_at=timezone.now() - services.REPORT_GRACE * 2)


class FinalizationScenarios(FlowBase):
    def test_1_with_customer_email_sends_to_both_without_clicks(self):
        attendance = self.ready()
        self.finalize(attendance)
        self.assertEqual({m.to[0] for m in mail.outbox}, {OFICINA, CLIENTE})
        rows = EmailDispatch.objects.filter(attendance=attendance)
        self.assertEqual(rows.count(), 2)
        for row in rows:
            self.assertEqual(row.status, DispatchStatus.ENVIADO)
            self.assertEqual(row.report.version, 1)
            self.assertTrue(row.message_id)
            self.assertIsNotNone(row.accepted_at)
            self.assertIsNotNone(row.last_attempt_at)
            self.assertIsNone(row.next_attempt_at)
            self.assertEqual(row.attempt_log[0]["resultado"], "aceito")
        attendance.refresh_from_db()
        self.assertFalse(attendance.report_pending)

    def test_2_without_customer_email_sends_only_to_workshop(self):
        self.finalize(self.ready(customer_email=""))
        self.assertEqual([m.to[0] for m in mail.outbox], [OFICINA])
        self.assertEqual(EmailDispatch.objects.count(), 1)

    def test_3_opt_out_sends_only_to_workshop(self):
        self.finalize(self.ready(customer_email="", email_opt_out=True))
        self.assertEqual([m.to[0] for m in mail.outbox], [OFICINA])

    def test_3b_opt_out_wins_even_with_address_on_record(self):
        self.finalize(self.ready(customer_email=CLIENTE, email_opt_out=True))
        self.assertEqual([m.to[0] for m in mail.outbox], [OFICINA])

    def test_4_same_customer_two_attendances_two_reports_and_new_sends(self):
        vehicle = make_vehicle()
        first = self.ready(vehicle=vehicle)
        self.finalize(first)
        second = self.ready(vehicle=vehicle)
        self.finalize(second)
        self.assertEqual(first.customer_id, second.customer_id)
        self.assertEqual(len(mail.outbox), 4)
        self.assertEqual(sorted(m.to[0] for m in mail.outbox), sorted([OFICINA, CLIENTE] * 2))
        first_report = Report.objects.get(attendance=first)
        second_report = Report.objects.get(attendance=second)
        self.assertNotEqual(first_report.pk, second_report.pk)
        self.assertEqual(EmailDispatch.objects.filter(report=first_report).count(), 2)
        self.assertEqual(EmailDispatch.objects.filter(report=second_report).count(), 2)
        self.assertEqual({m.attachments[0][0] for m in mail.outbox[:2]}, {first_report.download_name})
        self.assertEqual({m.attachments[0][0] for m in mail.outbox[2:]}, {second_report.download_name})

    def test_5_finalizing_twice_does_not_duplicate(self):
        attendance = self.ready()
        self.finalize(attendance)
        self.client.raise_request_exception = False
        self.finalize(attendance)
        self.assertEqual(Report.objects.filter(attendance=attendance).count(), 1)
        self.assertEqual(EmailDispatch.objects.filter(attendance=attendance).count(), 2)
        self.assertEqual(len(mail.outbox), 2)

    def test_5b_issue_and_send_called_again_do_not_duplicate(self):
        attendance = self.ready()
        self.finalize(attendance)
        report = services.issue_report(attendance)
        self.assertEqual(report.version, 1)
        self.assertEqual(services.send_report(report), [])
        self.assertEqual(len(mail.outbox), 2)

    def test_6_reloading_after_finalizing_does_not_duplicate(self):
        attendance = self.ready()
        response = self.finalize(attendance)
        self.assertEqual(response.status_code, 200)
        summary = reverse("attendances:summary", args=[attendance.public_id])
        for _ in range(3):
            self.assertEqual(self.client.get(summary).status_code, 200)
        self.client.get(reverse("signatures:step", args=[attendance.public_id]))
        self.worker()
        self.assertEqual(len(mail.outbox), 2)
        self.assertEqual(Report.objects.filter(attendance=attendance).count(), 1)

    def test_9_same_address_for_workshop_and_customer_gets_one_copy(self):
        self.finalize(self.ready(customer_email=OFICINA.upper()))
        self.assertEqual([m.to[0] for m in mail.outbox], [OFICINA])
        row = EmailDispatch.objects.get()
        self.assertEqual(row.recipient_type, "oficina")

    def test_9b_same_address_counts_as_confirmed_for_retention(self):
        attendance = self.ready(customer_email=OFICINA)
        self.finalize(attendance)
        attendance.refresh_from_db()
        self.assertTrue(services.mandatory_emails_confirmed(attendance))

    def test_9c_same_address_is_listed_once_and_screen_offers_one_resend(self):
        attendance = self.ready(customer_email=OFICINA.upper())
        self.finalize(attendance)
        attendance.refresh_from_db()
        self.assertEqual([kind for kind, _ in services.required_recipients(attendance)], ["oficina"])
        response = self.client.post(reverse("mailing:resend", args=[attendance.public_id]), {"recipient": "cliente"}, follow=True)
        self.assertContains(response, "mesmo e-mail da oficina")
        self.assertEqual(len(mail.outbox), 1)

    def test_10_correct_pdf_attached_in_each_message(self):
        vehicle = make_vehicle()
        first = self.ready(vehicle=vehicle)
        self.finalize(first)
        second = self.ready(vehicle=vehicle)
        self.finalize(second)
        for message in mail.outbox:
            name, content, mimetype = message.attachments[0]
            self.assertEqual(mimetype, "application/pdf")
            self.assertEqual(len(message.attachments), 1)
            report = next(r for r in Report.objects.all() if r.download_name == name)
            self.assertIn(report.attendance.code, message.subject)
            with report.file.open("rb") as stored:
                self.assertEqual(stored.read(), content)

    def test_finalization_never_requires_a_click_on_send_pending(self):
        attendance = self.ready()
        with mock.patch("apps.mailing.views.services.send_report") as manual_button:
            self.finalize(attendance)
        manual_button.assert_not_called()
        self.assertEqual(len(mail.outbox), 2)


class NewVersionTests(FlowBase):
    def setUp(self):
        super().setUp()
        self.attendance = self.ready()
        self.finalize(self.attendance)
        self.attendance.refresh_from_db()
        self.first = Report.objects.get(attendance=self.attendance)
        self.url = reverse("reports:generate", args=[self.attendance.public_id])
        Report.objects.update(generated_at=timezone.now() - timedelta(minutes=2))
        mail.outbox.clear()

    def test_11_new_version_is_sent_once_and_keeps_the_old_records(self):
        self.client.post(self.url)
        second = Report.objects.get(attendance=self.attendance, version=2)
        self.assertEqual({m.to[0] for m in mail.outbox}, {OFICINA, CLIENTE})
        self.assertEqual({m.attachments[0][0] for m in mail.outbox}, {second.download_name})
        self.assertEqual(EmailDispatch.objects.filter(report=self.first, status=DispatchStatus.ENVIADO).count(), 2)
        self.worker()
        self.assertEqual(len(mail.outbox), 2)

    def test_11b_double_click_does_not_create_version_or_email(self):
        self.client.post(self.url)
        self.client.post(self.url)
        self.assertEqual(Report.objects.filter(attendance=self.attendance).count(), 2)
        self.assertEqual(len(mail.outbox), 2)

    def test_11c_new_version_cancels_retries_of_the_old_one(self):
        old = EmailDispatch.objects.get(report=self.first, recipient_email=CLIENTE)
        EmailDispatch.objects.filter(pk=old.pk).update(
            status=DispatchStatus.FALHOU, accepted_at=None, next_attempt_at=timezone.now(),
        )
        self.client.post(self.url)
        mail.outbox.clear()
        self.make_due()
        self.worker()
        old.refresh_from_db()
        self.assertEqual(mail.outbox, [])
        self.assertIsNone(old.next_attempt_at)
        self.assertIn("substituído pela versão 2", old.last_error)

    def test_11d_old_version_is_never_queued_again(self):
        generate_report(self.attendance)
        self.assertEqual(services.enqueue_report(self.first), [])


class FailureScenarios(FlowBase):
    def test_7_workshop_accepted_customer_failed_retries_only_customer(self):
        attendance = self.ready()
        with backend(CustomerTemporaryFailure):
            self.finalize(attendance)
        workshop_row = EmailDispatch.objects.get(recipient_email=OFICINA)
        customer_row = EmailDispatch.objects.get(recipient_email=CLIENTE)
        self.assertEqual(workshop_row.status, DispatchStatus.ENVIADO)
        self.assertEqual(customer_row.status, DispatchStatus.FALHOU)
        self.assertIsNotNone(customer_row.next_attempt_at)
        self.assertEqual([m.to[0] for m in mail.outbox], [OFICINA])

        self.make_due()
        mail.outbox.clear()
        self.worker()
        self.assertEqual([m.to[0] for m in mail.outbox], [CLIENTE])
        workshop_row.refresh_from_db()
        customer_row.refresh_from_db()
        self.assertEqual(workshop_row.attempts, 1)
        self.assertEqual(customer_row.attempts, 2)
        self.assertEqual(customer_row.status, DispatchStatus.ENVIADO)
        self.assertEqual([e["resultado"] for e in customer_row.attempt_log], ["falha_temporaria", "aceito"])
        self.assertIn("451", customer_row.attempt_log[0]["erro"])

    def test_8_temporary_failure_is_recorded_and_retried(self):
        attendance = self.ready(customer_email="")
        with backend(FailingBackend):
            self.finalize(attendance)
        row = EmailDispatch.objects.get()
        self.assertEqual(row.status, DispatchStatus.FALHOU)
        self.assertIn("conexão recusada", row.last_error)
        self.assertEqual(self.client.get(reverse("attendances:summary", args=[attendance.public_id])).status_code, 200)
        self.make_due()
        self.worker()
        row.refresh_from_db()
        self.assertEqual(row.status, DispatchStatus.ENVIADO)
        self.assertEqual(row.last_error, "")

    def test_retry_is_not_attempted_before_the_scheduled_time(self):
        with backend(FailingBackend):
            self.finalize(self.ready(customer_email=""))
        self.worker()
        self.assertEqual(mail.outbox, [])
        self.assertEqual(EmailDispatch.objects.get().attempts, 1)

    def test_progressive_intervals_and_attempt_limit(self):
        attendance = self.ready(customer_email="")
        with backend(FailingBackend):
            self.finalize(attendance)
            row = EmailDispatch.objects.get()
            gaps = []
            for _ in range(services.MAX_ATTEMPTS - 1):
                row.refresh_from_db()
                gaps.append(row.next_attempt_at - row.last_attempt_at)
                self.make_due()
                self.worker()
            row.refresh_from_db()
            self.assertEqual(row.attempts, services.MAX_ATTEMPTS)
            self.assertEqual(row.status, DispatchStatus.FALHOU)
            self.assertIsNone(row.next_attempt_at)
            self.worker()
        row.refresh_from_db()
        self.assertEqual(row.attempts, services.MAX_ATTEMPTS, "Passou do limite: só o reenvio manual tenta de novo")
        self.assertEqual(gaps, sorted(gaps))
        self.assertEqual(len(row.attempt_log), services.MAX_ATTEMPTS)
        for gap, expected in zip(gaps, services.RETRY_DELAYS, strict=True):
            self.assertAlmostEqual(gap.total_seconds(), expected.total_seconds(), delta=5)

    def test_permanent_refusal_is_not_retried(self):
        with backend(CustomerPermanentFailure):
            self.finalize(self.ready())
        row = EmailDispatch.objects.get(recipient_email=CLIENTE)
        self.assertEqual(row.status, DispatchStatus.FALHOU)
        self.assertIsNone(row.next_attempt_at)
        self.assertIn("550", row.last_error)

    def test_lost_connection_during_send_is_uncertain_and_not_repeated(self):
        for failure in (CustomerConnectionLost, CustomerTimeout):
            with self.subTest(failure=failure.__name__):
                EmailDispatch.objects.all().delete()
                mail.outbox.clear()
                attendance = self.ready(vehicle=make_vehicle(make_customer(cpf="111.444.777-35" if failure is CustomerTimeout else "390.533.447-05"), plate="QWE1R23" if failure is CustomerTimeout else "QWE1R24"))
                with backend(failure):
                    self.finalize(attendance)
                row = EmailDispatch.objects.get(recipient_email=CLIENTE)
                self.assertEqual(row.status, DispatchStatus.INCERTO)
                self.assertFalse(row.is_confirmed)
                self.assertIsNone(row.next_attempt_at)
                self.assertTrue(row.message_id)
                self.worker()
                self.client.post(reverse("mailing:send_pending", args=[attendance.public_id]))
                self.assertEqual([m.to[0] for m in mail.outbox], [OFICINA], "Repetição cega duplicaria o e-mail")
                row.refresh_from_db()
                self.assertEqual(row.attempts, 1)
                Attendance.objects.filter(pk=attendance.pk).delete()

    def test_manual_resend_resolves_uncertain_and_opens_retention_gate(self):
        attendance = self.ready()
        with backend(CustomerConnectionLost):
            self.finalize(attendance)
        attendance.refresh_from_db()
        self.assertFalse(services.mandatory_emails_confirmed(attendance))
        response = self.client.post(reverse("mailing:resend", args=[attendance.public_id]), {"recipient": "cliente"}, follow=True)
        self.assertContains(response, "aceito pelo servidor")
        self.assertTrue(services.mandatory_emails_confirmed(attendance))
        self.assertEqual(EmailDispatch.objects.get(recipient_email=CLIENTE, is_manual_resend=False).status, DispatchStatus.INCERTO)

    def test_manual_resend_cancels_pending_automatic_retry(self):
        attendance = self.ready()
        with backend(CustomerTemporaryFailure):
            self.finalize(attendance)
        self.client.post(reverse("mailing:resend", args=[attendance.public_id]), {"recipient": "cliente"})
        self.assertEqual([m.to[0] for m in mail.outbox], [OFICINA, CLIENTE])
        self.make_due()
        self.worker()
        self.assertEqual(len(mail.outbox), 2)

    def test_accepted_is_never_sent_again_by_the_worker(self):
        self.finalize(self.ready())
        EmailDispatch.objects.update(next_attempt_at=timezone.now() - timedelta(minutes=1))
        self.worker()
        self.assertEqual(len(mail.outbox), 2)

    def test_two_workers_cannot_claim_the_same_record(self):
        with backend(FailingBackend):
            self.finalize(self.ready(customer_email=""))
        row = EmailDispatch.objects.get()
        loaded_by_a, loaded_by_b = EmailDispatch.objects.get(pk=row.pk), EmailDispatch.objects.get(pk=row.pk)
        services.deliver(loaded_by_a)
        services.deliver(loaded_by_b)
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(EmailDispatch.objects.get().attempts, 2)

    def test_failure_does_not_delete_report_or_undo_completion(self):
        attendance = self.ready()
        with backend(FailingBackend):
            self.finalize(attendance)
        attendance.refresh_from_db()
        self.assertEqual(attendance.status, wf.STATUS_CONCLUIDO)
        report = Report.objects.get(attendance=attendance)
        self.assertTrue(report.file.storage.exists(report.file.name))
        self.assertFalse(services.mandatory_emails_confirmed(attendance))


class SecretTests(FlowBase):
    @override_settings(EMAIL_HOST_PASSWORD=SECRET)
    def test_password_never_reaches_record_screen_or_log(self):
        for failure in (AuthFailure, LeakyFailure):
            with self.subTest(failure=failure.__name__):
                attendance = self.ready(vehicle=make_vehicle(make_customer(cpf="111.444.777-35" if failure is AuthFailure else "390.533.447-05"), plate="ZXC1V23" if failure is AuthFailure else "ZXC1V24"))
                with backend(failure), self.assertLogs("autocheck.mailing", level="WARNING") as logs:
                    response = self.finalize(attendance)
                self.assertNotContains(response, SECRET)
                for row in EmailDispatch.objects.filter(attendance=attendance):
                    self.assertNotIn(SECRET, row.last_error)
                    self.assertNotIn(SECRET, str(row.attempt_log))
                self.assertNotIn(SECRET, "\n".join(logs.output))
                Attendance.objects.filter(pk=attendance.pk).delete()


class WorkerRecoveryTests(FlowBase):
    def test_process_died_before_pdf_worker_generates_and_sends(self):
        attendance = self.ready()
        with mock.patch("apps.reports.services.build_pdf", side_effect=ValueError("quebrou")):
            response = self.finalize(attendance)
        self.assertContains(response, "tentará de novo automaticamente")
        attendance.refresh_from_db()
        self.assertEqual(attendance.status, wf.STATUS_CONCLUIDO)
        self.assertTrue(attendance.report_pending)
        self.age_completion(attendance)
        output = self.worker()
        self.assertIn("relatorios: 1", output)
        self.assertEqual(Report.objects.filter(attendance=attendance).count(), 1)
        self.assertEqual({m.to[0] for m in mail.outbox}, {OFICINA, CLIENTE})
        attendance.refresh_from_db()
        self.assertFalse(attendance.report_pending)

    def test_worker_waits_while_the_request_may_still_be_generating(self):
        attendance = self.ready()
        with mock.patch("apps.reports.services.build_pdf", side_effect=ValueError("quebrou")):
            self.finalize(attendance)
        self.worker()
        self.assertEqual(Report.objects.filter(attendance=attendance).count(), 0)

    def test_pdf_failure_in_worker_is_logged_and_stays_pending(self):
        broken = self.ready()
        with mock.patch("apps.reports.services.build_pdf", side_effect=ValueError("quebrou")):
            self.finalize(broken)
            self.age_completion(broken)
            with self.assertLogs("autocheck.mailing", level="ERROR"):
                output = self.worker()
        self.assertIn("relatorios_com_erro: 1", output)
        broken.refresh_from_db()
        self.assertTrue(broken.report_pending)
        self.assertFalse(services.mandatory_emails_confirmed(broken))

    def test_user_left_before_the_first_send_worker_finishes_without_duplicates(self):
        attendance = self.ready()
        with mock.patch("apps.mailing.services.deliver", side_effect=RuntimeError("processo caiu")):
            response = self.finalize(attendance)
        self.assertContains(response, "ficaram na fila")
        self.assertEqual(mail.outbox, [])
        self.assertEqual(EmailDispatch.objects.filter(status=DispatchStatus.PENDENTE).count(), 2)
        self.worker()
        self.worker()
        self.assertEqual({m.to[0] for m in mail.outbox}, {OFICINA, CLIENTE})
        self.assertEqual(len(mail.outbox), 2)

    def test_worker_stale_record_becomes_uncertain(self):
        self.finalize(self.ready())
        row = EmailDispatch.objects.get(recipient_email=CLIENTE)
        EmailDispatch.objects.filter(pk=row.pk).update(
            status=DispatchStatus.ENVIANDO, accepted_at=None, next_attempt_at=None,
            last_attempt_at=timezone.now() - services.STALE_AFTER * 2,
        )
        mail.outbox.clear()
        self.worker()
        row.refresh_from_db()
        self.assertEqual(row.status, DispatchStatus.INCERTO)
        self.assertEqual(mail.outbox, [])

    def test_legacy_pending_records_are_not_sent_automatically(self):
        attendance = self.ready()
        Attendance.objects.filter(pk=attendance.pk).update(status=wf.STATUS_CONCLUIDO, current_step=wf.FINALIZADO,
                                                           completed_at=timezone.now() - timedelta(days=3))
        attendance.refresh_from_db()
        report = generate_report(attendance)
        EmailDispatch.objects.create(attendance=attendance, report=report, recipient_type="cliente", recipient_email=CLIENTE,
                                     idempotency_key=EmailDispatch.automatic_key(report, CLIENTE))
        self.worker()
        self.assertEqual(mail.outbox, [], "Pendente antigo só sai com ação de alguém")
        self.client.post(reverse("mailing:send_pending", args=[attendance.public_id]))
        self.assertEqual({m.to[0] for m in mail.outbox}, {OFICINA, CLIENTE})

    def test_legacy_completed_attendance_without_report_is_not_generated(self):
        attendance = self.ready()
        Attendance.objects.filter(pk=attendance.pk).update(status=wf.STATUS_CONCLUIDO, current_step=wf.FINALIZADO,
                                                           completed_at=timezone.now() - timedelta(hours=1))
        self.worker()
        self.assertEqual(Report.objects.count(), 0)

    @override_settings(EMAIL_BACKEND="django.core.mail.backends.console.EmailBackend")
    def test_without_smtp_queue_waits_and_sends_after_configuring(self):
        with mock.patch("sys.stdout", new=io.StringIO()):
            self.finalize(self.ready())
            output = self.worker()
        self.assertIn("smtp_configurado: False", output)
        self.assertEqual(EmailDispatch.objects.filter(status=DispatchStatus.PENDENTE).count(), 2)
        self.assertEqual(EmailDispatch.objects.filter(attempts=0).count(), 2)

    def test_queue_goes_out_once_smtp_is_configured(self):
        with override_settings(EMAIL_BACKEND="django.core.mail.backends.console.EmailBackend"), mock.patch("sys.stdout", new=io.StringIO()):
            self.finalize(self.ready())
        self.worker()
        self.assertEqual(len(mail.outbox), 2)

    def test_worker_output_has_no_personal_data(self):
        self.finalize(self.ready())
        output = self.worker()
        self.assertNotIn("@", output)

    def test_loop_mode_stops_cleanly(self):
        output = io.StringIO()
        with mock.patch("apps.mailing.management.commands.process_email_queue.time.sleep", side_effect=KeyboardInterrupt), \
                mock.patch("apps.mailing.management.commands.process_email_queue.close_old_connections"), \
                mock.patch("apps.mailing.management.commands.process_email_queue.process_queue", return_value={}):
            call_command("process_email_queue", "--loop", stdout=output)
        self.assertIn("Fila encerrada", output.getvalue())

    def test_worker_serves_every_workshop_with_its_own_addresses(self):
        attendance = self.ready()
        self.finalize(attendance)
        other = make_workshop("Oficina Dois", report_email="dois@oficina.com.br")
        customer = make_customer(workshop=other)
        foreign = complete_through(make_attendance(vehicle=make_vehicle(customer), customer_email=""), wf.REVISAO)
        self.client.force_login(make_user("dois@oficina.com.br", workshop=other))
        with mock.patch("apps.mailing.services.deliver", side_effect=RuntimeError("processo caiu")):
            self.finalize(foreign)
        mail.outbox.clear()
        self.worker()
        self.assertEqual([m.to[0] for m in mail.outbox], ["dois@oficina.com.br"])
        self.assertIn(foreign.code, mail.outbox[0].subject)


class ProviderEventTests(FlowBase):
    def setUp(self):
        super().setUp()
        self.attendance = self.ready()
        self.finalize(self.attendance)
        self.attendance.refresh_from_db()
        self.row = EmailDispatch.objects.get(recipient_email=CLIENTE)

    def test_smtp_acceptance_is_not_reported_as_delivery(self):
        self.assertEqual(self.row.status, DispatchStatus.ENVIADO)
        self.assertEqual(self.row.get_status_display(), "Aceito pelo servidor SMTP")
        self.assertIsNone(self.row.provider_event_at)
        response = self.client.get(reverse("attendances:summary", args=[self.attendance.public_id]))
        self.assertContains(response, "Aceito pelo servidor SMTP")
        self.assertNotContains(response, "Entrega confirmada")

    def test_delivery_only_with_provider_evidence_and_after_acceptance(self):
        services.register_provider_event(self.row, DispatchStatus.ENTREGUE)
        self.row.refresh_from_db()
        self.assertTrue(self.row.is_confirmed)
        self.assertIsNotNone(self.row.provider_event_at)
        never_accepted = EmailDispatch(status=DispatchStatus.FALHOU)
        with self.assertRaises(ValueError):
            services.register_provider_event(never_accepted, DispatchStatus.ENTREGUE)

    def test_bounce_closes_retention_gate_and_does_not_resend_alone(self):
        services.register_provider_event(self.row, DispatchStatus.DEVOLVIDO, "550 caixa inexistente")
        self.attendance.refresh_from_db()
        self.assertFalse(services.mandatory_emails_confirmed(self.attendance))
        self.worker()
        self.assertEqual(len(mail.outbox), 2)

    def test_retention_blocked_while_new_version_is_open(self):
        self.assertTrue(services.mandatory_emails_confirmed(self.attendance))
        report = generate_report(self.attendance)
        services.enqueue_report(report)
        self.assertFalse(services.mandatory_emails_confirmed(self.attendance))


class _SlowHandler:
    """Recebe a mensagem e demora para responder: o cliente SMTP estoura o tempo sem saber o resultado."""

    def __init__(self):
        self.received = 0

    async def handle_DATA(self, server, session, envelope):  # noqa: ARG002,N802
        self.received += 1
        await asyncio.sleep(3)
        return "250 OK"


class _TemporaryRefusal:
    async def handle_DATA(self, server, session, envelope):  # noqa: ARG002,N802
        return "451 Tente mais tarde"


class RealSmtpFailureTests(FlowBase):
    """Backend SMTP de verdade contra um servidor local nesta máquina (nada sai para a internet)."""

    def _server(self, handler, timeout=5):
        port = free_port()
        # Nome fixo: sem ele o servidor consulta o nome da máquina e o tempo esgotaria já na conexão.
        controller = Controller(handler, hostname="127.0.0.1", port=port, server_hostname="localhost")
        controller.start()
        self.addCleanup(controller.stop)
        return override_settings(EMAIL_BACKEND=SMTP, EMAIL_HOST="127.0.0.1", EMAIL_PORT=port, EMAIL_USE_TLS=False,
                                 EMAIL_USE_SSL=False, EMAIL_HOST_USER="", EMAIL_HOST_PASSWORD="", EMAIL_TIMEOUT=timeout)

    def test_timeout_after_message_was_transmitted_is_uncertain(self):
        handler = _SlowHandler()
        logging.disable(logging.WARNING)
        self.addCleanup(logging.disable, logging.NOTSET)
        with self._server(handler, timeout=1):
            self.finalize(self.ready(customer_email=""))
        row = EmailDispatch.objects.get()
        self.assertEqual(handler.received, 1, f"A mensagem chegou ao servidor ({row.status}: {row.last_error})")
        self.assertEqual(row.status, DispatchStatus.INCERTO)
        self.assertIsNone(row.next_attempt_at)

    def test_timeout_before_any_transmission_can_be_retried(self):
        logging.disable(logging.WARNING)
        self.addCleanup(logging.disable, logging.NOTSET)
        with socket.socket() as silent:
            silent.bind(("127.0.0.1", 0))
            silent.listen()  # aceita a conexão e nunca responde: nada foi transmitido
            with override_settings(EMAIL_BACKEND=SMTP, EMAIL_HOST="127.0.0.1", EMAIL_PORT=silent.getsockname()[1], EMAIL_USE_TLS=False,
                                   EMAIL_USE_SSL=False, EMAIL_HOST_USER="", EMAIL_HOST_PASSWORD="", EMAIL_TIMEOUT=1):
                self.finalize(self.ready(customer_email=""))
        row = EmailDispatch.objects.get()
        self.assertEqual(row.status, DispatchStatus.FALHOU)
        self.assertIsNotNone(row.next_attempt_at)

    def test_temporary_refusal_schedules_retry(self):
        logging.disable(logging.WARNING)
        self.addCleanup(logging.disable, logging.NOTSET)
        with self._server(_TemporaryRefusal()):
            self.finalize(self.ready(customer_email=""))
        row = EmailDispatch.objects.get()
        self.assertEqual(row.status, DispatchStatus.FALHOU)
        self.assertIn("451", row.last_error)
        self.assertIsNotNone(row.next_attempt_at)


class LegacyKeyMigrationTests(TransactionTestCase):
    """A migração de chave não pode fazer um envio antigo parecer inexistente."""

    def test_old_keys_are_rewritten_so_records_are_not_repeated(self):
        executor = MigrationExecutor(connection)
        executor.migrate([("mailing", "0002_envio_automatico")])
        apps = executor.loader.project_state([("mailing", "0002_envio_automatico"), ("reports", "0001_initial")]).apps
        self.addCleanup(call_command, "migrate", "mailing", verbosity=0)

        call_command("seed_checklist", verbosity=0)
        workshop = default_workshop()
        workshop.report_email = OFICINA
        workshop.save()
        attendance = make_attendance(customer_email=CLIENTE)
        Attendance.objects.filter(pk=attendance.pk).update(status=wf.STATUS_CONCLUIDO)
        report = Report.objects.create(attendance=attendance, version=1, file="x.pdf", sha256="x")
        OldDispatch = apps.get_model("mailing", "EmailDispatch")
        accepted = OldDispatch.objects.create(
            attendance_id=attendance.pk, report_id=report.pk, recipient_type="oficina", recipient_email=OFICINA,
            status="enviado", accepted_at=timezone.now(), idempotency_key=f"auto:{report.pk}:oficina:{OFICINA}",
        )
        pending = OldDispatch.objects.create(
            attendance_id=attendance.pk, report_id=report.pk, recipient_type="cliente", recipient_email=CLIENTE,
            idempotency_key=f"auto:{report.pk}:cliente:{CLIENTE}",
        )
        manual = OldDispatch.objects.create(
            attendance_id=attendance.pk, report_id=report.pk, recipient_type="oficina", recipient_email=OFICINA,
            is_manual_resend=True, status="pendente", idempotency_key=f"manual:{report.pk}:oficina:abc",
        )

        call_command("migrate", "mailing", verbosity=0)

        self.assertEqual(EmailDispatch.objects.count(), 3)
        self.assertEqual(EmailDispatch.objects.get(pk=accepted.pk).idempotency_key, EmailDispatch.automatic_key(report, OFICINA))
        migrated_pending = EmailDispatch.objects.get(pk=pending.pk)
        self.assertEqual(migrated_pending.idempotency_key, EmailDispatch.automatic_key(report, CLIENTE))
        self.assertIsNone(migrated_pending.next_attempt_at)
        self.assertEqual(EmailDispatch.objects.get(pk=manual.pk).idempotency_key, f"manual:{report.pk}:oficina:abc")
