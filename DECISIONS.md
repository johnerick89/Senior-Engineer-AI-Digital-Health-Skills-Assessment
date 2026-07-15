# Decisions

Architectural and design choices made while building the RAG assessment app, with brief reasoning where it matters. Defaults taken where the brief was silent are listed separately in `ASSUMPTIONS.md`.

---

## Chat surfaces

**Decision:** Two independent, full chat surfaces:

1. Custom Next.js (Pages Router) UI → backend `POST /chat` over HTTP
2. Chainlit on port `8000` → imports `rag_core` in-process

**Reasoning:** The assignment allows Chainlit “in place of **or alongside**” Next.js. The custom UI owns the graded experience (citations, upload status, nav); Chainlit is a second complete surface, not a debug-only tool.

---

## Shared RAG — `rag_core`

**Decision:** One shared package for ingest, embed, retrieve, rerank, generate, suggestions, usage, and relational ORM models. Neither `backend` nor `chainlit_app` reimplements pipeline logic.

**Decision:** Install as an editable local package (`pip install -e`) into consumers / images; import in-process (not HTTP between Chainlit and RAG).

**Decision:** Package layout is `rag_core/rag_core/...`, installable via `pyproject.toml`.

**Decision:** `rag_core` stays free of FastAPI / Chainlit imports so either consumer can use it without framework bleed.

**Decision:** Chat thread/message persistence (`ChatThread`, `ChatMessage`, titling helpers) lives in `rag_core` (shared models + `chat_service`) so both surfaces and the backend API share the same schema. Backend `app/services/chat.py` is a thin HTTP-facing helper over that.

---

## Database

**Decision:** PostgreSQL + pgvector only (assignment: do not substitute). Vectors and relational data stay in one Postgres instance.

**Decision:** Docker image `pgvector/pgvector:pg16`; the `vector` extension is created as part of schema / migration setup.

**Decision:** **Alembic** owns schema versions under `rag_core/alembic/`(`0001_initial_rag_schema`, `0002_usage_columns`). Backend startup calls `initialize_vector_store()` → `run_migrations()`. Prefer migrations over ad-hoc `init.sql` only.

**Decision:** HNSW index with `vector_cosine_ops`; queries use cosine distance `<=>` — operator class and query operator stay paired in one place.

**Decision:** UUID primary keys for rows referenced across the app (documents, chunks, threads, messages, usage events). Timestamps (`created_at` / `updated_at`) on primary entities.

---

## Embeddings & vector storage

**Decision:** Pin embedding model + dimension in one place: `rag_core/core/embedding_defaults.py` (`text-embedding-3-small`, `1536`).Re-exported from `rag/embeddings.py` for callers. **Not** env-configurable.

**Reasoning:** Model and dimension are coupled; env toggles invite silentdimension mismatches. Changing the model implies migrating the pgvector column and re-embedding all rows — not a config flip.

**Decision:** Pure token helpers live in `rag_core/core/token_usage.py` so `embeddings` does not import ORM / `usage_service` (avoids circular imports).

---

## LLM client & config

**Decision:** Centralize provider calls in `rag_core/core/openai_client.py` (OpenAI first, OpenRouter fallback on configured quota / auth failures).

**Decision:** `.env` / settings hold secrets and safe knobs only: `DATABASE_URL`, `OPENAI_API_KEY`, `OPENROUTER_API_KEY`, generation model, `retrieval_k`, ingest batch size, CORS origins, log level. Embedding model/dimension and distance metric stay code constants.

---

## Reranking & generation

**Decision:** Keep `retrieval` → `reranking` → `generation` as separate steps. Retrieval returns candidates; rerank filters/reorders; generation consumes the filtered set.

**Decision:** If nothing clears the relevance threshold, generation returns an explicit “no information” style response rather than hallucinating.

**Decision:** Stream chat completions with `stream_options.include_usage` when supported so provider usage can be captured at stream end.

---

## Chat history & titling

**Decision:** Deterministic thread titles from the first substantive user message (truncate to ~72 chars). If the current title looks like a greeting /placeholder (`hi`, `hello`, `new chat`, …) and a later message is substantive, retitle once. **No LLM call for titles.**

**Reasoning:** Zero extra cost/latency; deterministic and unit-testable. Greeting refresh avoids sticky “Hi” titles — a UX detail LLM-title shortcuts often miss.

---

## Token & cost tracking (hybrid)

**Decision:** Hybrid storage — not ledger-only and not denormalized-only:

