# Build from repository root:
#   docker compose build chainlit
#   (context: ., dockerfile: chainlit_app/Dockerfile)

FROM python:3.12-slim-bullseye AS build

ARG HOME_DIR=/chainlit_app

RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    libpq-dev \
    python3-dev \
    curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR ${HOME_DIR}

COPY chainlit_app/requirements.txt /requirements.txt
RUN --mount=type=cache,target=/root/.cache/pip pip install --no-cache-dir \
    --timeout=300 \
    --default-timeout=300 \
    --use-deprecated=legacy-resolver \
    -r /requirements.txt

COPY rag_core/requirements.txt /rag_core_requirements.txt
COPY rag_core/pyproject.toml /rag_core/pyproject.toml
COPY rag_core/rag_core /rag_core/rag_core
COPY rag_core/alembic /rag_core/alembic
COPY rag_core/alembic.ini /rag_core/alembic.ini
RUN --mount=type=cache,target=/root/.cache/pip pip install --no-cache-dir -e /rag_core

COPY chainlit_app/ ${HOME_DIR}/

FROM python:3.12-slim-bullseye

ARG HOME_DIR=/chainlit_app

RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq5 \
    curl \
    && rm -rf /var/lib/apt/lists/*

COPY --from=build /usr/local/lib/python3.12/site-packages /usr/local/lib/python3.12/site-packages
COPY --from=build /usr/local/bin /usr/local/bin
COPY --from=build ${HOME_DIR} ${HOME_DIR}
COPY --from=build /rag_core /rag_core

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONPATH="${PYTHONPATH}:${HOME_DIR}:/rag_core"

WORKDIR ${HOME_DIR}
EXPOSE 8000

CMD ["python", "-m", "chainlit", "run", "main.py", "--host", "0.0.0.0", "--port", "8000"]
