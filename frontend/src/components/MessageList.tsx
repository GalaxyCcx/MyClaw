import { useEffect, useRef } from "react";
import type { MessageItem as MessageItemType } from "../types";
import MessageItem from "./MessageItem";
import ThinkingIndicator from "./ThinkingIndicator";

interface Props {
  messages: MessageItemType[];
  isAgentRunning: boolean;
}

export default function MessageList({ messages, isAgentRunning }: Props) {
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, isAgentRunning]);

  return (
    <div
      style={{
        flex: 1,
        overflowY: "auto",
        padding: "16px 0",
      }}
    >
      {messages.map((msg) => (
        <MessageItem key={msg.id} message={msg} />
      ))}
      {isAgentRunning && <ThinkingIndicator />}
      <div ref={bottomRef} />
    </div>
  );
}
