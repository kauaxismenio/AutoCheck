"""Padronização de texto. Regra pura, sem Django.

Usada só em dados identificadores (nomes, marca, modelo, cor). Nunca em e-mail,
URL, senha, nome de acesso ou credencial, que dependem da grafia original.
"""


def to_upper(value):
    """'joão da silva 2' -> 'JOÃO DA SILVA 2'. Mantém acentos, números e pontuação."""
    return (value or "").strip().upper()
