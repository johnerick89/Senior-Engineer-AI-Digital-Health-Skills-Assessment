# Frontend (Next.js)

Pages Router UI for the RAG app: chat, PDF upload (list / status / delete), usage summary, and assignment brief. Talks to the FastAPI backend over `**/api/v1**` (`clientConfig.apiV1Url`).

Deeper stack notes: root `[README.md](../README.md)`,`[DECISIONS.md](../DECISIONS.md)`.

---

## Setup

```bash
cd frontend
npm install
```

Env (optional; Compose sets this for you):


| Variable                  | Default                 | Notes                                         |
| ------------------------- | ----------------------- | --------------------------------------------- |
| `NEXT_PUBLIC_BACKEND_URL` | `http://localhost:6100` | Backend origin; `/api/v1` is appended in code |


---

## Local

Prerequisites: Node 20+, backend reachable (Docker or host).

```bash
cd frontend
npm install
NEXT_PUBLIC_BACKEND_URL=http://localhost:6100 npm run dev
```

- App: [http://localhost:3000](http://localhost:3000)
- Routes: `/` chat · `/upload` · `/usage` · `/assignment`

Production-style local build:

```bash
npm run build && npm start
```

---

## Docker

From **repository root**:

```bash
docker compose -p assessment build frontend
docker compose -p assessment up -d frontend

docker compose -p assessment logs -f frontend
docker compose -p assessment stop frontend
```

Compose mounts `./frontend`, runs `npm run dev` with polling, and sets `NEXT_PUBLIC_BACKEND_URL=http://localhost:6100` (browser → host backend port).

Full stack:

```bash
docker compose -p assessment up -d --build
```

---

## Tests

```bash
cd frontend
npm test
```

Jest + Testing Library: `clientConfig`, UploadPanel (list/delete), UsagePanel.

---

## Layout

```
frontend/
  pages/           # index, upload, usage, assignment (_app)
  src/
    components/    # ChatPanel, UploadPanel, UsagePanel, shell
    config/        # client.ts (backendUrl, apiV1Url), navigation
    context/       # ChatSessionContext
  __tests__/       # under src/**/__tests__
  Dockerfile
```

