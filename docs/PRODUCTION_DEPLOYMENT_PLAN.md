# Production Deployment Plan

This document outlines how the application would be deployed to production. It covers cloud provider choice, deployment architecture, CI/CD strategy, and the main infrastructure considerations for operating and scaling the system.

Note: CI already runs in-repo, but the full production infrastructure described here is a deployment plan for the assessment rather than a live environment that has been applied against a cloud account.

---

## Cloud Provider Choice

**Recommendation:** GCP, using **Cloud Run** for the application services, **Cloud SQL for PostgreSQL** for the database, **Artifact Registry** for images, and **Secret Manager** for runtime secrets.

This fits the current codebase well because:

- all application surfaces already ship as containers (`frontend`, `backend`, `chainlit_app`)
- traffic is likely to be low-to-moderate and bursty, which fits Cloud Run's scale-to-zero model
- Cloud Run gives managed HTTPS, revisions, autoscaling, and simple rollback without introducing Kubernetes operational overhead
- Cloud SQL is the natural managed destination for the existing Postgres + pgvector setup

**Why not GKE initially:** the operational complexity is not justified for an assessment-sized workload. The services are already cleanly containerized, so Cloud Run gives a faster path to production. Kubernetes becomes relevant later only if traffic, networking, or scaling constraints genuinely require it.

---

## Target Architecture

The system deploys as three independent services plus a managed database:

```text
Cloud Run: frontend        -> Next.js UI (public)
Cloud Run: backend         -> FastAPI API (public)
Cloud Run: chainlit_app    -> Chainlit chat surface (public)

Cloud SQL: PostgreSQL + pgvector
Secret Manager
Artifact Registry
GitHub Actions
```

**Service boundaries:**

- `frontend` remains the primary user-facing web app
- `backend` serves `/api/v1/*` over HTTP for the frontend
- `chainlit_app` remains a real second chat surface, not a debug tool
- `rag_core` is **not** deployed as a standalone service; it remains an in-process shared Python package imported by both `backend` and `chainlit_app`

---

## Container and Package Strategy

Each deployable surface is built from its existing Dockerfile:

- `backend/Dockerfile`
- `frontend/Dockerfile`
- `chainlit_app/Dockerfile`

For production, `rag_core` should be versioned independently and consumed as a package dependency rather than copied ad hoc into consumer images. The cleanest path is:

1. Build a versioned `rag_core` package from `rag_core/pyproject.toml`
2. Publish it to a private package registry
3. Pin that version from `backend` and `chainlit_app` image builds

This makes shared RAG logic explicitly releasable and avoids ambiguity about which application image contains which `rag_core` revision.

---

## Database and Migrations

**Database:** Cloud SQL for PostgreSQL with `pgvector` enabled.

The current local system already depends on PostgreSQL + pgvector, so production should keep the same shape instead of introducing a different vector store.

**Migration strategy:**

- Alembic remains the source of truth for schema changes
- migrations should run as a dedicated deploy step or one-off job
- they should **not** run opportunistically from every application instance at startup in production

That avoids race conditions when multiple backend revisions start at once.

---

## Networking and Secrets

**Secrets**

Runtime secrets should be stored in **Secret Manager**, not committed in env files:

- `OPENAI_API_KEY`
- `OPENROUTER_API_KEY`
- `DATABASE_URL`
- service-specific auth secrets such as `CHAINLIT_AUTH_SECRET`

**Ingress**

- `frontend` should be public
- `chainlit_app` should be public because it is a legitimate independent chat surface in this project
- `backend` can be public for simplicity, but should remain CORS-restricted to the deployed frontend and Chainlit origins

If this system moved beyond demo/assessment usage, the next hardening step would be private service-to-service networking and identity-aware access instead of broad public reachability.

---

## CI/CD Strategy

**Platform:** GitHub Actions

GitHub Actions is the best fit because the repository already lives on GitHub and the required pipeline is straightforward: test, build, publish, deploy.

### Suggested pipeline stages

#### 1. Validate on pull requests

- `rag_core`: `pytest tests/ -v`
- `backend`: `PYTHONPATH=../rag_core:. pytest tests/ -v`
- `chainlit_app`: `PYTHONPATH=../rag_core:. pytest tests/ -v`
- `frontend`: `npm test`

Optional additions:

- frontend lint
- Python formatting/lint checks
- Terraform validation if infrastructure code is committed in this repo

#### 2. Build on merge to `main`

- build Docker images for `backend`, `frontend`, and `chainlit_app`
- publish images to Artifact Registry
- tag images with immutable references such as the Git SHA
- publish the `rag_core` package artifact

