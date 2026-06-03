# Prompt para Claude Code — Bolão da Copa

## Contexto do projeto

Você vai desenvolver o **backend** de um aplicativo web de bolão para os jogos da Copa do Mundo 2026. O sistema permite que o usuário crie múltiplas competições independentes (cada uma com um grupo diferente de amigos) e que os participantes façam apostas nos jogos.

Neste primeiro momento, o foco é **exclusivamente no backend**. O frontend será desenvolvido posteriormente em React.

---

## Stack

- **Linguagem/framework:** Python + FastAPI
- **Banco de dados:** PostgreSQL
- **ORM:** SQLAlchemy (com Alembic para migrations)
- **Autenticação:** JWT (JSON Web Tokens)

---

## API externa de jogos — worldcup26.ir

Os dados dos jogos vêm de uma API pública e gratuita, sem necessidade de API key para leitura.

**Base URL:** `https://worldcup26.ir`

### Autenticação da API externa
Todos os endpoints (exceto os de auth) exigem um Bearer Token JWT no header:
```
Authorization: Bearer YOUR_TOKEN
```

Para obter o token, use:
```http
POST /auth/register
Content-Type: application/json
{ "name": "...", "email": "...", "password": "..." }

POST /auth/authenticate
Content-Type: application/json
{ "email": "...", "password": "..." }
```
Ambos retornam `{ "user": {...}, "token": "..." }`. Os tokens têm validade de **84 dias**.

### Setup do token da API externa

Crie um script `scripts/setup_external_api.py` que:
1. Registra uma conta na API externa (ou faz login se já existir)
2. Salva o token retornado na variável `WORLDCUP_API_TOKEN` no arquivo `.env`

O script deve ser executado uma vez durante o setup inicial do projeto, com instruções claras no `README.md`. O `MatchService` deve ler esse token do `.env` e renová-lo automaticamente caso receba um erro 401 da API externa.

### Endpoints relevantes

#### Jogos
```http
GET /get/games                    # todos os 104 jogos
GET /get/game/{matchId}           # jogo específico (matchId de 1 a 104)
```

**Campos do objeto de jogo:**
| Campo | Tipo | Descrição |
|---|---|---|
| `id` | string | ID do jogo (1–104) |
| `home_team_id` | string | ID do time da casa (`"0"` se ainda não definido) |
| `away_team_id` | string | ID do time visitante (`"0"` se ainda não definido) |
| `home_score` | int | Gols do time da casa |
| `away_score` | int | Gols do time visitante |
| `group` | string | Grupo (A–L) ou fase (R32, R16, QF, SF, 3RD, FINAL) |
| `matchday` | string | Rodada (1–3 grupo; 4=R32; 5=R16; 6=QF; 7=SF; 8=3º lugar; 9=Final) |
| `local_date` | string | Data/hora local no formato `"MM/DD/YYYY HH:MM"` |
| `stadium_id` | string | ID do estádio |
| `finished` | string | `"TRUE"` ou `"FALSE"` |
| `type` | string | `group`, `r32`, `r16`, `qf`, `sf`, `third`, `final` |
| `home_team_label` | string | Placeholder para knockout ainda não definido (ex: `"Winner Group A"`) |
| `away_team_label` | string | Idem para visitante |

**Estágios do torneio:**
| type | matchday | Fase | Jogos | IDs |
|---|---|---|---|---|
| `group` | 1–3 | Fase de grupos | 72 | 1–72 |
| `r32` | 4 | Round of 32 | 16 | 73–88 |
| `r16` | 5 | Oitavas de final | 8 | 89–96 |
| `qf` | 6 | Quartas de final | 4 | 97–100 |
| `sf` | 7 | Semifinais | 2 | 101–102 |
| `third` | 8 | Disputa de 3º lugar | 1 | 103 |
| `final` | 9 | Final | 1 | 104 |

#### Times
```http
GET /get/teams                    # todos os 48 times
GET /get/team/{teamId}            # time por ID
GET /get/teams/?group={letter}    # times por grupo (A–L)
```
Campos relevantes: `id`, `name_en`, `fifa_code`, `groups`, `flag`

