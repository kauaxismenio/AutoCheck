from datetime import datetime, timedelta, timezone as dt_tz
from io import StringIO
from unittest import mock

from django.core.files.storage import default_storage
from django.core.management import call_command
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from apps.aftersales import services
from apps.attendances import workflow as wf
from apps.attendances.models import Attendance
from apps.checklist.models import ChecklistItem, Result
from apps.checklist.services import save_item
from apps.core.models import AuditLog
from apps.core.testing import complete_through, default_workshop, make_attendance, make_mechanic, make_user, make_vehicle, tiny_png
from apps.customers.models import Customer
from apps.mailing.services import send_report
from apps.photos import categories as cat
from apps.photos.models import Photo
from apps.replacements import services as rep_services
from apps.replacements.models import Decision
from apps.reports.models import Report
from apps.reports.services import generate_report
from apps.signatures.services import register_refusal
from apps.vehicles.models import Vehicle
from apps.workshop.models import WorkshopSettings


def finish(att, *, completed_at=None):
    register_refusal(att)
    now = completed_at or timezone.now()
    type(att).objects.filter(pk=att.pk).update(status=wf.STATUS_CONCLUIDO, current_step=wf.FINALIZADO, completed_at=now)
    att.refresh_from_db()
    type(att).objects.filter(pk=att.pk).update(retention_until=att.compute_retention_until())
    att.refresh_from_db()
    return att


def run(*args):
    out = StringIO()
    call_command("purge_expired", *args, stdout=out)
    return out.getvalue()


class Base(TestCase):
    @classmethod
    def setUpTestData(cls):
        call_command("seed_checklist", verbosity=0)

    def setUp(self):
        self.mechanic = make_mechanic()
        workshop = default_workshop()
        workshop.report_email = "dono@oficinaboa.com.br"
        workshop.save()

    def attendance(self, vehicle=None, **extra):
        return complete_through(make_attendance(vehicle=vehicle, mechanic=self.mechanic, **extra), wf.REVISAO)

    def expired(self, *, email=True, vehicle=None):
        att = finish(self.attendance(vehicle=vehicle), completed_at=timezone.now() - timedelta(days=400))
        report = generate_report(att)
        if email:
            send_report(report)
        return att


class CalendarRuleTests(Base):
    def test_retention_is_six_calendar_months_not_180_days(self):
        att = self.attendance()
        att.completed_at = datetime(2026, 1, 15, 10, 0, tzinfo=dt_tz.utc)
        self.assertEqual(att.compute_retention_until(), datetime(2026, 7, 15, 10, 0, tzinfo=dt_tz.utc))
        self.assertNotEqual(att.compute_retention_until(), att.completed_at + timedelta(days=180))

    def test_end_of_month_is_clamped(self):
        att = self.attendance()
        att.completed_at = datetime(2027, 8, 31, 10, 0, tzinfo=dt_tz.utc)
        self.assertEqual(att.compute_retention_until(), datetime(2028, 2, 29, 10, 0, tzinfo=dt_tz.utc))

    def test_one_day_before_deadline_is_kept(self):
        att = finish(self.attendance(), completed_at=timezone.now())
        generate_report(att)
        almost = att.retention_until - timedelta(days=1)
        self.assertEqual(services.expired_items(now=almost), [])
        # No prazo já aparece, mas fica bloqueado enquanto não houver aceite dos e-mails.
        due = services.expired_items(now=att.retention_until)
        self.assertEqual([item.attendance.pk for item in due], [att.pk])
        self.assertFalse(due[0].eligible)


class DryRunTests(Base):
    def test_default_is_simulation_and_deletes_nothing(self):
        att = self.expired()
        names = [p.image.name for p in att.photos.all()]
        output = run()
        self.assertIn("SIMULAÇÃO", output)
        self.assertIn(f"EXCLUIRIA  {att.code}", output)
        self.assertTrue(Attendance.objects.filter(pk=att.pk).exists())
        self.assertTrue(all(default_storage.exists(name) for name in names))
        self.assertFalse(AuditLog.objects.filter(action="retention.purged").exists())

    def test_output_has_no_personal_data(self):
        att = self.expired()
        output = run()
        self.assertNotIn(att.customer.full_name, output)
        self.assertNotIn(att.customer.cpf, output)
        self.assertNotIn(att.vehicle.plate, output)

    def test_active_or_recent_attendances_not_listed(self):
        self.attendance()
        finish(self.attendance(vehicle=make_vehicle(Customer.objects.first(), plate="XYZ9K88")))
        self.assertEqual(services.expired_items(), [])


