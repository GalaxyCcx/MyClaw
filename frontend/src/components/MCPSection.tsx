import { useState, useEffect } from "react";
import { Switch, Typography, Tooltip } from "antd";
import { ApiOutlined } from "@ant-design/icons";
import type { MCPInfo } from "../types";

const { Text } = Typography;

interface Props {
  onToggle?: () => void;
}

export default function MCPSection({ onToggle }: Props) {
  const [mcps, setMcps] = useState<MCPInfo[]>([]);
  const [loading, setLoading] = useState(false);

  const fetchMcps = async () => {
    try {
      const r = await fetch("/api/mcp");
      const data = await r.json();
      setMcps(data.mcps || []);
    } catch (e) {
      setMcps([]);
    }
  };

  useEffect(() => {
    fetchMcps();
  }, []);

  const handleToggle = async (mcpId: string, enabled: boolean) => {
    setLoading(true);
    try {
      const r = await fetch(`/api/mcp/${encodeURIComponent(mcpId)}/enabled`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ enabled }),
      });
      if (!r.ok) throw new Error(await r.text());
      setMcps((prev) =>
        prev.map((m) => (m.id === mcpId ? { ...m, enabled } : m))
      );
      onToggle?.();
      window.location.reload();
    } catch (e) {
      console.error("Failed to toggle MCP:", e);
    } finally {
      setLoading(false);
    }
  };

  if (mcps.length === 0) return null;

  return (
    <div style={{ marginBottom: 8 }}>
      <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 6 }}>
        <ApiOutlined style={{ color: "#1890ff", fontSize: 12 }} />
        <Text strong style={{ fontSize: 12, color: "#888", textTransform: "uppercase", letterSpacing: 0.5 }}>
          MCP 扩展
        </Text>
      </div>
      <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
        {mcps.map((mcp) => (
          <div
            key={mcp.id}
            style={{
              display: "flex",
              alignItems: "center",
              gap: 12,
              padding: "8px 12px",
              background: "#fff",
              border: "1px solid #f0f0f0",
              borderRadius: 6,
            }}
          >
            <div style={{ flex: 1, minWidth: 0 }}>
              <Text strong style={{ fontSize: 13 }}>{mcp.name}</Text>
              <div style={{ fontSize: 11, color: "#666", marginTop: 2 }}>
                {mcp.description}
              </div>
            </div>
            <Tooltip title={mcp.enabled ? "已启用，点击禁用" : "已禁用，点击启用"}>
              <Switch
                size="small"
                checked={mcp.enabled}
                loading={loading}
                onChange={(checked) => handleToggle(mcp.id, checked)}
              />
            </Tooltip>
          </div>
        ))}
      </div>
    </div>
  );
}
