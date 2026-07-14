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

COPY requirements.txt pyproject.toml ./
COPY rag_core ./rag_core
COPY tests ./tests

RUN pip install --no-cache-dir -r requirements.txt \
    && pip install --no-cache-dir -e .

# Initialize pgvector schema by default; override command for tests or a shell.
# Examples:
#   docker compose --profile tools run --rm rag_core pytest tests/ -v
#   docker compose --profile tools run --rm rag_core bash
CMD ["python", "-m", "rag_core"]
