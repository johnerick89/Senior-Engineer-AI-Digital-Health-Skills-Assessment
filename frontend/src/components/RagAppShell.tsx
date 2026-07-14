"use client";

import { useRef, useState } from "react";
import { usePathname, useRouter } from "next/navigation";
import {
  Plus,
  MessageCircle,
  Upload as UploadIcon,
  FileText,
  Menu,
  X,
  File,
  Trash2,
  CheckCircle2,
  Loader2,
  AlertCircle,
  UploadCloud,
} from "lucide-react";
import ChatPanel from "./ChatPanel";
import AssignmentPanel from "./AssignmentPanel";

type Tab = "chat" | "upload" | "assignment";

type DocStatus = "ready" | "processing" | "failed";

type UploadedDoc = {
  id: string;
  name: string;
  sizeKb: number;
  status: DocStatus;
  uploadedAt: string;
};

const DUMMY_THREADS = [
  { id: "t1", title: "Community health worker training docs" },
  { id: "t2", title: "Malaria protocol Q&A" },
  { id: "t3", title: "Supply chain SOPs" },
];

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

function tabFromPath(pathname: string): Tab {
  if (pathname === "/upload") return "upload";
  if (pathname === "/assignment") return "assignment";
  return "chat";
}

export default function RagAppShell() {
  const pathname = usePathname();
  const router = useRouter();
  const activeTab = tabFromPath(pathname);
  const [activeThreadId, setActiveThreadId] = useState("");
  const [chatSessionKey, setChatSessionKey] = useState(0);
  const [docs, setDocs] = useState<UploadedDoc[]>(DUMMY_DOCS);
  const [isDragging, setIsDragging] = useState(false);
  const [sidebarOpen, setSidebarOpen] = useState(true);

  function navigate(tab: Tab) {
    const href =
      tab === "upload" ? "/upload" : tab === "assignment" ? "/assignment" : "/";
    router.push(href);
    setSidebarOpen(false);
  }

  function selectThread(id: string) {
    setActiveThreadId(id);
    router.push("/");
    setSidebarOpen(false);
  }

  function startNewChat() {
    setActiveThreadId("");
    setChatSessionKey((k) => k + 1);
    router.push("/");
    setSidebarOpen(false);
  }

  function handleFiles(fileList: FileList | null) {
    if (!fileList || fileList.length === 0) return;
    const newDocs: UploadedDoc[] = Array.from(fileList).map((f, i) => ({
      id: `new-${Date.now()}-${i}`,
      name: f.name,
      sizeKb: Math.round(f.size / 1024),
      status: "processing",
      uploadedAt: "just now",
    }));
    setDocs((prev) => [...newDocs, ...prev]);

    setTimeout(() => {
      setDocs((prev) =>
        prev.map((d) =>
          newDocs.some((n) => n.id === d.id) ? { ...d, status: "ready" } : d,
        ),
      );
    }, 1800);
  }

  function removeDoc(id: string) {
    setDocs((prev) => prev.filter((d) => d.id !== id));
  }

  return (
    <div className="flex h-screen w-full bg-slate-50 text-slate-900">
      <div className="fixed inset-x-0 top-0 z-30 flex h-14 items-center justify-between border-b border-slate-200 bg-white px-4 md:hidden">
        <button
          onClick={() => setSidebarOpen(true)}
          aria-label="Open menu"
          className="rounded-lg p-2 hover:bg-slate-100"
        >
          <Menu className="h-5 w-5" />
        </button>
        <span className="text-sm font-medium">
          {activeTab === "chat"
            ? "Chat"
            : activeTab === "upload"
              ? "Upload"
              : "Assignment"}
        </span>
        <div className="w-9" />
      </div>

      {sidebarOpen && (
        <div
          className="fixed inset-0 z-40 bg-black/30 md:hidden"
          onClick={() => setSidebarOpen(false)}
        />
      )}

      <aside
        className={`fixed z-50 flex h-full w-72 flex-col border-r border-slate-200 bg-white p-4 transition-transform md:static md:z-auto md:translate-x-0 ${
          sidebarOpen ? "translate-x-0" : "-translate-x-full"
        }`}
      >
        <div className="mb-4 flex items-center justify-between">
          <span className="text-sm font-semibold text-teal-700">
            LMH RAG Assistant
          </span>
          <button
            onClick={() => setSidebarOpen(false)}
            aria-label="Close menu"
            className="rounded-lg p-1 hover:bg-slate-100 md:hidden"
          >
            <X className="h-4 w-4" />
          </button>
        </div>

        <button
          onClick={startNewChat}
          className="mb-4 flex items-center justify-center gap-2 rounded-lg border border-teal-600 bg-teal-600 px-3 py-2 text-sm font-medium text-white hover:bg-teal-700"
        >
          <Plus className="h-4 w-4" />
          New chat
        </button>

        <nav className="mb-4 flex flex-col gap-1">
          <NavItem
            icon={<MessageCircle className="h-4 w-4" />}
            label="Chat"
            active={activeTab === "chat"}
            onClick={() => navigate("chat")}
          />
          <NavItem
            icon={<UploadIcon className="h-4 w-4" />}
            label="Upload documents"
            active={activeTab === "upload"}
            onClick={() => navigate("upload")}
          />
          <NavItem
            icon={<FileText className="h-4 w-4" />}
            label="Assignment brief"
            active={activeTab === "assignment"}
            onClick={() => navigate("assignment")}
          />
        </nav>

        <p className="mb-2 px-2 text-xs font-medium uppercase tracking-wide text-slate-400">
          History
        </p>
        <div className="flex flex-1 flex-col gap-1 overflow-y-auto">
          {DUMMY_THREADS.map((t) => (
            <button
              key={t.id}
              onClick={() => selectThread(t.id)}
              className={`truncate rounded-lg px-3 py-2 text-left text-sm ${
                t.id === activeThreadId
                  ? "bg-teal-50 text-teal-800"
                  : "text-slate-600 hover:bg-slate-100"
              }`}
            >
              {t.title}
            </button>
          ))}
        </div>
      </aside>

      <main className="flex flex-1 flex-col overflow-hidden pt-14 md:pt-0">
        {activeTab === "chat" && (
          <ChatPanel key={chatSessionKey} />
        )}
        {activeTab === "upload" && (
          <UploadPanel
            docs={docs}
            isDragging={isDragging}
            setIsDragging={setIsDragging}
            onFiles={handleFiles}
            onRemove={removeDoc}
          />
        )}
        {activeTab === "assignment" && <AssignmentPanel />}
      </main>
    </div>
  );
}

