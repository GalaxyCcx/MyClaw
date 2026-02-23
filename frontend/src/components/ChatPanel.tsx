import type { MessageItem } from "../types";
import MessageList from "./MessageList";
import InputBar from "./InputBar";
import WelcomeScreen from "./WelcomeScreen";

interface Props {
  messages: MessageItem[];
  isAgentRunning: boolean;
  isConnected: boolean;
  onSend: (content: string) => void;
}

export default function ChatPanel({ messages, isAgentRunning, isConnected, onSend }: Props) {
  return (
    <div style={{ display: "flex", flexDirection: "column", height: "100%" }}>
      {messages.length === 0 && !isAgentRunning ? (
        <WelcomeScreen onExampleClick={onSend} />
      ) : (
        <MessageList messages={messages} isAgentRunning={isAgentRunning} />
      )}
      <InputBar onSend={onSend} disabled={isAgentRunning || !isConnected} />
    </div>
  );
}
