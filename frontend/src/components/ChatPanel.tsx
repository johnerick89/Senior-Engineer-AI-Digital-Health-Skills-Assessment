import { useEffect, useRef, useState } from "react";
import { MessageCircle, Send } from "lucide-react";
import {
  ChatMessage,
  ChatTurn,
  clientConfig,
} from "@/config/client";
import { useChatSession } from "@/context/ChatSessionContext";
import MarkdownMessage from "@/components/MarkdownMessage";

function buildHistory(messages: ChatMessage[]): ChatTurn[] {
  const history: ChatTurn[] = [];

  for (let i = 0; i < messages.length; i++) {
    const message = messages[i];
    if (message.role !== "user") continue;

    const response = messages[i + 1];
    if (!response || response.role !== "assistant") continue;

    history.push({
      input: message.content,
      response: response.content,
    });
  }

  return history;
}

export default function ChatPanel() {
  const { activeThreadId, upsertThread, refreshThreads } = useChatSession();
  const [threadId, setThreadId] = useState(activeThreadId);
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [draft, setDraft] = useState("");
  const [isStreaming, setIsStreaming] = useState(false);
  const [isLoadingThread, setIsLoadingThread] = useState(Boolean(activeThreadId));
  const [error, setError] = useState<string | null>(null);
  const bottomRef = useRef<HTMLDivElement>(null);
  const skipLoadRef = useRef(false);

  useEffect(() => {
    setThreadId(activeThreadId);
  }, [activeThreadId]);

  useEffect(() => {
    let cancelled = false;

    async function loadThread() {
      if (!activeThreadId) {
        setMessages([]);
        setIsLoadingThread(false);
        return;
      }

      if (skipLoadRef.current) {
        skipLoadRef.current = false;
        setIsLoadingThread(false);
        return;
      }

      setIsLoadingThread(true);
      setError(null);
      try {
        const response = await fetch(
          `${clientConfig.backendUrl}/chats/${activeThreadId}/messages`
        );
        if (!response.ok) {
          throw new Error(`Failed to load chat (${response.status})`);
        }
        const data = (await response.json()) as Array<{
          id: string;
          role: "user" | "assistant";
          content: string;
        }>;
        if (cancelled) return;
        setMessages(
          data.map((message) => ({
            id: message.id,
            role: message.role,
            content: message.content,
          }))
        );
      } catch {
        if (!cancelled) {
          setError("Failed to load this chat.");
          setMessages([]);
        }
      } finally {
        if (!cancelled) setIsLoadingThread(false);
      }
    }

    void loadThread();
    return () => {
      cancelled = true;
    };
  }, [activeThreadId]);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  async function handleSend() {
    const text = draft.trim();
    if (!text || isStreaming || isLoadingThread) return;

    const userMessage: ChatMessage = {
      id: `user-${Date.now()}`,
      role: "user",
      content: text,
    };
    const assistantId = `assistant-${Date.now()}`;
    const history = buildHistory(messages);

    setMessages((prev) => [
      ...prev,
      userMessage,
      { id: assistantId, role: "assistant", content: "" },
    ]);
    setDraft("");
    setError(null);
    setIsStreaming(true);

    try {
      const response = await fetch(`${clientConfig.backendUrl}/chat`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          input: text,
          history,
          id: threadId || undefined,
        }),
      });

      if (!response.ok) {
        throw new Error(`Chat request failed (${response.status})`);
      }

      const responseThreadId = response.headers.get("X-Chat-Id");
      const rawTitle = response.headers.get("X-Chat-Title");
      const responseTitle = rawTitle ? decodeURIComponent(rawTitle) : null;
      if (responseThreadId) {
        if (!threadId) {
          skipLoadRef.current = true;
        }
        setThreadId(responseThreadId);
        upsertThread({
          id: responseThreadId,
          title: responseTitle || text,
        });
      }

      const reader = response.body?.getReader();
      if (!reader) {
        throw new Error("No response stream available");
      }

      const decoder = new TextDecoder();
      let streamed = "";

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        streamed += decoder.decode(value, { stream: true });
        const nextContent = streamed;
        setMessages((prev) =>
          prev.map((message) =>
            message.id === assistantId
              ? { ...message, content: nextContent }
              : message
          )
        );
      }

      await refreshThreads();
    } catch {
      setError("Failed to get a response from the chat service.");
      setMessages((prev) => prev.filter((message) => message.id !== assistantId));
    } finally {
      setIsStreaming(false);
    }
  }

  return (
    <div className="flex h-full flex-col">
      <div className="flex-1 space-y-4 overflow-y-auto p-4 md:p-6">
        {error && (
          <div className="rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
            {error}
          </div>
        )}

        {isLoadingThread && (
          <div className="flex h-full items-center justify-center text-sm text-slate-400">
            Loading chat…
          </div>
        )}

        {!isLoadingThread && messages.length === 0 && !error && (
          <div className="flex h-full flex-col items-center justify-center text-center text-slate-400">
            <MessageCircle className="mb-3 h-8 w-8" />
            <p className="text-sm">
              Ask a question about your uploaded documents to get started.
            </p>
          </div>
        )}

        {!isLoadingThread &&
          messages.map((message) => {
            if (message.role === "assistant" && !message.content && isStreaming) {
              return (
                <div key={message.id} className="flex justify-start">
                  <div className="max-w-[85%] rounded-xl border border-slate-200 bg-white px-4 py-2.5 text-sm text-slate-400 md:max-w-[70%]">
                    Thinking…
                  </div>
                </div>
              );
            }

            if (!message.content) return null;

            const isUser = message.role === "user";

            return (
              <div
                key={message.id}
                className={`flex ${isUser ? "justify-end" : "justify-start"}`}
              >
                <div
                  className={`max-w-[85%] rounded-xl px-4 py-2.5 text-sm leading-relaxed md:max-w-[70%] ${
                    isUser
                      ? "bg-teal-600 text-white"
                      : "border border-slate-200 bg-white text-slate-800 shadow-sm"
                  }`}
                >
                  {isUser ? (
                    <p className="whitespace-pre-wrap">{message.content}</p>
                  ) : (
                    <MarkdownMessage content={message.content} />
                  )}
                </div>
              </div>
            );
          })}
        <div ref={bottomRef} />
      </div>

      <div className="border-t border-slate-200 bg-white p-3 md:p-4">
        <div className="mx-auto flex max-w-3xl items-center gap-2">
          <input
            value={draft}
            onChange={(e) => setDraft(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && handleSend()}
            placeholder="Ask about your uploaded documents"
            disabled={isStreaming || isLoadingThread}
            className="h-11 flex-1 rounded-lg border border-slate-300 px-3 text-sm outline-none focus:border-teal-500 focus:ring-1 focus:ring-teal-500 disabled:bg-slate-50 disabled:text-slate-400"
          />
          <button
            onClick={handleSend}
            disabled={isStreaming || isLoadingThread || !draft.trim()}
            aria-label="Send message"
            className="flex h-11 w-11 shrink-0 items-center justify-center rounded-lg bg-teal-600 text-white hover:bg-teal-700 disabled:cursor-not-allowed disabled:bg-slate-300"
          >
            <Send className="h-4 w-4" />
          </button>
        </div>
      </div>
    </div>
  );
}
