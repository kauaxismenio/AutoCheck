# AUTOCHECK — PROJETO COMPLETO DO SISTEMA WEB PARA OFICINAS MECÂNICAS

Você será o arquiteto de software e principal desenvolvedor responsável por criar o AutoCheck, um sistema profissional de inspeção automotiva e gerenciamento de atendimentos para oficinas mecânicas.

O projeto será iniciado COMPLETAMENTE DO ZERO. Não existe código anterior que você deva presumir que está disponível.

Sua responsabilidade é planejar, desenvolver, organizar, documentar e testar o sistema, entregando uma aplicação funcional e pronta para evoluir até sua utilização real em uma oficina.

**Não quero apenas protótipos, telas demonstrativas ou um planejamento teórico. Quero um sistema de verdade, com frontend, backend, banco de dados, validações, integrações e funcionalidades conectadas.**

Não invente funcionalidades como concluídas. Tudo que for implementado precisa ter comportamento real.

# 1. OBJETIVO DO AUTOCHECK

O AutoCheck será um sistema digital utilizado por oficinas mecânicas para registrar clientes e veículos, realizar inspeções automotivas, documentar as condições dos veículos por fotografias, registrar serviços e substituições de peças, obter autorizações dos clientes e emitir relatórios profissionais.

O sistema substituirá o processo manual de inspeção e documentação da oficina.

O fluxo deverá ser sequencial, organizado e seguro, impedindo que o funcionário pule etapas obrigatórias.

O objetivo é que o mecânico ou atendente consiga realizar todo o atendimento utilizando um tablet, celular Android ou computador.

# 2. TECNOLOGIAS E ARQUITETURA

Preferência tecnológica: Python.

Utilize uma arquitetura moderna, estável, organizada e de fácil manutenção.

Stack desejada:

- Backend: Python com Django.
- Frontend: HTML5, CSS3 e JavaScript.
- Banco de desenvolvimento: SQLite.
- Banco de produção: PostgreSQL.
- Interface responsiva.
- PWA instalável em celulares e tablets Android e computadores.
- Geração de PDF profissional.
- Armazenamento seguro de fotografias e documentos.

A aplicação deverá utilizar internet e banco de dados. Não é necessário desenvolver funcionamento offline nesta versão.

Não contratar serviços pagos nem gerar custos sem autorização.

Utilize bibliotecas gratuitas e adequadas ao projeto sempre que possível.

Organize o código em módulos, separando modelos, formulários, views, serviços, integrações, templates, arquivos estáticos e testes.

Não concentre toda a aplicação em um único arquivo Python ou JavaScript.

# 3. USUÁRIOS, LOGIN E CONFIGURAÇÕES

Criar uma tela profissional de login.

O sistema deverá possuir autenticação e controle de acesso.

Modelo de acesso:

- Proprietário da plataforma: único com administração geral. Só ele cadastra oficinas e acompanha quantas usam o AutoCheck. Não há cadastro público.
- Oficina: conta independente, com login próprio por e-mail e senha. Todos que usam esse acesso veem o dashboard e as configurações. Não há perfis individuais.

Cada oficina acessa exclusivamente os próprios clientes, veículos, atendimentos, vendedores/atendentes, mecânicos e configurações. Não há filiais ou unidades dentro de uma oficina.

Vendedor/atendente é uma só função: cadastro com nome completo e situação (ativo/inativo), sem login, senha ou e-mail. É selecionado obrigatoriamente no início do atendimento e permanece responsável até a finalização.

Mecânicos têm cadastro separado, sem login nem senha, e podem ser adicionados, editados e desativados. A seleção do mecânico fica no fim da primeira etapa, junto aos dados do veículo e à quilometragem.

Dados identificadores ficam em MAIÚSCULAS, inclusive no backend: nome completo, razão social, nome fantasia, marca, modelo, cor, placa, nomes de vendedores/atendentes e mecânicos e nome da oficina. E-mails, URLs, senhas e credenciais mantêm a grafia original.

O responsável deverá possuir acesso às configurações da oficina e aos dados administrativos.

