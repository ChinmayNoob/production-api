# Production API

A production-ready AI chat API built with **FastAPI**, **LangGraph**, **LangChain**, and **OpenAI**. Features include primary/fallback LLM routing with automatic retries, input security sanitization, request metrics collection, rate limiting, and full Docker support.

---

## Table of Contents

- [Architecture Overview](#architecture-overview)
- [Project Structure](#project-structure)
- [How It Works](#how-it-works)
- [API Endpoints](#api-endpoints)
- [Setup](#setup)
- [Environment Variables](#environment-variables)
- [Running Locally](#running-locally)
- [Running with Docker](#running-with-docker)
- [Testing](#testing)

---

## Architecture Overview

```
Client Request
     |
     v
[FastAPI Server]  -- rate limiting (20/min)
     |
     v
[InputSanitizer]  -- injection/XSS/SQL/command detection
     |
     v
[ProductionAgent] -- LangGraph state machine
     |                 |
     |          call_primary (gpt-4o-mini)
     |                 |
     |           success? --done--> response
     |           fail?
     |                 |
     |          call_fallback (retry up to max_retries)
     |
     v
[MetricsCollector] -- thread_id, latency, errors, tokens, cache
     |
     v
JSON Response
```

### Request Flow

1. **Rate Limit** — Each IP is limited to 20 requests per minute via SlowAPI
2. **Security Check** — The incoming message is scanned for prompt injection, SQL injection, XSS, and command injection patterns. Malicious requests are rejected with `400`
3. **Agent Invocation** — The message enters a LangGraph state machine:
   - First tries the **primary LLM** (`gpt-4o-mini`)
   - On failure, retries with the **fallback LLM** up to `max_retries` times
   - All steps are traced in LangSmith for observability
4. **Metrics Recording** — Every request is logged with a `thread_id`, latency, error status, and token counts
5. **Response** — Returns the LLM output, model used, thread ID, and processing time in ms

---

## Project Structure

```
production-api/
├── app/
│   ├── __init__.py
│   ├── main.py           # FastAPI app, routes, lifespan, rate limiting
│   ├── agent.py           # LangGraph agent with primary/fallback routing
│   ├── config.py          # Pydantic settings from .env
│   ├── models.py          # Request/response Pydantic schemas
│   ├── monitoring.py      # MetricsCollector + JSON log formatter
│   └── security.py        # InputSanitizer (injection, XSS, SQL, PII)
├── test/
│   ├── __inti__.py
│   ├── test_api.py         # Integration tests against live server
│   ├── test_metrics.py     # MetricsCollector + LLM cache demo
│   ├── test_security.py
│   ├── test_security_pipeline.py
│   ├── test_cache.py
│   └── test_output_validator.py
├── Dockerfile
├── .dockerignore
├── pyproject.toml
├── uv.lock
└── .env                   # (not committed)
```

### Module Breakdown

#### `app/config.py`

Configuration is managed through `pydantic-settings`. All values are loaded from the `.env` file or environment variables. The `get_settings()` function is `@lru_cache`-decorated so settings are parsed once and reused.

Key settings:
- `primary_model` / `fallback_model` — OpenAI model names
- `max_retries` — How many times the fallback LLM is retried
- `rate_limit` — SlowAPI rate limit string
- `cache_ttl_seconds` — Cache time-to-live for future caching layer

#### `app/agent.py`

The `ProductionAgent` builds a **LangGraph** state machine with two nodes:

```
__start__ --> call_primary --(done)--> __end__
                    |
               (on error)
                    |
                call_fallback --(done)--> __end__
                    |
              (retry or error_out)--> __end__
```

- **`AgentState`** — TypedDict with `messages` (uses `add_messages` reducer), `error`, `retry_count`, `model_used`
- **`call_primary`** — Invokes the primary LLM. On success, appends an `AIMessage`. On failure, sets `error`
- **`call_fallback`** — Invokes the fallback LLM, increments `retry_count`
- **Routing** — `route_after_primary` and `route_after_fallback` decide: done, retry fallback, or give up
- **`@traceable`** — The `invoke` method is traced by LangSmith for full observability

#### `app/security.py`

`InputSanitizer` is a comprehensive security layer:

| Category | Patterns | Method |
|---|---|---|
| Prompt Injection | "ignore previous instructions", "pretend you are", etc. | `check()` |
| SQL Injection | SELECT, DROP, UNION, OR 1=1, sleep(), etc. | `check_sql()` |
| XSS | `<script>`, `<iframe>`, `onerror=`, `eval()`, etc. | `check_xss()` |
| Command Injection | `&&`, pipes, backticks, `curl`, `rm -rf`, etc. | `check_command()` |
| PII Detection | Email, phone, SSN, credit card, IP, DOB, address, passport | `detect_pii()` / `redact_pii()` |

The main entry point is `check(text)` which runs all injection checks and returns `(is_safe, reason)`. The `security_pipeline()` method combines validation, PII detection/redaction, and output validation into a single call.

#### `app/monitoring.py`

Two classes:

- **`JSONFormatter`** — Custom `logging.Formatter` that outputs structured JSON logs with timestamp, level, module, function, and line number
- **`MetricsCollector`** — Thread-safe metrics accumulator using `threading.Lock`:
  - `requests_total` / `errors_total`
  - `latency_sum` (seconds)
  - `tokens_input` / `tokens_output`
  - `cache_hits` / `cache_misses`
  - `request_log` — list of `{thread_id, timestamp}` for every request
  - `record_request(thread_id)` — accepts an optional thread ID (auto-generates UUID if omitted)
  - `snapshot()` — returns all metrics as a dict
  - `reset()` — zeroes all counters

#### `app/models.py`

Pydantic v2 schemas for request/response validation:

- **`ChatRequest`** — `message` (1-10000 chars) + optional `thread_id`
- **`ChatResponse`** — `response`, `thread_id`, `model_used`, `cached`, `processing_time_ms`, `timestamp`
- **`HealthResponse`** — `status`, `environment`, `version`, `checks`
- **`MetricsResponse`** — `total_requests`, `total_errors`, `error_rate`, `avg_latency_ms`, `cache_hit_rate`, `total_input_tokens`, `total_output_tokens`

#### `app/main.py`

FastAPI application with lifespan management:

- **Startup** — Initializes `ProductionAgent`, `MetricsCollector`, and `InputSanitizer` as singletons
- **Routes** — 4 endpoints (see below)
- **Error handling** — Custom handler for `RateLimitExceeded` (429), plus HTTPException for security blocks (400), upstream failures (502), and internal errors (500)

---

## API Endpoints

### `GET /health`

Health check endpoint.

```json
{
  "status": "healthy",
  "environment": "development",
  "version": "1.0.0",
  "timestamp": "2026-05-31T12:00:00.000000Z",
  "checks": {
    "agent": "ready"
  }
}
```

### `POST /chat`

Send a message to the AI agent. Rate limited to 20 requests/minute per IP.

**Request:**
```json
{
  "message": "What is the capital of France?",
  "thread_id": "my-thread-001"
}
```

**Response:**
```json
{
  "response": "Paris.",
  "thread_id": "my-thread-001",
  "model_used": "gpt-4o-mini",
  "cached": false,
  "processing_time_ms": 1234.56,
  "timestamp": "2026-05-31T12:00:01.000000Z"
}
```

**Error responses:**
- `400` — Security violation (injection/XSS/SQL detected)
- `429` — Rate limit exceeded
- `502` — LLM returned an error after all retries
- `503` — Agent not initialized

### `GET /metrics`

Get accumulated request metrics.

```json
{
  "total_requests": 15,
  "total_errors": 1,
  "error_rate": "6.67%",
  "avg_latency_ms": 1452.30,
  "cache_hit_rate": "33.33%",
  "total_input_tokens": 0,
  "total_output_tokens": 0
}
```

### `POST /metrics/reset`

Reset all counters to zero.

```json
{
  "detail": "Metrics reset"
}
```

---

## Setup

### Prerequisites

- Python 3.12+
- [uv](https://docs.astral.sh/uv/) package manager
- OpenAI API key
- (Optional) LangSmith account for tracing

### Install

```bash
# Clone the repo
git clone <repo-url>
cd production-api

# Install dependencies
uv sync

# Activate virtual environment
# Windows:
.venv\Scripts\activate
# macOS/Linux:
source .venv/bin/activate
```

---

## Environment Variables

Create a `.env` file in the project root:

```env
# Required
OPENAI_API_KEY=sk-proj-...

# Optional - LLM models
PRIMARY_MODEL=gpt-4o-mini
FALLBACK_MODEL=gpt-4o-mini

# Optional - LangSmith tracing
LANGCHAIN_TRACING_V2=true
LANGCHAIN_PROJECT=prodapp
LANGSMITH_API_KEY=lsv2_...

# Optional - App settings
APP_ENV=development
LOG_LEVEL=INFO
RATE_LIMIT=20/minute
CACHE_TTL_SECONDS=300
MAX_RETRIES=3
```

| Variable | Default | Description |
|---|---|---|
| `OPENAI_API_KEY` | *(required)* | Your OpenAI API key |
| `PRIMARY_MODEL` | `gpt-4o-mini` | Primary LLM model |
| `FALLBACK_MODEL` | `gpt-4o-mini` | Fallback LLM model on primary failure |
| `LANGCHAIN_TRACING_V2` | `true` | Enable LangSmith tracing |
| `LANGCHAIN_PROJECT` | `prodapp` | LangSmith project name |
| `APP_ENV` | `development` | Environment name (`development` / `production`) |
| `LOG_LEVEL` | `INFO` | Logging level |
| `RATE_LIMIT` | `20/minute` | Rate limit per IP |
| `CACHE_TTL_SECONDS` | `300` | Cache TTL for future caching layer |
| `MAX_RETRIES` | `3` | Max fallback LLM retries |

---

## Running Locally

```bash
uv run uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
```

Test it:

```bash
# Health check
curl http://127.0.0.1:8000/health

# Chat
curl -X POST http://127.0.0.1:8000/chat \
  -H "Content-Type: application/json" \
  -d '{"message": "Hello!", "thread_id": "test-001"}'

# Metrics
curl http://127.0.0.1:8000/metrics
```

### Verify Config & Connectivity

Run this one-liner to validate your full setup:

```bash
uv run python -c "
from app.config import get_settings
s = get_settings()
print(f'Config OK: model={s.primary_model}, env={s.app_env}')

from langchain_openai import ChatOpenAI
llm = ChatOpenAI(model=s.primary_model, max_tokens=5, temperature=0)
resp = llm.invoke('Say OK')
print(f'OpenAI OK: {resp.content.strip()[:50]}')
"
```

---

## Running with Docker

### Build

```bash
docker build -t production-api .
```

### Run

```bash
docker run -d --name production-api -p 8000:8000 --env-file .env production-api
```

### Test

```bash
curl http://127.0.0.1:8000/health
```

### Useful Commands

```bash
# View logs
docker logs -f production-api

# Stop
docker stop production-api

# Remove
docker rm production-api

# Rebuild after code changes
docker build -t production-api . && docker rm -f production-api && docker run -d --name production-api -p 8000:8000 --env-file .env production-api
```

The Docker image uses `python:3.12-slim`, installs dependencies via `uv sync` (using the lockfile for reproducible builds), and only copies the `app/` directory. Tests, docs, `.venv`, and `.git` are excluded via `.dockerignore`.

---

## Testing

### Prerequisites

Start the server first (locally or via Docker):

```bash
# Local
uv run uvicorn app.main:app --host 127.0.0.1 --port 8000

# Or Docker
docker run -d --name production-api -p 8000:8000 --env-file .env production-api
```

### Run All Tests

```bash
uv run pytest -v -s
```

### Run Specific Test Files

```bash
# API integration tests (requires running server)
uv run pytest test/test_api.py -v -s

# Metrics + LLM cache demo
uv run pytest test/test_metrics.py -v -s
```

### Test Suite (`test/test_api.py`)

| Test | Endpoint | Description |
|---|---|---|
| `test_health` | `GET /health` | Verifies agent is ready and status is healthy |
| `test_chat_hello` | `POST /chat` | Sends "Say hello", validates response + model |
| `test_chat_math` | `POST /chat` | Sends "What is 2+2?", checks answer |
| `test_chat_sky` | `POST /chat` | Sends "What color is the sky?" |
| `test_chat_injection_blocked` | `POST /chat` | Sends a prompt injection attack, expects `400` |
| `test_metrics` | `GET /metrics` | Verifies accumulated request counts and latency |
| `test_metrics_reset` | `POST /metrics/reset` | Resets metrics and confirms all zeros |

---

## Tech Stack

| Component | Technology | Purpose |
|---|---|---|
| Web Framework | FastAPI | Async API server with Pydantic validation |
| LLM Orchestration | LangGraph | State machine for primary/fallback routing |
| LLM Provider | LangChain + OpenAI | GPT-4o-mini inference |
| Observability | LangSmith | Trace every agent invocation |
| Security | Custom (regex-based) | Injection, XSS, SQL, PII detection |
| Rate Limiting | SlowAPI | Per-IP request throttling |
| Settings | pydantic-settings | Typed config from `.env` |
| Package Manager | uv | Fast dependency resolution with lockfile |
| Containerization | Docker | Slim Python 3.12 image |
