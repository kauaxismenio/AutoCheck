"""Dashboard e views de infraestrutura."""
from django.contrib.auth.decorators import login_required
from django.db import connection
from django.http import JsonResponse
from django.shortcuts import render
from django.views.decorators.http import require_GET

from .activity import recent_activity


@require_GET
def health(request):  # noqa: ARG001
    """Verificação de saúde para monitoramento: confirma acesso ao banco."""
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
        db_ok = True
    except Exception:  # noqa: BLE001 — não expor detalhes do erro
        db_ok = False
    return JsonResponse({"status": "ok" if db_ok else "erro", "database": db_ok},
                        status=200 if db_ok else 503)


@login_required
def home(request):
    from apps.attendances import workflow as wf
    from apps.attendances.models import Attendance
    from apps.customers.models import Customer
    from apps.vehicles.models import Vehicle

    attendances = Attendance.objects.all()
    in_progress = attendances.filter(status=wf.STATUS_EM_ANDAMENTO)
    return render(request, "core/dashboard.html", {
        "stats": {
            "total": attendances.exclude(status=wf.STATUS_CANCELADO).count(),
            "in_progress": in_progress.count(),
            "completed": attendances.filter(status=wf.STATUS_CONCLUIDO).count(),
            "customers": Customer.objects.count(),
            "vehicles": Vehicle.objects.count(),
        },
        "open_attendances": in_progress.select_related("customer", "vehicle", "mechanic")[:6],
        "activity": recent_activity(request.user.workshop_id),
    })