Criar uma área de configurações contendo:

- Nome da oficina.
- Logotipo.
- CNPJ da oficina.
- Telefone.
- Endereço.
- E-mail fixo do responsável pelo recebimento dos relatórios.
- Configurações do serviço de e-mail.
- Dados necessários às integrações externas.
- Configurações dos usuários.

O e-mail do responsável pela oficina será configurado uma vez, podendo ser alterado pelo administrador.

Credenciais e chaves deverão ficar em variáveis de ambiente, nunca expostas no frontend ou no repositório.

# 4. DASHBOARD

Criar um painel inicial profissional, inspirado no funcionamento de sistemas de gestão de oficinas.

O dashboard deverá apresentar:

- Atendimentos realizados.
- Atendimentos em andamento.
- Atendimentos concluídos.
- Clientes cadastrados.
- Veículos cadastrados.
- Atividades recentes.
- Acesso rápido para iniciar um novo atendimento.

Criar menu lateral responsivo com botão hambúrguer de três linhas.

Comportamento do menu:

- Em computadores, iniciar aberto, mas permitir recolher.
- Em celulares e tablets, iniciar fechado.
- Ao navegar entre páginas, preservar a preferência do usuário.
- Não reabrir automaticamente o menu a cada nova tela.

Criar navegação clara entre Dashboard, Atendimentos, Clientes, Veículos, Histórico, Pós-venda e Configurações.

# 5. PRIMEIRA ETAPA — CADASTRO DE CLIENTE E VEÍCULO

Esta etapa inicia obrigatoriamente todos os atendimentos.

O cadastro de cliente e veículo será realizado na mesma etapa, com os campos organizados de forma clara.

## 5.1. Identificação do cliente

Exibir três cartões selecionáveis:

- CPF — Pessoa Física.
- CNPJ — Pessoa Jurídica.
- Ambos — Permitir informar CPF e CNPJ.

Esses cartões devem ser botões reais, inteiramente clicáveis.

Ao selecionar:

- Destacar o cartão escolhido.
- Usar borda e fundo alaranjados para a seleção.
- Deixar os outros cartões neutros, mas visualmente clicáveis.
- Mostrar um indicador de seleção somente no cartão ativo.
- Atualizar imediatamente os campos exibidos.

Não utilizar cartões meramente decorativos.

### CPF

Exibir:

- Nome completo.
- CPF.

O nome será obrigatório.

CPF terá a opção:

"Cliente não deseja informar CPF".

Quando marcada, esconder o campo CPF e dispensar sua validação e obrigatoriedade.

### CNPJ

Exibir:

- CNPJ.
- Razão Social.
- Nome Fantasia.
- Responsável, quando aplicável.

Razão Social obrigatória quando o cadastro empresarial for informado.

Nome Fantasia opcional.

Disponibilizar o checkbox:

"Cliente não sabe ou não deseja informar CNPJ".

Quando marcado, esconder somente o campo CNPJ, mantendo os demais campos empresariais disponíveis.

### Ambos

Exibir os campos pessoais e empresariais.

As dispensas de CPF e CNPJ devem ser independentes.

Não perder os valores digitados quando o usuário alternar entre modalidades ou marcar e desmarcar os checkboxes.

Campos ocultos não poderão bloquear o formulário por validações HTML.

## 5.2. Máscaras e validações de documentos

Todas as máscaras devem funcionar automaticamente enquanto o usuário digita e também quando cola informações.

Não basta colocar exemplos nos placeholders.

### CPF

Formato:

`000.000.000-00`

Regras:

- Aceitar somente números.
- Aplicar a máscara automaticamente.
- Validar os dígitos verificadores.
- Rejeitar documentos inválidos.
- Validar também no backend Django.

### CNPJ

O sistema deverá aceitar tanto o CNPJ numérico tradicional quanto o novo formato alfanumérico.

Isso é obrigatório: o CNPJ alfanumérico começou a ser implantado no Brasil em julho de 2026.

Regras:

