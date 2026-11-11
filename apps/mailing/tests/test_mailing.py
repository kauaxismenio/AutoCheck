import email
import io
import socket
from unittest import mock

from aiosmtpd.controller import Controller
from django.core import mail
from django.core.mail.backends.locmem import EmailBackend as LocMemBackend
from django.core.management import call_command
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from apps.attendances import workflow as wf
from apps.core.testing import complete_through, default_workshop, make_attendance, make_user
from apps.mailing import services
from apps.mailing.models import DispatchStatus, EmailDispatch
from apps.reports.services import generate_report
from apps.signatures.services import register_refusal
from apps.workshop.models import WorkshopSettings

OFICINA = "dono@oficinaboa.com.br"
CLIENTE = "cliente@empresa.com.br"
SMTP = "django.core.mail.backends.smtp.EmailBackend"
CONSOLE = "django.core.mail.backends.console.EmailBackend"


class FailingBackend(LocMemBackend):
    """Não consegue nem conectar: é certo que nada foi transmitido."""

    def open(self):
        raise OSError("conexão recusada")

    def send_messages(self, messages):
        raise OSError("conexão recusada")


class SilentBackend(LocMemBackend):
    def send_messages(self, messages):
        return 0


class MailBase(TestCase):
    @classmethod
    def setUpTestData(cls):
        call_command("seed_checklist", verbosity=0)

    def setUp(self):
        self.user = make_user("ana")
        self.client.force_login(self.user)
        workshop = default_workshop()
        workshop.report_email = OFICINA
        workshop.save()
        self.att = complete_through(make_attendance(customer_email=CLIENTE), wf.REVISAO)
        register_refusal(self.att, user=self.user)
        type(self.att).objects.filter(pk=self.att.pk).update(status=wf.STATUS_CONCLUIDO, current_step=wf.FINALIZADO)
        self.att.refresh_from_db()
        self.report = generate_report(self.att)


class AutomaticSendTests(MailBase):
    def test_sends_to_workshop_and_customer_with_pdf(self):
        results = services.send_report(self.report)
        self.assertEqual(len(mail.outbox), 2)
        self.assertEqual({m.to[0] for m in mail.outbox}, {OFICINA, CLIENTE})
        attachment = mail.outbox[0].attachments[0]
        self.assertEqual(attachment[0], self.report.download_name)
        self.assertEqual(attachment[2], "application/pdf")
        self.assertTrue(attachment[1].startswith(b"%PDF"))
        for dispatch in results:
            self.assertTrue(dispatch.is_confirmed)
            self.assertEqual(dispatch.attempts, 1)
            self.assertIsNotNone(dispatch.accepted_at)
            self.assertTrue(dispatch.message_id)

    def test_opt_out_customer_gets_nothing(self):
        type(self.att).objects.filter(pk=self.att.pk).update(email_opt_out=True, customer_email="")
        self.report.attendance.refresh_from_db()
        services.send_report(self.report)
        self.assertEqual([m.to[0] for m in mail.outbox], [OFICINA])

    def test_customer_without_email_gets_nothing(self):
        type(self.att).objects.filter(pk=self.att.pk).update(customer_email="")
        self.report.attendance.refresh_from_db()
        services.send_report(self.report)
        self.assertEqual(len(mail.outbox), 1)

    def test_no_duplicate_on_repeated_call(self):
        services.send_report(self.report)
        services.send_report(self.report)
        self.assertEqual(len(mail.outbox), 2)
        self.assertEqual(EmailDispatch.objects.count(), 2)

    def test_new_report_version_sends_only_the_new_version(self):
        services.send_report(self.report)
        second = generate_report(self.att)
        self.assertEqual(len(services.send_report(second)), 2)
        self.assertEqual(len(mail.outbox), 4)
        self.assertEqual({m.attachments[0][0] for m in mail.outbox[2:]}, {second.download_name})
        self.assertEqual(services.send_report(self.report), [], "Versão antiga não volta para a fila")
        self.assertEqual(len(mail.outbox), 4)

    def test_two_concurrent_workers_cannot_send_same_record(self):
        dispatch = EmailDispatch.objects.create(
            attendance=self.att, report=self.report, recipient_type="oficina", recipient_email=OFICINA,
            idempotency_key="x", status=DispatchStatus.ENVIANDO,
        )
        services.deliver(dispatch)
        self.assertEqual(len(mail.outbox), 0)
        self.assertEqual(dispatch.attempts, 0)