#### Grupos
```http
GET /get/groups                   # todos os 12 grupos com classificação
GET /get/group/{groupId}
GET /get/group/?name={letter}
```

#### Estádios
```http
GET /get/stadiums                 # todos os 16 estádios
```
Campos: `id`, `name_en`, `city_en`, `country_en`, `capacity`

#### Health check
```http
GET /health                       # sem autenticação
```

---

## O que deve ser desenvolvido nesta fase

### 1. Estrutura do projeto

Organize o projeto seguindo boas práticas de FastAPI:

```
bolao/
├── app/
│   ├── main.py
│   ├── database.py
│   ├── models/
│   ├── schemas/
│   ├── routers/
│   ├── services/
│   │   ├── match_service.py      # consome a API externa
│   │   └── scoring_service.py    # calcula pontuação
│   └── dependencies.py
├── alembic/
├── .env.example
├── requirements.txt
└── README.md
```

---

### 2. Rotas de autenticação (`/auth`)

- `POST /auth/register` — cadastro de novo usuário (nome, e-mail, senha)
- `POST /auth/login` — login, retorna access token JWT
- `GET /auth/me` — retorna dados do usuário autenticado
- Senhas armazenadas com hash (bcrypt)
- Tokens JWT com expiração configurável via variável de ambiente

---

### 3. Rotas de competições (`/competitions`)

Um usuário pode criar várias competições, cada uma com um grupo diferente de participantes.

- `POST /competitions` — cria uma nova competição (nome, descrição opcional). O criador é automaticamente administrador.
- `GET /competitions` — lista as competições do usuário autenticado (criadas ou em que participa)
- `GET /competitions/{id}` — detalhes de uma competição + ranking atual dos participantes
- `POST /competitions/{id}/invite` — gera um código de convite
- `POST /competitions/join` — entra em uma competição via código de convite
- `DELETE /competitions/{id}` — encerra/deleta uma competição (só o admin)

---

### 4. Rotas de jogos (`/matches`)

O serviço deve consumir a API externa descrita acima, com cache no banco PostgreSQL para evitar chamadas desnecessárias.

- `GET /matches` — lista jogos com filtros:
  - `?round=1` — filtra pelo campo `matchday` da API externa (1–9)
  - `?date=2026-06-15` — filtra pelo campo `local_date`
  - `?stage=group` — filtra pelo campo `type`
- `GET /matches/{id}` — detalhes de um jogo, incluindo dados dos times (nome, bandeira, código FIFA)

**Estratégia de cache:**
- Ao receber uma requisição, verificar se os dados já estão no banco e há quanto tempo foram atualizados
- Jogos com `finished: "TRUE"` podem ser cacheados indefinidamente
- Jogos com `finished: "FALSE"` devem ser re-consultados na API a cada 5 minutos
- Criar um endpoint interno `POST /matches/sync` (admin) para forçar a sincronização de todos os jogos

---

### 5. Rotas de apostas (`/bets`)

Cada participante faz uma aposta por jogo, dentro de cada competição.

- `POST /bets` — registra ou atualiza uma aposta
  - Campos: `competition_id`, `match_id`, `predicted_home_score`, `predicted_away_score`, `predicted_top_scorer` (opcional)
  - **Regra de negócio crítica:** apostas só podem ser feitas ou alteradas **antes do horário de início do jogo** (`local_date`). Após esse momento, qualquer tentativa de criar ou editar retorna erro 403.
- `GET /bets?competition_id={id}&match_id={id}` — aposta do usuário autenticado para um jogo em uma competição
- `GET /bets/competition/{id}` — todas as apostas da competição; para jogos ainda não iniciados, ocultar as apostas dos outros participantes (retornar só a do próprio usuário)

---

### 6. Sistema de pontuação

Implementar `ScoringService` com as seguintes regras:

| Situação | Pontos |
|---|---|
| Acertar o placar exato | **5 pontos** |
| Acertar apenas o resultado (quem ganhou ou empate) | **2 pontos** |
| Acertar o artilheiro do jogo (campo `predicted_top_scorer`) | **+1 ponto bônus** |
| Errar tudo | 0 pontos |

