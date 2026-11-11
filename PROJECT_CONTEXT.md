# PROJECT_CONTEXT — AutoCheck

Documento de continuidade. Atualizar ao final de cada etapa.
Última atualização: 11/11/2026 — preparação para publicação como projeto de portfólio.

## 1. Arquitetura

- **Monólito modular Django 5.2 LTS** (server-side rendering). Cada módulo de negócio é um app em `apps/`.
- **Oficinas independentes:** `WorkshopScopeMiddleware` define a oficina da requisição e os gerenciadores de `apps/core/tenancy.py`
  filtram por ela sozinhos. Formulário com lista de escolha deve montar o queryset no `__init__`, nunca na declaração da classe.
  O proprietário da plataforma (superusuário) só acessa `/plataforma/`, `/admin/` e `/conta/`.
- **Regras de negócio no backend.** O JS só dá retorno imediato (máscaras, pré-validação); o servidor decide.
- **Regras puras em Python sem Django** (`apps/core/validators/`, `apps/core/dates.py`,
  `apps/attendances/workflow.py`, `apps/photos/categories.py`): testáveis isoladamente e reutilizadas por
  modelos, formulários e serviços.
- **Fluxo protegido no servidor:** `Attendance.current_step` + `apps/attendances/services.py`
  (`get_step_or_403`, `advance`) + `step_validators.py` (um validador por etapa). Avanço com
  `select_for_update`, só a partir da etapa atual, um passo por vez.
- **Arquivos privados:** `apps.core.storage.PrivateMediaStorage` grava em `private_media/`, sem URL pública.
  Download só por view autenticada que checa permissão e chama `apps.core.protected_files.serve_protected_file`.
  Caminhos com UUID. Exclusão de registro apaga o arquivo físico após o commit (sinais).
- **Segredos só em variáveis de ambiente** (`.env`, nunca versionado). Settings: `config/settings/{base,development,production,test}.py`.
- **Auditoria:** `apps.core.audit.log_action` → `core.AuditLog`.
- **Integrações** em `apps/integrations/providers/`, com contrato comum (`base.py`) e erros tipados
  (`NotConfigured`, `NotFound`, `Unavailable`, `InvalidResponse`) que nunca bloqueiam o preenchimento manual.

## 2. Estrutura de pastas

```
autocheck/
├─ manage.py · README.md · PROJECT_CONTEXT.md · .env.example · .gitignore
├─ requirements/ base.txt · development.txt · production.txt
├─ config/ urls.py · wsgi.py · asgi.py
│  └─ settings/ env.py · base.py · development.py · production.py · test.py
├─ apps/
│  ├─ core/          base models, AuditLog, storage privado, permissões, validadores, auditoria, testing.py
│  ├─ accounts/      User: conta de acesso da oficina (login por e-mail) ou proprietário da plataforma
│  ├─ platform_admin/ área exclusiva do proprietário: cadastrar oficinas e acompanhar o uso
│  ├─ mechanics/     Mechanic e a base TeamMember (com telas em templates/team/), sem login nem senha
│  ├─ employees/     Employee: vendedor/atendente, mantido em Configurações, sem login nem senha
│  ├─ workshop/      WorkshopSettings (uma por oficina): nome, logo, CNPJ, telefone, endereço, e-mail do responsável, link de avaliação; review_qr.py
│  ├─ customers/     Customer (PF/PJ/Ambos)
│  ├─ vehicles/      Vehicle
│  ├─ attendances/   Attendance, workflow.py, step_validators.py, services.py
│  ├─ photos/        Photo, categories.py, sinais de limpeza
│  ├─ checklist/     ChecklistCategory/Component (catálogo), ChecklistItem, catalog.py, seed_checklist
│  ├─ tires/         TireInspection (5 posições)
│  ├─ replacements/  PartReplacement (recomendação + autorização do cliente)
│  ├─ services/      ServiceRecord (serviços efetivamente realizados)
│  ├─ signatures/    AttendanceSignature + snapshot.py (hash da versão assinada)
│  ├─ reports/       Report (PDF versionado)
│  ├─ mailing/       EmailDispatch (tentativas, erros, aceite SMTP, idempotência)
│  ├─ integrations/  ExternalCallLog, providers/base.py, providers/management_system.py
│  └─ aftersales/    consultas de pós-venda e rotina de retenção (purge_expired)
├─ templates/ base.html · layouts/ · partials/ · uma pasta por módulo · páginas de erro
├─ static/ css/ · js/ (um arquivo por tela) · img/ (ícones)
├─ e2e/             testes em navegador real (Playwright); só rodam com RUN_E2E=1
├─ docs/            ESPECIFICACAO.md · PRODUCAO.md
└─ private_media/   arquivos privados (fora do git)
```