class FailureTests(MailBase):
    @override_settings(EMAIL_BACKEND="apps.mailing.tests.test_mailing.FailingBackend")
    def test_failure_is_recorded_and_not_confirmed(self):
        results = services.send_report(self.report)
        for dispatch in results:
            self.assertEqual(dispatch.status, DispatchStatus.FALHOU)
            self.assertFalse(dispatch.is_confirmed)
            self.assertIsNone(dispatch.accepted_at)
            self.assertIn("conexão recusada", dispatch.last_error)
            self.assertEqual(dispatch.attempts, 1)

    @override_settings(EMAIL_BACKEND="apps.mailing.tests.test_mailing.SilentBackend")
    def test_function_returning_without_acceptance_is_not_sent(self):
        for dispatch in services.send_report(self.report):
            self.assertEqual(dispatch.status, DispatchStatus.FALHOU)
            self.assertFalse(dispatch.is_confirmed)

    def test_retry_after_failure_uses_same_record(self):
        with override_settings(EMAIL_BACKEND="apps.mailing.tests.test_mailing.FailingBackend"):
            services.send_report(self.report)
        results = services.send_report(self.report)
        self.assertEqual(EmailDispatch.objects.count(), 2)
        for dispatch in results:
            self.assertTrue(dispatch.is_confirmed)
            self.assertEqual(dispatch.attempts, 2)
            self.assertEqual(dispatch.last_error, "")

    @override_settings(EMAIL_BACKEND=CONSOLE)
    def test_console_backend_never_counts_as_sent(self):
        with mock.patch("sys.stdout", new=io.StringIO()) as out:
            results = services.send_report(self.report)
        self.assertEqual(out.getvalue(), "")
        for dispatch in results:
            self.assertEqual(dispatch.status, DispatchStatus.PENDENTE)
            self.assertIn("SMTP não configurado", dispatch.last_error)
            self.assertEqual(dispatch.attempts, 0)
        self.assertFalse(services.mandatory_emails_confirmed(self.att))

    @override_settings(EMAIL_BACKEND=SMTP, EMAIL_HOST="")
    def test_smtp_without_host_is_not_configured(self):
        self.assertFalse(services.smtp_configured())

    def test_interrupted_send_becomes_uncertain_and_is_not_repeated(self):
        dispatch = EmailDispatch.objects.create(
            attendance=self.att, report=self.report, recipient_type="oficina", recipient_email=OFICINA,
            idempotency_key=EmailDispatch.automatic_key(self.report, OFICINA),
            status=DispatchStatus.ENVIANDO, last_attempt_at=timezone.now() - services.STALE_AFTER * 2,
        )
        services.send_report(self.report)
        dispatch.refresh_from_db()
        self.assertEqual(dispatch.status, DispatchStatus.INCERTO)
        self.assertFalse(dispatch.is_confirmed)
        self.assertEqual([m.to[0] for m in mail.outbox], [CLIENTE])


