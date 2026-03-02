import { Layout, Typography, Tag, Button, Alert } from "antd";
import { ClearOutlined, SettingOutlined, PauseCircleOutlined } from "@ant-design/icons";
import { useCallback, useRef, useState } from "react";
import { useWebSocket } from "./hooks/useWebSocket";
import { useGraph } from "./hooks/useGraph";
import ChatPanel from "./components/ChatPanel";
import GraphPanel from "./components/GraphPanel";
import PromptManagerModal from "./components/PromptManagerModal";
import TokenUsageBar from "./components/TokenUsageBar";
import "./styles/global.css";
import "./styles/markdown.css";

const { Header, Content } = Layout;
const { Title } = Typography;

const WS_URL = `${window.location.protocol === "https:" ? "wss:" : "ws:"}//${window.location.host}/ws/chat`;

const MIN_PANEL_PCT = 20;

function App() {
  const graph = useGraph();
  const {
    status,
    messages,
    isAgentRunning,
    connectionStats,
    sendMessage,
    stopConversation,
    clearMessages,
  } =
    useWebSocket(WS_URL, graph.handleGraphEvent);

  const [leftPct, setLeftPct] = useState(50);
  const [promptModalOpen, setPromptModalOpen] = useState(false);
  const dragging = useRef(false);
  const containerRef = useRef<HTMLDivElement>(null);

  const onMouseDown = useCallback(() => {
    dragging.current = true;
    document.body.style.cursor = "col-resize";
    document.body.style.userSelect = "none";

    const onMouseMove = (e: MouseEvent) => {
      if (!dragging.current || !containerRef.current) return;
      const rect = containerRef.current.getBoundingClientRect();
      let pct = ((e.clientX - rect.left) / rect.width) * 100;
      pct = Math.max(MIN_PANEL_PCT, Math.min(100 - MIN_PANEL_PCT, pct));
      setLeftPct(pct);
    };

    const onMouseUp = () => {
      dragging.current = false;
      document.body.style.cursor = "";
      document.body.style.userSelect = "";
      document.removeEventListener("mousemove", onMouseMove);
      document.removeEventListener("mouseup", onMouseUp);
    };

    document.addEventListener("mousemove", onMouseMove);
    document.addEventListener("mouseup", onMouseUp);
  }, []);

  const statusColor =
    status === "connected"
      ? "green"
      : status === "connecting"
        ? "orange"
        : "red";
  const needManualIntervention =
    status === "disconnected" && connectionStats.reconnectCount >= 3;
  const disconnectDescriptionParts = [
    connectionStats.lastCloseCode !== null
      ? `close code: ${connectionStats.lastCloseCode}`
      : "",
    connectionStats.lastCloseReason
      ? `reason: ${connectionStats.lastCloseReason}`
      : "",
    connectionStats.lastDisconnectAt
      ? `last disconnect: ${connectionStats.lastDisconnectAt}`
      : "",
    `reconnect attempts: ${connectionStats.reconnectCount}`,
  ].filter(Boolean);

  return (
    <Layout style={{ height: "100vh" }}>
      <Header
        style={{
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
          background: "#fff",
          borderBottom: "1px solid #e8e8e8",
          padding: "0 24px",
          height: 56,
          gap: 12,
        }}
      >
        <Title level={4} style={{ margin: 0, whiteSpace: "nowrap" }}>
          MyClaw
        </Title>
        <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
          <TokenUsageBar
            tokenUsage={graph.tokenUsage}
            contextLimit={graph.contextLimit}
            modelName={graph.modelName}
          />
          <Tag color={statusColor}>{status}</Tag>
          <Button
            size="small"
            icon={<SettingOutlined />}
            onClick={() => setPromptModalOpen(true)}
          >
            Prompt 管理
          </Button>
          <Button
            size="small"
            icon={<PauseCircleOutlined />}
            onClick={stopConversation}
            disabled={!isAgentRunning || status !== "connected"}
          >
            停止对话
          </Button>
          <Button
            size="small"
            icon={<ClearOutlined />}
            onClick={clearMessages}
            disabled={messages.length === 0 || isAgentRunning}
          >
            新建对话
          </Button>
        </div>
      </Header>
      {status === "disconnected" && (
        <Alert
          type={needManualIntervention ? "warning" : "error"}
          message={
            needManualIntervention
              ? "WebSocket 多次重连失败，请检查网络或重启后端服务"
              : "WebSocket 连接已断开，正在自动重连..."
          }
          description={disconnectDescriptionParts.join(" | ")}
          banner
          showIcon
        />
      )}
      <Content
        style={{
          display: "flex",
          overflow: "hidden",
          flex: 1,
        }}
      >
        <div
          ref={containerRef}
          style={{
            display: "flex",
            width: "100%",
            height: "100%",
          }}
        >
          <div style={{ width: `${leftPct}%`, height: "100%", overflow: "hidden", display: "flex", flexDirection: "column" }}>
            <ChatPanel
              messages={messages}
              isAgentRunning={isAgentRunning}
              isConnected={status === "connected"}
              onSend={sendMessage}
              onStop={stopConversation}
            />
          </div>
          <div
            onMouseDown={onMouseDown}
            style={{
              width: 5,
              cursor: "col-resize",
              background: "#e8e8e8",
              flexShrink: 0,
              transition: "background 0.15s",
            }}
            onMouseEnter={(e) => (e.currentTarget.style.background = "#bbb")}
            onMouseLeave={(e) => (e.currentTarget.style.background = "#e8e8e8")}
          />
          <div style={{ flex: 1, height: "100%", overflow: "hidden" }}>
            <GraphPanel
              initJobs={graph.initJobs}
              initTools={graph.initTools}
              initSkills={graph.initSkills}
              systemPrompt={graph.systemPrompt}
              graphNodes={graph.graphNodes}
              graphEdges={graph.graphEdges}
              selectedNode={graph.selectedNode}
              onSelectNode={graph.setSelectedNode}
            />
          </div>
        </div>
      </Content>
      <PromptManagerModal
        open={promptModalOpen}
        onClose={() => setPromptModalOpen(false)}
      />
    </Layout>
  );
}

export default App;
