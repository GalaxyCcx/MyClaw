import { Tooltip, Progress } from "antd";
import type { TokenUsage } from "../types";

interface Props {
  tokenUsage: TokenUsage;
  contextLimit: number;
  modelName: string;
}

function formatNum(n: number): string {
  if (n >= 1000) return (n / 1000).toFixed(1) + "k";
  return String(n);
}

export default function TokenUsageBar({ tokenUsage, contextLimit, modelName }: Props) {
  const { prompt_tokens, completion_tokens, total_tokens } = tokenUsage;
  const pct = contextLimit > 0 ? Math.min((total_tokens / contextLimit) * 100, 100) : 0;

  const strokeColor =
    pct < 50 ? "#52c41a" : pct < 80 ? "#faad14" : "#ff4d4f";

  const tipContent = (
    <div style={{ fontSize: 12, lineHeight: 1.8 }}>
      <div><b>模型</b>: {modelName || "unknown"}</div>
      <div><b>上下文窗口</b>: {formatNum(contextLimit)} tokens</div>
      <hr style={{ margin: "4px 0", border: "none", borderTop: "1px solid rgba(255,255,255,0.2)" }} />
      <div><b>Prompt tokens</b>: {formatNum(prompt_tokens)}</div>
      <div><b>Completion tokens</b>: {formatNum(completion_tokens)}</div>
      <div><b>当前合计</b>: {formatNum(total_tokens)} / {formatNum(contextLimit)}</div>
    </div>
  );

  if (total_tokens === 0) {
    return (
      <Tooltip title={`${modelName} | 上下文窗口 ${formatNum(contextLimit)} tokens`}>
        <div style={{ display: "flex", alignItems: "center", gap: 6, cursor: "default" }}>
          <span style={{ fontSize: 11, color: "#999", whiteSpace: "nowrap" }}>
            Token: 0 / {formatNum(contextLimit)}
          </span>
          <Progress
            percent={0}
            size="small"
            showInfo={false}
            strokeColor={strokeColor}
            style={{ width: 80, margin: 0 }}
          />
        </div>
      </Tooltip>
    );
  }

  return (
    <Tooltip title={tipContent}>
      <div style={{ display: "flex", alignItems: "center", gap: 6, cursor: "default" }}>
        <span style={{ fontSize: 11, color: pct > 80 ? "#ff4d4f" : "#666", whiteSpace: "nowrap" }}>
          Token: {formatNum(total_tokens)} / {formatNum(contextLimit)}
        </span>
        <Progress
          percent={Math.round(pct * 10) / 10}
          size="small"
          showInfo={false}
          strokeColor={strokeColor}
          style={{ width: 80, margin: 0 }}
        />
      </div>
    </Tooltip>
  );
}