## 3. Entidades e relacionamentos

```
WorkshopSettings ──< User, Customer, Vehicle, Attendance, Mechanic, Employee (cada oficina isolada)
User (accounts) ──< Attendance.created_by (conta logada) / review_qr_presented_by
Employee (employees) ──< Attendance.attendant (vendedor/atendente)
Mechanic (mechanics) ──< Attendance.mechanic (responsável pelos serviços)
Customer 1─< Vehicle (proprietário atual)
Customer 1─< Attendance >─1 Vehicle         (atendimento guarda o cliente da época)
Attendance 1─< Photo                        (fase: checkin, checkout, componente, pneu, peça antiga/nova)
Attendance 1─< ChecklistItem >─1 ChecklistComponent >─1 ChecklistCategory
Attendance 1─< TireInspection               (único por posição)
ChecklistItem|TireInspection 1─1 PartReplacement   (exatamente uma origem — CheckConstraint)
PartReplacement 1─< Photo (peça antiga / nova)
PartReplacement 1─1 ServiceRecord;  Attendance 1─< ServiceRecord (também manuais)
Attendance 1─1 AttendanceSignature          (imagem XOR recusa — CheckConstraint; hash da versão)
Attendance 1─< Report (versões) 1─< EmailDispatch
AuditLog · ExternalCallLog
```

Opções do cliente por atendimento: `cpf_not_informed`, `cnpj_not_informed`, `email_opt_out`,
`customer_email` (cópia; o e-mail do cadastro não é apagado). Origem: `Attendance.origin` (7 opções).

## 4. Status por etapa do plano

| # | Etapa | Status |
|---|-------|--------|
| 1 | Arquitetura, estrutura, ambiente, banco | **Implementada** |
| 2 | Login, usuários, configurações, dashboard | **Implementada** |
| 3 | Cadastro de cliente e veículo (máscaras JS, BrasilAPI) | **Implementada** |
| 4 | Check-in e fotografias | **Implementada** |
| 5 | Checklist e pneus | **Implementada** (catálogo provisório até as capturas do WSmart) |
| 6 | Serviços e substituição de peças | **Implementada** |
| 7 | Check-out e assinatura | **Implementada** |
| 8 | Revisão, PDF e e-mails | **Implementada** (envio real aguardando dados de SMTP) |
| 9 | Histórico e pós-venda (retenção dry-run) | **Implementada** |
| 10 | PWA, segurança, testes de integração, produção | **Implementada** (PostgreSQL e HTTPS reais pendentes de ambiente) |
| 11 | Integração com sistema de gestão | Aguardando documentação |

### Etapa 1 — o que foi verificado de verdade

Primeira execução real em 06/11/2026 (Windows 10, Python 3.12.10, Django 5.2.19, SQLite):

- **Testado automaticamente (executado):** `manage.py test --settings=config.settings.test` →
  64 testes, todos OK: 39 puros — CPF, CNPJ numérico e alfanumérico (inclui o exemplo oficial da
  Receita `12.ABC.345/01DE-35`), telefone, placa, e-mail, meses de calendário, fluxo de etapas, fotos
  obrigatórias — e 25 Django — modelos, constraints, guarda de etapas, assinatura/hash, seed do
  checklist, health check, permissões. `manage.py check` sem problemas.
- **Migrações:** geradas com `makemigrations` e aplicadas com `migrate`; devem ser versionadas.
  `makemigrations --check` sem alterações pendentes. `aftersales` ainda não tem migração (Etapa 9).
- **Seed do checklist:** `seed_checklist` criou 47 componentes no banco de desenvolvimento
  (catálogo provisório até as capturas do WSmart).
