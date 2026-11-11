from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import Http404, HttpResponse
from django.shortcuts import redirect, render
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_POST

from apps.core.audit import log_action
from apps.core.protected_files import serve_protected_file

from . import review_qr as qr
from .forms import ReviewLinkForm, WorkshopSettingsForm


def _integration_status():
    """Somente situação; valores de credenciais nunca chegam ao template."""
    return {
        "smtp_host": settings.EMAIL_HOST or "",
        "smtp_port": settings.EMAIL_PORT,
        "smtp_from": settings.DEFAULT_FROM_EMAIL,
        "smtp_user_set": bool(settings.EMAIL_HOST_USER),
        "smtp_password_set": bool(settings.EMAIL_HOST_PASSWORD),
        "brasilapi_url": settings.AUTOCHECK["BRASILAPI_BASE_URL"],
        "management_configured": bool(settings.AUTOCHECK["MANAGEMENT_API_BASE_URL"]),
    }


@login_required
def settings_view(request):
    workshop = request.user.workshop
    form = WorkshopSettingsForm(request.POST or None, request.FILES or None, instance=workshop)
    if request.method == "POST" and form.is_valid():
        form.save()
        log_action("workshop.updated", request=request, obj=workshop)
        messages.success(request, "Configurações salvas.")
        return redirect("workshop:settings")
    return _render_settings(request, form, ReviewLinkForm(instance=workshop))


def _render_settings(request, form, review_form):
    return render(request, "workshop/settings.html", {
        "form": form, "review_form": review_form, "status": _integration_status(),
    })


@login_required
@require_POST
def review_link(request):
    workshop = request.user.workshop
    form = ReviewLinkForm(request.POST, instance=workshop)
    if form.is_valid():
        form.save()
        log_action("workshop.review_link_updated", request=request, obj=workshop, configured=bool(workshop.google_review_url))
        messages.success(request, "Link de avaliação salvo." if workshop.google_review_url else "Link de avaliação removido.")
        return redirect("workshop:settings")
    return _render_settings(request, WorkshopSettingsForm(instance=type(workshop).objects.get(pk=workshop.pk)), form)


def _review_qr_response(request, *, download=False):
    url = request.user.workshop.google_review_url
    if not url:
        raise Http404
    response = HttpResponse(qr.build_png(url), content_type="image/png")
    if download:
        response["Content-Disposition"] = 'attachment; filename="qrcode-avaliacao-google.png"'
    return response


@login_required
@never_cache
def review_qr(request):
    return _review_qr_response(request)


@login_required
@never_cache
def review_qr_download(request):
    return _review_qr_response(request, download=True)


@login_required
def logo(request):
    return serve_protected_file(request.user.workshop.logo)