class GateTests(Base):
    def test_blocked_without_confirmed_email(self):
        att = self.expired(email=False)
        output = run("--execute")
        self.assertIn(f"BLOQUEADO  {att.code}", output)
        self.assertIn("sem aceite", output)
        self.assertTrue(Attendance.objects.filter(pk=att.pk).exists())

    def test_blocked_when_customer_email_not_confirmed(self):
        att = complete_through(make_attendance(mechanic=self.mechanic, customer_email="c@empresa.com.br"), wf.REVISAO)
        finish(att, completed_at=timezone.now() - timedelta(days=400))
        report = generate_report(att)
        send_report(report)
        att.email_dispatches.filter(recipient_type="cliente").update(status="falhou", accepted_at=None)
        run("--execute")
        self.assertTrue(Attendance.objects.filter(pk=att.pk).exists())

    def test_purge_rechecks_gate_at_execution_time(self):
        att = self.expired()
        item = services.expired_items()[0]
        att.email_dispatches.update(status="falhou", accepted_at=None)
        with self.assertRaises(ValueError):
            services.purge(item)
        self.assertTrue(Attendance.objects.filter(pk=att.pk).exists())

    def test_cancelled_needs_no_email(self):
        att = make_attendance(mechanic=self.mechanic)
        type(att).objects.filter(pk=att.pk).update(status=wf.STATUS_CANCELADO, retention_until=timezone.now() - timedelta(days=1))
        self.assertIn("EXCLUÍDO", run("--execute"))
        self.assertFalse(Attendance.objects.filter(pk=att.pk).exists())


class PurgeTests(Base):
    def test_execute_removes_records_and_physical_files(self):
        att = self.expired()
        pk = att.pk
        photo_files = [p.image.name for p in att.photos.all()]
        report_files = [r.file.name for r in att.reports.all()]
        customer_id, vehicle_id = att.customer_id, att.vehicle_id
        self.assertTrue(photo_files and report_files)
        with self.captureOnCommitCallbacks(execute=True):
            output = run("--execute")
        self.assertIn("EXCLUÍDO", output)
        self.assertFalse(Attendance.objects.filter(pk=pk).exists())
        self.assertFalse(Photo.objects.filter(attendance_id=pk).exists())
        self.assertFalse(ChecklistItem.objects.filter(attendance_id=pk).exists())
        self.assertFalse(Report.objects.filter(attendance_id=pk).exists())
        self.assertFalse(Vehicle.objects.filter(pk=vehicle_id).exists())
        self.assertFalse(Customer.objects.filter(pk=customer_id).exists())
        for name in photo_files + report_files:
            self.assertFalse(default_storage.exists(name), name)

    def test_audit_keeps_no_personal_data(self):
        att = self.expired()
        name, cpf, plate = att.customer.full_name, att.customer.cpf, att.vehicle.plate
        run("--execute")
        entry = AuditLog.objects.get(action="retention.purged")
        self.assertEqual(entry.attendance_id, att.pk)
        text = str(entry.details)
        for secret in (name, cpf, plate):
            self.assertNotIn(secret, text)

    def test_customer_with_other_attendance_is_kept(self):
        att = self.expired()
        recent = self.attendance(vehicle=att.vehicle)
        run("--execute")
        self.assertTrue(Customer.objects.filter(pk=att.customer_id).exists())
        self.assertTrue(Vehicle.objects.filter(pk=att.vehicle_id).exists())
        self.assertTrue(Attendance.objects.filter(pk=recent.pk).exists())

    def test_one_failure_does_not_stop_others(self):
        self.expired()
        with mock.patch("apps.aftersales.management.commands.purge_expired.purge", side_effect=OSError("disco")):
            output = run("--execute")
        self.assertIn("FALHOU", output)
        self.assertIn("Falhas: 1", output)


