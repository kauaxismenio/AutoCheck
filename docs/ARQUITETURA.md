# Arquitetura do AutoCheck

Documento técnico: como o sistema está organizado e por quê. O histórico etapa por etapa está em
[`PROJECT_CONTEXT.md`](../PROJECT_CONTEXT.md); a especificação original, em [`ESPECIFICACAO.md`](ESPECIFICACAO.md).

## 1. Visão geral

**Monólito modular Django** com renderização no servidor. Cada área de negócio é um app em `apps/`, com modelos,
serviços, views e testes próprios. Princípios seguidos em todo o código:

1. **Regras de negócio no backend.** O JavaScript só dá retorno imediato (máscaras, pré-validação, gravação
   automática); o servidor sempre revalida e decide.
2. **Regras puras sem Django.** `apps/core/validators/` (CPF, CNPJ, telefone, placa, e-mail, texto),
   `apps/core/dates.py`, `apps/attendances/workflow.py` e `apps/photos/categories.py` são Python puro, testados
   isoladamente e reutilizados por modelos, formulários e serviços.
3. **Serviços concentram as operações.** Views chamam funções de `services.py`; o mesmo serviço é usado pelas telas,
   pelos comandos de gerenciamento e pelos testes (inclusive o `seed_demo`).
4. **Configuração só por ambiente.** Segredos ficam no `.env`; `config/settings/` tem `base`, `development`,
   `production` e `test`.

```
Navegador ──HTTP──> Middleware (segurança, CSP, oficina da requisição)
                     └─> View ──> Serviço ──> Modelos (gerenciadores filtram pela oficina)
                                    │             └─> SQLite / PostgreSQL
                                    ├─> Storage privado (fotos, assinaturas, PDFs)
                                    ├─> BrasilAPI (requests, timeout, erros tipados)
                                    └─> EmailDispatch (fila) ──> process_email_queue ──> SMTP
```

## 2. Módulos

| App | Responsabilidade |
|---|---|
| `core` | modelos base, `AuditLog`, storage privado, download protegido, tenancy, middleware de segurança, validadores, PWA, `seed_demo` |
| `accounts` | `User` customizado (login por e-mail), bloqueio após falhas de login (`LoginAttempt`) |
| `platform_admin` | área `/plataforma/` do proprietário: cadastrar, editar e desativar oficinas |
| `workshop` | `WorkshopSettings`: a oficina (nome, logotipo, CNPJ, e-mail do responsável, link de avaliação) |
| `customers`, `vehicles` | cadastro e histórico de clientes e veículos |
| `mechanics`, `employees` | mecânicos e vendedores/atendentes (sem login) |
| `attendances` | `Attendance`, abertura (`intake.py`), fluxo (`workflow.py`), validadores de etapa, resumo |
| `photos` | upload validado, EXIF removido, regras de fotos obrigatórias |
| `checklist`, `tires` | catálogo, avaliação OK/SUBSTITUIR, 5 pneus |
| `replacements`, `services` | recomendação de troca, decisão do cliente, serviços realizados |
| `signatures` | assinatura ou recusa, vinculada ao hash da versão do atendimento |
| `reports` | PDF com ReportLab, versionado |
| `mailing` | `EmailDispatch`: fila persistente de e-mails e o comando `process_email_queue` |
| `integrations` | provedores externos (`providers/`) e `ExternalCallLog` |
| `aftersales` | pós-venda e rotina de retenção `purge_expired` |

## 3. Modelos e relacionamentos

```
WorkshopSettings ──< User, Customer, Vehicle, Attendance, Mechanic, Employee   (cada oficina isolada)
Customer 1─< Vehicle                    (proprietário atual)
Customer 1─< Attendance >─1 Vehicle     (o atendimento guarda o cliente da época)
Attendance >─1 Mechanic · >─1 Employee (atendente) · >─1 User (conta que abriu)
Attendance 1─< Photo                    (fase: check-in, check-out, componente, pneu, peça antiga/nova)
Attendance 1─< ChecklistItem >─1 ChecklistComponent >─1 ChecklistCategory
Attendance 1─< TireInspection           (único por posição)
ChecklistItem | TireInspection 1─1 PartReplacement   (exatamente uma origem — CheckConstraint)
PartReplacement 1─< Photo · 1─1 ServiceRecord;  Attendance 1─< ServiceRecord (também manuais)
Attendance 1─1 AttendanceSignature      (imagem XOR recusa — CheckConstraint; hash SHA-256 da versão)
Attendance 1─< Report (versões) 1─< EmailDispatch
AuditLog · ExternalCallLog · LoginAttempt
```

