# Last Mile Health RAG App

Retrieval-Augmented Generation app for document-grounded chat: Next.js UI,
FastAPI backend, Chainlit second chat surface, shared `rag_core` package, and
PostgreSQL + pgvector.

> **Assignment brief:** The original skills-assessment instructions live in
> [`ASSIGNMENT.md`](./ASSIGNMENT.md) (also rendered in the app at
> `/assignment`). This README is the **application** runbook — not the brief.

Architecture choices and deferred scope: [`DECISIONS.md`](./DECISIONS.md),
[`ASSUMPTIONS.md`](./ASSUMPTIONS.md).

Per-service detail (API paths, tests, coverage, layout):

| Project | README |
|---------|--------|
| FastAPI API | [`backend/README.md`](./backend/README.md) |
| Shared RAG library | [`rag_core/README.md`](./rag_core/README.md) |
| Next.js UI | [`frontend/README.md`](./frontend/README.md) |
| Chainlit chat | [`chainlit_app/README.md`](./chainlit_app/README.md) |

---

## Stack & ports

| Service | Role | URL / port |
|---------|------|------------|
| `frontend` | Custom chat, upload, usage | http://localhost:3000 |
| `backend` | HTTP API under `/api/v1` | http://localhost:6100 |
| `chainlit` | Independent chat (imports `rag_core`) | http://localhost:8000 |
| `relational_db` | Postgres + pgvector | `localhost:5432` |
| `rag_core` | Library / CLI (`tools` profile) | — |

Compose project name used below: **`assessment`**.

---

## Prerequisites

- Docker + Docker Compose
- For host (non-Docker) runs: Python 3.12+, Node 20+, a venv at `.venv`
- API keys in `rag_core/.env` (copy from `rag_core/.env.example`)

```bash
cp rag_core/.env.example rag_core/.env
# set OPENAI_API_KEY and/or OPENROUTER_API_KEY
```

---

## Docker (recommended)

From the **repository root**:

```bash
# Build & start full stack (db + backend + frontend + chainlit)
docker compose -p assessment up -d --build

# Logs
docker compose -p assessment logs -f

# Stop
docker compose -p assessment down
```

Source is mounted with live-reload (`uvicorn --reload`, `next dev`, Chainlit
`-w`). Rebuild a service only when its `Dockerfile` or dependencies change:

```bash
docker compose -p assessment build backend frontend chainlit
docker compose -p assessment up -d backend frontend chainlit
```

DB only (useful for local Python against Compose Postgres):

```bash
docker compose -p assessment up -d relational_db
```

---

## Local (host processes)

1. Start Postgres (Compose DB is fine).
2. Shared Python env + `rag_core`:

```bash
source .venv/bin/activate
pip install -e ./rag_core
pip install -r backend/requirements.txt
pip install -r chainlit_app/requirements.txt
```

3. Env (`DATABASE_URL` → `localhost:5432`, keys in `rag_core/.env` or exports).
4. Run services in separate terminals:

```bash
# Backend — http://localhost:6100
cd backend && PYTHONPATH=../rag_core:. uvicorn app.main:app --reload --port 6100

# Frontend — http://localhost:3000
cd frontend && npm install && NEXT_PUBLIC_BACKEND_URL=http://localhost:6100 npm run dev

# Chainlit — http://localhost:8000 (optional)
cd chainlit_app && PYTHONPATH=../rag_core:. \
  DATABASE_URL=postgresql://postgres:postgres@localhost:5432/postgres \
  CHAINLIT_AUTH_SECRET=lmh-chainlit-dev-secret-change-me \
  python -m chainlit run main.py --port 8000 -w
```

---

## Tests (overview)

```bash
# rag_core
cd rag_core && pytest tests/ -v

# backend
cd backend && PYTHONPATH=../rag_core:. pytest tests/ -v

# frontend
cd frontend && npm test

# chainlit
cd chainlit_app && PYTHONPATH=../rag_core:. pytest tests/ -v
```

Coverage commands and service-specific notes are in each project README.

---

## Quick smoke

1. Open http://localhost:3000 → Upload a PDF → Chat asking about it.
2. `curl -s http://localhost:6100/api/v1/health`
3. Chainlit at http://localhost:8000 (demo login auto-submits for sidebar history).