- Aceitar letras de A a Z e números nas primeiras 12 posições.
- Os dois últimos caracteres serão exclusivamente numéricos.
- Normalizar letras para maiúsculas.
- Aplicar a máscara correspondente.
- Validar os dígitos verificadores de acordo com a especificação oficial da Receita Federal.
- Continuar aceitando todos os CNPJs numéricos tradicionais.
- Validar também no backend Django.

Não inventar um algoritmo próprio. Utilizar a documentação técnica oficial da Receita Federal.

Documentação oficial:
https://www.gov.br/receitafederal/pt-br/centrais-de-conteudo/publicacoes/documentos-tecnicos/cnpj

## 5.3. Preenchimento automático de CNPJ

Quando o usuário terminar de informar um CNPJ válido, o sistema deverá realizar uma consulta automática.

Utilizar a BrasilAPI ou outro serviço gratuito e confiável, verificando previamente a compatibilidade com os formatos de CNPJ utilizados.

O sistema deverá buscar e preencher:

- Razão Social.
- Nome Fantasia.

Fluxo esperado:

1. Usuário digita o CNPJ.
2. Sistema verifica se o número está completo.
3. Sistema valida os dígitos verificadores.
4. Realiza a consulta automaticamente.
5. Exibe indicador de carregamento.
6. Recebe os dados cadastrais.
7. Preenche Razão Social e Nome Fantasia.
8. Permite edição manual dos campos preenchidos.

Implementar debounce para evitar requisições excessivas.

Tratar CNPJ inexistente, falha de conexão, indisponibilidade e respostas incompletas.

A consulta não pode impedir o preenchimento manual quando falhar.

Não apresentar dados falsos como se fossem resultados de uma consulta real.

A integração deverá passar pelo backend, sem expor credenciais no navegador.

## 5.4. Consulta de CPF

A oficina utiliza um sistema próprio de gestão.

Existe a intenção de integrar a consulta de CPF com a API desse sistema para localizar clientes e preencher seus dados automaticamente.

Entretanto, a documentação técnica e as credenciais dessa API ainda não foram fornecidas.

Portanto:

- Criar uma estrutura de integração modular.
- Não inventar endpoints.
- Não simular uma consulta real.
- Permitir preenchimento manual normalmente.
- Deixar o serviço preparado para receber a documentação e as credenciais posteriormente.

Quando essa documentação estiver disponível, a integração deverá consultar o CPF e retornar os dados permitidos pelo sistema da oficina.

# 6. DADOS DE CONTATO

Campos:

- Telefone.
- E-mail.

O telefone será obrigatório.

### Telefone

Aplicar máscara automaticamente.

Exemplo:

`(81) 9 9000-1712`

Regras:

- Aceitar somente números.
- Aceitar telefones fixos e celulares.
- Suportar oito ou nove dígitos, conforme o tipo.
- Formatar durante a digitação.
- Tratar colagem.
- Validar quantidade de dígitos.
- Validar também no backend.

### E-mail

O e-mail será opcional.

Checkbox:

"Cliente não deseja informar e-mail ou receber o relatório".

Quando marcado:

- Esconder o campo.
- Não exigir preenchimento.
- Desabilitar a validação.
- Registrar a opção do cliente.

Quando desmarcado, mostrar novamente o campo.

Validar o formato do endereço e o domínio, sem restringir a Gmail ou Outlook. Permitir domínios empresariais válidos.

Não apagar o e-mail histórico do cliente se ele optar por não informar o endereço naquele atendimento.

Essa decisão deverá controlar o envio do relatório posteriormente.

# 7. DADOS DO VEÍCULO

O cadastro do veículo será realizado na mesma etapa do cliente.

Campos:

- Placa.
- Marca.
- Modelo.
- Ano.
- Cor.
- Quilometragem.
- Mecânico responsável.

### Placa

Aceitar os dois formatos brasileiros:

Antigo:
`ABC-1234`

Mercosul:
`ABC1D23`

Regras:

- Letras maiúsculas.
- Aceitar letras e números válidos.
- Aplicar a formatação automaticamente.
- Validar os formatos.
- Tratar colagem.
- Validar também no backend.

