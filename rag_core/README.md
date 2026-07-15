# rag_core

Shared RAG library used in-process by `backend/` and `chainlit_app/`: PDF ingest,
embeddings, pgvector storage, retrieval, reranking, generation, and usage helpers.
No FastAPI or Chainlit imports.

## Layout

```
rag_core/
  core/       # config, logging, OpenAI client, token pricing
  db/         # SQLAlchemy session + Alembic helpers
  models/     # ORM models
  services/   # ORM-backed persistence
  rag/        # ingest → embed → retrieve → rerank → generate
  alembic/    # schema migrations
  tests/
```

## Environment

Copy `.env.example` to `.env`:

| Variable | Required | Notes |
|----------|----------|-------|
| `DATABASE_URL` | Yes | Host: `localhost:5432`; Compose overrides to `relational_db:5432` |
| `OPENAI_API_KEY` | Primary | Embeddings + chat |
| `OPENROUTER_API_KEY` | Fallback | Used when OpenAI fails/unset |
| `RAG_CORE_GENERATION_MODEL` | No | Default `gpt-4o-mini` |
| `RAG_CORE_RETRIEVAL_K` | No | Default `10` |
| `RAG_CORE_INGESTION_BATCH_SIZE` | No | Default `100` |

Embedding model/dimension and chunk size/overlap are pinned in code (not env).

```bash
# Postgres + pgvector from repo root
docker compose -p assessment up -d relational_db
```

## Install (local)

From repo root, shared venv:

```bash
source .venv/bin/activate
pip install -e ./rag_core
pip install -r rag_core/requirements.txt   # includes pytest + pytest-cov
```

## Migrate / ingest

```bash
# Alembic (creates documents, chunks, chat, usage tables + pgvector index)
python -m rag_core migrate
# or: alembic upgrade head   (from rag_core/ with alembic.ini)

python -m rag_core ingest ./sample.pdf
```

```python
from pathlib import Path
from rag_core.rag.ingestion import ingest_pdf

result = ingest_pdf(Path("guide.pdf"))
# result.document_id, result.chunk_count, result.filename
```

## Tests

```bash
cd rag_core

# Normal
pytest tests/ -v

# With coverage (from repository root so --cov=backend resolves)
cd ..
pip install pytest-cov
pytest rag_core/tests --cov=rag_core --cov=backend --cov-report=term-missing
```

`pytest-cov` is listed in `rag_core/requirements.txt` and `pip install -e "./rag_core[dev]"`.
Integration tests (`@pytest.mark.integration`) need Postgres; they skip if unreachable.

## Docker (`tools` profile)

From **repo root**:

```bash
docker compose -p assessment build rag_core

docker compose -p assessment --profile tools run --rm rag_core
# migrate (default CMD) or:
docker compose -p assessment --profile tools run --rm rag_core python -m rag_core migrate

docker compose -p assessment --profile tools run --rm \
  -v "$PWD/path/to:/data" \
  rag_core python -m rag_core ingest /data/guide.pdf

docker compose -p assessment --profile tools run --rm rag_core pytest tests/ -v
docker compose -p assessment --profile tools run --rm rag_core bash
```
