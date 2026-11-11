# Desenvolvimento com auxílio de IA

O AutoCheck foi desenvolvido com o apoio de ferramentas de IA generativa — principalmente o **Claude** (Anthropic),
na interface web e no **Claude Code**, o assistente de programação em terminal. Este documento descreve como elas
foram usadas e onde ficou a responsabilidade humana.

## Como o trabalho foi organizado

1. **Especificação primeiro.** Os requisitos foram escritos antes do código, em linguagem de negócio, em
   [`ESPECIFICACAO.md`](ESPECIFICACAO.md): fluxo da oficina, regras de cada campo, segurança, LGPD e um plano em
   etapas (seção 22). Esse documento é a fonte da verdade usada em cada sessão com a IA.
2. **Instruções fixas para o assistente.** O arquivo [`CLAUDE.md`](../CLAUDE.md) define as regras de trabalho, por
   exemplo:
   - uma etapa do plano por vez, sem reconstruir o que já foi validado;
   - regras de negócio sempre no backend;
   - **nunca inventar endpoints ou credenciais e nunca simular consultas externas**;
   - **nunca afirmar que algo funciona sem executar** — ao fim de cada etapa, rodar `check` e a suíte de testes e
     relatar o resultado real;
   - separar no relatório o que foi implementado, testado automaticamente, testado manualmente e o que aguarda algo
     externo.
3. **Memória entre sessões.** [`PROJECT_CONTEXT.md`](../PROJECT_CONTEXT.md) registra arquitetura, decisões técnicas
   numeradas, o que foi verificado de verdade em cada etapa e as pendências. Cada sessão começa lendo esse arquivo e
   termina atualizando-o.
4. **Um commit por etapa**, depois da revisão humana do resultado.

## Onde a IA foi usada

| Atividade | Uso |
|---|---|
| Arquitetura | propor a divisão em apps, o mecanismo de isolamento entre oficinas e a fila de e-mails sem infraestrutura externa; as propostas foram discutidas e as decisões registradas em `PROJECT_CONTEXT.md` |
| Implementação | escrever modelos, serviços, views, templates, JavaScript e comandos de gerenciamento, etapa por etapa |
| Testes | escrever testes de regra pura, de integração pelas views, de isolamento (varredura de todas as rotas), de PDF, de SMTP contra servidor local e de navegador real com Playwright |
| Depuração | investigar falhas encontradas pelos testes — por exemplo, o service worker que quebrava com o armazenamento de estáticos com hash, encontrado ao subir um servidor real e coberto depois por teste de regressão |
| Revisão | revisões de segurança (permissões, IDOR, uploads, cabeçalhos, segredos) e de consistência com a especificação |
| Documentação | README, guias técnicos e de produção |

## Responsabilidade humana

- Definir o problema, os requisitos e as prioridades.
- Aprovar ou recusar decisões de arquitetura e de regra de negócio.
- Revisar o resultado de cada etapa, testar as telas e autorizar os commits.
- Decidir o que **não** fazer: não simular a integração com o sistema de gestão sem documentação real, não marcar
  e-mail como entregue sem comprovação do provedor.

## Salvaguardas contra erros da IA

Código gerado por IA pode parecer correto e não funcionar. Por isso o processo dependia de verificação, não de
confiança:

- A suíte de testes roda ao fim de cada etapa e o resultado real é registrado.
- Integrações externas foram verificadas contra o serviço real (BrasilAPI) ou contra um servidor local (SMTP), e o
  que não pôde ser verificado está listado como pendência, não como funcionalidade pronta.
- Regras críticas (fluxo de etapas, isolamento entre oficinas, duplicidade de e-mails) têm testes que tentam
  ativamente burlá-las.
