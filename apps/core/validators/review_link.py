"""Link de avaliação da oficina no Google. Regra pura, sem Django.

O QR Code é apresentado ao cliente em nome da oficina, por isso só aceita
endereços HTTPS de domínios do próprio Google. A comparação usa o host já
interpretado, para recusar truques como google.com@site.com ou google.com.site.com.
"""
from urllib.parse import urlsplit

GOOGLE_DOMAINS = ("google.com", "google.com.br", "g.page", "goo.gl", "g.co")


def is_valid_review_link(value):
    value = value or ""
    if not value or any(c.isspace() or ord(c) < 32 for c in value):
        return False
    try:
        parts = urlsplit(value)
        port = parts.port
    except ValueError:
        return False
    if parts.scheme != "https" or parts.username or parts.password or port not in (None, 443):
        return False
    host = (parts.hostname or "").lower()
    if not any(host == domain or host.endswith(f".{domain}") for domain in GOOGLE_DOMAINS):
        return False
    return parts.path.strip("/") != "" or bool(parts.query)
