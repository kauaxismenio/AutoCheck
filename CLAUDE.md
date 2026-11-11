# Instruções para o Claude Code — AutoCheck

Leia antes de qualquer tarefa:
1. `docs/ESPECIFICACAO.md` — especificação completa do sistema (fonte da verdade dos requisitos).
2. `PROJECT_CONTEXT.md` — arquitetura, decisões, status por etapa e pendências.

## Regras de trabalho
- Responder em português do Brasil.
- Ambiente: Windows + PowerShell, Python em `.venv`. Ative com `.\.venv\Scripts\Activate.ps1`.
- Trabalhar uma etapa do plano por vez (seção 22 da especificação). Não reconstruir o que já foi validado
  e não alterar módulos fora da tarefa atual.
- Regras de negócio sempre no backend; o JS só dá retorno imediato.
- Nunca inventar endpoints/credenciais do sistema de gestão. Nunca simular consultas externas.
- Nunca afirmar que algo funciona sem rodar. Ao fim de cada etapa:
  `python manage.py check` e `python manage.py test --settings=config.settings.test`,
  e informe os resultados reais.
- Separar no relatório: implementado / testado automaticamente / testado manualmente / aguardando externo.
- Atualizar `PROJECT_CONTEXT.md` ao concluir cada etapa.
- Segredos só no `.env` (nunca versionado). Não contratar serviços pagos.

## Comandos úteis
- Servidor: `python manage.py runserver`
- Migrações: `python manage.py makemigrations` / `python manage.py migrate`
- Catálogo do checklist: `python manage.py seed_checklist`
