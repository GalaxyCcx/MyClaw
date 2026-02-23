import { Card, Tag } from "antd";
import { ToolOutlined } from "@ant-design/icons";
import type { ToolCallData } from "../types";

interface Props {
  data: ToolCallData;
}

export default function ToolCallCard({ data }: Props) {
  return (
    <div style={{ padding: "4px 56px" }}>
      <Card
        size="small"
        style={{
          background: "#fafafa",
          border: "1px solid #e8e8e8",
          borderRadius: 8,
        }}
      >
        <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 8 }}>
          <ToolOutlined style={{ color: "#1677ff" }} />
          <span style={{ fontWeight: 600, fontSize: 13 }}>工具调用</span>
          <Tag color="blue">{data.name}</Tag>
        </div>
        <pre
          style={{
            margin: 0,
            padding: 8,
            background: "#f0f0f0",
            borderRadius: 4,
            fontSize: 12,
            overflow: "auto",
            maxHeight: 200,
          }}
        >
          {JSON.stringify(data.arguments, null, 2)}
        </pre>
      </Card>
    </div>
  );
}
