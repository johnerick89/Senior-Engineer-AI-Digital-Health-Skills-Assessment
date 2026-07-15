# Backend (FastAPI)

HTTP API for the Last Mile Health RAG assessment app. Serves the Next.js frontend
with document upload, chat streaming, thread history, and usage summaries. RAG
logic lives in the shared `rag_core` package (imported in-process — this service
does not reimplement ingest/retrieve/generate).

Chainlit on port `8000` is a **separate** chat surface that also imports
`rag_core` directly; it does **not** call this backend.

All versioned routes live under **`/api/v1`** with plural resource names.

---

## What this service does

| Concern     | Behavior                                                                          |
| ----------- | --------------------------------------------------------------------------------- |
| Health      | `GET /` and `GET /api/v1/health` JSON status; `GET /api/v1/assignment` HTML brief |
| Documents   | `POST /api/v1/documents` — PDF-only, ≤20MB, NDJSON progress per file              |
| Documents   | `GET /api/v1/documents` — list with status, size, chunk_count                     |
| Documents   | `DELETE /api/v1/documents/{id}` — removes document; chunks cascade via FK         |
| Chats       | `POST /api/v1/chats` — streams plain-text RAG answers; persists threads/messages  |
| History     | `GET /api/v1/chats`, `GET /api/v1/chats/{id}/messages`                             |
| Suggestions | `GET /api/v1/chats/suggestions` — starter topics from documents                   |
| Usage       | `GET /api/v1/chats/{id}/usage`, `GET /api/v1/usage`                               |

On startup the app calls `rag_core.rag.vector_store.initialize_vector_store()` so
Alembic migrations / schema are applied when Postgres is reachable.

---

## Run with Docker Compose

From the **repository root** (where `docker-compose.yaml` lives):

```bash
# Stop (optional — free ports / recreate cleanly)
docker compose stop backend
# or stop everything:
docker compose down

# Build backend image (also needed after Dockerfile / requirements / rag_core changes)
docker compose build backend

# Start backend (starts relational_db if needed)
docker compose up -d backend

# Tail logs
docker compose logs -f backend
```

Typical base URL on the host: **http://localhost:6100**

Postgres is the `relational_db` service. Backend env includes
`DATABASE_URL=postgresql://postgres:postgres@relational_db:5432/postgres` and
loads secrets from `rag_core/.env`.

Full stack (frontend + backend + db + chainlit):

```bash
docker compose up -d --build
```

---

## Run locally (outside Docker)

Prerequisites: Python 3.12+, Postgres + pgvector reachable (often the Compose DB
on `localhost:5432`), and the shared venv / `rag_core` package.

```bash
# From repository root
source .venv/bin/activate

pip install -r backend/requirements.txt
pip install -r backend/requirements-dev.txt
pip install -e ./rag_core

# Env — point at local Postgres and OpenAI / OpenRouter keys
export DATABASE_URL=postgresql://postgres:postgres@localhost:5432/postgres
export OPENAI_API_KEY=sk-proj-your-key-here
export OPENROUTER_API_KEY=sk-or-v1-your-key-here

cd backend
PYTHONPATH=../rag_core:. uvicorn app.main:app --host 0.0.0.0 --port 6100 --reload
```

Health check:

```bash
curl -s http://localhost:6100/
curl -s http://localhost:6100/api/v1/health
```

---

## Tests

```bash
# Normal (from backend/)
cd backend
pip install -r requirements-dev.txt
PYTHONPATH=../rag_core:. pytest tests/ -v

# With coverage (from repository root so --cov=backend resolves)
pip install pytest-cov
PYTHONPATH=rag_core:backend pytest backend/tests \
  --cov=rag_core --cov=backend --cov-report=term-missing
```

---

## Built-in API docs (FastAPI)

Uvicorn serves FastAPI’s interactive docs automatically (no extra code). With the
backend on port **6100**:

| URL                                | What it is                                    |
| ---------------------------------- | --------------------------------------------- |
| http://localhost:6100/docs         | **Swagger UI** — try endpoints in the browser |
| http://localhost:6100/redoc        | **ReDoc** — alternate readable reference      |
| http://localhost:6100/openapi.json | **OpenAPI 3** schema (for codegen / Postman)  |

Inside Docker on the published port this is the same host path
(`localhost:6100/...`). From another Compose service use
`http://backend:6100/docs`.

### Useful options while using `/docs`

- Expand an operation → **Try it out** → fill body/files → **Execute**
- `POST /api/v1/documents` needs multipart form field `files` (PDF)
- `POST /api/v1/chats` body example: `{ "input": "What is a CHW?", "history": [] }`
- Optional `id` on `POST /api/v1/chats` continues an existing thread UUID
- Streaming responses (`/api/v1/chats`, `/api/v1/documents`) show as downloaded /
  streamed text in Swagger; `curl` is often clearer for NDJSON / plain streams

### curl examples

```bash
# Health
curl -s http://localhost:6100/api/v1/health

# Chat (stream)
curl -N -X POST http://localhost:6100/api/v1/chats \
  -H 'Content-Type: application/json' \
  -d '{"input":"What is a CHW?","history":[]}'

# List documents
curl -s http://localhost:6100/api/v1/documents

# Upload
curl -N -X POST http://localhost:6100/api/v1/documents \
  -F 'files=@./sample.pdf;type=application/pdf'

# Delete document (cascades chunks)
curl -i -X DELETE http://localhost:6100/api/v1/documents/<document-uuid>

# Usage summary
curl -s http://localhost:6100/api/v1/usage
```

---

## Layout

```
backend/
  app/
    main.py          # FastAPI app, CORS, /api/v1 mount
    api/             # route handlers (chats, documents, usage, home)
    schemas/         # Pydantic models
    services/        # thin helpers over rag_core
  tests/
  Dockerfile
  requirements.txt
  requirements-dev.txt   # pytest, httpx, pytest-cov
  README.md
```
