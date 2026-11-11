from datetime import timedelta

from django.core.management import call_command
from django.utils import timezone

from apps.attendances import workflow as wf
from apps.core.testing import complete_through, make_attendance
from apps.signatures.services import register_refusal

from .base import PHONE, BrowserTestCase


class HistoryAndAftersalesTests(BrowserTestCase):
    def setUp(self):
        super().setUp()
        self.att = complete_through(make_attendance(mechanic=self.mechanic), wf.REVISAO)
        register_refusal(self.att)
        now = timezone.now()
        type(self.att).objects.filter(pk=self.att.pk).update(
            status=wf.STATUS_CONCLUIDO, current_step=wf.FINALIZADO, completed_at=now,
            retention_until=now + timedelta(days=180),
        )
        self.login()

    def test_history_search_and_customer_page(self):
        self.page.goto(self.url("/atendimentos/historico/"))
        self.page.fill("input[name=q]", "abc1d23")
        self.submit("button[type=submit].btn >> nth=-1")
        self.assertIn(self.att.code, self.page.inner_text("table"))
        self.shot("history")
        self.submit(self.page.locator("table a", has_text="João"))
        self.assertIn("/clientes/", self.page.url)
        self.assertIn(self.att.code, self.page.inner_text("main"))
        self.shot("customer-detail")

    def test_aftersales_filters_and_platform_blocked_for_workshop(self):
        self.page.goto(self.url("/pos-venda/"))
        self.assertIn(self.att.code, self.page.inner_text("main"))
        self.page.check("input[name=pendentes]")
        self.submit("form.filters button[type=submit]")
        self.assertIn("Nenhum atendimento", self.page.inner_text("main"))
        self.shot("aftersales")

        page = self.new_page(PHONE)
        self.login(page, "func")
        self.assertEqual(page.locator(".nav-link[href='/configuracoes/']").count(), 1)
        response = page.goto(self.url("/plataforma/"))
        self.assertEqual(response.status, 403)
        self.assertIn("Acesso negado", page.inner_text("main"))
        page.context.close()

    def test_purge_command_defaults_to_simulation(self):
        from io import StringIO

        type(self.att).objects.filter(pk=self.att.pk).update(retention_until=timezone.now() - timedelta(days=1))
        output = StringIO()
        call_command("purge_expired", stdout=output)
        self.assertIn("SIMULAÇÃO", output.getvalue())
        self.page.goto(self.url(f"/atendimentos/{self.att.public_id}/resumo/"))
        self.assertIn(self.att.code, self.page.inner_text(".topbar"))
