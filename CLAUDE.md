# Bolão da Copa 2026

Aplicativo de bolão para a Copa do Mundo 2026. Usuários criam competições independentes com grupos diferentes de amigos, fazem apostas nos jogos e acumulam pontos.

## Stack

- **Backend:** Python + FastAPI
- **Banco de dados:** PostgreSQL via SQLAlchemy + Alembic
- **Autenticação:** JWT (bcrypt para senhas)
- **Dados dos jogos:** API externa `https://worldcup26.ir`
- **Deploy:** Backend no Vercel (serverless), DB no Supabase, Frontend em React no Vercel

## Comandos principais

```bash
# Rodar o servidor local
uvicorn app.main:app --reload

# Criar nova migration
alembic revision --autogenerate -m "descricao"

# Aplicar migrations
alembic upgrade head

# Setup do token da API externa (rodar uma vez)
python scripts/setup_external_api.py

# Rodar testes
pytest
```

## Estrutura do projeto

```
bolao/
├── app/
│   ├── main.py
│   ├── database.py
│   ├── models/
│   ├── schemas/
│   ├── routers/
│   ├── services/
│   │   ├── match_service.py      # consome worldcup26.ir + cache no DB
│   │   └── scoring_service.py    # calcula pontuação das apostas
│   └── dependencies.py
├── scripts/
│   └── setup_external_api.py     # obtém e salva token da API externa
├── api/
│   └── index.py                  # handler ASGI para o Vercel
├── alembic/
├── vercel.json
├── .env.example
├── requirements.txt
├── CLAUDE.md
└── README.md
```

## Regras de negócio críticas

- Apostas só podem ser feitas/editadas **antes do início do jogo**
- Comparar sempre em UTC — converter `local_date` da API externa para `kickoff_utc` usando o fuso do estádio
- Placar exato = 5 pts; só resultado = 2 pts; artilheiro = +1 pt sempre que acertar (independe de acertar placar/resultado) — placar exato já engloba resultado, não somam
- Apostas de outros participantes ficam ocultas até o jogo começar
- Cache: jogos `finished=TRUE` são permanentes; jogos `finished=FALSE` expiram em 5 minutos

## Padrões de código

- Tipagem explícita em todas as funções (Python type hints)
- Schemas Pydantic para todos os request/response bodies
- Erros retornados com `HTTPException` e mensagens descritivas em português
- Variáveis de ambiente sempre via `python-dotenv` — nunca hardcoded
- Sem estado em memória entre requisições (serverless no Vercel)

## Variáveis de ambiente necessárias

Todas definidas em `.env` (ver `.env.example`):

```
DATABASE_URL          # postgresql://... (SSL obrigatório no Supabase)
JWT_SECRET
JWT_EXPIRE_MINUTES
WORLDCUP_API_TOKEN    # gerado por setup_external_api.py
WORLDCUP_API_EMAIL    # credencial para renovar o token
WORLDCUP_API_PASSWORD
CORS_ORIGINS          # ex: http://localhost:3000 ou domínio do Vercel
```

## Documentação de referência

- Prompt completo do projeto: `docs/prompt_inicial.md`
- Documentação da API externa: `docs/worldcup_api.md`
- Swagger local: `http://localhost:8000/docs`
