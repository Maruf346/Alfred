# Alfred — AI Dating Concierge (AI Service Layer)

This is the **AI service** for Alfred, built exactly to the scope defined in the AI Developer Brief:
it understands intent, talks to the user, ranks/summarizes recommendations, and proposes
actions/memory updates — but it **never** touches the database, payments, calendar, or auth.
That's the backend team's job. This service just answers `POST` requests with structured JSON.

## What's inside

```
alfred_ai/
├── app/
│   ├── main.py              FastAPI app, CORS, middleware, router wiring
│   ├── config.py            Settings (env-driven), local/LAN host config
│   ├── schemas.py           All Pydantic request/response models
│   ├── prompts.py           Alfred's personality + per-intent system prompts
│   ├── llm_client.py        Provider-agnostic LLM abstraction (Anthropic default)
│   ├── search_client.py     SerpAPI wrapper (restaurants/activities/flights/hotels)
│   ├── intent.py            Intent classification
│   ├── memory.py            Memory formatting + prompt injection helpers
│   ├── services.py          Core business logic for every endpoint
│   ├── dependencies.py      API key auth for the internal AI<->backend contract
│   ├── logging_config.py    Structured logging setup
│   └── routers/
│       ├── chat.py          POST /chat
│       ├── recommend.py     POST /recommend
│       ├── plan_date.py     POST /plan-date
│       ├── coach.py         POST /coach
│       ├── gift.py          POST /gift
│       ├── travel.py        POST /travel
│       └── health.py        GET /health
├── tests/                   pytest suite (mocked LLM + SerpAPI, no live calls)
├── requirements.txt
├── .env.example
├── run_local.sh             127.0.0.1 only
├── run_lan.sh                0.0.0.0, reachable from other devices on your LAN
├── Dockerfile
└── .gitignore
```

## 1. Install

```bash
cd alfred_ai
python3 -m venv venv
source venv/bin/activate          # Windows: venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env
```

Edit `.env`:

```
ANTHROPIC_API_KEY=sk-ant-...
LLM_PROVIDER=anthropic            # anthropic | openai
LLM_MODEL=claude-sonnet-4-6
SERPAPI_KEY=your_serpapi_key
AI_SERVICE_API_KEY=change-me      # shared secret the backend must send
ENV=development                   # development | production
ALLOWED_ORIGINS=http://localhost:3000
```

## 2. Run locally (this machine only)

```bash
./run_local.sh
# or: uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
```

## 3. Run on your LAN (reachable from phones/other devices on the same network)

```bash
./run_lan.sh
# or: uvicorn app.main:app --host 0.0.0.0 --port 8000
```

Find your machine's LAN IP (`ip addr` / `ipconfig`) and the backend can call
`http://<your-lan-ip>:8000`. Make sure your firewall allows inbound TCP on the port,
and keep `AI_SERVICE_API_KEY` set — do not expose this on `0.0.0.0` without it.

## 4. Docs

Once running: **Swagger UI** at `/docs`, **ReDoc** at `/redoc`, raw OpenAPI JSON at `/openapi.json`.

## 5. Tests

```bash
pytest -v
```

All 17+ tests run against mocked LLM/SerpAPI clients — no API keys or network calls needed.

## Auth contract

Every request from the backend must include:

```
X-API-Key: <AI_SERVICE_API_KEY>
```

This is a shared-secret between backend and AI layer only — it is **not** end-user auth
(the backend already handles that before it ever calls this service).

## Design notes

- **Stateless**: this service holds no database. Every request carries whatever memory/context
  the backend already has (per the brief). Nothing is persisted here.
- **No fabricated recommendations**: if SerpAPI is unavailable or returns nothing, the service
  says so plainly and offers general planning advice instead of inventing results.
- **Actions, not side effects**: the AI only ever *proposes* actions (`create_calendar_event`,
  `search_flights`, `save_memory`, ...). The backend decides what actually executes.
- **Swap LLM providers** by changing `LLM_PROVIDER` in `.env` — `llm_client.py` is written
  against a small internal interface so adding a new provider means adding one class.
