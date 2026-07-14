import { useRef, useState } from "react";
import {
  File,
  Trash2,
  CheckCircle2,
  Loader2,
  AlertCircle,
  UploadCloud,
} from "lucide-react";

type DocStatus = "ready" | "processing" | "failed";

type UploadedDoc = {
  id: string;
  name: string;
  sizeKb: number;
  status: DocStatus;
  uploadedAt: string;
};

const DUMMY_DOCS: UploadedDoc[] = [
  {
    id: "d1",
    name: "training_manual.pdf",
    sizeKb: 2380,
    status: "ready",
    uploadedAt: "2 days ago",
  },
  {
    id: "d2",
    name: "field_ops_protocol.pdf",
    sizeKb: 940,
    status: "ready",
    uploadedAt: "2 days ago",
  },
  {
    id: "d3",
    name: "supply_chain_sop.pdf",
    sizeKb: 1210,
    status: "processing",
    uploadedAt: "just now",
  },
  {
    id: "d4",
    name: "district_report_q2.pdf",
    sizeKb: 3040,
    status: "failed",
    uploadedAt: "10 minutes ago",
  },
];

export default function UploadPanel() {
  const [docs, setDocs] = useState<UploadedDoc[]>(DUMMY_DOCS);
  const [isDragging, setIsDragging] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);

  function handleFiles(fileList: FileList | null) {
    if (!fileList || fileList.length === 0) return;

    const newDocs: UploadedDoc[] = Array.from(fileList).map((file, index) => ({
      id: `new-${Date.now()}-${index}`,
      name: file.name,
      sizeKb: Math.round(file.size / 1024),
      status: "processing",
      uploadedAt: "just now",
    }));

    setDocs((prev) => [...newDocs, ...prev]);

    setTimeout(() => {
      setDocs((prev) =>
        prev.map((doc) =>
          newDocs.some((newDoc) => newDoc.id === doc.id)
            ? { ...doc, status: "ready" }
            : doc,
        ),
      );
    }, 1800);
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
          setIsDragging(true);
        }}
        onDragLeave={() => setIsDragging(false)}
        onDrop={(event) => {
          event.preventDefault();
          setIsDragging(false);
          handleFiles(event.dataTransfer.files);
        }}
        onClick={() => fileInputRef.current?.click()}
        className={`mb-8 flex cursor-pointer flex-col items-center justify-center rounded-xl border-2 border-dashed p-10 text-center transition-colors ${
          isDragging
            ? "border-teal-500 bg-teal-50"
            : "border-slate-300 bg-white hover:border-slate-400"
        }`}
      >
        <UploadCloud className="mb-3 h-8 w-8 text-teal-600" />
        <p className="text-sm font-medium text-slate-700">
          Drag and drop PDFs here, or click to browse
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
          onChange={(event) => handleFiles(event.target.files)}
        />
      </div>

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