Decisões relevantes:

- `User` customizado desde a primeira migração (trocar depois exigiria recriar o banco).
- CPF, CNPJ, telefone e placa são guardados sem máscara; CPF, CNPJ e placa são únicos **por oficina**.
- O atendimento copia CNPJ, razão social e e-mail do momento: o PDF e a assinatura continuam corretos mesmo se o
  cadastro mudar depois.
- URLs usam `public_id` (UUID), não a chave sequencial.
- Nomes ficam em maiúsculas (`to_upper` no `save()`); as buscas comparam em maiúsculas.

## 4. Fluxo de atendimento

```
CADASTRO → CHECKIN → CHECKLIST → SERVICOS → CHECKOUT → REVISAO → FINALIZADO
```

- `Attendance.current_step` guarda a etapa atual. `services.get_step_or_403` bloqueia etapas futuras;
  `services.advance` valida a etapa atual **e todas as anteriores** (`step_validators.py`) e avança um passo, com
  `select_for_update` contra avanços concorrentes.
- Reabrir uma etapa antiga e deixá-la incompleta (ex.: marcar SUBSTITUIR depois de passar pelos serviços) impede o
  avanço até ser resolvida.
- Peça recomendada exige decisão do cliente. Autorização exige fotos da peça antiga e da nova e gera o serviço
  realizado; recusa fica registrada e aparece no pós-venda.
- A finalização é transacional: registra assinatura (ou recusa), conclui o atendimento, calcula a data de retenção e
  marca `report_pending`. Depois do commit, gera o PDF e tenta os e-mails; uma falha aí **não desfaz** a conclusão e é
  retomada pelo comando da fila.
- A assinatura guarda o SHA-256 de um retrato canônico do atendimento. Se algo mudar, a assinatura deixa de valer e
  outra é exigida.

## 5. Integrações externas

| Integração | Situação |
|---|---|
| **BrasilAPI** (CNPJ) | Implementada. Chamada só pelo backend, com timeout, `User-Agent` próprio e registro em `ExternalCallLog`. Erros tipados (`NotConfigured`, `NotFound`, `Unavailable`, `InvalidResponse`) nunca bloqueiam o preenchimento manual. Validada contra a API real (testes opcionais `RUN_REAL_API=1`). |
| **Sistema de gestão** | Só o contrato (`providers/management_system.py`) e o tratamento de “não configurado”. Nenhum endpoint foi inventado. |
| **SMTP** | Backend padrão do Django, configurado por ambiente. Testado contra um servidor SMTP local nos testes. |

A consulta por CPF usa somente o cadastro local; não há consulta externa de CPF.

## 6. Fila de e-mails

`EmailDispatch` é ao mesmo tempo o registro de cada envio e a fila persistente — sem Redis, Celery ou serviço externo.

**Estados**

| Estado | Significado |
|---|---|
| Pendente | ainda não enviado (ex.: SMTP não configurado) |
| Em processamento | um processo assumiu o registro (`UPDATE` condicional: só um consegue) |
| Aceito pelo servidor SMTP | o servidor respondeu OK; `accepted_at` preenchido. **Não comprova entrega.** |
| Falha | erro; temporário recebe `next_attempt_at`, definitivo (ex.: 550) não |
| Resultado incerto | a conexão caiu depois de enviar os dados: não se repete sozinho, para não duplicar |
| Entrega confirmada / Devolvido | só por evento de um provedor (`register_provider_event`); nenhuma integração o chama hoje |

**Garantias**

- **Idempotência:** chave única `atendimento + versão do relatório + endereço`. Requisição repetida, duplo clique ou
  comando rodando junto não geram segundo envio automático. Reenvios manuais são registros próprios, com proteção de
  60 s contra duplo clique.
- **Novas tentativas:** 1 min, 5 min, 15 min, 1 h e 4 h; depois disso, só manualmente.
- **Sem SMTP configurado**, nada é marcado como enviado. Backends de console, arquivo e dummy nunca contam como envio.
- **Nova versão do relatório** cancela o que ainda não saiu das versões anteriores.
- Registros presos em “Em processamento” por mais de 15 min viram “incerto”.

