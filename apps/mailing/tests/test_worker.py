"""Comportamento do trabalhador em execução contínua. A fila em si é testada em test_automatic."""
import io
import signal
from datetime import timedelta
from unittest import mock

from django.core import mail
from django.core.management import call_command
from django.db import OperationalError
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from apps.attendances import workflow as wf
from apps.attendances.models import Attendance
from apps.core.testing import complete_through, default_workshop, make_attendance, make_user
from apps.mailing import services
from apps.mailing.management.commands.process_email_queue import Command
from apps.mailing.models import DispatchStatus, EmailDispatch
from apps.mailing.tests.test_mailing import FailingBackend

COMMAND = "apps.mailing.management.commands.process_email_queue"
OFICINA = "dono@oficinaboa.com.br"
CLIENTE = "cliente@empresa.com.br"
EMPTY = {"aceitos": 0}


class WorkerBase(TestCase):
    @classmethod
    def setUpTestData(cls):
        call_command("seed_checklist", verbosity=0)

    def setUp(self):
        self.client.force_login(make_user("oficina"))
        workshop = default_workshop()
        workshop.report_email = OFICINA
        workshop.save()
        self.attendance = complete_through(make_attendance(customer_email=CLIENTE), wf.REVISAO)
        self.step_url = reverse("signatures:step", args=[self.attendance.public_id])
        self.summary_url = reverse("attendances:summary", args=[self.attendance.public_id])

    def finalize_with_failure(self):
        with override_settings(EMAIL_BACKEND=f"{FailingBackend.__module__}.FailingBackend"):
            self.client.post(self.step_url, {"refused": "on"})

    def make_overdue(self, minutes=10):
        EmailDispatch.objects.filter(next_attempt_at__isnull=False).update(next_attempt_at=timezone.now() - timedelta(minutes=minutes))


class ContinuousLoopTests(WorkerBase):
    def run_loop(self, process_queue, *args, sleeps=1):
        """Roda o laço e o interrompe depois de `sleeps` esperas."""
        output = io.StringIO()
        waits = [None] * (sleeps - 1) + [KeyboardInterrupt]
        with mock.patch(f"{COMMAND}.process_queue", process_queue), mock.patch(f"{COMMAND}.time.sleep", side_effect=waits), \
                mock.patch(f"{COMMAND}.close_old_connections"):
            call_command("process_email_queue", "--loop", "--interval=1", *args, stdout=output)
        return output.getvalue()

    def test_survives_passing_error_and_keeps_processing(self):
        process_queue = mock.Mock(side_effect=[OperationalError("database is locked"), EMPTY, EMPTY])
        with self.assertLogs("autocheck.mailing", level="ERROR"):
            output = self.run_loop(process_queue, sleeps=3)
        self.assertEqual(process_queue.call_count, 3)
        self.assertIn("Fila encerrada", output)

    def test_stop_signal_finishes_the_current_pass_without_interrupting(self):
        def receive_stop_during_pass(**_):
            signal.raise_signal(signal.SIGINT)
            return EMPTY

        process_queue = mock.Mock(side_effect=receive_stop_during_pass)
        before = signal.getsignal(signal.SIGINT)
        output = io.StringIO()
        with mock.patch(f"{COMMAND}.process_queue", process_queue), mock.patch(f"{COMMAND}.time.sleep") as sleep, \
                mock.patch(f"{COMMAND}.close_old_connections"):
            call_command("process_email_queue", "--loop", "--interval=60", stdout=output)
        self.assertEqual(process_queue.call_count, 1, "A passada terminou e nenhuma outra começou")
        sleep.assert_not_called()
        self.assertIn("Fila encerrada", output.getvalue())
        self.assertEqual(signal.getsignal(signal.SIGINT), before, "O comportamento normal do Ctrl+C é restaurado")

    def test_wait_is_split_so_stop_is_answered_quickly(self):
        command = Command()
        command.stopping = False

        def stop_on_third_second(_):
            stop_on_third_second.calls += 1
            command.stopping = stop_on_third_second.calls == 3

        stop_on_third_second.calls = 0
        with mock.patch(f"{COMMAND}.time.sleep", side_effect=stop_on_third_second) as sleep:
            command._wait(60)
        self.assertEqual(sleep.call_count, 3)

    def test_stop_between_items_keeps_the_rest_in_the_queue(self):
        self.finalize_with_failure()
        self.make_overdue()
        results = iter([False, True])
        services.process_queue(should_stop=lambda: next(results))
        self.assertEqual(len(mail.outbox), 1, "O envio em curso terminou e o seguinte não começou")
        self.assertEqual(EmailDispatch.objects.filter(status=DispatchStatus.ENVIADO).count(), 1)
        self.assertEqual(EmailDispatch.objects.filter(status=DispatchStatus.FALHOU, next_attempt_at__isnull=False).count(), 1)
        call_command("process_email_queue", stdout=io.StringIO())
        self.assertEqual(sorted(m.to[0] for m in mail.outbox), sorted([OFICINA, CLIENTE]))