### Quilometragem

- Aceitar somente números.
- Não permitir letras.
- Não converter para maiúsculas.

Não incluir campo de chassi ou endereço nesta tela de atendimento.

Não apagar dados históricos de endereço ou chassi caso sejam necessários em outras partes do sistema.

# 8. ORIGEM DO ATENDIMENTO

No final do formulário, incluir um único menu suspenso obrigatório com o título:

"Como conheceu nossa loja?"

Opções:

- Indicação.
- Instagram.
- Anúncio.
- Google/Internet.
- Já é cliente.
- Fachada.
- Outro.

Não utilizar botões de rádio ou múltiplos blocos de opções.

Salvar o valor selecionado no atendimento.

# 9. SEGUNDA ETAPA — CHECK-IN E FOTOGRAFIAS DE ENTRADA

Após concluir o cadastro, avançar para a etapa de check-in.

Apresentar um resumo dos dados do cliente e do veículo.

Fotografias obrigatórias:

- Frente do veículo.
- Lateral direita.
- Lateral esquerda.
- Traseira.
- Painel mostrando a quilometragem.

Fotografias opcionais:

- Arranhões.
- Avarias.
- Danos existentes.
- Detalhes específicos.

Permitir múltiplas fotografias por categoria quando necessário.

As fotografias deverão ser capturadas diretamente pela câmera do dispositivo, sempre que possível.

Não salvar permanentemente as fotografias na galeria pessoal do aparelho por iniciativa do sistema. Armazená-las no ambiente privado da aplicação.

O usuário deverá conseguir visualizar as fotografias antes de confirmar.

Não permitir avançar sem as cinco fotografias obrigatórias.

Não incluir campo de observações iniciais.

# 10. TERCEIRA ETAPA — CHECKLIST AUTOMOTIVO

Criar um checklist profissional, baseado nas referências visuais do aplicativo WSmart que serão fornecidas separadamente.

Organizar o checklist por categorias.

Categorias previstas:

- Suspensão.
- Freios.
- Lubrificantes.
- Filtros.
- Pneus.
- Iluminação.
- Componentes elétricos.
- Outros componentes automotivos identificados nas referências.

Cada componente deverá possuir uma avaliação obrigatória:

- OK.
- SUBSTITUIR.

Não existe a opção "Não verificado".

O sistema deve impedir o avanço enquanto existir algum item sem avaliação.

Observações gerais e fotografias dos componentes serão opcionais, salvo nas regras específicas abaixo.

## 10.1. Pneus

Avaliar individualmente cinco posições:

- Dianteiro direito.
- Dianteiro esquerdo.
- Traseiro direito.
- Traseiro esquerdo.
- Estepe.

Para cada pneu:

- Condição obrigatória.
- Calibragem em PSI obrigatória.
- Medição TWI opcional.
- Fotografia obrigatória somente quando o pneu estiver classificado como ruim ou exigir substituição.

Se o pneu estiver OK, não exigir TWI nem fotografia.

# 11. QUARTA ETAPA — EXECUÇÃO DOS SERVIÇOS E SUBSTITUIÇÃO DE PEÇAS

Quando o mecânico marcar um componente como SUBSTITUIR:

1. Registrar automaticamente o componente recomendado.
2. Identificar a peça.
3. Solicitar a decisão do cliente.
4. Registrar a autorização ou recusa.

Estados possíveis:

- Aguardando decisão.
- Autorizado.
- Não autorizado.

Se o cliente autorizar:

- Exigir fotografia da peça antiga.
- Exigir fotografia da peça nova.
- Vincular as duas fotografias ao componente correto.
- Registrar a substituição realizada.

Se o cliente não autorizar:

- Registrar formalmente a recusa.
- Não exigir fotografias.
- Manter a recomendação no relatório final.

Não solicitar ao mecânico que digite novamente o nome do componente.

Não criar observações obrigatórias duplicadas.

Registrar quais serviços foram efetivamente realizados.

