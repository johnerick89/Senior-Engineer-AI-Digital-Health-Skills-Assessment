GET /documents — do this one. Cheap (single SELECT against your documents table, which you already have since ingestion writes to it), and it's the missing piece that makes your upload page actually functional rather than a one-way upload form.
DELETE /documents/{id} — worth adding if the first one goes quickly. Real value: lets you demo cleanup during review, and "manage what's grounding your RAG system" is a reasonable expectation for anything calling itself production-quality. If it turns out to need cascading deletes across document_chunks and you're not confident that's clean, it's fine to punt — note it in DECISIONS.md as scoped out rather than silently missing.
Skip: GET /documents/{id} (single-doc detail) — no UI need for it right now, and re-ingestion/reprocessing — genuinely out of scope for the time you have left.
Rolling this into the naming cleanup from earlier
Since you're touching this endpoint anyway, this is the natural moment to also do the rename we discussed — /upload → POST /documents, so the collection has one consistent resource name across create/list/delete:
POST /documents → upload/ingest (renamed from /upload)
GET /documents → list ingested documents + status (new)
DELETE /documents/{id} → remove a document (new, if time allows)
If deleting a document leaves its chunks/embeddings behind in pgvector, you get orphaned vectors: they still surface in retrieval, still get cited in generated answers, but the "source document" they point to no longer exists on the upload page. That's a worse bug than just leaving the document — a citation pointing at a deleted file actively undermines the "grounded in uploaded documents" claim (Requirement 1). Delete must always cascade to chunks.
Two ways to enforce it — pick one, don't rely on discipline alone:

DB-level ON DELETE CASCADE on the FK from document_chunks.document_id → documents.id. Preferred — it's enforced no matter what code path deletes the row, including a manual DELETE FROM documents someone runs directly in psql during debugging.
App-level transaction — delete chunks explicitly, then the document, wrapped in one transaction so a failure partway doesn't leave things half-deleted. Only needed if you have a reason to avoid DB-level cascade (you don't, here).

Go with (1). If your document_chunks migration didn't originally declare the FK with ondelete="CASCADE", that's a one-line migration to add now — cheap, and worth it over silently relying on app code to remember to clean up two tables in the right order.

Design: Document Management Endpoints
Change 1 — rename POST /upload → POST /documents
Same behavior (NDJSON stream, per-file ingestion status), just renamed to match resource-collection naming, consistent with /chats.
Change 2 — add GET /documents
GET /documents

Response 200:
[
{
"id": "uuid",
"filename": "training_manual.pdf",
"status": "ready" | "processing" | "failed",
"size_kb": 2380,
"chunk_count": 47,
"uploaded_at": "2026-07-13T10:22:00Z",
"error_message": null
}
]

Ordered by uploaded_at desc (matches your upload page's expected UX — newest first).
chunk_count is a cheap join/count, useful for a reviewer to visually confirm ingestion actually happened, not just that a row exists.
error_message populated only when status == "failed" — surfaces why in the UI rather than a bare failure badge.

Change 3 — add DELETE /documents/{id}
DELETE /documents/{id}

Response 204: (no body)
Response 404: {"detail": "Document not found"}

Deletes the documents row; document_chunks rows cascade via FK (see above).
No confirmation step needed server-side — that's a frontend concern (confirm dialog before calling this).
If status == "processing" when delete is called: allow it. Simpler than blocking, and an in-flight ingestion failing to write against a deleted parent row should just error harmlessly (or you can have ingestion check the document still exists before writing each chunk, if you want to be defensive — optional, skip if short on time).

Schema note
Only a migration is needed if the FK isn't already ON DELETE CASCADE:
sqlALTER TABLE document_chunks
DROP CONSTRAINT document_chunks_document_id_fkey,
ADD CONSTRAINT document_chunks_document_id_fkey
FOREIGN KEY (document_id) REFERENCES documents(id) ON DELETE CASCADE;
Frontend wiring

UploadPanel's dummy docs state → replace with GET /documents on mount.
onRemove(id) → call DELETE /documents/{id}, then refetch or optimistically remove from state.
Upload flow (POST /documents) unchanged aside from the URL rename.

Testing to add

GET /documents returns empty list before any upload, populated list after.
DELETE /documents/{id} removes the document and its chunks (assert chunk count in DB is 0 after) — this is the one test that actually proves the cascade works, worth prioritizing over the simpler "row is gone" check.
DELETE on a nonexistent id returns 404, not 500.