class ResendTests(MailBase):
    def setUp(self):
        super().setUp()
        self.url = reverse("mailing:resend", args=[self.att.public_id])

    def test_resend_blocked_for_a_minute_after_sending(self):
        services.send_report(self.report)
        mail.outbox.clear()
        response = self.client.post(self.url, {"recipient": "oficina"}, follow=True)
        self.assertContains(response, "acabou de receber")
        self.assertEqual(len(mail.outbox), 0)

    def test_manual_resend_creates_new_record(self):
        services.send_report(self.report)
        EmailDispatch.objects.update(created_at=timezone.now() - services.RESEND_GUARD * 2)
        mail.outbox.clear()
        self.client.post(self.url, {"recipient": "cliente"})
        self.assertEqual([m.to[0] for m in mail.outbox], [CLIENTE])
        manual = EmailDispatch.objects.get(is_manual_resend=True)
        self.assertEqual(manual.requested_by, self.user)
        self.assertTrue(manual.is_confirmed)

    def test_resend_to_opted_out_customer_refused(self):
        type(self.att).objects.filter(pk=self.att.pk).update(email_opt_out=True, customer_email="")
        response = self.client.post(self.url, {"recipient": "cliente"}, follow=True)
        self.assertContains(response, "optou por não receber")
        self.assertEqual(len(mail.outbox), 0)

    def test_send_pending_view(self):
        response = self.client.post(reverse("mailing:send_pending", args=[self.att.public_id]), follow=True)
        self.assertContains(response, "aceito pelo servidor")
        self.assertEqual(len(mail.outbox), 2)

    def test_requires_login(self):
        self.client.logout()
        self.assertEqual(self.client.post(self.url, {"recipient": "oficina"}).status_code, 302)


class RetentionGateTests(MailBase):
    def test_requires_workshop_and_customer_confirmation(self):
        self.assertFalse(services.mandatory_emails_confirmed(self.att))
        services.send_report(self.report)
        self.assertTrue(services.mandatory_emails_confirmed(self.att))

    def test_customer_failure_keeps_gate_closed(self):
        services.send_report(self.report)
        EmailDispatch.objects.filter(recipient_type="cliente").update(status=DispatchStatus.FALHOU, accepted_at=None)
        self.assertFalse(services.mandatory_emails_confirmed(self.att))

    def test_without_workshop_email_gate_stays_closed(self):
        workshop = default_workshop()
        workshop.report_email = ""
        workshop.save()
        type(self.att).objects.filter(pk=self.att.pk).update(customer_email="")
        self.att.refresh_from_db()
        self.assertFalse(services.mandatory_emails_confirmed(self.att))


class SettingsTestEmailTests(MailBase):
    def setUp(self):
        super().setUp()
        self.client.force_login(make_user("chefe"))
        self.url = reverse("mailing:test")

    def test_workshop_account_can_test(self):
        self.client.force_login(make_user("oficina"))
        self.assertEqual(self.client.post(reverse("mailing:test")).status_code, 302)

    def test_success_uses_server_response(self):
        response = self.client.post(self.url, follow=True)
        self.assertContains(response, "aceito pelo servidor")
        self.assertEqual(mail.outbox[0].to, [OFICINA])

    @override_settings(EMAIL_BACKEND=CONSOLE)
    def test_not_configured_message(self):
        self.assertContains(self.client.post(self.url, follow=True), "SMTP não configurado")

    @override_settings(EMAIL_BACKEND="apps.mailing.tests.test_mailing.FailingBackend")
    def test_failure_message(self):
        self.assertContains(self.client.post(self.url, follow=True), "Falha no envio de teste")