# 12. QUINTA ETAPA — CHECK-OUT E FOTOGRAFIAS DE SAÍDA

Fotografias obrigatórias:

- Frente.
- Lateral direita.
- Lateral esquerda.
- Traseira com placa visível.
- Painel.

Não repetir as fotografias das peças substituídas.

Não incluir observações finais obrigatórias.

Impedir avanço sem as fotografias necessárias.

# 13. SEXTA ETAPA — REVISÃO E FINALIZAÇÃO

Antes de finalizar, mostrar um resumo organizado de todo o atendimento.

Apresentar:

- Dados do cliente.
- Dados do veículo.
- Quilometragem.
- Fotografias de entrada.
- Checklist.
- Componentes avaliados.
- Componentes recomendados.
- Serviços realizados.
- Substituições autorizadas.
- Substituições recusadas.
- Fotografias das peças.
- Fotografias de saída.

## Assinatura digital

Criar uma área para assinatura diretamente na tela.

Permitir assinatura com dedo ou caneta digital em celulares e tablets.

Antes de assinar, apresentar as recomendações, autorizações e recusas.

Disponibilizar a opção:

"CLIENTE NÃO ACEITOU ASSINAR".

Quando marcada, registrar a recusa e apresentar no relatório PDF o seguinte texto:

"O cliente foi informado sobre as condições identificadas no veículo e os serviços recomendados, bem como sobre as autorizações e recusas registradas neste relatório. O cliente optou por não registrar sua assinatura digital."

A assinatura ou recusa deverá estar vinculada à versão final do atendimento e das autorizações.

## Avaliação Google

Nas configurações, o responsável informa o "LINK DE AVALIAÇÃO DA OFICINA NO GOOGLE". O sistema gera o QR Code, com pré-visualização e download em PNG.

Na finalização, exibir o QR Code com um convite e a orientação para o cliente escanear, e a ação:

"QR CODE APRESENTADO AO CLIENTE".

O registro indica apenas que o código foi apresentado, sem afirmar que uma avaliação foi publicada.

Não abrir automaticamente o Google.

# 14. RELATÓRIO PDF PROFISSIONAL

Gerar um PDF profissional ao concluir o atendimento.

O documento deverá conter:

- Logotipo e dados da oficina.
- Identificação do atendimento.
- Dados do cliente.
- Dados do veículo.
- Quilometragem.
- Fotografias de entrada.
- Checklist completo.
- Avaliação dos componentes.
- Recomendações de substituição.
- Autorizações e recusas.
- Serviços executados.
- Fotografias das peças antigas e novas, quando aplicável.
- Fotografias de saída.
- Assinatura digital ou registro da recusa.

Requisitos:

- Boa diagramação.
- Identidade visual profissional.
- Fotografias com tamanho adequado.
- Paginação correta.
- Cabeçalho e rodapé.
- Evitar cortes e imagens distorcidas.
- Permitir geração e reenvio do PDF.

# 15. ENVIO DE E-MAIL

Após finalizar o atendimento, enviar o PDF:

1. Sempre para o e-mail configurado do responsável pela oficina.
2. Para o cliente somente quando ele tiver fornecido um e-mail e não tiver optado por não receber o relatório.

Implementar:

- Configuração SMTP por variáveis de ambiente.
- Registro de tentativas.
- Registro de erros.
- Identificação dos destinatários.
- Confirmação de aceitação pelo serviço de e-mail.
- Possibilidade de reenvio.
- Proteção contra envio duplicado indevido.

Não considerar um e-mail enviado apenas porque a função foi chamada. Registrar o resultado informado pelo serviço.

# 16. HISTÓRICO DE CLIENTES E VEÍCULOS

O sistema deverá manter o histórico dos atendimentos durante seis meses após a conclusão.

Um mesmo cliente poderá possuir vários veículos.

Um mesmo veículo poderá possuir vários atendimentos ao longo do tempo.

Permitir consultar:

- Dados do cliente.
- Dados dos veículos.
- Atendimentos anteriores.
- Quilometragem registrada.
- Checklist anterior.
- Serviços realizados.
- Peças substituídas.
- Recomendações não autorizadas.
- Relatórios anteriores.

