# Assumptions

Defaults and scope choices where the assignment brief was silent or
underspecified. Architectural trade-offs with full reasoning live in
`DECISIONS.md`.

---

## Starter / bootstrap

### Chainlit Docker install

Building `chainlit_app` stalled resolving dependencies. To get containers running I assumed these starter fixes were necessary:

- Pinned `opentelemetry-instrumentation-groq==0.58.1` in `chainlit_app/requirements.txt` — `chainlit==2.5.5` (via literalai) pulls an
  OpenTelemetry graph that otherwise resolves poorly.
- Updated `chainlit_app/Dockerfile` install step for a longer timeout and the legacy pip resolver.

### Route remapping

- Backend root `GET /` stays a health JSON endpoint; assignment HTML is at
  `GET /api/v1/assignment` (also mirrored in the Next.js `/assignment` page).
- Application APIs are under **`/api/v1`** with plural resources (e.g.
  `POST /api/v1/chats`, `POST/GET/DELETE /api/v1/documents`). Pre-version paths
  (`/chat`, `/upload`, …) were removed in one cutover — no aliases.
- Frontend root `/` is the chat surface; the assignment brief page is `/assignment`.

---

## Scope intentionally deferred

- **No authentication / multi-tenant users.** The Next.js app has no login. Chainlit only has a **demo silent login** (`john.doe@example.com` / `1234`, auto-submitted via `public/silent_login.js`) because Chainlit’s history sidebar requires a user; the persisted user id stays `anonymous` and threads are still shared globally. A production digital-health system would need real access control before use.
- **No mid-stream token/cost updates.** Usage is finalized after the stream ends (footer refresh + ledger write), not live while tokens arrive.
- **No historical repricing.** Changing list prices in `token_pricing.py` does not rewrite old `chat_messages` / `usage_events` rows.
- **No per-message cost chips in the chat UI (v1).** Thread totals live in a footer; app-level rollups live on `/usage`.
- **Chainlit is not linked from the Next.js nav (current).** Nav is Chat /Upload / Usage / Assignment. Chainlit remains an independent surface on port `8000`. Deep-linking from nav (and surfacing its URL via `frontend/src/config/`) is optional later.
- **No single-document detail API or reprocess.** `GET /documents/{id}` and re-ingest were scoped out; list + delete cover the upload-page needs.
- **Deleting a document while `status=processing` is allowed.** Simpler than blocking; an in-flight ingest writing after delete should fail harmlessly against a missing parent.

---

## Runtime / ops defaults

- **Generation model default:** `gpt-4o-mini` (tunable via env) — good enough for grounded Q&A; much cheaper than `gpt-4o`.
- **OpenAI primary, OpenRouter fallback:** when OpenAI is missing or fails with quota/auth-style errors, calls use `OPENROUTER_API_KEY` with `openai/<model>` ids. Dual-key is assumed acceptable for local demos when OpenAI quota is exhausted.
- **DB driver:** sync `psycopg` (not `asyncpg`). FastAPI routes wrap blocking work in `asyncio.to_thread` where needed. Sync is simpler and consistent for one shared engine across `backend` + `rag_core`.
- **Upload limit:** 20MB per PDF, PDF-only — aligned with frontend copy; not specified in the brief.
- **Chunking defaults:** character-based `CHUNK_SIZE=800`, `CHUNK_OVERLAP=100` in `rag_core/rag/chunking.py` (pinned, not env). Assumed sufficient for sample docs / the 72-hour window.
- **Retrieval k default:** `10` candidates before threshold + MMR rerank(env-tunable).
- **Rerank approach:** similarity floor + MMR with `numpy`, not a cross-encoder (`torch` is too heavy for two Docker images under this timebox). Upgrade path: cross-encoder later.

---

## Product / UX defaults

- **Suggested topics on empty new chats:** LLM-generated starter questions from document snippets (capped at 5), with usage recorded as `usage_events` (`kind=suggestion`). Useful empty-state; not required by the brief.
- **Assistant answers rendered as Markdown** in the Next.js chat (GFM), while the HTTP stream itself stays plain text.
- **Chat stream transport:** plain `text/plain` stream + headers `X-Chat-Id` /`X-Chat-Title`, not SSE/JSON event stream — keeps markdown streaming simple.
- **Upload response transport:** NDJSON (`application/x-ndjson`), one result per file as ingest finishes, so the UI can show per-document processing / ready / failed status.