class FinalizationTests(TestCase):
    """Fluxo real: finalizar gera o PDF e dispara os e-mails."""

    @classmethod
    def setUpTestData(cls):
        call_command("seed_checklist", verbosity=0)

    def setUp(self):
        self.user = make_user("ana")
        self.client.force_login(self.user)
        self.att = complete_through(make_attendance(customer_email=CLIENTE), wf.REVISAO)
        self.url = reverse("signatures:step", args=[self.att.public_id])

    def _set_workshop_email(self):
        workshop = default_workshop()
        workshop.report_email = OFICINA
        workshop.save()

    def test_finish_generates_and_sends(self):
        self._set_workshop_email()
        response = self.client.post(self.url, {"refused": "on"}, follow=True)
        self.assertContains(response, "aceito pelo servidor")
        self.assertEqual(self.att.reports.count(), 1)
        self.assertEqual(len(mail.outbox), 2)

    def test_missing_workshop_email_warns_and_does_not_block(self):
        response = self.client.post(self.url, {"refused": "on"}, follow=True)
        self.assertContains(response, "E-mail do responsável não configurado")
        self.att.refresh_from_db()
        self.assertEqual(self.att.status, wf.STATUS_CONCLUIDO)
        self.assertEqual([m.to[0] for m in mail.outbox], [CLIENTE])

    def test_pdf_failure_does_not_undo_completion(self):
        self._set_workshop_email()
        with mock.patch("apps.reports.services.build_pdf", side_effect=ValueError("quebrou")):
            response = self.client.post(self.url, {"refused": "on"}, follow=True)
        self.assertContains(response, "Não foi possível gerar o relatório")
        self.assertNotContains(response, "quebrou")
        self.att.refresh_from_db()
        self.assertEqual(self.att.status, wf.STATUS_CONCLUIDO)
        self.assertEqual(self.att.reports.count(), 0)

    @override_settings(EMAIL_BACKEND="apps.mailing.tests.test_mailing.FailingBackend")
    def test_mail_failure_does_not_undo_completion(self):
        self._set_workshop_email()
        response = self.client.post(self.url, {"refused": "on"}, follow=True)
        self.assertContains(response, "não enviado")
        self.att.refresh_from_db()
        self.assertEqual(self.att.status, wf.STATUS_CONCLUIDO)
        self.assertEqual(self.att.reports.count(), 1)


class _Handler:
    def __init__(self, refuse=False):
        self.refuse = refuse
        self.messages = []

    async def handle_DATA(self, server, session, envelope):  # noqa: ARG002,N802
        if self.refuse:
            return "550 Caixa de correio inexistente"
        self.messages.append(envelope)
        return "250 OK"


def free_port():
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


class RealSmtpProtocolTests(MailBase):
    """Usa o backend SMTP de verdade contra um servidor local nesta máquina (nada sai para a internet)."""

    def _run(self, handler):
        port = free_port()
        controller = Controller(handler, hostname="127.0.0.1", port=port)
        controller.start()
        self.addCleanup(controller.stop)
        return override_settings(EMAIL_BACKEND=SMTP, EMAIL_HOST="127.0.0.1", EMAIL_PORT=port, EMAIL_USE_TLS=False,
                                 EMAIL_USE_SSL=False, EMAIL_HOST_USER="", EMAIL_HOST_PASSWORD="", EMAIL_TIMEOUT=5)

    def test_accepted_by_server_with_pdf_attached(self):
        handler = _Handler()
        with self._run(handler):
            results = services.send_report(self.report)
        self.assertTrue(all(d.is_confirmed for d in results))
        self.assertEqual({e.rcpt_tos[0] for e in handler.messages}, {OFICINA, CLIENTE})
        parsed = email.message_from_bytes(handler.messages[0].content)
        parts = [p for p in parsed.walk() if p.get_content_type() == "application/pdf"]
        self.assertEqual(len(parts), 1)
        self.assertTrue(parts[0].get_payload(decode=True).startswith(b"%PDF"))
        self.assertEqual(parsed["Message-ID"], next(d.message_id for d in results if d.recipient_email == parsed["To"]))

    def test_refused_by_server_is_recorded_as_failure(self):
        with self._run(_Handler(refuse=True)):
            results = services.send_report(self.report)
        for dispatch in results:
            self.assertEqual(dispatch.status, DispatchStatus.FALHOU)
            self.assertIn("550", dispatch.last_error)
            self.assertFalse(dispatch.is_confirmed)

    def test_server_offline_is_recorded_as_failure(self):
        offline = override_settings(EMAIL_BACKEND=SMTP, EMAIL_HOST="127.0.0.1", EMAIL_PORT=free_port(),
                                    EMAIL_USE_TLS=False, EMAIL_TIMEOUT=2, EMAIL_HOST_USER="", EMAIL_HOST_PASSWORD="")
        with offline:
            results = services.send_report(self.report)
        for dispatch in results:
            self.assertEqual(dispatch.status, DispatchStatus.FALHOU)
            self.assertTrue(dispatch.last_error)
