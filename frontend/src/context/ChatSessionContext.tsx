import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useState,
  type ReactNode,
} from "react";
import { clientConfig, type ChatThreadSummary } from "@/config/client";

type ChatSessionContextValue = {
  sessionKey: number;
  activeThreadId: string;
  threads: ChatThreadSummary[];
  threadsLoading: boolean;
  suggestedTopics: string[];
  topicsLoading: boolean;
  startNewChat: () => void;
  selectThread: (id: string) => void;
  upsertThread: (thread: ChatThreadSummary) => void;
  refreshThreads: () => Promise<void>;
};

const ChatSessionContext = createContext<ChatSessionContextValue | null>(null);

export function ChatSessionProvider({ children }: { children: ReactNode }) {
  const [sessionKey, setSessionKey] = useState(0);
  const [activeThreadId, setActiveThreadId] = useState("");
  const [threads, setThreads] = useState<ChatThreadSummary[]>([]);
  const [threadsLoading, setThreadsLoading] = useState(true);
  const [suggestedTopics, setSuggestedTopics] = useState<string[]>([]);
  const [topicsLoading, setTopicsLoading] = useState(true);

  const refreshThreads = useCallback(async () => {
    try {
      const response = await fetch(`${clientConfig.backendUrl}/chats`);
      if (!response.ok) return;
      const data = (await response.json()) as ChatThreadSummary[];
      setThreads(data);
    } catch {
      // Sidebar can stay on last known list.
    } finally {
      setThreadsLoading(false);
    }
  }, []);

  useEffect(() => {
    void refreshThreads();
  }, [refreshThreads]);

  // Fetch once on app load; refresh only when the page is reloaded.
  useEffect(() => {
    let cancelled = false;

    async function loadTopics() {
      setTopicsLoading(true);
      try {
        const response = await fetch(
          `${clientConfig.backendUrl}/chat/suggestions`
        );
        if (!response.ok) return;
        const data = (await response.json()) as { topics?: string[] };
        if (cancelled) return;
        setSuggestedTopics((data.topics ?? []).slice(0, 5));
      } catch {
        if (!cancelled) setSuggestedTopics([]);
      } finally {
        if (!cancelled) setTopicsLoading(false);
      }
    }

    void loadTopics();
    return () => {
      cancelled = true;
    };
  }, []);

  const startNewChat = useCallback(() => {
    setActiveThreadId("");
    setSessionKey((key) => key + 1);
  }, []);

  const selectThread = useCallback((id: string) => {
    setActiveThreadId(id);
    setSessionKey((key) => key + 1);
  }, []);

  const upsertThread = useCallback((thread: ChatThreadSummary) => {
    setActiveThreadId((current) => current || thread.id);
    setThreads((prev) => {
      const rest = prev.filter((item) => item.id !== thread.id);
      return [thread, ...rest];
    });
  }, []);

  return (
    <ChatSessionContext.Provider
      value={{
        sessionKey,
        activeThreadId,
        threads,
        threadsLoading,
        suggestedTopics,
        topicsLoading,
        startNewChat,
        selectThread,
        upsertThread,
        refreshThreads,
      }}
    >
      {children}
    </ChatSessionContext.Provider>
  );
}

export function useChatSession() {
  const context = useContext(ChatSessionContext);
  if (!context) {
    throw new Error("useChatSession must be used within ChatSessionProvider");
  }
  return context;
}
