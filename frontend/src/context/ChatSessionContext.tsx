import {
  createContext,
  useCallback,
  useContext,
  useState,
  type ReactNode,
} from "react";

type ChatSessionContextValue = {
  sessionKey: number;
  startNewChat: () => void;
};

const ChatSessionContext = createContext<ChatSessionContextValue | null>(null);

export function ChatSessionProvider({ children }: { children: ReactNode }) {
  const [sessionKey, setSessionKey] = useState(0);
  const startNewChat = useCallback(() => {
    setSessionKey((key) => key + 1);
  }, []);

  return (
    <ChatSessionContext.Provider value={{ sessionKey, startNewChat }}>
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
