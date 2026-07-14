"use client";

import { useEffect, useRef, useState } from "react";
import { MessageCircle, Send } from "lucide-react";
import {
  ChatMessage,
  ChatTurn,
  clientConfig,
} from "@/config/client";

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
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [draft, setDraft] = useState("");
  const [isStreaming, setIsStreaming] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  async function handleSend() {
    const text = draft.trim();
    if (!text || isStreaming) return;

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
        body: JSON.stringify({ input: text, history }),
      });

      if (!response.ok) {
        throw new Error(`Chat request failed (${response.status})`);
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

        {messages.length === 0 && !error && (
          <div className="flex h-full flex-col items-center justify-center text-center text-slate-400">
            <MessageCircle className="mb-3 h-8 w-8" />
            <p className="text-sm">
              Ask a question about your uploaded documents to get started.
            </p>
          </div>
        )}

        {messages.map((message) => {
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
                    : "border border-slate-200 bg-white text-slate-800"
                }`}
              >
                <p className="whitespace-pre-wrap">{message.content}</p>
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
            disabled={isStreaming}
            className="h-11 flex-1 rounded-lg border border-slate-300 px-3 text-sm outline-none focus:border-teal-500 focus:ring-1 focus:ring-teal-500 disabled:bg-slate-50 disabled:text-slate-400"
          />
          <button
            onClick={handleSend}
            disabled={isStreaming || !draft.trim()}
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