**Important:** deploy by immutable image tag, not `latest`, so every running revision maps back to a specific commit.

#### 3. Deploy in ordered stages

1. Apply infrastructure changes with Terraform
2. Run Alembic migrations
3. Deploy updated images to Cloud Run
4. Smoke test service health endpoints

If migrations fail or smoke tests fail, the workflow should stop before traffic is promoted further.

---

## Terraform Scope

Terraform should manage:

- Cloud Run services
- Cloud SQL instance
- Secret Manager secrets and IAM bindings
- Artifact Registry repositories
- service accounts and least-privilege IAM

Terraform state should be stored remotely, not in local `terraform.tfstate` files checked into source control.

A production-grade backend would use a remote state backend such as GCS with locking and restricted access.

---

## Environments

At minimum:

- `staging`
- `production`

Recommended behavior:

- pull requests run validation only
- merges to `main` deploy automatically to `staging`
- `production` requires a manual approval gate in GitHub Actions

This gives a real checkpoint before promoting changes to user-facing services.

---

## Rollback Strategy

Cloud Run revisions make rollback relatively cheap:

- keep prior known-good revisions available
- if a deployment fails smoke tests or regresses behavior, shift traffic back to the prior revision

Database rollbacks are a separate concern. For destructive schema changes, the safe approach is backward-compatible migrations first, application rollout second, cleanup migration later.

---

## Scaling Considerations

### Application services

Cloud Run should start with bounded autoscaling:

- configure sensible concurrency
- cap `max_instances`
- tune memory/CPU per service independently

This keeps cost and provider usage predictable during early rollout.

### Database

The most likely early bottleneck is the database, especially retrieval queries over pgvector as the document corpus grows.

Likely scaling steps before any major architecture change:

- increase Cloud SQL instance size
- review pgvector index/query performance
- monitor retrieval latency separately from generation latency

### Vector store consideration for production

This assessment requires PostgreSQL + pgvector, and that remains the right choice for the current application shape even beyond the assignment itself. At this scale, pgvector keeps relational document data, chunk text, and
embeddings inside one transactional system, which avoids the dual-write failure mode that appears when Postgres and a separate vector database have to stay in sync across ingest and delete operations. It also keeps the operational surface smaller: one system to secure, back up, monitor, and pay for, with no extra network hop on every retrieval call.

For the expected corpus size here, pgvector with an HNSW index is a pragmatic production choice. A dedicated vector database such as Pinecone would become more attractive only if retrieval scale materially outgrew the transactional workload, or if the corpus grew to the point that vector search needed to scale independently of the primary PostgreSQL instance. That is the point where the added complexity of a second system starts to pay for itself.

If the application reached that threshold, the clean migration path would be to keep PostgreSQL as the source of truth for documents and chunk text, and add a dedicated vector database as a read-path optimization. That would introduce a dual-write consistency trade-off, so it should be adopted only when scale demands it rather than preemptively.

### Shared-state caveat

Two current optimizations are intentionally process-local:

- query/retrieval caching
- `slowapi` in-memory rate limiting

If the backend scales to multiple Cloud Run instances, both should move to a shared backend such as Redis/Memorystore to avoid per-instance inconsistency.

---

## Monitoring and Observability

The current codebase already emits useful structured logs for:

- request tracing
- retrieval quality
- token usage
- estimated cost
- ingestion success/failure

In production on GCP:

- Cloud Run captures stdout/stderr into Cloud Logging
- baseline service metrics come from Cloud Run and Cloud Monitoring
- health checks should target `/api/v1/health` on the backend

Recommended next additions after initial deployment:

- alerting on error rate and latency
- alerting on unusual token/cost spikes
- OpenTelemetry tracing across backend -> `rag_core` -> database/provider calls

These are useful, but not required to achieve a credible first production deployment.

---

## Practical First Production Rollout

1. Provision Cloud SQL, Artifact Registry, Secret Manager, service accounts, and Cloud Run services with Terraform
2. Publish versioned `rag_core`
3. Build and push immutable image tags for `backend`, `frontend`, and `chainlit_app`
4. Run Alembic migrations once
5. Deploy backend first, then frontend and Chainlit
6. Update backend CORS to the final deployed frontend/Chainlit URLs if needed
7. Smoke test:
   - backend `/api/v1/health`
   - frontend loads and can call backend
   - Chainlit loads and can answer from the same corpus

This keeps the rollout close to the architecture already proven locally while avoiding premature complexity.
