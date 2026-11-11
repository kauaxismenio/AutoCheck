"""Itens do menu lateral. A permissão real é sempre conferida na view."""
from django.urls import reverse

NAV_ITEMS = (
    ("Dashboard", "core:home", "dashboard"),
    ("Atendimentos", "attendances:list", "clipboard"),
    ("Clientes", "customers:list", "users"),
    ("Veículos", "vehicles:list", "car"),
    ("Histórico", "attendances:history", "history"),
    ("Pós-venda", "aftersales:list", "headset"),
    ("Configurações", "workshop:settings", "settings"),
)
PLATFORM_NAV_ITEMS = (("Oficinas", "platform_admin:list", "settings"),)


def build_navigation(request):
    user = getattr(request, "user", None)
    if user is None or not user.is_authenticated:
        return []
    current = request.path
    history_url = reverse("attendances:history")
    items = []
    for label, url_name, icon in PLATFORM_NAV_ITEMS if user.is_superuser else NAV_ITEMS:
        url = reverse(url_name)
        if url == "/":
            active = current == url
        elif url_name == "attendances:list":
            # Histórico fica dentro de /atendimentos/, mas tem o próprio item no menu.
            active = current.startswith(url) and not current.startswith(history_url)
        else:
            active = current.startswith(url)
        items.append({"label": label, "url": url, "icon": icon, "active": active})
    return items
