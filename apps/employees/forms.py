from apps.mechanics.forms import TeamMemberForm

from .models import Employee


class EmployeeForm(TeamMemberForm):
    duplicate_message = "Já existe um vendedor/atendente com este nome."

    class Meta:
        model = Employee
        fields = ["name", "is_active"]