- **Aviso conhecido, sem falha:** nos testes, o WhiteNoise avisa que `staticfiles/` não existe,
  porque `collectstatic` ainda não foi rodado.
- **Testado manualmente:** nada ainda (servidor não iniciado, telas não abertas).

Ambiente: o `python` padrão desta máquina é o 3.14, fora da faixa do Django 5.2. Criar o `.venv` com
`py -3.12 -m venv .venv`.

### Etapa 2 — login, usuários, configurações e dashboard

- **Implementado:** login próprio (`/conta/entrar/`) com bloqueio após 5 falhas em 15 min (`LoginAttempt`,
  por usuário + IP); logout só por POST; CRUD de usuários e redefinição de senha (só admin), sem permitir
  remover o último admin; troca da própria senha; configurações da oficina com logotipo privado e regravado
  pelo Pillow (`apps/core/images.py`); situação do SMTP e das integrações sem exibir segredos; dashboard;
  menu lateral (computador inicia aberto e guarda a preferência; celular e tablet iniciam fechados).
- **Testado automaticamente:** 91 testes no total (27 novos).
- **Testado manualmente:** nada ainda.

### Etapa 3 — cadastro de cliente e veículo

- **Implementado:** formulário único de abertura (`attendances/forms.py`, `intake.py`) com cartões CPF/CNPJ/Ambos,
  dispensas independentes, máscaras (`static/js/masks.js`), consulta automática de CNPJ com debounce pelo backend,
  consulta local por CPF e placa, telas de clientes e veículos com busca, cancelamento (só admin) e histórico.
- **Testado automaticamente:** testes Django das regras de cadastro e testes em navegador real (`e2e/`, Edge):
  máscaras ao digitar e colar, cartões, valores preservados, menu em computador/tablet/celular.
- **Consulta real à BrasilAPI (executada):** `00000000000191` retorna dados; `12ABC34501DE35` é aceito e responde
  404 "não encontrado". Não há CNPJ alfanumérico real conhecido para confirmar uma resposta com dados.
- **CPF:** consulta só o cadastro local. O sistema de gestão continua sem documentação; nada é simulado.
- **Rodar os testes em navegador:** `$env:RUN_E2E="1"; python manage.py test e2e --settings=config.settings.test`.

### Etapa 4 — check-in e fotografias

- **Implementado:** componente único de foto (`photos/_slot.html`, `static/js/photo-widget.js`, `capture="environment"`),
  envio validado no servidor (`photos/services.py`), EXIF removido, redimensionamento a 2000 px, arquivo só por view
  autenticada, exclusão com remoção do arquivo físico, resumo do cliente e do veículo na tela.
- **Testado automaticamente:** testes Django de acesso, IDOR, CSRF, arquivo falso, limite de tamanho, bloqueio de etapa
  e envio pelo navegador (arquivo selecionado via Playwright).
- **Testar manualmente:** a abertura real da câmera em celular/tablet Android; o Playwright não aciona câmera real.

### Etapa 5 — checklist e pneus

- **Implementado:** tela única por categoria com OK/SUBSTITUIR, gravação automática a cada alteração
  (`checklist/views.py:autosave`, `static/js/checklist.js`) e formulário completo como reserva; observação e foto
  opcionais por item; 5 pneus com condição, PSI, TWI e foto só quando SUBSTITUIR; recomendação criada e removida
  automaticamente (`replacements/services.py`); item com decisão do cliente registrada não volta a OK sem refazê-la.
- **Testado automaticamente:** testes Django das regras e testes em navegador do preenchimento completo (52 avaliações).
- **Aguardando externo:** ajustar o catálogo e a aparência com as capturas do WSmart.

### Etapa 6 — serviços e substituição de peças

- **Implementado:** cartão por componente recomendado com os estados Aguardando/Autorizado/Não autorizado;
  autorização exige fotos da peça antiga e da nova vinculadas ao componente e a confirmação da troca, que gera o
  serviço realizado sem redigitar nome; recusa não exige foto e mantém a recomendação; serviços manuais; "Alterar
  decisão" limpa fotos e execução; excluir foto de peça desfaz a substituição.
