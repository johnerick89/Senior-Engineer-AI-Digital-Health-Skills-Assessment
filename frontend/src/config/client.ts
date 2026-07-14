export const clientConfig = {
  backendUrl: process.env.NEXT_PUBLIC_BACKEND_URL ?? "http://localhost:6100",
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
