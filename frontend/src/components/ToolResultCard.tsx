import { Card, Tag, Typography } from "antd";
import { CheckCircleOutlined, CloseCircleOutlined, DownOutlined, RightOutlined } from "@ant-design/icons";
import { useState } from "react";
import { Prism as SyntaxHighlighter } from "react-syntax-highlighter";
import { oneLight } from "react-syntax-highlighter/dist/esm/styles/prism";
import type { ToolResultData } from "../types";

const { Text } = Typography;

const CODE_TOOLS = new Set(["python_executor", "shell_executor"]);
const FILE_TOOLS = new Set(["read_file"]);
const MAX_COLLAPSED_LINES = 8;

interface Props {
  data: ToolResultData;
}

function guessLanguage(name: string, content: string): string | null {
  if (CODE_TOOLS.has(name)) return "python";
  if (FILE_TOOLS.has(name)) {
    if (content.trimStart().startsWith("{") || content.trimStart().startsWith("[")) return "json";
    if (content.includes("import ") || content.includes("def ")) return "python";
    if (content.includes("server:") || content.includes("host:")) return "yaml";
  }
  return null;
}

export default function ToolResultCard({ data }: Props) {
  const isSuccess = data.status === "success";
  const lines = data.content.split("\n");
  const isLong = lines.length > MAX_COLLAPSED_LINES;
  const [expanded, setExpanded] = useState(!isLong);
  const lang = guessLanguage(data.name, data.content);
  const displayContent = expanded ? data.content : lines.slice(0, MAX_COLLAPSED_LINES).join("\n") + "\n...";

  return (
    <div style={{ padding: "4px 56px" }}>
      <Card
        size="small"
        style={{
          background: isSuccess ? "#f6ffed" : "#fff2f0",
          border: `1px solid ${isSuccess ? "#b7eb8f" : "#ffccc7"}`,
          borderRadius: 8,
        }}
      >
        <div
          style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 8, cursor: "pointer" }}
          onClick={() => setExpanded(!expanded)}
        >
          {isSuccess ? (
            <CheckCircleOutlined style={{ color: "#52c41a" }} />
          ) : (
            <CloseCircleOutlined style={{ color: "#ff4d4f" }} />
          )}
          <span style={{ fontWeight: 600, fontSize: 13 }}>执行结果</span>
          <Tag color={isSuccess ? "success" : "error"}>{data.name}</Tag>
          <Tag color={isSuccess ? "green" : "red"}>{isSuccess ? "成功" : "失败"}</Tag>
          <span style={{ marginLeft: "auto", color: "#999", fontSize: 12 }}>
            {expanded ? <DownOutlined /> : <RightOutlined />}
            {isLong && <Text type="secondary" style={{ marginLeft: 4, fontSize: 12 }}>{lines.length} 行</Text>}
          </span>
        </div>
        {lang ? (
          <SyntaxHighlighter
            language={lang}
            style={oneLight}
            customStyle={{
              margin: 0,
              padding: 8,
              borderRadius: 4,
              fontSize: 12,
              maxHeight: expanded ? 500 : 200,
              overflow: "auto",
            }}
          >
            {displayContent}
          </SyntaxHighlighter>
        ) : (
          <pre
            style={{
              margin: 0,
              padding: 8,
              background: "rgba(0,0,0,0.04)",
              borderRadius: 4,
              fontSize: 12,
              overflow: "auto",
              maxHeight: expanded ? 500 : 200,
              whiteSpace: "pre-wrap",
              wordBreak: "break-word",
            }}
          >
            {displayContent}
          </pre>
        )}
      </Card>
    </div>
  );
}
