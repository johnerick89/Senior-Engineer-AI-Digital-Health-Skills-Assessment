import { useRef, useState } from "react";
import {
  File,
  Trash2,
  CheckCircle2,
  Loader2,
  AlertCircle,
  UploadCloud,
} from "lucide-react";
import { clientConfig } from "@/config/client";

type DocStatus = "ready" | "processing" | "failed";

type UploadedDoc = {
  id: string;
  name: string;
  sizeKb: number;
  status: DocStatus;
  uploadedAt: string;
  documentId?: string;
  error?: string;
};

type UploadStreamResult = {
  filename: string;
  document_id: string | null;
  status: "ready" | "failed";
  chunk_count: number;
  error: string | null;
};

const MAX_FILE_SIZE_BYTES = 20 * 1024 * 1024;

function isPdfFile(file: File): boolean {
  return (
    file.type === "application/pdf" ||
    file.name.toLowerCase().endsWith(".pdf")
  );
}

export default function UploadPanel() {
  const [docs, setDocs] = useState<UploadedDoc[]>([]);
  const [isDragging, setIsDragging] = useState(false);
  const [isUploading, setIsUploading] = useState(false);
  const [batchError, setBatchError] = useState<string | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  async function handleFiles(fileList: FileList | null) {
    if (!fileList || fileList.length === 0 || isUploading) return;

    const files = Array.from(fileList);
    const invalid = files.find((file) => !isPdfFile(file));
    if (invalid) {
      setBatchError(`Only PDF files are supported. Invalid: ${invalid.name}`);
      return;
    }
    const oversized = files.find((file) => file.size > MAX_FILE_SIZE_BYTES);
    if (oversized) {
      setBatchError(`File exceeds 20MB limit: ${oversized.name}`);
      return;
    }

    setBatchError(null);
    const batchId = Date.now();
    // Track queue order so duplicate filenames in one batch still map correctly.
    const newDocs: UploadedDoc[] = files.map((file, index) => ({
      id: `upload-${batchId}-${index}`,
      name: file.name,
      sizeKb: Math.round(file.size / 1024),
      status: "processing",
      uploadedAt: "just now",
    }));

    setDocs((prev) => [...newDocs, ...prev]);
    setIsUploading(true);

    const formData = new FormData();
    for (const file of files) {
      formData.append("files", file);
    }

    // Pending new-doc ids in order — stream results arrive in the same order.
    const pendingIds = newDocs.map((doc) => doc.id);
    let resultIndex = 0;

    try {
      const response = await fetch(`${clientConfig.backendUrl}/upload`, {
        method: "POST",
        body: formData,
      });

      if (!response.ok) {
        let detail = `Upload failed (${response.status})`;
        try {
          const payload = await response.json();
          if (typeof payload.detail === "string") {
            detail = payload.detail;
          }
        } catch {
          // ignore non-JSON error bodies
        }
        setDocs((prev) =>
          prev.map((doc) =>
            pendingIds.includes(doc.id)
              ? { ...doc, status: "failed", error: detail }
              : doc,
          ),
        );
        setBatchError(detail);
        return;
      }

      const reader = response.body?.getReader();
      if (!reader) {
        throw new Error("No response stream available");
      }

      const decoder = new TextDecoder();
      let buffer = "";

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split("\n");
        buffer = lines.pop() ?? "";

        for (const line of lines) {
          const trimmed = line.trim();
          if (!trimmed) continue;

          const result = JSON.parse(trimmed) as UploadStreamResult;
          const targetId = pendingIds[resultIndex];
          resultIndex += 1;

          if (!targetId) continue;

          setDocs((prev) =>
            prev.map((doc) =>
              doc.id === targetId
                ? {
                    ...doc,
                    name: result.filename || doc.name,
                    status: result.status,
                    documentId: result.document_id ?? undefined,
                    error: result.error ?? undefined,
                  }
                : doc,
            ),
          );
        }
      }

      if (buffer.trim()) {
        const result = JSON.parse(buffer.trim()) as UploadStreamResult;
        const targetId = pendingIds[resultIndex];
        if (targetId) {
          setDocs((prev) =>
            prev.map((doc) =>
              doc.id === targetId
                ? {
                    ...doc,
                    name: result.filename || doc.name,
                    status: result.status,
                    documentId: result.document_id ?? undefined,
                    error: result.error ?? undefined,
                  }
                : doc,
            ),
          );
        }
      }
    } catch (error) {
      const message =
        error instanceof Error ? error.message : "Upload request failed";
      setBatchError(message);
      setDocs((prev) =>
        prev.map((doc) =>
          pendingIds.includes(doc.id) && doc.status === "processing"
            ? { ...doc, status: "failed", error: message }
            : doc,
        ),
      );
    } finally {
      setIsUploading(false);
      if (fileInputRef.current) {
        fileInputRef.current.value = "";
      }
    }
  }

  function removeDoc(id: string) {
    setDocs((prev) => prev.filter((doc) => doc.id !== id));
  }

  return (
    <div className="mx-auto w-full max-w-2xl overflow-y-auto p-4 md:p-8">
      <h1 className="mb-1 text-lg font-medium">Upload documents</h1>
      <p className="mb-6 text-sm text-slate-500">
        PDFs added here are chunked, embedded, and stored for retrieval in chat.
      </p>

      <div
        onDragOver={(event) => {
          event.preventDefault();
          if (!isUploading) setIsDragging(true);
        }}
        onDragLeave={() => setIsDragging(false)}
        onDrop={(event) => {
          event.preventDefault();
          setIsDragging(false);
          if (!isUploading) handleFiles(event.dataTransfer.files);
        }}
        onClick={() => {
          if (!isUploading) fileInputRef.current?.click();
        }}
        className={`mb-8 flex cursor-pointer flex-col items-center justify-center rounded-xl border-2 border-dashed p-10 text-center transition-colors ${
          isUploading ? "pointer-events-none opacity-60" : ""
        } ${
          isDragging
            ? "border-teal-500 bg-teal-50"
            : "border-slate-300 bg-white hover:border-slate-400"
        }`}
      >
        <UploadCloud className="mb-3 h-8 w-8 text-teal-600" />
        <p className="text-sm font-medium text-slate-700">
          {isUploading
            ? "Uploading and ingesting…"
            : "Drag and drop PDFs here, or click to browse"}
        </p>
        <p className="mt-1 text-xs text-slate-400">
          Supports multiple files, up to 20MB each
        </p>
        <input
          ref={fileInputRef}
          type="file"
          accept="application/pdf"
          multiple
          className="hidden"
          disabled={isUploading}
          onChange={(event) => handleFiles(event.target.files)}
        />
      </div>

      {batchError && (
        <p className="mb-4 rounded-lg border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700">
          {batchError}
        </p>
      )}

      <h2 className="mb-3 text-sm font-medium text-slate-700">
        Ingested documents
      </h2>
      <div className="flex flex-col gap-2">
        {docs.map((doc) => (
          <div
            key={doc.id}
            className="flex items-center justify-between rounded-lg border border-slate-200 bg-white px-4 py-3"
          >
            <div className="flex min-w-0 items-center gap-3">
              <File className="h-4 w-4 shrink-0 text-slate-400" />
              <div className="min-w-0">
                <p className="truncate text-sm text-slate-800">{doc.name}</p>
                <p className="text-xs text-slate-400">
                  {doc.sizeKb.toLocaleString()} KB · {doc.uploadedAt}
                  {doc.error ? ` · ${doc.error}` : ""}
                </p>
              </div>
            </div>
            <div className="flex shrink-0 items-center gap-3">
              <StatusBadge status={doc.status} />
              <button
                onClick={() => removeDoc(doc.id)}
                aria-label={`Remove ${doc.name}`}
                className="rounded-md p-1.5 text-slate-400 hover:bg-slate-100 hover:text-red-600"
              >
                <Trash2 className="h-4 w-4" />
              </button>
            </div>
          </div>
        ))}
        {docs.length === 0 && (
          <p className="py-6 text-center text-sm text-slate-400">
            No documents uploaded yet.
          </p>
        )}
      </div>
    </div>
  );
}

function StatusBadge({ status }: { status: DocStatus }) {
  if (status === "ready") {
    return (
      <span className="flex items-center gap-1 rounded-md bg-emerald-50 px-2 py-1 text-xs font-medium text-emerald-700">
        <CheckCircle2 className="h-3 w-3" /> Ready
      </span>
    );
  }

  if (status === "processing") {
    return (
      <span className="flex items-center gap-1 rounded-md bg-amber-50 px-2 py-1 text-xs font-medium text-amber-700">
        <Loader2 className="h-3 w-3 animate-spin" /> Processing
      </span>
    );
  }

  return (
    <span className="flex items-center gap-1 rounded-md bg-red-50 px-2 py-1 text-xs font-medium text-red-700">
      <AlertCircle className="h-3 w-3" /> Failed
    </span>
  );
}
