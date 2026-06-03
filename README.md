# Bolão da Copa 2026 — Backend

Backend FastAPI para o sistema de bolão da Copa do Mundo 2026.

## Setup local

### 1. Pré-requisitos

- Python 3.11+
- PostgreSQL rodando localmente (ou credenciais do Supabase)

### 2. Instalar dependências

```bash
pip install -r requirements.txt
```

### 3. Configurar variáveis de ambiente

```bash
cp .env.example .env
# Edite .env com suas credenciais
```

Variáveis obrigatórias:

| Variável | Descrição |
|---|---|
| `DATABASE_URL` | Connection string PostgreSQL |
| `DB_SSL_REQUIRED` | `true` para Supabase, `false` para local |
| `JWT_SECRET` | Chave secreta para assinar tokens JWT |
| `JWT_EXPIRE_MINUTES` | Expiração do token (ex: `60`) |
| `WORLDCUP_API_EMAIL` | E-mail para autenticar na API externa |
| `WORLDCUP_API_PASSWORD` | Senha para autenticar na API externa |
| `WORLDCUP_API_TOKEN` | Preenchido automaticamente pelo script abaixo |
| `ADMIN_API_KEY` | Chave para endpoints administrativos |
| `CORS_ORIGINS` | Origens permitidas (ex: `http://localhost:3000`) |

### 4. Criar o banco de dados (local)

```sql
CREATE DATABASE bolao;
```

### 5. Aplicar migrations

```bash
alembic upgrade head
```

### 6. Obter token da API externa de jogos

Execute **uma única vez** durante o setup:

```bash
python scripts/setup_external_api.py
```

O script registra uma conta na API `worldcup26.ir` (ou faz login se já existir) e salva o token em `WORLDCUP_API_TOKEN` no `.env`. O token dura 84 dias. Após esse prazo, o sistema renova automaticamente.

### 7. Rodar o servidor

```bash
uvicorn app.main:app --reload
```

Acesse a documentação interativa em: http://localhost:8000/docs

---

## Endpoints

### Autenticação (`/auth`)

| Método | Rota | Descrição |
|---|---|---|
| POST | `/auth/register` | Cadastro de novo usuário |
| POST | `/auth/login` | Login, retorna token JWT |
| GET | `/auth/me` | Dados do usuário autenticado |

### Competições (`/competitions`)

| Método | Rota | Descrição |
|---|---|---|
| POST | `/competitions` | Criar nova competição |
| GET | `/competitions` | Listar competições do usuário |
| GET | `/competitions/{id}` | Detalhes + ranking da competição |
| POST | `/competitions/{id}/invite` | Gerar novo código de convite |
| POST | `/competitions/join` | Entrar via código de convite |
| DELETE | `/competitions/{id}` | Encerrar competição (admin) |

### Jogos (`/matches`)

| Método | Rota | Descrição | Auth |
|---|---|---|---|
| GET | `/matches` | Listar jogos (filtros: `round`, `date`, `stage`) | JWT |
| GET | `/matches/{id}` | Detalhes do jogo + times | JWT |
| POST | `/matches/sync` | Forçar sincronização com API externa | Admin |

### Apostas (`/bets`)

| Método | Rota | Descrição |
|---|---|---|
| POST | `/bets` | Registrar/atualizar aposta |
| GET | `/bets` | Minha aposta (`?competition_id=&match_id=`) |
| GET | `/bets/competition/{id}` | Apostas da competição |

### Pontuação (`/scoring`)

| Método | Rota | Descrição | Auth |
|---|---|---|---|
| POST | `/scoring/update/{match_id}` | Calcular pontuação após jogo terminar | Admin |

---

## Endpoints administrativos

Os endpoints de admin exigem o header `X-Admin-Key` com o valor de `ADMIN_API_KEY`:

```bash
curl -X POST http://localhost:8000/matches/sync \
  -H "X-Admin-Key: sua-chave-admin"

curl -X POST http://localhost:8000/scoring/update/1 \
  -H "X-Admin-Key: sua-chave-admin" \
  -H "Content-Type: application/json" \
  -d '{"top_scorer": "Lionel Messi"}'
```

---

## Sistema de pontuação

| Situação | Pontos |
|---|---|
| Placar exato | **5 pts** |
| Resultado correto (quem ganhou / empate) | **2 pts** |
| Artilheiro do jogo correto (bônus) | **+1 pt** |
| Tudo errado | 0 pts |

Máximo por jogo: **6 pontos**.

---

## Deploy (Vercel + Supabase)

1. Configure `DATABASE_URL` apontando para o Supabase e `DB_SSL_REQUIRED=true`
2. Cadastre todas as variáveis do `.env` no painel do Vercel em **Settings → Environment Variables**
3. O `vercel.json` já está configurado para servir o FastAPI como serverless function

---

## Comandos úteis

```bash
# Criar nova migration
alembic revision --autogenerate -m "descricao"

# Aplicar migrations
alembic upgrade head

# Reverter última migration
alembic downgrade -1

# Rodar testes
pytest
```
