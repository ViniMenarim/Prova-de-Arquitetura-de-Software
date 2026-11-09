# Projeto das duas aulas

## Iniciar

Na pasta do projeto, copie `.env.example` para `.env` e execute:

```powershell
Copy-Item .env.example .env
docker compose up -d --build
```

- Tarefas: `http://localhost:8000/docs`
- Pedidos: `http://localhost:8001/docs`
- Adminer: `http://localhost:8080` — servidor `db`, banco `tarefas_db`
- RabbitMQ: `http://localhost:15672`

Adminer e RabbitMQ usam as credenciais do `.env`. O MySQL fica apenas na rede interna do Compose.

## Tarefas

`GET /tarefas/{id}` retorna 404 se não encontrar a tarefa. `PATCH /tarefas/{id}` atualiza `concluida`:

```powershell
curl.exe http://localhost:8000/tarefas/1
curl.exe http://localhost:8000/tarefas/99999
curl.exe -X PATCH http://localhost:8000/tarefas/1 -H "Content-Type: application/json" -d "{`"concluida`":true}"
```

Se o volume MySQL já existia antes da coluna `concluida`, aplique a migração uma vez:

```powershell
docker compose exec db mysql -uapp -p tarefas_db -e "ALTER TABLE tarefas ADD COLUMN concluida BOOLEAN NOT NULL DEFAULT FALSE"
```

Digite a senha `MYSQL_PASSWORD` do `.env`. `docker compose down -v` apaga os dados do volume.

## Pedidos e mensageria

Envie um pedido e veja os dois workers processarem cópias do evento:

```powershell
curl.exe -X POST http://localhost:8001/pedidos -H "Content-Type: application/json" -d "{`"cliente`":`"Ana Souza`",`"email`":`"ana@example.com`",`"valor_total`":300}"
docker compose logs -f notificacoes-worker estoque-worker
```

Para conferir as DLQs, publique `{malformado` no exchange `pedido.criado.fanout` pelo painel RabbitMQ. Os ADRs e diagramas C4 estão em `docs/`.

Para rodar os testes, entre em `pedidos_api`, instale `requirements.txt` e `requirements-dev.txt` e execute `python -m pytest -q`.
