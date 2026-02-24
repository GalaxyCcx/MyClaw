import { useCallback, useEffect, useRef, useState } from "react";
import type { AgentEvent, MessageItem } from "../types";

type Status = "connecting" | "connected" | "disconnected";

const GRAPH_EVENTS = new Set([
  "init_status",
  "graph_reset",
  "user_input",
  "node_enter",
  "node_exit",
  "context_pruned",
  "context_compacted",
  "overflow_recovered",
]);

const CHAT_IGNORE = new Set([
  "user_input",
  "init_status",
  "graph_reset",
  "node_enter",
  "node_exit",
  "context_pruned",
  "context_compacted",
  "overflow_recovered",
]);

let msgIdCounter = 0;
function nextId() {
  return `msg-${++msgIdCounter}-${Date.now()}`;
}

const STREAMING_ID = "__streaming__";

export type GraphEventHandler = (event: AgentEvent) => void;

export function useWebSocket(
  url: string,
  onGraphEvent?: GraphEventHandler,
) {
  const wsRef = useRef<WebSocket | null>(null);
  const [status, setStatus] = useState<Status>("disconnected");
  const [messages, setMessages] = useState<MessageItem[]>([]);
  const [isAgentRunning, setIsAgentRunning] = useState(false);
  const streamingContentRef = useRef("");
  const onGraphEventRef = useRef(onGraphEvent);
  onGraphEventRef.current = onGraphEvent;

  const connect = useCallback(() => {
    if (wsRef.current?.readyState === WebSocket.OPEN) return;

    setStatus("connecting");
    const ws = new WebSocket(url);

    ws.onopen = () => {
      setStatus("connected");
    };

    ws.onmessage = (e) => {
      try {
        const event: AgentEvent = JSON.parse(e.data);

        if (GRAPH_EVENTS.has(event.type)) {
          onGraphEventRef.current?.(event);
        }

        if (event.type === "tool_call" || event.type === "tool_result" || event.type === "final_answer") {
          onGraphEventRef.current?.(event);
        }

        if (CHAT_IGNORE.has(event.type)) {
          return;
        }

        if (event.type === "llm_token") {
          const token = (event.data as { token: string }).token;
          streamingContentRef.current += token;
          const content = streamingContentRef.current;
          setMessages((prev) => {
            const existing = prev.findIndex((m) => m.id === STREAMING_ID);
            const streamMsg: MessageItem = {
              id: STREAMING_ID,
              type: "final_answer",
              step: event.step,
              timestamp: event.timestamp,
              data: { content },
            };
            if (existing >= 0) {
              const next = [...prev];
              next[existing] = streamMsg;
              return next;
            }
            return [...prev, streamMsg];
          });
          return;
        }

        if (event.type === "final_answer") {
          streamingContentRef.current = "";
          setMessages((prev) => {
            const filtered = prev.filter((m) => m.id !== STREAMING_ID);
            return [
              ...filtered,
              {
                id: nextId(),
                type: event.type,
                step: event.step,
                timestamp: event.timestamp,
                data: event.data,
              },
            ];
          });
          setIsAgentRunning(false);
          return;
        }

        if (event.type === "tool_call") {
          streamingContentRef.current = "";
          setMessages((prev) => {
            const filtered = prev.filter((m) => m.id !== STREAMING_ID);
            return [
              ...filtered,
              {
                id: nextId(),
                type: event.type,
                step: event.step,
                timestamp: event.timestamp,
                data: event.data,
              },
            ];
          });
          return;
        }

        const item: MessageItem = {
          id: nextId(),
          type: event.type,
          step: event.step,
          timestamp: event.timestamp,
          data: event.data,
        };
        setMessages((prev) => [...prev, item]);

        if (event.type === "error") {
          setIsAgentRunning(false);
        }
      } catch {
        // ignore malformed messages
      }
    };

    ws.onclose = () => {
      setStatus("disconnected");
      setIsAgentRunning(false);
      setTimeout(() => connect(), 3000);
    };

    ws.onerror = () => {
      ws.close();
    };

    wsRef.current = ws;
  }, [url]);

  const sendMessage = useCallback((content: string) => {
    if (!wsRef.current || wsRef.current.readyState !== WebSocket.OPEN) return;

    streamingContentRef.current = "";
    const userItem: MessageItem = {
      id: nextId(),
      type: "user_input",
      step: 0,
      timestamp: new Date().toISOString(),
      data: { content },
    };
    setMessages((prev) => [...prev, userItem]);
    setIsAgentRunning(true);

    wsRef.current.send(
      JSON.stringify({ type: "user_input", data: { content } })
    );
  }, []);

  const clearMessages = useCallback(() => {
    setMessages([]);
    streamingContentRef.current = "";
    wsRef.current?.close();
    setTimeout(() => connect(), 200);
  }, [connect]);

  useEffect(() => {
    connect();
    return () => {
      wsRef.current?.close();
    };
  }, [connect]);

  return { status, messages, isAgentRunning, sendMessage, clearMessages };
}
