import { useState, type ReactNode } from "react";
import Link from "next/link";
import { useRouter } from "next/router";
import {
  Plus,
  MessageCircle,
  Upload as UploadIcon,
  FileText,
  Menu,
  X,
} from "lucide-react";
import {
  ChatSessionProvider,
  useChatSession,
} from "@/context/ChatSessionContext";
import { mobileTitleForPath, NAV_ITEMS, type AppRoute } from "@/config/navigation";

const DUMMY_THREADS = [
  { id: "t1", title: "Community health worker training docs" },
  { id: "t2", title: "Malaria protocol Q&A" },
  { id: "t3", title: "Supply chain SOPs" },
];

const NAV_ICONS = {
  "/": MessageCircle,
  "/upload": UploadIcon,
  "/assignment": FileText,
} as const;

export default function RagAppShell({ children }: { children: ReactNode }) {
  return (
    <ChatSessionProvider>
      <ShellLayout>{children}</ShellLayout>
    </ChatSessionProvider>
  );
}

function ShellLayout({ children }: { children: ReactNode }) {
  const router = useRouter();
  const { startNewChat } = useChatSession();
  const [activeThreadId, setActiveThreadId] = useState("");
  const [sidebarOpen, setSidebarOpen] = useState(true);
  const pathname = router.pathname as AppRoute;

  function handleNewChat() {
    setActiveThreadId("");
    startNewChat();
    void router.push("/");
    setSidebarOpen(false);
  }

  function handleSelectThread(id: string) {
    setActiveThreadId(id);
    void router.push("/");
    setSidebarOpen(false);
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
          {mobileTitleForPath(pathname)}
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
          onClick={handleNewChat}
          className="mb-4 flex items-center justify-center gap-2 rounded-lg border border-teal-600 bg-teal-600 px-3 py-2 text-sm font-medium text-white hover:bg-teal-700"
        >
          <Plus className="h-4 w-4" />
          New chat
        </button>

        <nav className="mb-4 flex flex-col gap-1">
          {NAV_ITEMS.map((item) => {
            const Icon = NAV_ICONS[item.href];
            const active = pathname === item.href;

            return (
              <Link
                key={item.href}
                href={item.href}
                onClick={() => setSidebarOpen(false)}
                className={`flex items-center gap-2 rounded-lg px-3 py-2 text-sm ${
                  active
                    ? "bg-teal-50 text-teal-800"
                    : "text-slate-600 hover:bg-slate-100"
                }`}
              >
                <Icon className="h-4 w-4" />
                {item.label}
              </Link>
            );
          })}
        </nav>

        <p className="mb-2 px-2 text-xs font-medium uppercase tracking-wide text-slate-400">
          History
        </p>
        <div className="flex flex-1 flex-col gap-1 overflow-y-auto">
          {DUMMY_THREADS.map((thread) => (
            <button
              key={thread.id}
              onClick={() => handleSelectThread(thread.id)}
              className={`truncate rounded-lg px-3 py-2 text-left text-sm ${
                thread.id === activeThreadId
                  ? "bg-teal-50 text-teal-800"
                  : "text-slate-600 hover:bg-slate-100"
              }`}
            >
              {thread.title}
            </button>
          ))}
        </div>
      </aside>

      <main className="flex flex-1 flex-col overflow-hidden pt-14 md:pt-0">
        {children}
      </main>
    </div>
  );
}
