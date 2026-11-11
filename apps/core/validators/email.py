"""Validação de domínio de e-mail (complementa o EmailValidator do Django).

Aceita qualquer domínio válido (empresariais incluídos), sem restringir a
provedores. Verifica sintaxe do domínio: rótulos de 1–63 caracteres, letras,
números e hífen (não nas pontas), ao menos um ponto e TLD alfabético de 2+.
Domínios internacionalizados são aceitos via codificação IDNA.

Decisão: não fazemos consulta DNS/MX na validação do formulário, porque ela
depende de rede, deixa o cadastro lento e falha em redes instáveis. Endereço
inexistente é detectado pelo registro de retorno do SMTP (módulo mailing).
"""
import re

_LABEL = re.compile(r"^(?!-)[a-z0-9-]{1,63}(?<!-)$")
_TLD = re.compile(r"^(?:[a-z]{2,63}|xn--[a-z0-9-]{1,59})$")


def normalize_email(value):
    value = (value or "").strip()
    if "@" not in value:
        return value
    local, _, domain = value.rpartition("@")
    return f"{local}@{domain.lower()}"


def is_valid_email_domain(domain):
    domain = (domain or "").strip().rstrip(".").lower()
    if not domain or len(domain) > 253:
        return False
    try:
        domain = domain.encode("idna").decode("ascii")
    except UnicodeError:
        return False
    labels = domain.split(".")
    if len(labels) < 2:
        return False
    if not all(_LABEL.fullmatch(label) for label in labels):
        return False
    return bool(_TLD.fullmatch(labels[-1]))


def is_valid_email(value):
    value = normalize_email(value)
    if value.count("@") != 1:
        return False
    local, domain = value.split("@")
    if not local or len(local) > 64 or local.startswith(".") or local.endswith(".") or ".." in local:
        return False
    if not re.fullmatch(r"[A-Za-z0-9.!#$%&'*+/=?^_`{|}~-]+", local):
        return False
    return is_valid_email_domain(domain)
