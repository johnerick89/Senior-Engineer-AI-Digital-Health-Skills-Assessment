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
| `RAG_CORE_INGESTION_BATCH_SIZE` | No (default `100`) | Embedding / ingestion batch size |
| `RAG_CORE_STEP_TIMEOUT_SECONDS` | No (default `120`) | Per-step OpenAI / agent timeout |

Embedding model/dimension and chunk size/overlap are **not** env-configurable — they are pinned in `rag_core/embeddings.py` and `rag_core/chunking.py`.

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

### Migrate schema (Alembic)

```bash
docker compose -p assessment --profile tools run --rm rag_core python -m rag_core migrate
# or (default command):
docker compose -p assessment --profile tools run --rm rag_core
```

### Ingest a PDF

```bash
docker compose -p assessment --profile tools run --rm \
  -v "$PWD/path/to:/data" \
  rag_core python -m rag_core ingest /data/guide.pdf
```

### Tests

```bash
docker compose -p assessment --profile tools run --rm rag_core pytest tests/ -v
```

### Interactive shell

```bash
docker compose -p assessment --profile tools run --rm rag_core bash
```

## Local (optional)

```bash
cd rag_core
pip install -e .
alembic upgrade head
python -m rag_core ingest ./sample.pdf
pytest tests/ -v
```
