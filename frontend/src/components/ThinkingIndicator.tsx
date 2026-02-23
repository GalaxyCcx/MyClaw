import { RobotOutlined, LoadingOutlined } from "@ant-design/icons";

export default function ThinkingIndicator() {
  return (
    <div style={{ display: "flex", justifyContent: "flex-start", padding: "8px 16px" }}>
      <div
        style={{
          width: 32,
          height: 32,
          borderRadius: "50%",
          background: "#52c41a",
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          marginRight: 8,
          flexShrink: 0,
        }}
      >
        <RobotOutlined style={{ color: "#fff", fontSize: 14 }} />
      </div>
      <div
        style={{
          background: "#fff",
          border: "1px solid #e8e8e8",
          padding: "10px 16px",
          borderRadius: "12px 12px 12px 2px",
          fontSize: 14,
          color: "#999",
          display: "flex",
          alignItems: "center",
          gap: 8,
        }}
      >
        <LoadingOutlined spin />
        Agent 正在思考...
      </div>
    </div>
  );
}
