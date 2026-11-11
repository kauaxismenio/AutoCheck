"""Remoção de arquivos físicos vinculada à exclusão dos registros.

O arquivo só é apagado depois do commit, para não perder mídia se a transação
for desfeita. Usado pelos sinais de fotos, assinaturas, relatórios e logotipo.
"""
from django.db import transaction


def delete_file_after_commit(file_field):
    if not file_field or not file_field.name:
        return
    storage, name = file_field.storage, file_field.name

    def _delete():
        if storage.exists(name):
            storage.delete(name)

    transaction.on_commit(_delete)
