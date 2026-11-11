from datetime import datetime, timezone as dt_tz

from django.core.exceptions import PermissionDenied
from django.db import IntegrityError, transaction
from django.test import TestCase

from apps.attendances import services
from apps.attendances import workflow as wf
from apps.core.testing import make_attendance, tiny_png
from apps.photos import categories as cat
from apps.photos.models import Photo


class AttendanceModelTests(TestCase):
    def test_code_generated(self):
        att = make_attendance()
        self.assertTrue(att.code.startswith("AC-"))
        self.assertEqual(att.current_step, wf.CADASTRO)

    def test_email_opt_out_clears_attendance_email_only(self):
        att = make_attendance(customer_email="joao@empresa.com.br", email_opt_out=True)
        self.assertEqual(att.customer_email, "")
        self.assertFalse(att.should_email_customer)

    def test_retention_uses_calendar_months(self):
        att = make_attendance()
        att.completed_at = datetime(2026, 8, 31, 12, 0, tzinfo=dt_tz.utc)
        self.assertEqual(att.compute_retention_until(), datetime(2027, 2, 28, 12, 0, tzinfo=dt_tz.utc))


class StepGuardTests(TestCase):
    def setUp(self):
        self.att = make_attendance()

    def test_cannot_open_future_step(self):
        with self.assertRaises(PermissionDenied):
            services.get_step_or_403(self.att, wf.CHECKLIST)

    def test_advance_cadastro_then_checkin_requires_photos(self):
        services.advance(self.att, wf.CADASTRO)
        self.assertEqual(self.att.current_step, wf.CHECKIN)

        with self.assertRaises(services.StepIncomplete) as ctx:
            services.advance(self.att, wf.CHECKIN)
        self.assertEqual(len(ctx.exception.errors), 5)

        for category in cat.CHECKIN_REQUIRED:
            Photo.objects.create(attendance=self.att, phase=cat.PHASE_CHECKIN, category=category, image=tiny_png())
        services.advance(self.att, wf.CHECKIN)
        self.assertEqual(self.att.current_step, wf.CHECKLIST)

    def test_cannot_skip_by_resubmitting_old_step(self):
        services.advance(self.att, wf.CADASTRO)
        with self.assertRaises(wf.WorkflowError):
            services.advance(self.att, wf.CADASTRO)

    def test_cpf_required_unless_opted_out(self):
        self.att.customer.cpf = None
        self.att.customer.save()
        with self.assertRaises(services.StepIncomplete):
            services.advance(self.att, wf.CADASTRO)
        self.att.cpf_not_informed = True
        self.att.save()
        services.advance(self.att, wf.CADASTRO)


class ConstraintTests(TestCase):
    def test_replacement_needs_exactly_one_source(self):
        from apps.replacements.models import PartReplacement

        att = make_attendance()
        with self.assertRaises(IntegrityError), transaction.atomic():
            PartReplacement.objects.create(attendance=att, component_name="Pastilhas")

    def test_signature_requires_image_or_refusal(self):
        from apps.signatures.models import AttendanceSignature

        att = make_attendance()
        with self.assertRaises(IntegrityError), transaction.atomic():
            AttendanceSignature.objects.create(attendance=att, refused=False, snapshot_sha256="x")
        sig = AttendanceSignature(attendance=att, refused=True)
        sig.bind_to_current_version()
        sig.save()
        self.assertTrue(sig.matches_current_version())
        att.mileage += 1
        att.save()
        sig.attendance.refresh_from_db()
        self.assertFalse(sig.matches_current_version())