**Processamento:** `python manage.py process_email_queue` faz uma passada (útil para testar localmente ou em um
agendador); `--loop` mantém um processo contínuo que termina o envio em curso ao receber Ctrl+C; `--status` só
mostra contagens. A tela do atendimento avisa quando há item atrasado (trabalhador parado).

## 7. Segurança e isolamento entre oficinas

- **Isolamento:** `WorkshopScopeMiddleware` define a oficina da requisição em uma `ContextVar`; os gerenciadores de
  `apps/core/tenancy.py` filtram todas as consultas por ela. Formulários montam querysets no `__init__`. O teste
  `apps/core/tests/test_isolation.py` percorre **todas as rotas** com identificadores de outra oficina e exige 404 (para a outra oficina, o registro
  simplesmente não existe).
- **Perfis:** a conta da oficina usa os módulos da própria oficina; o superusuário (proprietário da plataforma) só
  acessa `/plataforma/`, `/admin/` e `/conta/`. Oficina desativada perde o acesso imediatamente, inclusive sessões
  abertas.
- **Autenticação:** login por e-mail, bloqueio após 5 falhas em 15 minutos por usuário + IP (no banco, vale entre
  processos), logout só por POST, validadores de senha do Django.
- **Arquivos privados:** fotos, assinaturas, logotipos e PDFs ficam fora de pastas públicas, com nomes UUID, e só são
  servidos por views autenticadas que conferem a oficina. Uploads são reabertos e regravados pelo Pillow (arquivo
  falso é recusado), com limite de tamanho e EXIF removido.
- **Cabeçalhos:** CSP sem `unsafe-inline` (nenhum JS ou estilo inline nos templates — há teste para isso),
  `Permissions-Policy`, `X-Frame-Options: DENY`, `nosniff`, `Referrer-Policy`. Em produção: HTTPS obrigatório,
  cookies seguros e HSTS.
- **Configuração:** `DJANGO_SECRET_KEY` é obrigatória; `DEBUG` é falso por padrão e só liga em `development`;
  `production` recusa a chave de exemplo e exige PostgreSQL. `X-Forwarded-For` só é usado com
  `AUTOCHECK_TRUST_PROXY=true`.
- **Erros:** páginas 403/404/500 sem detalhes internos; o detalhe vai para o log do servidor.
- **CSRF** em todos os formulários e chamadas `fetch`.
- **LGPD:** retenção de 6 meses de calendário após a conclusão (`purge_expired`, simulação por padrão), que remove
  registros e arquivos físicos e não exclui nada sem o aceite dos e-mails obrigatórios.

## 8. Testes

| Tipo | Onde | Observação |
|---|---|---|
| Regras puras | `apps/core/tests/test_validators.py`, `test_dates.py`, workflow | sem banco |
| Django (unitários e integração) | `apps/*/tests/` | banco em memória, mídia temporária, e-mail `locmem` |
| Fluxo completo | `apps/attendances/tests/test_full_flow.py` | todas as etapas pelas views, tentando furar o fluxo |
| Isolamento e rotas | `apps/core/tests/test_isolation.py`, `test_security.py` | todas as URLs |
| PDF | `apps/reports/tests/` | texto extraído com pypdf |
| SMTP | `apps/mailing/tests/` | servidor local `aiosmtpd`: aceite, recusa 550, servidor fora do ar |
| Navegador real | `e2e/` | Playwright; só com `RUN_E2E=1` |

## 9. Limitações conhecidas e próximos passos

- Integração com sistema de gestão não implementada (sem documentação de API).
- Nenhum provedor de e-mail envia eventos de entrega/devolução ao sistema (seria um webhook chamando
  `register_provider_event`).
- Não testado em ambiente real: PostgreSQL, HTTPS, instalação do PWA e câmera/assinatura em Android.
- Catálogo do checklist genérico; sem tela para editá-lo (só em `catalog.py` + `seed_checklist`).
- Sem orçamento/valores, estoque ou agenda — fora do escopo da especificação.
- Possíveis evoluções: webhook de provedor de e-mail, edição do catálogo pela interface, pipeline de CI executando a
  suíte, imagem Docker para a demonstração.
