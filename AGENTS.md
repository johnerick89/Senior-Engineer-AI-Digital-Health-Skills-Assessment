# AGENTS.md

This file provides guidance to AI coding agents (Claude Code, Cursor, etc.) when working on this repository.

## Confirmed Architectural Decision

There are **two independent chat surfaces**, per the assignment's substitution
policy ("Chainlit may be used in place of **or alongside** the Next.js
frontend"):

1. A custom chat UI in `frontend/` (Next.js, Pages Router) — calls the backend's
   `/chat` endpoint over HTTP.
2. The full Chainlit chat app in `chainlit_app/`, served on its own at
   port `8000` — a complete, independent chat experience, not a debug-only tool.

Both surfaces call into **one shared `rag_core` package** for retrieval and
generation. This is settled — do not create a second copy of ingestion,
retrieval, or generation logic inside either `backend/` or `chainlit_app/`, and
do not collapse the two chat surfaces into one. `backend/` calls `rag_core` via
its own Python process (in-process import, not HTTP) to serve `frontend/`'s
`/chat` requests; `chainlit_app/` also imports `rag_core` in-process for its own
`on_message` handler. Neither service re-implements what `rag_core` already
provides.

If a design doc for a given module is missing from `designs/`, stop and ask —
do not infer the design from the assignment brief alone.

## Project Structure

```
.
├── ASSIGNMENT.md          ← original assessment brief, do not edit
├── ASSUMPTIONS.md         ← human-authored, do not edit
├── DECISIONS.md           ← human-authored architecture/trade-off log, do not edit
├── README.md
├── docker-compose.yaml
├── .env.example
│
├── backend/                       ← FastAPI: ingestion API, document mgmt, /chat for frontend
│   ├── Dockerfile
│   ├── requirements.txt
│   ├── startup.sh / startup_unix.sh
│   ├── migrations/                ← Alembic (or numbered SQL) — schema + pgvector setup
│   │   └── versions/
│   ├── app/
│   │   ├── main.py
│   │   ├── models.py              ← SQLAlchemy models (documents, chunks, chat_history)
│   │   ├── schemas.py             ← Pydantic request/response models
│   │   ├── deps.py                ← DB session, settings injection
│   │   ├── config.py              ← env var loading (pydantic-settings)
│   │   ├── routers/
│   │   │   ├── documents.py       ← POST /documents/upload, GET /documents
│   │   │   ├── chat.py            ← POST /chat — imports rag_core, serves frontend/
│   │   │   └── health.py
│   │   └── home/
│   └── tests/
│
├── rag_core/                      ← single shared RAG package — no framework imports
│   ├── ingestion.py                   PDF parsing, chunking
│   ├── embeddings.py                  embedding generation, pinned model + dimension
│   ├── retrieval.py                   vector search against pgvector
│   ├── reranking.py                   reranking + relevance/quality filtering of retrieved chunks
│   ├── generation.py                  prompt construction + LLM call, structured citations
│   ├── vector_store.py                pgvector query/insert helpers
│   └── tests/
│
├── chainlit_app/                  ← Chainlit: full independent chat experience
│   ├── Dockerfile
│   ├── requirements.txt
│   ├── main.py
│   ├── app/
│   │   └── chat.py                ← on_message handler, imports rag_core directly
│   └── tests/
│
└── frontend/                      ← Next.js, Pages Router
    ├── Dockerfile
    ├── package.json
    ├── pages/
    │   ├── index.tsx               ← chat (custom, calls backend /chat — not linked to Chainlit)
    │   ├── upload.tsx              ← dedicated PDF upload page (Requirement 2)
    │   ├── assignment.tsx          ← renders ASSIGNMENT.md
    │   └── api/                    ← optional Next.js API routes proxying backend, if needed
    ├── src/
    │   ├── components/
    │   └── config/                 ← backend API base URL, Chainlit app URL (if linked from nav)
    └── __tests__/
```

The `.venv` for Python services lives at the **parent directory** level, one
level above each service folder. Activate it before running backend or
Chainlit commands locally (outside Docker).

## Environment Setup

```bash
# Python services (backend, chainlit_app, rag_core) — shared venv from repo root
source ../.venv/bin/activate   # macOS/Linux
..\.venv\Scripts\activate      # Windows

pip install "fastapi[standard]" sqlalchemy alembic pydantic pydantic-settings
pip install pytest pytest-asyncio httpx
pip install chainlit
pip install pgvector psycopg[binary]
pip install pypdf  # or your chosen PDF parser

# rag_core is a local editable package — install into both backend and chainlit_app envs
pip install -e ./rag_core

# Frontend (Pages Router)
cd frontend && npm install
```

`rag_core` should be installable as a local package (a minimal `pyproject.toml`
or `setup.py` at `rag_core/`) so both `backend` and `chainlit_app` can
`pip install -e ../rag_core` in their Docker images and `import rag_core`
cleanly, rather than relying on fragile relative path hacks.

## Development Commands

### Run everything

```bash
docker compose up
```

All application services (`backend`, `chainlit_app`, `frontend`) must run with
live-reload enabled in `docker-compose.yaml` (`--reload` for uvicorn, `-w` for
Chainlit, `npm run dev` for Next.js) so code edits don't require manual
container restarts. Rebuild (`docker compose build <service>`) only when a
`Dockerfile` changes or a new dependency is added to a `requirements.txt` /
`package.json` — including changes to `rag_core`, since it's installed as a
dependency into both `backend` and `chainlit_app` images.

### Run tests

```bash
# rag_core — test the shared logic once, here, not duplicated per-service
cd rag_core && pytest tests/ -v

# Backend
cd backend && pytest tests/ -v

# Chainlit handlers
cd chainlit_app && pytest tests/ -v

# Frontend
cd frontend && npm test
```

Run the relevant test suite after **every code change** to the module you
touched — no exceptions. If tests fail, fix them before proceeding. Do not
skip or comment out failing tests.

### After every change — checklist

1. Run the test suite for the service(s) you touched — all must pass.
2. If you touched `rag_core/`, run its tests, then also run `backend` and
   `chainlit_app` tests — a change here affects two independent consumers.
3. `docker compose up` (or confirm it's already running) — all services must
   start without errors.
4. Hit `GET /health` on the backend and confirm `200 OK`.
5. If you touched the chat flow, manually verify both chat surfaces
   (`frontend` at `/`, and Chainlit at port `8000`) still work — they are
   independent UIs and a break in one won't surface in the other.
6. Only then proceed to the next task.

## Stack

- **Frontend**: Next.js, **Pages Router**, TypeScript, Tailwind
- **Chat surface 1**: custom chat page in `frontend/pages/index.tsx`, calls
  `backend`'s `/chat` endpoint over HTTP — no dependency on Chainlit
- **Chat surface 2**: Chainlit, full independent chat app at port `8000`,
  imports `rag_core` directly in-process
- **Backend**: FastAPI (ingestion, document management, `/chat` for the
  frontend, migrations)
- **Shared logic**: `rag_core/` — plain Python, no FastAPI or Chainlit imports,
  installed as a local package into both `backend` and `chainlit_app`
- **Database**: PostgreSQL + pgvector
- **Migrations**: Alembic (or numbered SQL files run at container init —
  confirm in `DECISIONS.md` which was chosen, don't assume)
- **Testing**: pytest + httpx `TestClient` for backend; pytest for `rag_core`;
  your frontend framework's standard test runner for React components

## Coding Standards

### General

- Type annotations on all Python functions and methods; TypeScript strict mode
  for all frontend code.
- Every public function has a one-line docstring minimum.
- No dead code, commented-out blocks, or debug `print()`/`console.log()` left in
  committed code. Use `logging` (Python) or a proper logger (frontend).
- No placeholder/stub implementations left in — either implement fully or stop
  and ask.

### rag_core — Critical

- **Pin the embedding model and dimension in exactly one place**:
  `rag_core/embeddings.py`. Never hardcode a vector dimension in migrations,
  schemas, or query code separately — import the constant from here.
- If the embedding model ever changes, the pgvector column dimension and every
  existing row's embedding must be regenerated. This is not a drop-in swap —
  flag it explicitly rather than changing the model casually.
- Always match the pgvector index's distance operator class
  (`vector_cosine_ops`, `vector_l2_ops`, etc.) to the operator used in queries
  (`<=>`, `<->`) in `vector_store.py`. A mismatch silently disables the index
  rather than erroring.
- Chunking parameters (chunk size, overlap) live in one place in
  `rag_core/ingestion.py` as named constants, not magic numbers scattered
  across `backend` or `chainlit_app`.
- `retrieval.py` returns candidate chunks; `reranking.py` is a distinct step
  that filters/reorders them by relevance and quality before they reach
  `generation.py` — keep this separation, don't fold reranking logic into
  either retrieval or generation.
- `generation.py` must return structured output — `{answer, sources: [{doc,
page}]}` — not a plain string with citations embedded in prose. Both
  `backend/app/routers/chat.py` and `chainlit_app/app/chat.py` depend on this
  shape; changing it is a breaking change for both consumers.
- If retrieval + reranking yields no chunks above the relevance threshold,
  `generation.py` must return an explicit "I don't have information on that"
  style response, not a hallucinated answer.

### SQLAlchemy Models (backend)

- Define all models in `backend/app/models.py`.
- Use `DeclarativeBase` (SQLAlchemy 2.x style).
- Every model has `created_at` and `updated_at` timestamp columns.
- Use UUID primary keys where a row is referenced across services (e.g.
  `document_id` referenced by both ingestion and retrieval).

### API Layer (backend)

- All routes live in `backend/app/routers/`, using `APIRouter` with a prefix
  and tags per module.
- Return structured error responses — never bare strings.
- File upload endpoints must validate file type (PDF only) and size before
  handing off to `rag_core.ingestion`.
- `/chat` is consumed only by `frontend/` — Chainlit does not call this
  endpoint, it uses `rag_core` directly. Do not add a Chainlit-specific
  branch here.

### Frontend / React (Pages Router)

- Pages live under `frontend/pages/` — `index.tsx`, `upload.tsx`,
  `assignment.tsx`. Do not introduce an `app/` directory alongside `pages/`;
  pick one routing convention and stay in it.
- Components have no required props, or provide sensible defaults.
- The backend API base URL (and, if the nav links out to Chainlit, its URL) is
  read from `frontend/src/config/`, never hardcoded inline in components.
- The upload page must show ingestion status per document (processing / ready
  / failed) — this is a graded requirement, not a nice-to-have.
- The custom chat page (`index.tsx`) must render source citations from the
  `/chat` response's `sources` array — don't parse them out of response text.

## Design Docs

Before implementing any module, check `designs/` for a corresponding doc. If
none exists for the module you're about to build, stop and ask — do not infer
the design from the assignment brief alone.

## Git Discipline

- Small, focused commits — one logical change per commit, matching the
  assessment's explicit instruction to commit frequently with descriptive
  messages.
- Commit message format: `<type>(<scope>): <short description>` — e.g.
  `feat(rag_core): add reranking step before generation`.
- A single "initial commit" containing all code is not acceptable and directly
  contradicts the assignment's stated expectations.

## What the Agent Should Not Do

- Do not edit `ASSIGNMENT.md`, `ASSUMPTIONS.md`, or `DECISIONS.md` — those are
  human-authored artifacts.
- Do not create a second copy of ingestion/retrieval/reranking/generation logic
  in `backend/` or `chainlit_app/` — both must import `rag_core`.
- Do not collapse the two chat surfaces (custom Next.js chat, Chainlit) into
  one — they are intentionally independent
- Do not introduce Next.js App Router files or conventions — this frontend is
  Pages Router only.
- Do not swap out core libraries (FastAPI, SQLAlchemy, Chainlit, pgvector)
  without explicit instruction.
- Do not add dependencies to any `requirements.txt` or `package.json` without
  being asked.
- Do not hardcode the embedding dimension or chunking parameters in more than
  one place.
- Do not change the `rag_core` structured output shape
  (`{answer, sources}`) without updating both consumers.