class SinglePassTests(WorkerBase):
    """Cada ciclo chama process_queue uma única vez, e sem --loop existe um único ciclo."""

    def test_without_loop_processes_the_queue_exactly_once(self):
        process_queue = mock.Mock(return_value=EMPTY)
        with mock.patch(f"{COMMAND}.process_queue", process_queue), mock.patch(f"{COMMAND}.time.sleep") as sleep:
            call_command("process_email_queue", stdout=io.StringIO())
        self.assertEqual(process_queue.call_count, 1)
        sleep.assert_not_called()

    def test_one_pass_sends_each_due_record_once(self):
        self.finalize_with_failure()
        self.make_overdue()
        real = services.process_queue
        with mock.patch(f"{COMMAND}.process_queue", side_effect=real) as spy:
            call_command("process_email_queue", stdout=io.StringIO())
        self.assertEqual(spy.call_count, 1)
        self.assertEqual(sorted(m.to[0] for m in mail.outbox), sorted([OFICINA, CLIENTE]))
        for row in EmailDispatch.objects.all():
            self.assertEqual(row.attempts, 2, "Uma falha na finalização e uma única tentativa nesta passada")
            self.assertEqual(row.status, DispatchStatus.ENVIADO)

    def test_each_loop_cycle_runs_one_pass_whatever_the_interval(self):
        process_queue = mock.Mock(return_value=EMPTY)
        output = io.StringIO()
        waits = [None] * 5 + [KeyboardInterrupt]  # intervalo de 2 s: duas fatias por ciclo
        with mock.patch(f"{COMMAND}.process_queue", process_queue), mock.patch(f"{COMMAND}.time.sleep", side_effect=waits), \
                mock.patch(f"{COMMAND}.close_old_connections"):
            call_command("process_email_queue", "--loop", "--interval=2", stdout=output)
        self.assertEqual(process_queue.call_count, 3)
        self.assertEqual(output.getvalue().count("Fila iniciada"), 1)
        self.assertEqual(output.getvalue().count("Fila encerrada"), 1)

    def test_failure_in_single_pass_is_reported_to_the_scheduler(self):
        with mock.patch(f"{COMMAND}.process_queue", side_effect=OperationalError("database is locked")), \
                self.assertRaises(OperationalError):
            call_command("process_email_queue", stdout=io.StringIO())


class StopDuringSendTests(WorkerBase):
    """Ctrl+C de verdade no meio de um envio: ele termina, é registrado, e o seguinte não começa."""

    def _run_with_ctrl_c_during_send(self, *args):
        self.finalize_with_failure()
        self.make_overdue()
        before = signal.getsignal(signal.SIGINT)
        calls = []

        def send_receiving_ctrl_c(dispatch, message_id):
            calls.append(dispatch.pk)
            signal.raise_signal(signal.SIGINT)
            return "aceito", ""

        output = io.StringIO()
        with mock.patch("apps.mailing.services._transmit", side_effect=send_receiving_ctrl_c), \
                mock.patch(f"{COMMAND}.close_old_connections"):
            call_command("process_email_queue", *args, stdout=output)
        self.assertEqual(signal.getsignal(signal.SIGINT), before, "O comportamento normal do Ctrl+C é restaurado")
        self.assertEqual(len(calls), 1, "O envio seguinte não começa depois do pedido de parada")
        accepted = EmailDispatch.objects.get(pk=calls[0])
        self.assertEqual(accepted.status, DispatchStatus.ENVIADO, "O envio em curso termina e fica registrado")
        waiting = EmailDispatch.objects.exclude(pk=calls[0]).get()
        self.assertEqual(waiting.status, DispatchStatus.FALHOU)
        self.assertIsNotNone(waiting.next_attempt_at, "O restante continua na fila")
        return output.getvalue()

    def test_in_continuous_mode(self):
        self.assertIn("Fila encerrada", self._run_with_ctrl_c_during_send("--loop", "--interval=60"))

    def test_in_single_pass_mode(self):
        self.assertIn("aceitos: 1", self._run_with_ctrl_c_during_send())


