# rag_core

Shared RAG library: embeddings, pgvector storage, retrieval, and generation.

## Environment

Copy `.env.example` to `.env` and set values as needed:

| Variable | Required | Description |
|----------|----------|-------------|
| `DATABASE_URL` | Yes | Postgres URL. Use `localhost:5432` on the host; Compose overrides this to `relational_db:5432` inside Docker. |
| `OPENAI_API_KEY` | For LLM/embedding calls | OpenAI API key |
| `RAG_CORE_GENERATION_MODEL` | No (default `gpt-4o-mini`) | Chat completion model (`RAG_CORE_MODEL` also accepted) |
| `RAG_CORE_RETRIEVAL_K` | No (default `10`) | Chunks retrieved per query |
| `RAG_CORE_INGESTION_BATCH_SIZE` | No (default `100`) | Ingestion batch size |
| `RAG_CORE_STEP_TIMEOUT_SECONDS` | No (default `120`) | Per-step OpenAI / agent timeout |

Embedding model and dimension are **not** env-configurable — they are pinned in `rag_core/embeddings.py`.

Start Postgres (pgvector) from the repo root:

```bash
docker compose -p assessment up -d relational_db
```

## Docker

`rag_core` is on the `tools` profile (not started with the main stack). Run commands from the **repo root**.

### Build

```bash
docker compose -p assessment build rag_core
```

### Initialize schema

```bash
docker compose -p assessment --profile tools run --rm rag_core
```

### Tests

```bash
docker compose -p assessment --profile tools run --rm rag_core pytest tests/ -v
```

### Interactive shell

```bash
docker compose -p assessment --profile tools run --rm rag_core bash
```
