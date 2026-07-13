"use client";

import { useEffect, useRef, useState } from "react";
import { MessageCircle, Send } from "lucide-react";
import {
  IStep,
  useChatData,
  useChatInteract,
  useChatMessages,
  useChatSession,
} from "@chainlit/react-client";

function getMessageText(message: IStep): string {
  return message.output || message.input || "";
}

function isVisibleMessage(message: IStep): boolean {
  return (
    message.type === "user_message" ||
    message.type === "assistant_message" ||
    message.type === "system_message"
  );
}

export default function ChainlitChatPanel({
  sessionKey,
}: {
  sessionKey: number;
}) {
  const [draft, setDraft] = useState("");
  const bottomRef = useRef<HTMLDivElement>(null);
  const { connect, disconnect } = useChatSession();
  const { messages } = useChatMessages();
  const { sendMessage } = useChatInteract();
  const { connected, loading, error } = useChatData();

  useEffect(() => {
    connect({});
    return () => {
      disconnect();
    };
  }, [connect, disconnect, sessionKey]);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  function handleSend() {
    const text = draft.trim();
    if (!text || !connected) return;

    sendMessage({
      name: "User",
      type: "user_message",
      output: text,
      createdAt: new Date().toISOString(),
    } as IStep);
    setDraft("");
  }

  const visibleMessages = messages.filter(isVisibleMessage);

  return (
    <div className="flex h-full flex-col">
      <div className="flex-1 space-y-4 overflow-y-auto p-4 md:p-6">
        {loading && visibleMessages.length === 0 && (
          <div className="flex h-full flex-col items-center justify-center text-center text-slate-400">
            <MessageCircle className="mb-3 h-8 w-8 animate-pulse" />
            <p className="text-sm">Connecting to Chainlit…</p>
          </div>
        )}

        {error && (
          <div className="rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
            Could not connect to Chainlit at http://localhost:8000. Make sure the
            Chainlit app is running.
          </div>
        )}

        {!loading && visibleMessages.length === 0 && !error && (
          <div className="flex h-full flex-col items-center justify-center text-center text-slate-400">
            <MessageCircle className="mb-3 h-8 w-8" />
            <p className="text-sm">
              Ask a question about your uploaded documents to get started.
            </p>
          </div>
        )}

        {visibleMessages.map((message) => {
          const isUser = message.type === "user_message";
          const text = getMessageText(message);

          if (!text) return null;

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
                <p className="whitespace-pre-wrap">{text}</p>
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
            disabled={!connected}
            className="h-11 flex-1 rounded-lg border border-slate-300 px-3 text-sm outline-none focus:border-teal-500 focus:ring-1 focus:ring-teal-500 disabled:bg-slate-50 disabled:text-slate-400"
          />
          <button
            onClick={handleSend}
            disabled={!connected || !draft.trim()}
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
