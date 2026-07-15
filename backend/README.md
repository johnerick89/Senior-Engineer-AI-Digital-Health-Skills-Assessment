# Backend (FastAPI)

HTTP API for the Next.js frontend: documents, chats, usage. RAG logic lives in
`rag_core` (imported in-process). Chainlit does **not** call this service.

All application routes use **`/api/v1`** and plural resource names. Root
[`README.md`](../README.md) covers full-stack setup; this file is backend-specific.

---

## Setup

```bash
# From repository root
source .venv/bin/activate
pip install -e ./rag_core
pip install -r backend/requirements.txt
pip install -r backend/requirements-dev.txt
cp rag_core/.env.example rag_core/.env   # OPENAI_ / OPENROUTER_ keys
```

Needs Postgres + pgvector (`docker compose -p assessment up -d relational_db`).

---

## What this service does

| Concern     | Behavior                                                                          |
| ----------- | --------------------------------------------------------------------------------- |
| Health      | `GET /` and `GET /api/v1/health`; `GET /api/v1/assignment` HTML                   |
| Documents   | `POST /api/v1/documents` — PDF ≤20MB, NDJSON progress                             |
| Documents   | `GET /api/v1/documents` — list + status / size / chunks                           |
| Documents   | `DELETE /api/v1/documents/{id}` — cascades chunks via FK                          |
| Chats       | `POST /api/v1/chats` — stream RAG answers; persist threads                        |
| History     | `GET /api/v1/chats`, `GET /api/v1/chats/{id}/messages`                             |
| Suggestions | `GET /api/v1/chats/suggestions`                                                   |
| Usage       | `GET /api/v1/chats/{id}/usage`, `GET /api/v1/usage`                               |

Startup runs `initialize_vector_store()` → Alembic migrations when DB is up.

---

## Docker

From **repository root**:

```bash
docker compose -p assessment build backend
docker compose -p assessment up -d backend

docker compose -p assessment logs -f backend
docker compose -p assessment stop backend
```

Uses `rag_core/.env`, `DATABASE_URL` → Compose DB, `--reload` via volume mount.
Rebuild after Dockerfile / requirements / `rag_core` dependency changes.

Full stack: `docker compose -p assessment up -d --build`

---

## Local

```bash
export DATABASE_URL=postgresql://postgres:postgres@localhost:5432/postgres
# keys: rag_core/.env or export OPENAI_API_KEY / OPENROUTER_API_KEY

cd backend
PYTHONPATH=../rag_core:. uvicorn app.main:app --host 0.0.0.0 --port 6100 --reload
```

```bash
curl -s http://localhost:6100/api/v1/health
```

Docs: http://localhost:6100/docs · http://localhost:6100/redoc

---

## Tests

```bash
# Normal (from backend/)
cd backend
PYTHONPATH=../rag_core:. pytest tests/ -v

# Coverage (from repository root)
pip install pytest-cov
PYTHONPATH=rag_core:backend pytest backend/tests \
  --cov=rag_core --cov=backend --cov-report=term-missing
```

---

## curl examples

```bash
curl -s http://localhost:6100/api/v1/health

curl -N -X POST http://localhost:6100/api/v1/chats \
  -H 'Content-Type: application/json' \
  -d '{"input":"What is a CHW?","history":[]}'

curl -s http://localhost:6100/api/v1/documents

curl -N -X POST http://localhost:6100/api/v1/documents \
  -F 'files=@./sample.pdf;type=application/pdf'

curl -i -X DELETE http://localhost:6100/api/v1/documents/<document-uuid>

curl -s http://localhost:6100/api/v1/usage
```

---

## Layout

```
backend/
  app/
    main.py          # FastAPI app, CORS, /api/v1 mount
    api/             # chats, documents, usage, home
    schemas/
    services/
  tests/
  Dockerfile
  requirements.txt
  requirements-dev.txt
```