- **Testado automaticamente:** testes Django das regras e fluxo completo em navegador.

### Etapa 7 — check-out, revisão e assinatura

- **Implementado:** check-out com as cinco fotos; resumo completo (`attendances/summary.py`); área de assinatura com
  dedo, caneta ou mouse (`static/js/signature-pad.js`); validação da imagem no servidor (PNG real, não em branco);
  recusa com o texto oficial; opção de avaliação solicitada, sem abrir o Google; finalização transacional; assinatura
  vinculada ao hash da versão, que exige nova coleta se o atendimento mudar.
- **Testado automaticamente:** testes Django e assinatura desenhada no navegador com mouse.
- **Testar manualmente:** assinatura com dedo e caneta em tablet/celular real.

### Etapa 8 — relatório PDF e e-mails

- **Implementado:** PDF com ReportLab (`reports/pdf.py`) com todo o conteúdo da seção 14, cabeçalho, rodapé, "Página X
  de Y", fotos sem corte ou distorção; versões (`reports/services.py`); envio automático após concluir e idempotente,
  com registro de tentativas, erros, destinatários e aceite (`mailing/services.py`); reenvio manual protegido contra
  duplo clique; e-mail de teste nas configurações. Falha no PDF ou e-mail não desfaz a conclusão e pode ser refeita.
- **Testado automaticamente:** conteúdo real do PDF lido com pypdf; envio pelo backend SMTP real contra servidor local
  (aceite, recusa 550 e servidor fora do ar); fluxo completo em navegador com download do PDF. Páginas conferidas a olho.
- **Aguardando externo:** credenciais SMTP. Nenhum e-mail real saiu desta máquina; sem SMTP nada é marcado como enviado.

### Etapa 9 — histórico, pós-venda e retenção

- **Implementado:** histórico com busca e por cliente/veículo (km, serviços, recusas, relatórios); pós-venda com filtros
  por texto, período e pendências; `python manage.py purge_expired` em simulação por padrão, exclusão real só com
  `--execute`, sem agendamento automático. Reavalia as regras antes de apagar, exige aceite dos e-mails obrigatórios,
  remove arquivos físicos e registros, e audita sem dados pessoais.
- **Testado automaticamente:** meses de calendário, simulação sem efeito, bloqueio sem aceite, exclusão de arquivos.

### Etapa 10 — PWA, segurança, integração e produção

- **Implementado:** manifest, ícones originais e service worker (`apps/core/pwa.py`), que guarda só arquivos públicos e a
  página "sem conexão"; CSP sem `unsafe-inline` e Permissions-Policy (`apps/core/middleware.py`); `X-Forwarded-For` só com
  `AUTOCHECK_TRUST_PROXY`; páginas 403/404/500 sem detalhes internos; guia `docs/PRODUCAO.md`.
- **Testado automaticamente:** varredura de TODAS as rotas (exigem login, salvo as públicas declaradas); perfis; cabeçalhos;
  fluxo completo pelas views e pelo navegador; ausência de JS e estilo inline nos templates; cache sem dados privados;
  rolagem horizontal em celular e tablet.
- **Testado com servidor real:** `check --deploy` com settings de produção (apenas os avisos W005/W021, decisão documentada),
  `collectstatic` e waitress respondendo por HTTP com estáticos versionados. Esse teste revelou que o service worker quebrava
  com o armazenamento com hash; corrigido e coberto por teste de regressão.
- **Não testado por falta de ambiente:** PostgreSQL real (não instalado), HTTPS, instalação do PWA e câmera em Android real.

### Complementos após a Etapa 10 — QR Code, vendedores, mecânicos e maiúsculas

- **QR Code:** link em Configurações com formulário próprio (só HTTPS e domínios do Google), QR gerado a cada pedido com `segno`,
  sem arquivo guardado; seção visual na revisão; `review_qr_presented_at/by` registram só a apresentação, com opção de desfazer.
  Os campos antigos `review_requested*` ficam apenas para leitura dos atendimentos anteriores.
