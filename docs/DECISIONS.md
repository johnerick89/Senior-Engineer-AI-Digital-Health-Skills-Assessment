# Decisions

Architectural and design choices made while building the RAG assessment app, with brief reasoning where it matters. Defaults taken where the brief was silent are listed separately in `ASSUMPTIONS.md`.

---

## Chat surfaces

**Decision:** Two independent, full chat surfaces:

1. Custom Next.js (Pages Router) UI → backend `POST /api/v1/chats` over HTTP
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

**Decision:** **Alembic** owns schema versions under `rag_core/alembic/`
(`0001_initial_rag_schema`, `0002_usage_columns`, `0003_document_metadata`).
Backend startup calls `initialize_vector_store()` → `run_migrations()`. Prefer
migrations over ad-hoc `init.sql` only.

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

### Cost-estimation layer (operational visibility)

**What it does:** Records **per-step USD/token usage** across:

- Query embeddings (user messages)
- Chat completions (assistant messages)
- Ingest embeddings (document chunks; apportioned across batches)
- Suggested topics (`usage_events.kind=suggestion`)

This is exposed through:

- Data: `chat_messages.*`, `document_chunks.*`, and the `usage_events` ledger
- API: `GET /api/v1/chats/{id}/usage`, `GET /api/v1/usage`
- UI: chat footer totals + `/usage` page rollups

**Why it exists:** The assignment didn’t require cost tracking, but any
production LLM system needs **operational visibility** into spend and token
drivers (embeddings vs completion vs background UX calls) to set budgets, debug
spikes, and make trade-offs.

**Trade-off:** Rates are hardcoded list-price estimates in
`rag_core/core/token_pricing.py` (good for visibility, not billing-accurate).
A production system would add a **scheduled job** to refresh pricing against
provider updates (and/or ingest provider-reported costs), rather than manually
editing a table. This “pricing refresh” scheduler is documented but not built.

### Suggested topics (UX service layer)

**Decision:** LLM-generated starter questions on empty chats via
`rag_core/rag/suggestions.py` (`suggest_chat_topics`), recorded as a usage event
(`usage_events.kind=suggestion`).

**Why it exists:** Improves first-turn UX (especially in demos) by showing
document-grounded prompts when users don’t know what to ask.

**Trade-off:** It’s an extra LLM call per “new chat” experience. Spend is bounded
by capping the list to **5** topics, and by falling back to heuristic topics
when the LLM call fails.

**API:**

- `GET /api/v1/chats/{id}/usage` → thread totals
- `GET /api/v1/usage` → chats / suggestions / embeddings buckets

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
  api/               # routers: chats, documents, usage, home
  schemas/           # Pydantic request/response
  services/          # thin HTTP-facing helpers over rag_core
