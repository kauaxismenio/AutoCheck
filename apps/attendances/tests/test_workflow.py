import unittest

from apps.attendances import workflow as wf
from apps.photos import categories as cat


class WorkflowTests(unittest.TestCase):
    def test_order(self):
        self.assertEqual(wf.STEPS[0], wf.CADASTRO)
        self.assertEqual(wf.next_step(wf.CADASTRO), wf.CHECKIN)
        self.assertEqual(wf.next_step(wf.REVISAO), wf.FINALIZADO)
        with self.assertRaises(wf.WorkflowError):
            wf.next_step(wf.FINALIZADO)

    def test_cannot_open_future_step(self):
        self.assertTrue(wf.can_open(wf.CHECKLIST, wf.CHECKIN))
        self.assertTrue(wf.can_open(wf.CHECKLIST, wf.CHECKLIST))
        self.assertFalse(wf.can_open(wf.CHECKLIST, wf.SERVICOS))
        self.assertFalse(wf.can_open(wf.CADASTRO, wf.REVISAO))

    def test_finished_or_cancelled_is_read_only(self):
        self.assertFalse(wf.can_open(wf.FINALIZADO, wf.CADASTRO, wf.STATUS_CONCLUIDO))
        self.assertFalse(wf.can_open(wf.CHECKIN, wf.CHECKIN, wf.STATUS_CANCELADO))

    def test_advance_only_from_current_step(self):
        self.assertEqual(wf.ensure_can_advance(wf.CHECKIN, wf.CHECKIN), wf.CHECKLIST)
        with self.assertRaises(wf.WorkflowError):
            wf.ensure_can_advance(wf.CHECKIN, wf.CADASTRO)  # reenviar etapa antiga não pula
        with self.assertRaises(wf.WorkflowError):
            wf.ensure_can_advance(wf.CHECKIN, wf.CHECKIN, wf.STATUS_CANCELADO)

    def test_unknown_step(self):
        with self.assertRaises(wf.WorkflowError):
            wf.can_open("hackeado", wf.CADASTRO)

    def test_progress(self):
        states = [state for _, _, state in wf.progress(wf.CHECKLIST)]
        self.assertEqual(states, ["done", "done", "current", "pending", "pending", "pending"])
        self.assertTrue(all(s == "done" for _, _, s in wf.progress(wf.FINALIZADO)))


class PhotoCategoryTests(unittest.TestCase):
    def test_checkin_requires_five(self):
        self.assertEqual(len(cat.missing_required(cat.PHASE_CHECKIN, [])), 5)
        present = [cat.FRENTE, cat.TRASEIRA, cat.ARRANHOES]
        self.assertEqual(
            cat.missing_required(cat.PHASE_CHECKIN, present),
            [cat.LATERAL_DIREITA, cat.LATERAL_ESQUERDA, cat.PAINEL],
        )

    def test_checkout_requires_plate_rear(self):
        missing = cat.missing_required(cat.PHASE_CHECKOUT, [cat.TRASEIRA])
        self.assertIn(cat.TRASEIRA_PLACA, missing)

    def test_allowed_categories(self):
        self.assertTrue(cat.is_category_allowed(cat.PHASE_CHECKIN, cat.DANOS))
        self.assertFalse(cat.is_category_allowed(cat.PHASE_CHECKOUT, cat.DANOS))


if __name__ == "__main__":
    unittest.main()
