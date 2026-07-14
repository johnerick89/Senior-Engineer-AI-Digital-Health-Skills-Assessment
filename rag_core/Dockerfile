FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PYTHONDONTWRITEBYTECODE=1

WORKDIR /rag_core

RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    libpq-dev \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt pyproject.toml alembic.ini ./
COPY rag_core ./rag_core
COPY alembic ./alembic
COPY tests ./tests

RUN pip install --no-cache-dir -r requirements.txt \
    && pip install --no-cache-dir -e .

# Migrate pgvector schema by default; override for ingest, tests, or a shell.
# Examples:
#   docker compose --profile tools run --rm rag_core python -m rag_core ingest /data/doc.pdf
#   docker compose --profile tools run --rm rag_core pytest tests/ -v
#   docker compose --profile tools run --rm rag_core bash
CMD ["python", "-m", "rag_core", "migrate"]
