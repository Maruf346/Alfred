# CLAUDE.md

Guidance for Claude Code when working in this repository.

## What this is

Alfred is an AI dating-concierge **service layer**: a FastAPI app that a Django backend calls over HTTP. It understands intent, converses, ranks search results, and *proposes* actions and memory updates as structured JSON. It never touches a database, payments, calendar, or end-user auth — the backend owns all of that and decides whether to execute any proposed `actions`. `README.md` has the product overview; `BACKEND_DJANGO_HANDOFF.md` is the integration guide for the Django team (keep it in sync when an endpoint's request/response contract changes).

## Commands

Windows dev machine; a virtualenv lives in `.venv` (`.venv-1` is a stray second one — ignore it).

```powershell
.venv\Scripts\python -m pytest -q                     # full suite (64 tests, ~3s, no network/keys needed)
.venv\Scripts\python -m pytest tests/test_budget.py   # one file
.venv\Scripts\python -m pytest -k dedup               # one test by name
.venv\Scripts\python app/main.py                      # run; prints local + LAN URLs, reload on unless ENV=production
.venv\Scripts\python -m uvicorn app.main:app --host 127.0.0.1 --port 8001 --reload
```

`run_local.sh` / `run_lan.sh` are bash scripts (use Git Bash on Windows). Swagger UI is at `/docs`. There is no linter/formatter config and no CI in the repo.

Config comes from `.env` (see `.env.example`), loaded by `app/config.py`. **The default port is 8001** (`config.py`), but the shell scripts, Dockerfile and README say 8000 — pass the port explicitly if it matters. `.env.example` sets `LLM_MAX_TOKENS=1024` while the code default is 2048.

## Architecture

Request path: `app/routers/<x>.py` → `app/services.py::handle_<x>` → `llm_client` / `search_client` / `exchange_client` → Pydantic response from `app/schemas.py`.

- **Routers are thin.** They declare the OpenAPI examples, fetch client singletons (`get_llm_client()` etc.), and call one `handle_*` function. All prompt assembly, search orchestration and response building lives in `app/services.py` (one ~860-line module, sections marked per endpoint).
- **`app/main.py`** wires routers, CORS, and exception handlers that turn `LLMError`/`SearchError`/`VoiceError` into 502 `ErrorResponse` bodies. Every router except `health` uses `dependencies=[Depends(verify_service_api_key)]`.
- **Auth (`dependencies.py`)**: `X-API-Key` is checked only when `ENV=production` or `REQUIRE_SERVICE_API_KEY_IN_DEV=true`. In dev it is skipped entirely.
- **`schemas.py`** holds every request/response model. `Currency` and `Budget` are `Annotated` types with `BeforeValidator`s that normalize messy input ("tk /bdt" → `BDT`, "around 50 dollars" → `50.0`); default currency is USD. `UserMemory` allows extra fields.
- **`prompts.py`** holds `ALFRED_PERSONA`, one prompt template per flow, and `format_*_block` helpers. Templates use `str.format`, so **literal JSON braces must be doubled (`{{ }}`)**.
- **`llm_client.py`**: `BaseLLMClient` with `complete` / `complete_json` (strips ``` fences, raises `LLMError` on bad JSON) / `complete_multimodal(_json)` (image or PDF as base64). `AnthropicClient` and `OpenAIClient` implement it, each with tenacity retry (3 attempts). Provider chosen by `LLM_PROVIDER`; `get_llm_client()` is a module singleton. OpenAI multimodal sends images as `image_url` and PDFs as a `file` block (requires a PDF-capable model such as gpt-4o); any other attachment type raises `LLMError` rather than being silently dropped. Adding a provider = one class + one branch in `get_llm_client`.
- **`search_client.py`**: SerpAPI wrapper (google_local places, flights, hotels, google_shopping products, events). Returns `[]` when `SERPAPI_KEY` is unset. Locale-scoped searches retry once without the `currency`/`gl` override. Shopping is always searched in USD and converted afterward.
- **`exchange_client.py`**: keyless FX rates (open.er-api.com), cached 6h. **`http_client.py`**: one pooled `httpx.AsyncClient` shared by search/FX/ElevenLabs. **`voice_client.py`**: OpenAI Whisper STT + ElevenLabs TTS behind `/voice/transcribe`, `/voice/speak`.
- **`intent.py`**: LLM-based intent classifier returning `DetectedIntent` (intent, location, budget, travel slots, coach topic, search keywords).
- **`memory.py`**: formats/validates memory; `safe_user_memory` drops individual invalid fields instead of failing the request.
- **`session_store.py`**: in-process dict keyed by `session_id` (history capped at 20 turns, 2h idle TTL, lock-guarded). Used only by `/chat`. Lost on restart — this is by design; swap for Redis behind the same methods if multi-process is ever needed.

### Endpoints

| Route | Handler | Notes |
|---|---|---|
| `GET /health` | health router | |
| `POST /chat` | `handle_chat` | Master endpoint: classifies intent, then routes internally to the recommend / plan-date / gift / travel / coach flows and folds the result into one `ChatResponse`. Optional `session_id` memory. |
| `POST /recommend` | `handle_recommend` | restaurant / activity / event / hotel |
| `POST /plan-date` | `handle_plan_date` | single plan, or several options with timelines |
| `POST /coach` | `handle_coach` | |
| `POST /gift` | `handle_gift` | Google Shopping, filtered on real USD prices against the converted budget |
| `POST /travel` | `handle_travel` | flights/hotels/activities; LLM resolves airport codes |
| `POST /budget/analyze` | `handle_budget_analysis` | JSON body: structured expenses, free text, or base64 receipt (image/PDF) |
| `POST /budget/analyze/upload` | same | multipart file upload; rejects unsupported types, empty files, encrypted PDFs (400) |
| `POST /voice/transcribe`, `POST`+`GET /voice/speak` | voice router | |

### Key `/chat` behaviour (easy to break)

- Search-backed intents (restaurant, activity, hotel, date, gift, travel) only fire once a **budget is known** from the request, session slots, memory, or the classifier — or the user said budget doesn't matter (`budget_no_limit`). Otherwise chat falls through to the generic reply, which asks a follow-up. Events only need a city. Travel additionally needs origin, destination and both dates.
- Precedence for values: caller-sent > session-remembered > classifier-extracted. Caller memory overrides stored memory field-by-field (`_merge_memory`).
- Search preferences use only the classifier's cleaned `search_keywords`, **never the raw user message** (raw text produced garbage SerpAPI queries).
- Every return path goes through `_finalize_chat`, which persists turns/memory to the session. Use it for any new branch.
- `session_status` (`new` / `active` / `expired`) tells the backend whether context carried over.

### Budget analyzer

`handle_budget_analysis` makes a single multimodal LLM call using `EXPENSE_ANALYSIS_SYSTEM_PROMPT` (`max_tokens=8000` — itemizing every transaction of a real statement overflows small limits and truncates the JSON), then post-processes: builds `ExpenseItem`s, **de-duplicates** overlapping transactions on `(date, amount, merchant-or-notes)` and reports `receipt_summary.deduplicated_count`, and assembles `spending_breakdown` and `next_month_plan`. On `LLMError` it returns a friendly reply with `confidence=0.0` rather than a 5xx.

The "planner" is **not a separate endpoint**: the same response carries `next_month_plan` (`estimated_total_budget`, `weekly_spending_target`, `projected_savings`, `suggested_allocations[]`, `planner_tips`), a full-month plan the prompt forces to cover rent, groceries, utilities, transport, dining, personal care and savings — not just the categories on the receipt. It also proposes a `save_budget_plan` action and `last_analyzed_monthly_spending` / `recommended_next_month_budget` memory updates. The prompt also asks for `follow_up_questions` (rent, savings goal, ...); the response is stateless, so the backend must feed the answers back in on the next call (`notes` / `expenses_text` / `memory`). `/chat` classifies a `budget_planning` intent but has **no route to this analyzer** — such messages fall through to the generic chat reply.

## Testing conventions

- `tests/conftest.py` monkeypatches the LLM, search and FX clients with `FakeLLMClient` (a **FIFO queue of canned JSON dicts**, consumed one per `complete` call; falls back to `{"reply":"ok"}`), `FakeSearchClient`, `FakeExchangeClient` (identity rates unless given). Fake multimodal calls fall back to `complete`.
- Routers import `get_*_client` by name, so the `client` fixture patches each router module's bound name. **When you add a router, add it to the module tuple in `conftest.py::client`** or it will hit the real providers.
- A `/chat` request that triggers intent detection consumes a queue entry for the classifier *before* the handler's own call — queue responses in call order.
- Tests never hit the network; env vars are forced blank/known in an autouse fixture and `get_settings` is cache-cleared. Auth tests rely on `AI_SERVICE_API_KEY=test-key`.

## Gotchas

- README says the service is fully stateless; that is true for everything except `/chat` sessions.
- The repo checks in stray artifacts (`hotel_sample.json`, `search_out.json`); don't treat them as fixtures.
- Git shows LF→CRLF warnings on Windows; line endings aren't normalized by config.
- Don't fabricate results: when search returns nothing or fails, flows use `NO_SEARCH_RESULTS_PROMPT` / raw-result fallbacks instead of inventing venues. Preserve that behaviour.
