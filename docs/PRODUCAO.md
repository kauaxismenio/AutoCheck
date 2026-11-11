# Colocar o AutoCheck em produção

Guia de referência para implantar em um servidor; **não foi executado em produção real**. **PostgreSQL ainda não foi testado de verdade**, pois não está instalado nesta
máquina; faça o passo 5 e rode o fluxo completo uma vez antes de usar com clientes reais.

## O que é necessário

- Servidor Linux ou Windows com Python 3.12 ou 3.13.
- PostgreSQL.
- **Domínio com HTTPS.** Sem HTTPS, o aplicativo não instala em celular ou tablet, e a câmera direta pode não abrir.
- Conta SMTP para envio de e-mails.
- Rotina de backup do banco e da pasta `private_media/`.

## Passos

1. Copie o projeto e instale: `pip install -r requirements/production.txt`.
2. Crie o `.env` a partir do `.env.example`, com pelo menos:

   ```
   DJANGO_SECRET_KEY=<nova, nunca reutilize a de desenvolvimento>
   DJANGO_SETTINGS_MODULE=config.settings.production
   DJANGO_ALLOWED_HOSTS=autocheck.suaoficina.com.br
   DJANGO_CSRF_TRUSTED_ORIGINS=https://autocheck.suaoficina.com.br
   DB_ENGINE=postgresql
   POSTGRES_DB=autocheck
   POSTGRES_USER=autocheck
   POSTGRES_PASSWORD=<senha forte>
   POSTGRES_HOST=localhost
   AUTOCHECK_TRUST_PROXY=true
   ```

   `AUTOCHECK_TRUST_PROXY=true` somente atrás de um proxy (Nginx, Caddy) que define `X-Forwarded-For`.
   `DJANGO_SETTINGS_MODULE` precisa estar no ambiente do processo, antes de o Django iniciar.

3. Prepare:

   ```
   python manage.py check --deploy
   python manage.py migrate
   python manage.py seed_checklist
   python manage.py collectstatic --noinput
   python manage.py createsuperuser   # proprietário da plataforma; as oficinas são criadas em /plataforma/
   ```

   O `check --deploy` mostra dois avisos esperados: W005 e W021, sobre HSTS em subdomínios e lista de preload. Ficam
   desligados de propósito, porque valem para o domínio inteiro e são difíceis de desfazer. Ative só se todos os
   subdomínios usarem HTTPS.

4. Inicie o servidor atrás do proxy com HTTPS:

   ```
   # Linux
   gunicorn config.wsgi:application --bind 127.0.0.1:8000 --workers 3 --timeout 90
   # Windows
   python -m waitress --listen=127.0.0.1:8000 config.wsgi:application
   ```

   Use tempo limite de pelo menos 90 segundos: a finalização gera o PDF e faz a primeira tentativa de SMTP dentro da
   requisição. No proxy, limite o tamanho das requisições a uns 15 MB (`client_max_body_size` no Nginx). Não publique
   `private_media/` em nenhuma rota do proxy.

5. Deixe a **fila de e-mails** rodando (obrigatório, ver abaixo).

6. Valide: faça um atendimento completo, abra o PDF, confira o e-mail recebido e instale o aplicativo em um Android.

## Fila de e-mails (obrigatória)

A primeira tentativa acontece na finalização. As novas tentativas, e tudo que ficar para trás se o processo cair, dependem
de `process_email_queue`, um processo separado do site. **Sem ele, um e-mail que falhar não é reenviado sozinho.** O site
nunca inicia esse processo: ele precisa ser mantido pelo sistema operacional, reiniciando em caso de falha.

Linux (systemd), em `/etc/systemd/system/autocheck-fila.service`:

```ini
[Unit]
Description=AutoCheck - fila de e-mails
After=network-online.target

[Service]
User=autocheck
WorkingDirectory=/caminho/autocheck
EnvironmentFile=/caminho/autocheck/.env
Environment=DJANGO_SETTINGS_MODULE=config.settings.production
ExecStart=/caminho/autocheck/.venv/bin/python manage.py process_email_queue --loop
Restart=always
RestartSec=10
TimeoutStopSec=120

[Install]
WantedBy=multi-user.target
```

```
sudo systemctl enable --now autocheck-fila
journalctl -u autocheck-fila -f
```

Windows Server, com o Agendador de Tarefas (uma passada por minuto, sem processo permanente):

```
schtasks /Create /TN "AutoCheck Fila de E-mails" /SC MINUTE /MO 1 /RU SYSTEM /TR "cmd /c cd /d C:\caminho\autocheck && set DJANGO_SETTINGS_MODULE=config.settings.production&& .venv\Scripts\python.exe manage.py process_email_queue"
```

Rode só uma das opções. Rodar dois processos ao mesmo tempo não duplica envios, pois cada registro só é assumido por um deles,
mas não traz vantagem. Atualizou o código? Reinicie também este serviço (`sudo systemctl restart autocheck-fila`).

Acompanhamento:

```
python manage.py process_email_queue --status
```

Só lê: não envia nada. `atrasados` acima de zero indica que o trabalhador está parado; a tela do atendimento mostra o mesmo
aviso. `falhas_sem_nova_tentativa` e `incertos` precisam de reenvio manual. A saída traz só contagens, sem endereços.

| Situação | O que o sistema faz |
|---|---|
| Falha temporária (conexão, autenticação, código 4xx) | Até 6 tentativas: depois de 1 min, 5 min, 15 min, 1 h e 4 h |
| Recusa definitiva (código 5xx) | Não repete; use o reenvio manual depois de corrigir |
| Queda ou tempo esgotado durante o envio | **Resultado incerto:** não repete sozinho, para não duplicar. Confira a mensagem e use o reenvio manual |
| Limite de tentativas atingido | Fica como falha, com o erro registrado; use o reenvio manual |

"Aceito pelo servidor SMTP" não significa entregue. Entrega confirmada e devolução dependem de comprovação do provedor, e o
SMTP do Gmail não informa isso: hoje nenhuma integração preenche esses estados.

Os registros anteriores à fila ficam fora dela e só saem com "Enviar pendentes" na tela do atendimento.

## Rotina

- **Backup:** banco e `private_media/` juntos, pois um depende do outro.
- **Retenção:** rode `python manage.py purge_expired` periodicamente e confira a lista. Só use `--execute` depois de
  conferir. Faça backup antes da primeira execução real.
- **Atualizações:** `pip install -r requirements/production.txt`, `migrate`, `collectstatic` e reinicie o serviço.
- **Monitoramento:** `GET /saude/` responde 200 com o banco acessível, ou 503 caso contrário.
