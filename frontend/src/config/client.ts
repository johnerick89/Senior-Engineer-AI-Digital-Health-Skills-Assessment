const backendUrl =
  process.env.NEXT_PUBLIC_BACKEND_URL ?? "http://localhost:6100";

export const clientConfig = {
  backendUrl,
  /** Versioned REST base used by all resource calls. */
  apiV1Url: `${backendUrl.replace(/\/$/, "")}/api/v1`,
};

export type ChatTurn = {
  input: string;
  response: string;
};

export type ChatMessage = {
  id: string;
  role: "user" | "assistant";
  content: string;
};

export type ChatThreadSummary = {
  id: string;
  title: string | null;
  updated_at?: string | null;
  created_at?: string | null;
};
