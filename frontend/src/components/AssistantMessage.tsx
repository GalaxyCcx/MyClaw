import { RobotOutlined } from "@ant-design/icons";
import MarkdownRenderer from "./MarkdownRenderer";
import type { FinalAnswerData } from "../types";

interface Props {
  data: FinalAnswerData;
}

export default function AssistantMessage({ data }: Props) {
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
          maxWidth: "75%",
          background: "#fff",
          border: "1px solid #e8e8e8",
          padding: "12px 20px",
          borderRadius: "12px 12px 12px 2px",
          wordBreak: "break-word",
        }}
      >
        <MarkdownRenderer content={data.content} />
      </div>
    </div>
  );
}
