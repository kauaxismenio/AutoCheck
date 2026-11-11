from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied, ValidationError
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from apps.attendances import services as att_services
from apps.attendances import workflow as wf
from apps.attendances.navigation import step_url, steps_nav
from apps.attendances.summary import build_summary
from apps.attendances.views import get_attendance
from apps.core.protected_files import serve_protected_file

from . import categories as cat
from . import services
from .models import Photo


def _photo_step(request, public_id, step, phase, *, title, intro):
    attendance = get_attendance(public_id)
    att_services.get_step_or_403(attendance, step)
    errors = []
    if request.method == "POST":
        try:
            att_services.complete_step(attendance, step, user=request.user, request=request)
        except att_services.StepIncomplete as exc:
            errors = exc.errors
        else:
            return redirect(step_url(attendance))
    return render(request, "photos/step.html", {
        "attendance": attendance, "steps": steps_nav(attendance, step), "title": title, "intro": intro,
        "slots": services.phase_slots(attendance, phase), "errors": errors,
        "summary": build_summary(attendance), "show_summary": phase == cat.PHASE_CHECKIN,
    })


@login_required
def checkin(request, public_id):
    return _photo_step(request, public_id, wf.CHECKIN, cat.PHASE_CHECKIN, title="Check-in — fotografias de entrada",
                       intro="Registre o estado do veículo na chegada. As cinco fotos obrigatórias liberam a próxima etapa.")


@login_required
def checkout(request, public_id):
    return _photo_step(request, public_id, wf.CHECKOUT, cat.PHASE_CHECKOUT, title="Check-out — fotografias de saída",
                       intro="Registre o estado do veículo na entrega.")


@login_required
@require_POST
def upload(request, public_id):
    attendance = get_attendance(public_id)
    uploaded = request.FILES.get("image")
    if uploaded is None:
        return JsonResponse({"error": "Selecione uma imagem."}, status=400)
    try:
        photo = services.save_photo(
            attendance, phase=request.POST.get("phase", ""), category=request.POST.get("category", ""),
            uploaded=uploaded, user=request.user, target_id=request.POST.get("target"), request=request,
        )
    except ValidationError as exc:
        return JsonResponse({"error": " ".join(exc.messages)}, status=400)
    except PermissionDenied:
        return JsonResponse({"error": "Esta etapa não está aberta para envio de fotos."}, status=403)
    return JsonResponse(services.photo_payload(photo), status=201)


@login_required
@require_POST
def delete(request, public_id, pk):
    photo = get_object_or_404(Photo.objects.select_related("attendance"), pk=pk, attendance__public_id=public_id)
    try:
        services.delete_photo(photo, user=request.user, request=request)
    except PermissionDenied:
        return JsonResponse({"error": "Esta etapa não está aberta para alterar fotos."}, status=403)
    return JsonResponse({"deleted": True})


@login_required
def photo_file(request, public_id, pk):
    photo = get_object_or_404(Photo, pk=pk, attendance__public_id=public_id)
    return serve_protected_file(photo.image)
