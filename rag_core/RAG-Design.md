# RAG Design — `rag_core`

This documents how the RAG pipeline in `rag_core` actually works: ingestion, embeddings, vector storage, retrieval, reranking, generation, chat persistence, cost tracking, and caching. It's a technical reference for understanding the implementation, not a decision log — see [`../docs/DECISIONS.md`](../docs/DECISIONS.md) for the reasoning and trade-offs behind these choices.

`rag_core` is a single shared Python package (`rag_core/rag_core/...`, installable via `pyproject.toml`) with no FastAPI or Chainlit imports. Both `backend` and `chainlit_app` install it as a local editable package and import it in-process — neither reimplements pipeline logic.

---

## Package Layout

```
rag_core/
  core/       # config, logging, OpenAI client, token pricing, caches
  db/         # SQLAlchemy session + Alembic helpers
  models/     # ORM models (documents, chunks, chat threads/messages, usage)
  services/   # ORM-backed persistence (documents, chat, usage)
  rag/        # ingest → embed → retrieve → rerank → generate
  alembic/    # schema migrations
  tests/
```

**CLI** (`python -m rag_core`): `migrate` applies Alembic migrations; `ingest FILE` runs `ingest_pdf()` on a local PDF.

---

## Pipeline Overview

```
Ingestion → Embedding → Vector Storage
                              ↓
User query → Embedding → Retrieval → Reranking → Generation → Response
```

Each stage is a distinct step with a clear handoff: retrieval returns candidate chunks, reranking filters/reorders them, generation consumes only the filtered set. No stage reimplements another's responsibility.

**Main chat entry point:** `stream_rag_answer()` in `rag/generation.py` orchestrates retrieve → rerank → stream. Callers (`backend`, `chainlit_app`) iterate the async generator and forward tokens to their respective UIs.

**Shared schemas** (`rag/schemas.py`): `ChatQuery` (user input + prior turns), `ChatTurn`, and `RetrievedChunk` (content, filename, page, score, embedding).

---

## Ingestion & Chunking

`rag/ingestion.py` → `ingest_pdf(source, *, filename=None)` is the `rag_core` entry point:

1. Extract page text via `rag/pdf.py`
2. Chunk via `rag/chunking.py`
3. Embed and store via `services/document_service.py`

Chunk size and overlap are pinned in `rag/chunking.py` (not env-configurable):

| Constant        | Value           |
| --------------- | --------------- |
| `CHUNK_SIZE`    | 1200 characters |
| `CHUNK_OVERLAP` | 150 characters  |

Document status transitions (`processing` → `ready` / `failed`) and metadata (`size_bytes`, `error_message`) are tracked in the ORM so callers can surface per-document state. The backend's `POST /api/v1/documents` endpoint wraps `ingest_pdf()` and streams NDJSON progress to the upload UI — that HTTP layer lives in `backend/`, not here.

---

## Embeddings

- Model and vector dimension are pinned in one place: `rag_core/core/embedding_defaults.py` — `text-embedding-3-small`, `1536`. Re-exported from `rag/embeddings.py` for all callers.
- **Not environment-configurable.** Model and dimension are coupled by definition; making them independent `.env` values risks a silent mismatch between what's stored and what pgvector expects. Changing the embedding model is treated as a migration (re-embed existing rows, alter the column), not a config flip.
- Pure token-counting helpers live in `rag_core/core/token_usage.py`, separate from the ORM/usage-recording layer, so `embeddings.py` has no circular import back through `usage_service`.
- Query embedding calls check the query embedding cache first (see Caching below) before hitting the OpenAI API.

---

## Vector Storage

- PostgreSQL + pgvector — the only vector store; no separate vector database. Vectors and relational data live in one Postgres instance, giving transactional consistency between chunk text and its embedding (see [`../docs/PRODUCTION_DEPLOYMENT_PLAN.md`](../docs/PRODUCTION_DEPLOYMENT_PLAN.md) for the fuller pgvector-vs-Pinecone/Chroma discussion).
- Schema versioning via **Alembic** (`rag_core/alembic/`) — `0001_initial_rag_schema`, `0002_usage_columns`, `0003_document_metadata`. Backend startup calls `initialize_vector_store()` → `run_migrations()` rather than relying on an ad-hoc `init.sql`.
- Index: **HNSW** with `vector_cosine_ops`; queries use the matching cosine distance operator (`<=>`). Operator class and query operator are kept paired in the same module so they can't silently drift out of sync.
- Primary keys are UUIDs on every row referenced across services (documents, chunks, threads, messages, usage events), with `created_at`/`updated_at` timestamps on primary entities.
- **Cascading delete**: `document_chunks.document_id` has `ON DELETE CASCADE` (added in `0001`, mirrored in the ORM). Deleting a document removes its chunks — and therefore their embeddings — atomically. Retrieval can never cite a chunk whose parent document no longer exists.