Criar telas de busca e consulta.

# 17. PÓS-VENDA

Criar um módulo de pós-venda para acompanhamento dos clientes.

Permitir consultar atendimentos concluídos e identificar:

- Serviços realizados.
- Peças substituídas.
- Recomendações pendentes.
- Serviços recusados.
- Data do atendimento.
- Quilometragem.

O histórico será mantido por seis meses após a conclusão, conforme a regra de retenção definida.

A exclusão dos dados expirados deverá ocorrer somente depois que os envios de e-mail obrigatórios forem confirmados.

A exclusão deverá abranger arquivos físicos de mídia e registros correspondentes.

Não implementar exclusão automática sem mecanismos de segurança e auditoria.

Criar inicialmente uma rotina de limpeza em modo simulação (dry-run). A execução efetiva deverá exigir comando explícito.

Utilizar seis meses de calendário, não uma aproximação fixa de 180 dias.

# 18. SEGURANÇA E PRIVACIDADE

O sistema armazenará dados pessoais e fotografias de clientes e veículos.

Implementar boas práticas de segurança:

- Autenticação.
- Controle de permissões.
- Proteção CSRF.
- Validação no backend.
- Proteção contra acesso indevido.
- Proteção de arquivos enviados.
- Restrições de acesso às fotografias.
- Segredos em variáveis de ambiente.
- Tratamento seguro de erros.
- Registro de operações importantes.

Fotografias e documentos não podem ficar publicamente acessíveis por URLs sem autenticação e autorização.

Considerar a LGPD e armazenar somente os dados necessários ao atendimento.

# 19. INTERFACE E EXPERIÊNCIA DO USUÁRIO

Utilizar como referência visual as capturas do WSmart que serão anexadas a esta conversa.

Não copiar marcas, logotipos ou identidade proprietária. Utilizar a organização visual como referência de experiência.

Estilo desejado:

- Tema claro como padrão.
- Fundo branco e cinza suave.
- Cartões com bordas discretas.
- Botões grandes e fáceis de tocar.
- Laranja/amarelo como cor de destaque.
- Verde para OK.
- Vermelho para substituição, recusa ou alerta.
- Tipografia legível.
- Espaçamento adequado.
- Formulários organizados.
- Visual profissional e moderno.

A aplicação deve funcionar adequadamente em:

- Computador.
- Tablet Android.
- Celular Android.

Criar indicadores de progresso que mostrem claramente a etapa atual do atendimento.

Não permitir pular etapas obrigatórias.

A interface deve ser consistente em todas as telas.

# 20. REGRAS DE ARQUITETURA E QUALIDADE DO CÓDIGO

Organizar a aplicação em módulos independentes.

Separar, no mínimo:

- Autenticação.
- Clientes.
- Veículos.
- Atendimentos.
- Fotografias.
- Checklist.
- Pneus.
- Serviços.
- Substituição de peças.
- Autorizações.
- Assinaturas.
- Relatórios.
- E-mails.
- Integrações.
- Pós-venda.
- Configurações.

Utilizar nomes claros e documentação objetiva.

Evitar duplicação de código.

Evitar funções gigantes.

Não colocar regras de negócio exclusivamente no JavaScript.

Todas as regras importantes devem possuir validação no backend.

As etapas do atendimento devem ser protegidas no servidor para impedir que alguém pule uma fase alterando a URL ou manipulando o navegador.

# 21. INTEGRAÇÃO COM O SISTEMA DE GESTÃO DA OFICINA

Um dos objetivos principais do projeto é integrar o AutoCheck ao sistema de gestão já utilizado pela oficina.

A API específica ainda será disponibilizada posteriormente.

Prepare uma camada independente de integração para permitir:

- Consultar clientes pelo CPF.
- Consultar dados existentes de clientes.
- Consultar veículos, quando suportado.
- Preencher dados automaticamente.
- Enviar ou sincronizar informações, conforme as possibilidades da API.

