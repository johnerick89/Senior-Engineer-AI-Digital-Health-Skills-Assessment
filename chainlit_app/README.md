# Chainlit app

Independent chat surface on port **8000**. Imports `rag_core` **in-process**
(same DB as the FastAPI backend). Does **not** call `backend` over HTTP.

Demo silent login (`john.doe@example.com` / `1234`) exists only so Chainlit’s
thread sidebar can load; persisted user id stays `anonymous` (shared threads
with Next.js). PDF upload and Usage stay on the Next.js app.

See root [`README.md`](../README.md) and [`DECISIONS.md`](../DECISIONS.md).

---

## Setup

```bash
# From repo root
source .venv/bin/activate
pip install -e ./rag_core
pip install -r chainlit_app/requirements.txt
cp rag_core/.env.example rag_core/.env   # keys + DATABASE_URL
```

Set `CHAINLIT_AUTH_SECRET` when running outside Compose (Compose provides a
dev default).

---

## Local

Postgres must be up (`docker compose -p assessment up -d relational_db`).

```bash
cd chainlit_app
export DATABASE_URL=postgresql://postgres:postgres@localhost:5432/postgres
export CHAINLIT_AUTH_SECRET=lmh-chainlit-dev-secret-change-me
export PYTHONPATH=../rag_core:.

python -m chainlit run main.py --host 0.0.0.0 --port 8000 -w
```

Open http://localhost:8000.

---

## Docker

From **repository root**:

```bash
docker compose -p assessment build chainlit
docker compose -p assessment up -d chainlit

docker compose -p assessment logs -f chainlit
docker compose -p assessment stop chainlit
```

Mounts `chainlit_app` + `rag_core`, uses `rag_core/.env`, `-w` watch mode.

---

## Tests

```bash
cd chainlit_app
PYTHONPATH=../rag_core:. pytest tests/ -v
```

---

## Layout

```
chainlit_app/
  main.py
  app/           # chat, turn helpers, data_layer
  public/        # silent_login.js
  tests/
  Dockerfile
  requirements.txt
```