function NavItem({
  icon,
  label,
  active,
  onClick,
}: {
  icon: React.ReactNode;
  label: string;
  active: boolean;
  onClick: () => void;
}) {
  return (
    <button
      onClick={onClick}
      className={`flex items-center gap-2 rounded-lg px-3 py-2 text-sm ${
        active
          ? "bg-teal-50 text-teal-800"
          : "text-slate-600 hover:bg-slate-100"
      }`}
    >
      {icon}
      {label}
    </button>
  );
}

function UploadPanel({
  docs,
  isDragging,
  setIsDragging,
  onFiles,
  onRemove,
}: {
  docs: UploadedDoc[];
  isDragging: boolean;
  setIsDragging: (v: boolean) => void;
  onFiles: (files: FileList | null) => void;
  onRemove: (id: string) => void;
}) {
  const fileInputRef = useRef<HTMLInputElement>(null);
  return (
    <div className="mx-auto w-full max-w-2xl overflow-y-auto p-4 md:p-8">
      <h1 className="mb-1 text-lg font-medium">Upload documents</h1>
      <p className="mb-6 text-sm text-slate-500">
        PDFs added here are chunked, embedded, and stored for retrieval in chat.
      </p>

      <div
        onDragOver={(e) => {
          e.preventDefault();
          setIsDragging(true);
        }}
        onDragLeave={() => setIsDragging(false)}
        onDrop={(e) => {
          e.preventDefault();
          setIsDragging(false);
          onFiles(e.dataTransfer.files);
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
          onChange={(e) => onFiles(e.target.files)}
        />
      </div>

      <h2 className="mb-3 text-sm font-medium text-slate-700">
        Ingested documents
      </h2>
      <div className="flex flex-col gap-2">
        {docs.map((d) => (
          <div
            key={d.id}
            className="flex items-center justify-between rounded-lg border border-slate-200 bg-white px-4 py-3"
          >
            <div className="flex min-w-0 items-center gap-3">
              <File className="h-4 w-4 shrink-0 text-slate-400" />
              <div className="min-w-0">
                <p className="truncate text-sm text-slate-800">{d.name}</p>
                <p className="text-xs text-slate-400">
                  {d.sizeKb.toLocaleString()} KB · {d.uploadedAt}
                </p>
              </div>
            </div>
            <div className="flex shrink-0 items-center gap-3">
              <StatusBadge status={d.status} />
              <button
                onClick={() => onRemove(d.id)}
                aria-label={`Remove ${d.name}`}
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
