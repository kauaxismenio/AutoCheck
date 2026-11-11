"""PWA instalável. Não há funcionamento offline nesta versão (decisão da especificação):
o service worker guarda só arquivos públicos e a página "sem conexão", nunca telas
autenticadas, fotos ou relatórios."""
import hashlib
import json

from django.conf import settings
from django.http import JsonResponse
from django.shortcuts import render
from django.templatetags.static import static
from django.urls import reverse
from django.views.decorators.cache import cache_control
from django.views.decorators.http import require_GET

THEME_COLOR = "#f28c18"


def _icon(path, size, purpose="any"):
    return {"src": static(path), "sizes": f"{size}x{size}", "type": "image/png", "purpose": purpose}


@require_GET
def manifest(request):  # noqa: ARG001
    data = {
        "name": "AutoCheck", "short_name": "AutoCheck",
        "description": "Inspeção automotiva e gestão de atendimentos para oficinas.",
        "lang": "pt-BR", "start_url": "/", "scope": "/", "display": "standalone", "orientation": "any",
        "background_color": "#f5f6f8", "theme_color": THEME_COLOR,
        "icons": [
            _icon("img/icons/icon-192.png", 192), _icon("img/icons/icon-512.png", 512),
            _icon("img/icons/maskable-512.png", 512, "maskable"),
        ],
    }
    return JsonResponse(data, content_type="application/manifest+json", json_dumps_params={"ensure_ascii": False})


@require_GET
@cache_control(no_cache=True, max_age=0)
def service_worker(request):
    precache = [reverse("core:offline")] + [
        static(path) for path in ("css/tokens.css", "css/base.css", "css/app.css", "img/icons/icon-192.png")
    ]
    # O nome do cache muda quando os arquivos mudam, o que descarta a versão anterior.
    version = hashlib.sha256("|".join(precache).encode()).hexdigest()[:12]
    response = render(request, "core/sw.js", {
        "cache_name": f"autocheck-{version}", "precache": json.dumps(precache),
        # STATIC_URL, e não static(""): em produção, o armazenamento com hash recusa caminho vazio.
        "offline_url": json.dumps(reverse("core:offline")), "static_prefix": json.dumps(settings.STATIC_URL),
    }, content_type="text/javascript; charset=utf-8")
    response["Service-Worker-Allowed"] = "/"
    return response


@require_GET
def offline(request):
    return render(request, "core/offline.html")