class RequestDoesNotStartWorkerTests(WorkerBase):
    def test_finalizing_and_viewing_never_start_a_process_or_thread(self):
        with mock.patch("subprocess.Popen") as popen, mock.patch("threading.Thread.start") as thread, \
                mock.patch("multiprocessing.Process.start") as process:
            self.client.post(self.step_url, {"refused": "on"})
            self.client.get(self.summary_url)
        popen.assert_not_called()
        thread.assert_not_called()
        process.assert_not_called()
        self.assertEqual(len(mail.outbox), 2)


class StatusTests(WorkerBase):
    def status(self):
        output = io.StringIO()
        call_command("process_email_queue", "--status", stdout=output)
        return output.getvalue()

    def test_reports_queue_without_sending_or_changing_anything(self):
        self.finalize_with_failure()
        self.make_overdue()
        before = list(EmailDispatch.objects.order_by("pk").values())
        output = self.status()
        self.assertEqual(mail.outbox, [])
        self.assertEqual(list(EmailDispatch.objects.order_by("pk").values()), before)
        self.assertIn("na_fila: 2", output)
        self.assertIn("atrasados: 2", output)
        self.assertIn("aceitos: 0", output)

    def test_status_never_calls_the_processing_or_touches_signals(self):
        self.finalize_with_failure()
        self.make_overdue()
        before = signal.getsignal(signal.SIGINT)
        with mock.patch(f"{COMMAND}.process_queue") as process_queue, mock.patch("apps.mailing.services.deliver") as deliver, \
                mock.patch(f"{COMMAND}.signal.signal") as install, mock.patch(f"{COMMAND}.time.sleep") as sleep:
            self.status()
            output = io.StringIO()
            call_command("process_email_queue", "--status", "--loop", stdout=output)
        process_queue.assert_not_called()
        deliver.assert_not_called()
        install.assert_not_called()
        sleep.assert_not_called()
        self.assertNotIn("Fila iniciada", output.getvalue(), "--status prevalece sobre --loop")
        self.assertEqual(signal.getsignal(signal.SIGINT), before)

    def test_counts_what_needs_manual_action(self):
        self.client.post(self.step_url, {"refused": "on"})
        EmailDispatch.objects.filter(recipient_email=OFICINA).update(status=DispatchStatus.INCERTO, accepted_at=None)
        EmailDispatch.objects.filter(recipient_email=CLIENTE).update(status=DispatchStatus.PENDENTE, accepted_at=None)
        output = self.status()
        self.assertIn("incertos: 1", output)
        self.assertIn("pendentes_manuais: 1", output)
        self.assertIn("na_fila: 0", output)

    def test_output_has_no_personal_data(self):
        self.finalize_with_failure()
        self.assertNotIn("@", self.status())


class StalledWarningTests(WorkerBase):
    MESSAGE = "A fila de e-mails parece parada"

    def test_overdue_item_shows_warning(self):
        self.finalize_with_failure()
        self.make_overdue()
        self.assertContains(self.client.get(self.summary_url), self.MESSAGE)

    def test_item_recently_due_or_scheduled_does_not_warn(self):
        self.finalize_with_failure()
        self.assertNotContains(self.client.get(self.summary_url), self.MESSAGE)
        self.make_overdue(minutes=1)
        self.assertNotContains(self.client.get(self.summary_url), self.MESSAGE)

    def test_accepted_does_not_warn(self):
        self.client.post(self.step_url, {"refused": "on"})
        self.assertNotContains(self.client.get(self.summary_url), self.MESSAGE)

    def test_old_pending_report_warns_and_clears_after_worker_runs(self):
        with mock.patch("apps.reports.services.build_pdf", side_effect=ValueError("quebrou")):
            self.client.post(self.step_url, {"refused": "on"})
        Attendance.objects.filter(pk=self.attendance.pk).update(completed_at=timezone.now() - timedelta(minutes=10))
        self.assertContains(self.client.get(self.summary_url), self.MESSAGE)
        call_command("process_email_queue", stdout=io.StringIO())
        self.assertNotContains(self.client.get(self.summary_url), self.MESSAGE)
        self.assertEqual(len(mail.outbox), 2)

    def test_manual_buttons_stay_available(self):
        self.finalize_with_failure()
        self.make_overdue()
        response = self.client.get(self.summary_url)
        self.assertContains(response, reverse("mailing:send_pending", args=[self.attendance.public_id]))
        self.assertContains(response, reverse("mailing:resend", args=[self.attendance.public_id]))
        self.client.post(reverse("mailing:send_pending", args=[self.attendance.public_id]))
        self.assertEqual(sorted(m.to[0] for m in mail.outbox), sorted([OFICINA, CLIENTE]))
        self.assertEqual(EmailDispatch.objects.filter(status=DispatchStatus.ENVIADO).count(), 2)