Não invente endpoints, parâmetros ou credenciais.

Quando a documentação for fornecida, analisar os recursos disponíveis e implementar a integração de forma segura.

Enquanto isso, o AutoCheck deverá funcionar integralmente com os cadastros manuais e com as integrações que já possuem fonte e documentação disponíveis.

# 22. ESTRATÉGIA DE DESENVOLVIMENTO NO CLAUDE WEB

Este projeto será desenvolvido utilizando o Claude Web, e não presumindo que você tenha acesso direto ao computador ou ao terminal local do usuário.

Portanto:

- Não afirme que criou arquivos diretamente no computador do usuário se isso não ocorreu.
- Utilize os recursos de criação de arquivos, projetos ou artefatos disponíveis na plataforma.
- Quando possível, entregue os arquivos organizados em um projeto completo e disponibilize um pacote para download.
- Se não for possível gerar um pacote, apresente os arquivos com seus caminhos completos e conteúdo integral, organizados em lotes coerentes.
- Nunca entregue apenas trechos incompletos quando o usuário precisar do arquivo inteiro.
- Forneça comandos exatos para instalar, configurar e executar o projeto no Windows PowerShell.
- Mantenha um documento `PROJECT_CONTEXT.md` atualizado com a arquitetura, as funcionalidades concluídas, os arquivos criados, as decisões e as pendências, para permitir continuidade em outras conversas.

## Desenvolvimento por etapas

Não tente gerar todo o sistema em uma única resposta enorme.

Implemente em etapas integradas:

1. Arquitetura, estrutura inicial, ambiente e banco de dados.
2. Login, usuários, configurações e dashboard.
3. Cadastro completo de clientes e veículos.
4. Check-in e fotografias.
5. Checklist automotivo e pneus.
6. Serviços e substituição de peças.
7. Check-out e assinatura digital.
8. Revisão, PDF e envio de e-mails.
9. Histórico e pós-venda.
10. PWA, segurança, testes de integração e preparação para produção.
11. Integração com o sistema de gestão da oficina, quando a documentação estiver disponível.

Cada etapa deverá funcionar e ser testada antes de depender dela na próxima.

Não reconstruir funcionalidades que já foram concluídas e validadas.

Não fazer auditorias gerais repetidas sem necessidade.

Não alterar módulos que não estejam relacionados à tarefa atual.

Manter uma documentação curta e objetiva das decisões técnicas.

## Testes e honestidade técnica

Criar testes automatizados para as regras de negócio.

Quando existir ambiente de execução disponível, executar os testes e informar os resultados reais.

Quando não existir, apresentar os comandos e deixar explícito que os testes ainda precisam ser executados pelo usuário.

Nunca afirmar que uma API foi testada sem realizar uma consulta real.

Nunca afirmar que uma funcionalidade está funcionando apenas porque o código foi escrito.

Separar claramente:
- Implementado.
- Testado automaticamente.
- Testado manualmente.
- Aguardando credenciais ou documentação externa.

## Controle de escopo e custos

Não contratar serviços pagos.

Não adicionar serviços que gerem custos sem autorização.

Não complicar a arquitetura sem necessidade.

Priorizar um sistema funcional, seguro e de fácil manutenção.

Não abandonar uma etapa com funções essenciais pendentes.

# 23. PRIMEIRA RESPOSTA E INÍCIO DO PROJETO

Leia toda esta especificação antes de começar.

Primeiro, apresente:

1. A arquitetura técnica que será utilizada.
2. A estrutura de pastas do projeto.
3. As principais entidades e relacionamentos do banco de dados.
4. A estratégia para desenvolver as etapas sem criar retrabalho.
5. As dependências necessárias.

Depois, comece a construir a primeira versão do projeto, com a estrutura inicial e a preparação do ambiente.

Não faça perguntas sobre requisitos que já estão definidos neste documento.

Se faltar alguma informação realmente indispensável, identifique exatamente o que falta e continue implementando as partes que não dependem dela.

O objetivo final é entregar o AutoCheck completo e funcional, não apenas uma demonstração visual.