- **Mecânicos:** app `apps/mechanics`; perfil Mecânico removido de `Role`, perfil Vendedor criado. Migração: perfil Mecânico vira
  mecânico ativo e a conta antiga fica desativada e sem senha; administrador que era responsável vira mecânico desativado, só para
  o histórico. Novo mecânico é digitado no formulário de abertura e só
  é criado se o atendimento for válido; nome igual (sem considerar caixa e acento, `name_key`) reaproveita o cadastro.
- **Vendedor/atendente:** `Attendance.attendant` (`apps/employees`) é escolhido no início e fica fixo até a finalização, com cadastro em
  Configurações. `created_by` guarda só a conta logada. Atendimentos antigos recebem quem os abriu como cadastro desativado.
- **Maiúsculas:** `apps/core/validators/text.py:to_upper`, aplicada no `save()` dos modelos; máscara `upper` em `masks.js`, marcada por
  `apps/core/forms.py:mark_uppercase`; `core.0002` converte os registros antigos, só dados. As buscas comparam em maiúsculas.
- **Assinaturas antigas:** o hash registrado não é reescrito. `matches_current_version` aceita o retrato antigo convertido com
  `with_uppercase_identifiers`, para a mudança de grafia não exigir nova assinatura. Outra alteração continua exigindo.
- **Volta atrás das migrações:** só restaurando o backup do banco, pois a conversão de mecânicos é de mão única.

### Oficinas independentes

- **Implementado:** login da oficina por e-mail; área `/plataforma/` para o proprietário; um cadastro de vendedor/atendente; dados e
  unicidade de CPF, CNPJ, placa e nomes por oficina; dados existentes atribuídos à oficina já cadastrada, sem apagar nada.
- **Contas:** criadas só na plataforma, com senha gerada exibida uma vez. Contas individuais antigas ficam desativadas. Desativar a
  oficina encerra as sessões abertas (`WorkshopAccountBackend`).
- **Testado automaticamente:** varredura de todas as rotas com identificadores de outra oficina (`apps/core/tests/test_isolation.py`).

### Preparação para publicação como portfólio (11/11/2026)

O objetivo mudou: o AutoCheck deixa de ser entrega comercial e passa a ser projeto público de portfólio.

- **Implementado:** `python manage.py seed_demo` (`apps/core/management/commands/seed_demo.py`): oficina fictícia,
  conta `demo@example.com`, 3 clientes, 3 veículos, 3 atendimentos (1 concluído com PDF, 2 em andamento). Usa os mesmos
  serviços e validadores das telas; só acrescenta dados; idempotente; senha por `AUTOCHECK_DEMO_PASSWORD`, `getpass` ou
  `changepassword`, nunca exibida. Envios da demo ficam fora da fila automática (`next_attempt_at=None`).
- **Dados reais removidos dos arquivos rastreados:** nome/e-mail da oficina original nos testes e um número de celular
  usado como exemplo foram trocados por valores fictícios. O repositório público começa em um commit novo, sem o histórico antigo.
- **Segurança:** `.gitignore` ampliado; `.env.example` revisado; `production` recusa a chave de exemplo/curta.
- **Documentação:** README reescrito, `docs/ARQUITETURA.md`, `docs/DESENVOLVIMENTO_COM_IA.md`, capturas em `docs/img/`
  (geradas a partir da demo).
- **Testado automaticamente:** `apps/core/tests/test_seed_demo.py` (isolamento dos dados existentes, idempotência,
  nenhum e-mail mesmo com a fila rodando, senha fora da saída, senha fraca recusada).
- **Testado manualmente (servidor real + navegador):** demo em banco temporário, login, painel, abertura, checklist,
  resumo, download do PDF (5 páginas).

## 5. Decisões técnicas

1. User customizado criado já na Etapa 1 (trocar depois exigiria recriar o banco).
2. CPF/CNPJ/telefone/placa armazenados sem máscara; CPF e CNPJ únicos quando preenchidos.
3. CNPJ: valor de cada caractere = ASCII − 48, módulo 11, pesos 2–9 (FAQ oficial da Receita Federal).
   Caracteres inválidos fazem a validação falhar (não são removidos silenciosamente).
4. Pneu "ruim" = SUBSTITUIR (mantém o padrão binário OK/SUBSTITUIR).
5. E-mail: valida sintaxe e domínio; sem consulta DNS/MX no formulário (lenta e frágil). Falhas reais
   vêm do retorno do SMTP.
