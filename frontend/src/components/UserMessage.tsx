import { UserOutlined } from "@ant-design/icons";
import type { UserInputData } from "../types";

interface Props {
  data: UserInputData;
}

export default function UserMessage({ data }: Props) {
  return (
    <div style={{ display: "flex", justifyContent: "flex-end", padding: "8px 16px" }}>
      <div
        style={{
          maxWidth: "70%",
          background: "#1677ff",
          color: "#fff",
          padding: "10px 16px",
          borderRadius: "12px 12px 2px 12px",
          fontSize: 14,
          lineHeight: 1.6,
          wordBreak: "break-word",
        }}
      >
        {data.content}
      </div>
      <div
        style={{
          width: 32,
          height: 32,
          borderRadius: "50%",
          background: "#1677ff",
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          marginLeft: 8,
          flexShrink: 0,
        }}
      >
        <UserOutlined style={{ color: "#fff", fontSize: 14 }} />
      </div>
    </div>
  );
}