---

## Retrieval & Reranking

Kept as two distinct steps, not folded together.

### Retrieval (`rag/retrieval.py`)

- Vector similarity search over `document_chunks` using pgvector cosine distance; scores are `1 - distance`.
- Only chunks whose parent document has `status = ready` are searched.
- `retrieval_k` defaults to `20` and is environment-tunable via `RAG_CORE_RETRIEVAL_K` — changing it doesn't require a data migration, just different candidate-set sizing.
- Retrieval results are checked against a short-lived cache before hitting Postgres (see Caching below).

### Reranking (`rag/reranking.py`)

Lightweight threshold + MMR — no cross-encoder (avoids a heavy `torch` dependency):

| Constant               | Value | Role                                      |
| ---------------------- | ----- | ----------------------------------------- |
| `SIMILARITY_THRESHOLD` | 0.25  | Minimum cosine similarity to keep a chunk |
| `RERANK_TOP_N`         | 5     | Max chunks passed to generation           |
| `MMR_LAMBDA`           | 0.7   | Diversity vs relevance trade-off          |

If nothing clears the threshold after reranking, `stream_rag_answer()` returns an explicit "no information available" style response (listing available document filenames when any exist) rather than producing an answer not grounded in retrieved content.

---

## Generation

- LLM calls are centralized through `rag_core/core/openai_client.py`, which tries OpenAI first and falls back to OpenRouter on configured quota/auth-style failures.
- Chat completions stream with `stream_options.include_usage` where supported, so provider-reported token usage is captured at the end of the stream rather than estimated.
- `stream_rag_answer()` yields **plain text tokens** — not a structured `{answer, sources}` JSON object. Citations are instructed in the system prompt as inline prose (`[filename, page N]` when page is known, `[filename]` otherwise).
- `RagStreamCapture` exposes retrieved/selected chunks and token usage for logging and cost attribution; callers do not receive citations as a separate API payload today.
- Generation model is environment-tunable via `RAG_CORE_GENERATION_MODEL` (default `gpt-4o-mini`). Ingest batch size via `RAG_CORE_INGESTION_BATCH_SIZE` (default `100`).

---

## Chat History & Titling

- `ChatThread` and `ChatMessage` (plus titling helpers) live in `rag_core` as shared ORM models, so both chat surfaces (Next.js and Chainlit) and the backend API read/write the same schema rather than maintaining separate copies. `backend/app/services/chat.py` is a thin HTTP-facing helper over the shared `chat_service`.
- **Thread titles are generated deterministically**, not via an LLM call: the first substantive user message is truncated to ~72 characters. If the existing title looks like a greeting or placeholder ("hi", "hello", "new chat") and a later message is substantive, the thread is retitled once. This avoids extra cost/latency for a cosmetic feature, is trivially unit-testable, and specifically avoids the sticky "Hi" title problem an LLM-generated title can miss.

---

## Cost & Token Tracking

A hybrid storage design, not a single ledger table:

| Store                        | Role                                                   |
| ---------------------------- | ------------------------------------------------------ |
| Columns on `chat_messages`   | Per-turn tokens/cost; powers the chat footer via `SUM` |
| Columns on `document_chunks` | Ingest embedding tokens/cost per chunk                 |
| `usage_events` ledger        | Suggestions + app-wide `/usage` rollups                |

**Attribution**:

- User message ← query-embedding usage
- Assistant message ← chat completion usage
- Document chunk ← ingest embedding usage (apportioned across the ingest batch)
- Suggestions ← `usage_events` only (`kind=suggestion`)