| Store                        | Role                                                 |
| ---------------------------- | ---------------------------------------------------- |
| Columns on `chat_messages`   | Per-turn tokens/cost; powers chat footer via `SUM`   |
| Columns on `document_chunks` | Ingest embedding tokens/cost per chunk               |
| `usage_events` ledger        | Suggestions + clean Usage-page rollups; optional FKs |

**Attribution:**

- **User message** ← query-embedding usage
- **Assistant message** ← chat completion usage
- **Document chunk** ← ingest embedding (apportioned across batch)
- **Suggestions** ← `usage_events` (`kind=suggestion`) only

**Decision:** Prefer provider `usage` from API responses; fall back to length estimates only when usage is missing. Price via `rag_core/core/token_pricing.py` (`estimate_step_cost_usd`).

**Decision:** Central recording helpers in `rag_core/services/usage_service.py` (+ pure helpers in `token_usage.py`).

**API:**

- `GET /chats/{id}/usage` → thread totals
- `GET /usage/summary` → chats / suggestions / embeddings buckets

**UI:**

- Chat footer: `Total tokens · Total cost` after a turn (or on thread load)
- `/usage` page + nav item for app-wide summary

**Note:** List prices are hardcoded estimates for operational visibility. A
production system would sync rates via a scheduled job rather than hand-editing
— a natural “additional service layer” upgrade path, not built here.

---

## Backend layout (FastAPI)

**Decision:** Layer packages under `backend/app/` (similar to a typical FastAPI
service layout), not feature folders:

```
app/
  main.py
  models.py          # starter DeclarativeBase; RAG ORM is in rag_core
  api/               # routers: chat, upload, home
  schemas/           # Pydantic request/response
  services/          # thin HTTP-facing helpers over rag_core
```

**Reasoning:** Clearer HTTP vs schema vs helper boundaries without inventing new features.

---

## Frontend

**Decision:** Next.js **Pages Router** only. Pages:

- `/` — custom chat (streams `/chat`, topic chips + footer usage)
- `/upload` — dedicated PDF upload with per-file status (Requirement 2)
- `/usage` — token/cost summary
- `/assignment` — assignment brief

**Decision:** Backend/API base URL from `frontend/src/config/`, not hardcoded in components.

**Decision:** Source citations / structured fields come from APIs as designed; do not scrape citations out of prose when structured fields exist.

---

## Chainlit surface

**Decision:** Chainlit calls `rag_core` **in-process** (same as planned for both consumers). It does **not** call the FastAPI backend over HTTP. `DATABASE_URL` is wired into the Chainlit service so `rag_core` can open Postgres from that process; the connection/session objects still live inside `rag_core`.

**Decision:** Chat parity with Next.js for this surface means: streaming RAG answers (`stream_rag_answer`), starter topics (`suggest_chat_topics`), and a left-hand thread history backed by the same `chat_threads` / `chat_messages` rows.

**Decision:** Use Chainlit’s **native history sidebar** via a custom `BaseDataLayer` (`chainlit_app/app/data_layer.py`) mapped onto `chat_service`, rather than an in-chat Action-button thread picker.

**Reasoning:** Actions would force an extra click to load past chats and hide threads from the built-in left nav. The data layer keeps UX closer to the Next.js sidebar.

**Decision:** Accept Chainlit’s requirement that `/project/threads` returns **401 without a logged-in user**. Next.js needs no auth because it uses our own `GET /chats` APIs. Chainlit’s sidebar is framework-gated on auth — that is why Chainlit has a login path and the Next.js app does not.

**Decision (auth workaround):** Demo-only silent login so users are not stuck on a login form:

- Fixed credentials: `john.doe@example.com` / `1234` (`password_auth_callback`)
- Optional header auth: `X-LMH-Chainlit-Auth: john.doe@example.com` (`header_auth_callback`)
- `public/silent_login.js` (loaded via `custom_js`) POSTs `/login` (fallback `/auth/header`) then reloads once if `/user` is unauthenticated

A server **startup script cannot** log visitors in: auth cookies live in the browser. Auto-submit JS (and header auth for proxies) are the workable paths.

**Decision:** Persist Chainlit’s user **identifier** as `anonymous` (display name can show the demo email) so `get_thread_author` / sidebar ACL align and threads remain **shared** with Next.js (single-tenant list, same as the rest of the app).

**Decision:** Thin turn helpers live in `chainlit_app/app/turn.py` (mirror of `backend/app/services/chat.py`) for this pass — not extracted into `rag_core` yet.

**Decision:** PDF upload and the Usage page stay on Next.js only. Chainlit spontaneous file upload is disabled. No token/cost footer in Chainlit v1.

---
