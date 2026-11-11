"""Cadastro de vendedores/atendentes, acessado em Configurações."""
from django.contrib.auth.decorators import login_required

from apps.mechanics.views import TeamPage, team_create, team_edit, team_list

from .forms import EmployeeForm
from .models import Employee

PAGE = TeamPage(
    model=Employee, form_class=EmployeeForm, namespace="employees", audit_prefix="employee", singular="vendedor/atendente",
    plural="Vendedores/Atendentes", note="Vendedores/atendentes não têm login nem senha. Quem está desativado sai da lista do atendimento, "
                                "mas continua nos atendimentos antigos.",
)


@login_required
def employee_list(request):
    return team_list(request, PAGE)


@login_required
def employee_create(request):
    return team_create(request, PAGE)


@login_required
def employee_edit(request, pk):
    return team_edit(request, PAGE, pk)
