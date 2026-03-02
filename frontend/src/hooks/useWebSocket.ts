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
  "agent_stopped",
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
  "agent_stopped",
]);

let msgIdCounter = 0;
function nextId() {
  return `msg-${++msgIdCounter}-${Date.now()}`;
}

const STREAMING_ID = "__streaming__";

export type GraphEventHandler = (event: AgentEvent) => void;

type ConnectionStats = {
  reconnectCount: number;
  lastDisconnectAt: string | null;
  lastCloseCode: number | null;
  lastCloseReason: string | null;
  lastErrorAt: string | null;
};

export function useWebSocket(
  url: string,
  onGraphEvent?: GraphEventHandler,
) {
  const wsRef = useRef<WebSocket | null>(null);
  const shouldReconnectRef = useRef(true);
  const manualCloseRef = useRef(false);
  const reconnectTimerRef = useRef<number | null>(null);
  const reconnectCountRef = useRef(0);
  const [status, setStatus] = useState<Status>("disconnected");
  const [messages, setMessages] = useState<MessageItem[]>([]);
  const [isAgentRunning, setIsAgentRunning] = useState(false);
  const [connectionStats, setConnectionStats] = useState<ConnectionStats>({
    reconnectCount: 0,
    lastDisconnectAt: null,
    lastCloseCode: null,
    lastCloseReason: null,
    lastErrorAt: null,
  });
  const streamingContentRef = useRef("");
  const onGraphEventRef = useRef(onGraphEvent);
  onGraphEventRef.current = onGraphEvent;

  const connect = useCallback(() => {
    if (wsRef.current?.readyState === WebSocket.OPEN) return;

    setStatus("connecting");
    const ws = new WebSocket(url);

    ws.onopen = () => {
      if (reconnectTimerRef.current !== null) {
        window.clearTimeout(reconnectTimerRef.current);
        reconnectTimerRef.current = null;
      }
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

        if (event.type === "agent_stopped") {
          const partial = streamingContentRef.current.trim();
          streamingContentRef.current = "";
          setMessages((prev) => {
            const filtered = prev.filter((m) => m.id !== STREAMING_ID);
            const stopMsg = partial
              ? `${partial}\n\n（已手动停止本轮对话）`
              : "已手动停止本轮对话，你可以继续提问，我会基于当前历史继续。";
            return [
              ...filtered,
              {
                id: nextId(),
                type: "final_answer",
                step: event.step,
                timestamp: event.timestamp,
                data: { content: stopMsg },
              },
            ];
          });
          setIsAgentRunning(false);
          return;
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

    ws.onclose = (event) => {
      const disconnectedAt = new Date().toISOString();
      const wasManualClose = manualCloseRef.current;
      if (!wasManualClose) {
        setStatus("disconnected");
      } else {
        manualCloseRef.current = false;
      }
      setIsAgentRunning(false);
      setConnectionStats((prev) => ({
        ...prev,
        lastDisconnectAt: disconnectedAt,
        lastCloseCode: event.code ?? null,
        lastCloseReason: event.reason || null,
      }));

      if (shouldReconnectRef.current && !wasManualClose) {
        reconnectCountRef.current += 1;
        setConnectionStats((prev) => ({
          ...prev,
          reconnectCount: reconnectCountRef.current,
        }));
        reconnectTimerRef.current = window.setTimeout(() => {
          setStatus("connecting");
          connect();
        }, 3000);
      }
    };

    ws.onerror = () => {
      setConnectionStats((prev) => ({
        ...prev,
        lastErrorAt: new Date().toISOString(),
      }));
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
    manualCloseRef.current = true;
    wsRef.current?.close();
    setTimeout(() => connect(), 200);
  }, [connect]);

  const stopConversation = useCallback(() => {
    if (!wsRef.current || wsRef.current.readyState !== WebSocket.OPEN) return;
    wsRef.current.send(JSON.stringify({ type: "stop", data: {} }));
  }, []);

  useEffect(() => {
    shouldReconnectRef.current = true;
    connect();
    return () => {
      shouldReconnectRef.current = false;
      manualCloseRef.current = true;
      if (reconnectTimerRef.current !== null) {
        window.clearTimeout(reconnectTimerRef.current);
        reconnectTimerRef.current = null;
      }
      wsRef.current?.close();
    };
  }, [connect]);

  return {
    status,
    messages,
    isAgentRunning,
    connectionStats,
    sendMessage,
    stopConversation,
    clearMessages,
  };
}