class AftersalesViewTests(Base):
    def setUp(self):
        super().setUp()
        self.url = reverse("aftersales:list")
        self.client.force_login(make_user("ana"))

    def _with_refusal(self, vehicle=None, completed_at=None):
        att = self.attendance(vehicle=vehicle)
        type(att).objects.filter(pk=att.pk).update(current_step=wf.SERVICOS)
        item = att.checklist_items.select_related("attendance").get(component_name="Pastilhas dianteiras")
        save_item(item, result=Result.SUBSTITUIR)
        rep_services.register_decision(att.replacements.get(), Decision.NAO_AUTORIZADO)
        return finish(att, completed_at=completed_at)

    def test_workshop_account_has_access(self):
        self.client.force_login(make_user("oficina"))
        self.assertEqual(self.client.get(self.url).status_code, 200)

    def test_lists_required_information(self):
        att = self._with_refusal()
        rep_services.add_manual_service(att, "Alinhamento")
        response = self.client.get(self.url)
        for expected in (att.code, att.vehicle.plate_formatted, "Alinhamento", "Pastilhas dianteiras", str(att.mileage)):
            self.assertContains(response, expected)
        row = response.context["rows"][0]
        self.assertEqual(row["refused"], ["Pastilhas dianteiras"])
        self.assertEqual(row["pending"], ["Pastilhas dianteiras"])

    def test_refusal_solved_later_is_no_longer_pending(self):
        first = self._with_refusal(completed_at=timezone.now() - timedelta(days=30))
        second = self.attendance(vehicle=first.vehicle)
        type(second).objects.filter(pk=second.pk).update(current_step=wf.SERVICOS)
        item = second.checklist_items.select_related("attendance").get(component_name="Pastilhas dianteiras")
        save_item(item, result=Result.SUBSTITUIR)
        replacement = second.replacements.get()
        rep_services.register_decision(replacement, Decision.AUTORIZADO)
        for phase in (cat.PHASE_PART_OLD, cat.PHASE_PART_NEW):
            Photo.objects.create(attendance=second, phase=phase, replacement=replacement, image=tiny_png())
        rep_services.confirm_replacement(replacement)
        finish(second)
        row = services.describe(Attendance.objects.get(pk=first.pk))
        self.assertEqual(row["refused"], ["Pastilhas dianteiras"])
        self.assertEqual(row["pending"], [])
        rows = self.client.get(self.url, {"pendentes": "1"}).context["rows"]
        self.assertEqual(rows, [])

    def test_pending_filter_and_period_filter(self):
        refused = self._with_refusal(completed_at=timezone.now() - timedelta(days=10))
        plain = finish(self.attendance(vehicle=make_vehicle(refused.customer, plate="XYZ9K88")))
        rows = self.client.get(self.url, {"pendentes": "1"}).context["rows"]
        self.assertEqual([r["attendance"].pk for r in rows], [refused.pk])
        today = timezone.localdate().isoformat()
        rows = self.client.get(self.url, {"de": today, "ate": today}).context["rows"]
        self.assertEqual([r["attendance"].pk for r in rows], [plain.pk])

    def test_invalid_dates_are_ignored(self):
        self.assertEqual(self.client.get(self.url, {"de": "xx", "ate": "99/99"}).status_code, 200)

    def test_in_progress_not_listed(self):
        self.attendance()
        self.assertEqual(self.client.get(self.url).context["rows"], [])


class HistoryTests(Base):
    def setUp(self):
        super().setUp()
        self.client.force_login(make_user("ana"))

    def test_customer_history_shows_everything_for_many_vehicles(self):
        first = finish(self.attendance())
        generate_report(first)
        other_vehicle = make_vehicle(first.customer, plate="XYZ9K88")
        second = finish(self.attendance(vehicle=other_vehicle))
        response = self.client.get(reverse("customers:detail", args=[first.customer_id]))
        for expected in (first.code, second.code, "ABC1D23", "XYZ9K88", "Baixar v1"):
            self.assertContains(response, expected)

    def test_vehicle_history_many_attendances(self):
        first = finish(self.attendance())
        second = finish(self.attendance(vehicle=first.vehicle))
        response = self.client.get(reverse("vehicles:detail", args=[first.vehicle_id]))
        self.assertContains(response, first.code)
        self.assertContains(response, second.code)

    def test_history_search(self):
        att = finish(self.attendance())
        make_attendance(vehicle=make_vehicle(att.customer, plate="XYZ9K88"), mechanic=self.mechanic)
        url = reverse("attendances:history")
        self.assertEqual([a.pk for a in self.client.get(url).context["page"].object_list], [att.pk])
        for term in ("abc1d23", "João", "52998224725", att.code):
            self.assertEqual(len(self.client.get(url, {"q": term}).context["page"].object_list), 1, term)
        self.assertEqual(len(self.client.get(url, {"q": "inexistente"}).context["page"].object_list), 0)

    def test_old_attendance_summary_shows_checklist_and_refusal(self):
        att = finish(self.attendance())
        response = self.client.get(reverse("attendances:summary", args=[att.public_id]))
        self.assertContains(response, "Checklist e pneus")
        self.assertContains(response, "Pastilhas dianteiras")
