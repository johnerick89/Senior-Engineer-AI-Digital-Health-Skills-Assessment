import ChatPanel from "@/components/ChatPanel";
import { useChatSession } from "@/context/ChatSessionContext";

export default function ChatPage() {
  const { sessionKey } = useChatSession();

  return <ChatPanel key={sessionKey} />;
}
