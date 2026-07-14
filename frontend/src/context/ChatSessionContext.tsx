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