```

**Reasoning:** Clearer HTTP vs schema vs helper boundaries without inventing new features.

---

## API versioning & resources

**Decision:** All application HTTP routes (except root health) live under
**`/api/v1`** with **plural** resource names. One cutover — no dual-route aliases.

| Resource  | Examples                                                                         |
| --------- | -------------------------------------------------------------------------------- |
| Chats     | `POST/GET /api/v1/chats`, `GET …/suggestions`, `…/{id}/messages`, `…/{id}/usage` |
| Documents | `POST/GET /api/v1/documents`, `DELETE /api/v1/documents/{id}`                    |
| Usage     | `GET /api/v1/usage`                                                              |
| Meta      | `GET /` and `GET /api/v1/health`, `GET /api/v1/assignment`                       |

**Reasoning:** Stable prefix for future `v2`; REST collection naming matches how
the upload page talks about “documents” and the sidebar about “chats”.

---

## Document management

**Decision:** Documents are a first-class collection on the backend:

- `POST /api/v1/documents` — PDF ingest (NDJSON progress; renamed from `/upload`)
- `GET /api/v1/documents` — list newest-first (`status`, `size_kb`, `chunk_count`,
  `uploaded_at`, `error_message`)
- `DELETE /api/v1/documents/{id}` — `204` / `404`; **must** remove embeddings

**Decision:** Chunk rows cascade via DB `ON DELETE CASCADE` on
`document_chunks.document_id` (already in `0001`; ORM matches). Deleting a
document never leaves orphan vectors that retrieval could still cite.

**Decision:** `documents.size_bytes` and `documents.error_message` added in
`0003_document_metadata` so list/upload UX can show size and failure reasons.

**Decision:** Upload page loads the list on mount and calls DELETE (with confirm)
instead of client-only dummy state.

**Scoped out:** `GET /documents/{id}`, re-ingest / reprocess.

---

## Frontend

**Decision:** Next.js **Pages Router** only. Pages:

- `/` — custom chat (streams `POST /api/v1/chats`, topic chips + footer usage)
- `/upload` — PDF upload with list/status/delete against `/api/v1/documents`
- `/usage` — token/cost summary (`GET /api/v1/usage`)
- `/assignment` — assignment brief

**Decision:** Backend base URL and versioned API root from
`frontend/src/config/client.ts` (`backendUrl`, `apiV1Url`) — not hardcoded in
components.

**Decision:** Source citations / structured fields come from APIs as designed; do not scrape citations out of prose when structured fields exist.

---

## Chainlit surface

**Decision:** Chainlit calls `rag_core` **in-process** (same as planned for both consumers). It does **not** call the FastAPI backend over HTTP. `DATABASE_URL` is wired into the Chainlit service so `rag_core` can open Postgres from that process; the connection/session objects still live inside `rag_core`.

**Decision:** Chat parity with Next.js for this surface means: streaming RAG answers (`stream_rag_answer`), starter topics (`suggest_chat_topics`), and a left-hand thread history backed by the same `chat_threads` / `chat_messages` rows.

**Decision:** Use Chainlit’s **native history sidebar** via a custom `BaseDataLayer` (`chainlit_app/app/data_layer.py`) mapped onto `chat_service`, rather than an in-chat Action-button thread picker.

**Reasoning:** Actions would force an extra click to load past chats and hide threads from the built-in left nav. The data layer keeps UX closer to the Next.js sidebar.

**Decision:** Accept Chainlit’s requirement that `/project/threads` returns **401 without a logged-in user**. Next.js needs no auth because it uses our own `GET /api/v1/chats` APIs. Chainlit’s sidebar is framework-gated on auth — that is why Chainlit has a login path and the Next.js app does not.

**Decision (auth workaround):** Demo-only silent login so users are not stuck on a login form:

- Fixed credentials: `john.doe@example.com` / `1234` (`password_auth_callback`)
- Optional header auth: `X-LMH-Chainlit-Auth: john.doe@example.com` (`header_auth_callback`)
- `public/silent_login.js` (loaded via `custom_js`) POSTs `/login` (fallback `/auth/header`) then reloads once if `/user` is unauthenticated

A server **startup script cannot** log visitors in: auth cookies live in the browser. Auto-submit JS (and header auth for proxies) are the workable paths.

**Decision:** Persist Chainlit’s user **identifier** as `anonymous` (display name can show the demo email) so `get_thread_author` / sidebar ACL align and threads remain **shared** with Next.js (single-tenant list, same as the rest of the app).

**Decision:** Thin turn helpers live in `chainlit_app/app/turn.py` (mirror of `backend/app/services/chat.py`) for this pass — not extracted into `rag_core` yet.

**Decision:** PDF upload and the Usage page stay on Next.js only. Chainlit spontaneous file upload is disabled. No token/cost footer in Chainlit v1.

---

## Security & abuse prevention

**Decision:** Authentication/authorization is out of scope: no JWT-based auth, no user accounts, and no per-user document/chat isolation. The system uses a shared anonymous access model.

**Decision:** Backend CORS is restricted to explicit known origins (frontend `:3000`, Chainlit `:8000`) rather than a wildcard `*`.

**Decision:** Backend input validation and safety checks are enforced server-side:

- Pydantic schemas validate all request bodies.
- PDF upload validation is enforced in the backend (PDF-only and size-limited) rather than relying on frontend-only checks.

**Decision:** Backend exceptions are translated to structured HTTP responses; stack traces / raw SQL errors are not returned to clients.

**Decision:** Add in-memory per-IP rate limiting via `slowapi` to protect expensive endpoints (single-instance assessment scope; no Redis-backed shared limiter):

- Chat generation: `POST /api/v1/chats` limited to `20/minute`.
- PDF ingestion: `POST /api/v1/documents` (upload) limited to `10/minute`.

**Implementation detail:** Rate limiting uses `get_remote_address` (client IP) as the key function, and relies on slowapi’s default `429 Too Many Requests` response with a `Retry-After` header. SlowAPI requires the handler to accept a `Request` parameter for IP resolution; the documents upload route includes it.

## Caching

**Decision:** In-memory process-local caches in `rag_core` for query embeddings and short-TTL retrieval results. Redis (or similar) would be the natural upgrade for multi-instance deployment.

**Reasoning:** Assessment scope runs single-process Docker Compose services with no cross-instance invalidation complexity. A shared external cache would be required for consistent hits across horizontally scaled replicas.

**Limitation:** `backend` and `chainlit_app` are separate processes in Compose. Each gets its own in-memory cache. That is acceptable for this scale.

**Decision:** All cache logic lives in `rag_core/core/cache.py` and is consulted from `embeddings.py` and `retrieval.py`. Neither `backend/` nor `chainlit_app/` reimplements caching.

| Opportunity               | Action            | Rationale                                                                                           |
| ------------------------- | ----------------- | --------------------------------------------------------------------------------------------------- |
| Query embedding cache     | **Built**         | Same normalized question → skip duplicate OpenAI embed calls                                        |
| Retrieval result cache    | **Built**         | Short TTL on `(embedding_hash, k)` → chunk ids; helps repeated questions and suggested-topic clicks |
| Ingest embedding cache    | **Document only** | Content-hash skip is useful in production; low value when re-uploads are rare during grading        |
| Generation response cache | **Document only** | Semantic answer cache needs careful invalidation; stale answers can cite deleted documents          |

**Query embedding cache (built):**

- Hook: `_embed_texts_async` in `rag_core/rag/embeddings.py`
- Key: `normalize_query(text)` — lowercase, collapsed whitespace; exact match only (no fuzzy dedup)
- Value: `list[float]` vector; LRU-capped at 512 entries per process
- No TTL (vectors are deterministic for the pinned model)
- Batch behavior: cache hits are merged with API calls for misses only; usage tokens recorded for misses only

**Retrieval result cache (built):**

- Hook: `_retrieve_with_cache` in `rag_core/rag/retrieval.py`
- Key: `(sha256(embedding_bytes), k)` — reranking threshold is **not** in the key (applied after retrieval)
- Value: ordered `(document_id, chunk_index)` tuples; full `RetrievedChunk` rows rehydrated from DB on hit
- TTL: 5 minutes (`RETRIEVAL_CACHE_TTL_SECONDS = 300`)
- Invalidation: clear retrieval cache on document delete and when status transitions to `ready` (corpus change). Query embedding cache is **not** cleared on corpus change.

**Explicit non-goals:**

- Redis or any external shared cache
- Fuzzy / semantic near-duplicate query matching
- Caching full LLM generation responses
- Content-hash skip at ingest time
- Cross-process cache sharing between `backend` and `chainlit_app`

---

## Logging & observability

**Decision:** **structlog** for structured logging in both `rag_core` and `backend`. JSON renderer when `app_env=production`; human-readable console renderer in development.

**Decision:** Backend request logging via `RequestLoggingMiddleware` assigns a per-request `trace_id` from `X-Trace-Id` / `X-Request-Id` headers (or a generated UUID) and binds it into structlog contextvars for downstream log lines.

**Decision:** Backend chat completion logs use a `log_event` helper (`backend/app/core/logging.py`) that JSON-sanitizes `Decimal` and `UUID` values before emission.

**Built now:**

- Structured JSON request/response logs in the backend middleware and chat endpoint, including trace id, path, latency, status, thread id, retrieval counts, tokens, and cost.
- Retrieval-quality logs emitted by the shared RAG generation path, including the selected chunk count and per-chunk similarity scores.
- Ingestion outcome logs for each PDF upload, including chunk count and failure reason so the upload UI and operators see the same signal.

**Production follow-up:**

- OpenTelemetry spans across backend → `rag_core` → Postgres/OpenAI calls. This is a valid production concern, but adds instrumentation and deployment overhead beyond the time budget of this pass.
- Centralized log aggregation and alerting on error rates or cost anomalies. These are deployment and operations concerns, not local application-code work.

**Reasoning:** The current pass focuses on low-effort instrumentation that is immediately useful for debugging retrieval quality and validating chat/ingest behavior in development. The more distributed and operational concerns are left for a later production rollout.