6. Assinatura vinculada à versão: SHA-256 de um retrato canônico do atendimento; qualquer mudança exige nova assinatura.
7. E-mail "aceito" só com aceite do servidor SMTP (`EmailDispatch.accepted_at`), que não comprova a entrega; envio automático com chave de idempotência.
8. Retenção: 6 meses de calendário (`add_months`), configurável por `AUTOCHECK_RETENTION_MONTHS`.
9. PDF com ReportLab (Python puro; WeasyPrint exige bibliotecas nativas no Windows).
10. Telefone: celular = DDD + 9 dígitos iniciando em 9; fixo = DDD + 8 dígitos iniciando em 2–5.
11. Permissões: a conta da oficina usa todos os módulos da própria oficina; só o superusuário administra a plataforma.
12. Nenhum JS inline nos templates, para permitir uma política CSP restritiva na Etapa 10.
13. Git: durante o desenvolvimento, repositório local com um commit por etapa. A publicação como portfólio começou em um repositório novo, com um único commit inicial, sem o histórico anterior.
14. Reaproveitamento no cadastro: cliente por CPF e depois CNPJ; sem documento, o dono da placa só é reutilizado
    se o telefone for o mesmo. Campo em branco nunca apaga dado histórico. Ano e cor são opcionais.
15. `advance` valida a etapa atual e todas as anteriores: reabrir uma etapa antiga e deixá-la incompleta impede
    o avanço (a especificação não permite pular etapas obrigatórias).
16. Atendimento cancelado também recebe `retention_until`, para não guardar dados pessoais indefinidamente.
17. Retenção: ao excluir, cliente e veículo sem nenhum outro atendimento também são removidos (LGPD). Cancelado não
    exige e-mail. Recomendação pendente = recusa não resolvida em atendimento posterior do mesmo veículo.
18. E-mail automático: `EmailDispatch` é a fila persistente (sem serviço externo). A finalização grava
    `Attendance.report_pending` na transação da conclusão, gera o PDF, cria um registro por destinatário e faz a primeira
    tentativa na requisição; `process_email_queue` retoma o resto. Chave: atendimento + versão + endereço (nunca por
    cliente). Só `next_attempt_at` preenchido entra na fila, então os pendentes anteriores não saem sozinhos. Timeout ou
    queda depois de conectar vira INCERTO e não repete sozinho. "Gerar nova versão" envia a versão nova e cancela o que não
    saiu das anteriores. Entrega/devolução só por `register_provider_event`; nenhuma integração o chama ainda.
    O trabalhador (`process_email_queue --loop`) é um processo próprio, nunca iniciado por requisição, e encerra sem cortar um
    envio. Item vencido há mais de 5 minutos gera aviso na tela e aparece em `--status`.
19. CPF e CNPJ são independentes. A consulta por CPF só devolve dados pessoais; a de CNPJ só usa a BrasilAPI, sem olhar o
    histórico. CNPJ, Razão Social, Nome Fantasia, Responsável e modalidade ficam em `Attendance`, de onde saem revisão, PDF,
    retrato da assinatura e busca. Cliente com CPF não recebe CNPJ pelo atendimento; só CNPJ cai no cadastro da própria
    empresa (`cpf` nulo). Atendimentos anteriores receberam, na migração, o que já mostravam. Isto prevalece sobre
    qualquer trecho da especificação que localize o cliente pelo CNPJ.

## 6. Pendências e informações externas

- **Capturas do WSmart** (referência visual e lista de componentes): o catálogo em
  `apps/checklist/catalog.py` é provisório até elas chegarem.
- **API do sistema de gestão:** documentação, autenticação e credenciais. Nada foi inventado.
- **SMTP:** servidor, usuário e senha de envio (ex.: conta da oficina). Envio testado só contra servidor local.
- **Produção:** servidor, PostgreSQL e domínio com HTTPS (`docs/PRODUCAO.md`).
- **Teste em aparelho real:** câmera, assinatura com dedo/caneta e instalação do PWA em Android.
- **BrasilAPI:** formato alfanumérico aceito (404 estruturado), mas sem CNPJ alfanumérico real para confirmar resposta com dados.