Provider-reported `usage` from API responses is preferred; length-based estimates are only a fallback when usage data is missing. Pricing lives in `rag_core/core/token_pricing.py` (`estimate_step_cost_usd`) as hardcoded list rates — good for operational visibility, not billing-grade accuracy. A production version would refresh these via a scheduled job rather than hand-editing the table; not built here (see [`../docs/DECISIONS.md`](../docs/DECISIONS.md)).

Recording is centralized in `rag_core/services/usage_service.py`, with pure helpers in `token_usage.py`.

**Exposed via backend HTTP** (not part of `rag_core` itself):

- `GET /api/v1/chats/{id}/usage` — thread totals
- `GET /api/v1/usage` — app-wide chats/suggestions/embeddings breakdown

---

## Suggested Topics

- `rag_core/rag/suggestions.py` (`suggest_chat_topics`) generates document-grounded starter questions for empty chat threads via an LLM call, recorded as a `usage_events` row (`kind=suggestion`).
- Bounded to 5 topics per call to cap spend; falls back to heuristic topics if the LLM call fails, so the empty-state UX degrades gracefully rather than breaking.

---

## Caching

All caching logic lives in `rag_core/core/cache.py`, consulted from `embeddings.py` and `retrieval.py` — neither `backend` nor `chainlit_app` implements its own caching.

| Cache                                | Status                | Key                                                   | Notes                                                                                                                                   |
| ------------------------------------ | --------------------- | ----------------------------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------- |
| Query embedding                      | Built                 | `normalize_query(text)` — exact match, no fuzzy dedup | LRU-capped at 512 entries/process; no TTL (embeddings are deterministic for a pinned model); usage tokens only recorded on cache misses |
| Retrieval result                     | Built                 | `(sha256(embedding_bytes), k)`                        | 5-minute TTL; invalidated on document delete or a document transitioning to `ready` (corpus change)                                     |
| Ingest embedding (content-hash skip) | Documented, not built | —                                                     | Real production value; low likelihood of mattering when re-uploads are rare during grading                                              |
| Generation response cache            | Documented, not built | —                                                     | Semantic caching needs careful invalidation; a stale cached answer could cite a deleted document                                        |

On a retrieval cache hit, cached chunk IDs are **rehydrated from Postgres** (`_rehydrate_cached_chunks`). If any row is missing or stale, the cache entry is discarded and a fresh vector search runs.

In-memory, process-local caches — deliberately not Redis. At this application's scale (one backend instance, one Chainlit instance in Docker Compose), a shared external cache isn't needed; `backend` and `chainlit_app` simply each carry their own in-memory cache, which is an acceptable limitation at this scale. Redis is the documented upgrade path if this were deployed across multiple instances (see [`../docs/PRODUCTION_DEPLOYMENT_PLAN.md`](../docs/PRODUCTION_DEPLOYMENT_PLAN.md)).

---

## Logging & Observability

### `rag_core`

- **structlog** configured in `core/logging.py` — JSON output in production, human-readable console output in development.
- Pipeline events logged from `rag_core`: per-chunk similarity scores on the generation path (`rag.retrieval.completed`), ingestion outcomes (chunk count, failure reason), cache hits/stale fallbacks.

### `backend` (request-level, not in `rag_core`)

- Every backend request gets a `trace_id` (from `X-Trace-Id`/`X-Request-Id`, or generated) bound into structlog's context for all downstream log lines in that request.
- Request/response details (trace id, path, latency, status, thread id, retrieval count, tokens, cost) on the chat HTTP path.

Not built, documented as production follow-up: OpenTelemetry tracing across backend → `rag_core` → Postgres/OpenAI, centralized log aggregation, and alerting — all deployment/operational concerns out of scope for this pass (see [`../docs/PRODUCTION_DEPLOYMENT_PLAN.md`](../docs/PRODUCTION_DEPLOYMENT_PLAN.md)).

---

## What's Deliberately Out of Scope

See [`../docs/DECISIONS.md`](../docs/DECISIONS.md) for full reasoning. In short:

- No authentication/authorization (shared anonymous access model)
- No Redis-backed **caching** in `rag_core` (single-instance, process-local caches only)
- **Rate limiting** is implemented in `backend/` via in-memory `slowapi` (20/min chat, 10/min upload) — not in `rag_core`. Redis-backed shared limits are the multi-instance upgrade path.
- No cross-encoder reranking (avoids a heavy `torch` dependency across two Docker images)
- No scheduled pricing-refresh job for cost estimates