> Acertar o placar exato já engloba o resultado — não somam separadamente. Máximo por jogo: 6 pontos (5 + bônus).

- `POST /scoring/update/{match_id}` — endpoint interno/admin para calcular e registrar a pontuação de todas as apostas de um jogo após ele terminar
- O ranking de cada competição é calculado dinamicamente via query somando os pontos por `competition_id`

---

## Requisitos gerais

- Todas as rotas protegidas exigem autenticação via Bearer Token JWT
- Retornar erros padronizados e descritivos (400, 401, 403, 404, 422)
- Variáveis sensíveis (chave JWT, URL do banco, credenciais da API externa) em `.env`
- `README.md` com instruções para rodar localmente
- `.env.example` com todas as variáveis necessárias

---

## O que **não** deve ser feito agora

- Não desenvolver o frontend (será feito em React em fase posterior)
- Não implementar notificações, e-mails ou webhooks
- Não fazer deploy — apenas ambiente local

---

## Entregável esperado

Projeto pronto para rodar com `uvicorn app.main:app --reload`, migrations aplicadas com Alembic, e todas as rotas testáveis via `/docs` (Swagger UI do FastAPI).

---

## Arquitetura de deploy (referência para decisões de código)

O deploy será feito da seguinte forma — leve isso em conta ao estruturar o projeto para evitar retrabalho:

| Camada | Serviço |
|---|---|
| Banco de dados PostgreSQL | **Supabase** (PostgreSQL gerenciado) |
| Backend FastAPI | **Vercel** (Serverless Functions) |
| Frontend React | **Vercel** |

### Implicações para o backend

**Vercel + FastAPI (serverless):**
- O Vercel executa aplicações Python como serverless functions. Criar um arquivo `vercel.json` na raiz configurando o handler do FastAPI, e um `api/index.py` que exporta o app como handler ASGI compatível com o Vercel.
- Por ser serverless, **não use estado em memória entre requisições** (ex: cache em variável global). Todo cache deve ser persistido no banco PostgreSQL.
- O `uvicorn` é usado apenas localmente. No Vercel, o runtime cuida do servidor ASGI.

**Supabase (PostgreSQL):**
- A `DATABASE_URL` deve seguir o formato de connection string do Supabase: `postgresql://postgres:[PASSWORD]@[HOST]:5432/postgres`
- O Supabase exige conexão SSL. Configurar o SQLAlchemy com `connect_args={"sslmode": "require"}`.
- Para ambiente local, usar um PostgreSQL local normal; a troca é apenas na variável `DATABASE_URL`.

**Variáveis de ambiente no Vercel:**
- Todas as variáveis do `.env` precisarão ser cadastradas no painel do Vercel em Environment Variables. Documentar isso no `README.md`.

---

## Detalhes adicionais

### CORS

Como o frontend React e o backend FastAPI estarão em domínios diferentes no Vercel, configurar o middleware de CORS no `main.py`:

```python
from fastapi.middleware.cors import CORSMiddleware

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # em produção, substituir pelo domínio do frontend no Vercel
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
```

A lista de origens permitidas deve vir de uma variável de ambiente `CORS_ORIGINS` no `.env`, para facilitar a troca entre desenvolvimento (`http://localhost:3000`) e produção (domínio do Vercel).

### Fuso horário das apostas

Os horários dos jogos no campo `local_date` da API externa estão no **horário local de cada sede** (cidades nos EUA, México e Canadá — múltiplos fusos). Para que o bloqueio de apostas funcione corretamente para usuários no Brasil e em qualquer outro fuso:

- Ao salvar um jogo no cache do banco, converter `local_date` para **UTC** e armazenar em um campo `kickoff_utc` (timestamp with timezone)
- A verificação de bloqueio de aposta deve comparar `datetime.utcnow()` com `kickoff_utc`, nunca com a string original `local_date`
- Incluir um mapeamento de estádio → fuso horário para fazer a conversão correta (ex: estádios no Texas → `America/Chicago`, Califórnia → `America/Los_Angeles`, Cidade do México → `America/Mexico_City`, Vancouver → `America/Vancouver`, etc.)
- Usar a biblioteca `pytz` ou `zoneinfo` (Python 3.9+) para as conversões
