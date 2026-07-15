import { useCallback, useEffect, useRef, useState } from "react";
import { MessageCircle, Send } from "lucide-react";
import {
  ChatMessage,
  ChatTurn,
  clientConfig,
} from "@/config/client";
import { useChatSession } from "@/context/ChatSessionContext";
import MarkdownMessage from "@/components/MarkdownMessage";

type ThreadUsage = {
  total_tokens: number;
  estimated_cost_usd: number;
};

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

function formatUsd(amount: number): string {
  if (amount <= 0) return "$0.00";
  if (amount < 0.01) return `$${amount.toFixed(6)}`;
  return `$${amount.toFixed(4)}`;
}

async function fetchThreadUsage(id: string): Promise<ThreadUsage | null> {
  try {
    const response = await fetch(`${clientConfig.apiV1Url}/chats/${id}/usage`);
    if (!response.ok) return null;
    return (await response.json()) as ThreadUsage;
  } catch {
    return null;
  }
}

export default function ChatPanel() {
  const {
    activeThreadId,
    suggestedTopics,
    topicsLoading,
    upsertThread,
    refreshThreads,
  } = useChatSession();
  const [threadId, setThreadId] = useState(activeThreadId);
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [draft, setDraft] = useState("");
  const [isStreaming, setIsStreaming] = useState(false);
  const [isLoadingThread, setIsLoadingThread] = useState(Boolean(activeThreadId));
  const [error, setError] = useState<string | null>(null);
  const [selectedTopic, setSelectedTopic] = useState<string | null>(null);
  const [usage, setUsage] = useState<ThreadUsage | null>(null);
  const bottomRef = useRef<HTMLDivElement>(null);
  const skipLoadRef = useRef(false);

  // Show on a new chat that has not sent any message yet.
  const showTopicSuggestions =
    !activeThreadId &&
    !threadId &&
    !isLoadingThread &&
    messages.length === 0 &&
    !isStreaming;

  useEffect(() => {
    setThreadId(activeThreadId);
  }, [activeThreadId]);

  useEffect(() => {
    let cancelled = false;

    async function loadThread() {
      if (!activeThreadId) {
        setMessages([]);
        setIsLoadingThread(false);
        setSelectedTopic(null);
        setUsage(null);
        return;
      }

      if (skipLoadRef.current) {
        skipLoadRef.current = false;
        setIsLoadingThread(false);
        void fetchThreadUsage(activeThreadId).then((next) => {
          if (!cancelled) setUsage(next);
        });
        return;
      }

      setIsLoadingThread(true);
      setError(null);
      try {
        const response = await fetch(
          `${clientConfig.apiV1Url}/chats/${activeThreadId}/messages`
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
        const nextUsage = await fetchThreadUsage(activeThreadId);
        if (!cancelled) setUsage(nextUsage);
      } catch {
        if (!cancelled) {
          setError("Failed to load this chat.");
          setMessages([]);
          setUsage(null);
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

  const sendMessage = useCallback(
    async (rawText: string) => {
      const text = rawText.trim();
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
        const response = await fetch(`${clientConfig.apiV1Url}/chats`, {
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
        const usageId = responseThreadId || threadId;
        if (usageId) {
          const nextUsage = await fetchThreadUsage(usageId);
          setUsage(nextUsage);
        }
      } catch {
        setError("Failed to get a response from the chat service.");
        setMessages((prev) =>
          prev.filter((message) => message.id !== assistantId)
        );
        setSelectedTopic(null);
      } finally {
        setIsStreaming(false);
      }
    },
    [
      isStreaming,
      isLoadingThread,
      messages,
      threadId,
      upsertThread,
      refreshThreads,
    ]
  );

  function handleSend() {
    void sendMessage(draft);
  }

  function handleTopicClick(topic: string) {
    if (isStreaming || selectedTopic) return;
    setSelectedTopic(topic);
    setDraft(topic);
    void sendMessage(topic);
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
          <div className="flex h-full flex-col items-center justify-center px-2 text-center text-slate-400">
            <MessageCircle className="mb-3 h-8 w-8" />
            <p className="text-sm">
              Ask a question about your uploaded documents to get started.
            </p>

            {showTopicSuggestions && (
              <div className="mt-6 w-full max-w-2xl">
                {topicsLoading && (
                  <p className="text-xs text-slate-400">Finding topic ideas…</p>
                )}
                {!topicsLoading && suggestedTopics.length > 0 && (
                  <>
                    <p className="mb-3 text-xs font-medium uppercase tracking-wide text-slate-400">
                      Suggested topics
                    </p>
                    <div className="flex flex-wrap justify-center gap-2">
                      {suggestedTopics.map((topic) => {
                        const isSelected = selectedTopic === topic;
                        const disabled = Boolean(selectedTopic) || isStreaming;
                        return (
                          <button
                            key={topic}
                            type="button"
                            onClick={() => handleTopicClick(topic)}
                            disabled={disabled}
                            aria-pressed={isSelected}
                            className={`max-w-full rounded-full border px-3.5 py-2 text-left text-sm transition ${
                              isSelected
                                ? "border-teal-600 bg-teal-600 text-white"
                                : disabled
                                  ? "cursor-not-allowed border-slate-200 bg-slate-50 text-slate-400"
                                  : "border-teal-200 bg-white text-teal-800 hover:border-teal-500 hover:bg-teal-50"
                            }`}
                          >
                            <span className="line-clamp-2">{topic}</span>
                          </button>
                        );
                      })}
                    </div>
                  </>
                )}
              </div>
            )}
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

      {usage && usage.total_tokens > 0 && (
        <div className="border-t border-slate-100 px-4 py-2 text-center text-[11px] text-slate-400 md:px-6">
          Total tokens: {usage.total_tokens.toLocaleString()} · Total cost:{" "}
          {formatUsd(usage.estimated_cost_usd)}
        </div>
      )}

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
