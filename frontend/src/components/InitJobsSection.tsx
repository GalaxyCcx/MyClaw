import { useState } from "react";
import {
  CheckCircleFilled,
  CloseCircleFilled,
  ExclamationCircleFilled,
  DownOutlined,
  RightOutlined,
  FileTextOutlined,
  ReadOutlined,
} from "@ant-design/icons";
import { Typography, Tag, Button } from "antd";
import type { InitJob, InitSkillInfo } from "../types";
import SkillDocModal from "./SkillDocModal";

const { Text } = Typography;

const statusConfig: Record<string, { icon: React.ReactNode }> = {
  success: { icon: <CheckCircleFilled style={{ color: "#52c41a" }} /> },
  error: { icon: <CloseCircleFilled style={{ color: "#ff4d4f" }} /> },
  warning: { icon: <ExclamationCircleFilled style={{ color: "#faad14" }} /> },
};

const JOB_LABELS: Record<string, string> = {
  load_config: "Load Config",
  load_system_prompt: "Load System Prompt",
  check_llm: "Check LLM Connection",
  discover_skills: "Discover Skills (metadata only)",
  register_tools: "Register Builtin Tools",
  check_mcp_chrome: "MCP Chrome Bridge",
};

function SkillListPanel({ skills, onViewDoc }: { skills: InitSkillInfo[]; onViewDoc: (name: string) => void }) {
  if (skills.length === 0) {
    return <Text type="secondary" style={{ fontSize: 11 }}>No skills discovered</Text>;
  }
  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 4 }}>
      {skills.map((s) => (
        <div
          key={s.name}
          style={{
            display: "flex",
            alignItems: "center",
            gap: 8,
            padding: "4px 8px",
            background: "#f0f5ff",
            borderRadius: 4,
            border: "1px solid #d6e4ff",
          }}
        >
          <Tag color="blue" style={{ margin: 0, fontSize: 11 }}>{s.name}</Tag>
          <span style={{ flex: 1, fontSize: 11, color: "#555", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
            {s.description}
          </span>
          <span style={{ fontSize: 10, color: "#999", whiteSpace: "nowrap" }}>
            {s.scripts.length} script(s)
          </span>
          <Button
            size="small"
            type="link"
            icon={<ReadOutlined />}
            onClick={(e) => { e.stopPropagation(); onViewDoc(s.name); }}
            style={{ fontSize: 11, padding: "0 4px" }}
          >
            查看文档
          </Button>
        </div>
      ))}
    </div>
  );
}

function JobRow({
  job,
  skills,
  onViewDoc,
}: {
  job: InitJob;
  skills?: InitSkillInfo[];
  onViewDoc?: (name: string) => void;
}) {
  const [expanded, setExpanded] = useState(false);
  const cfg = statusConfig[job.status] || statusConfig.error;
  const label = JOB_LABELS[job.name] || job.name;
  const isSkillJob = job.name === "discover_skills" && skills && skills.length > 0;

  return (
    <div
      style={{
        borderRadius: 4,
        background: "#fff",
        border: "1px solid #f0f0f0",
        fontSize: 12,
        overflow: "hidden",
      }}
    >
      <div
        onClick={() => setExpanded(!expanded)}
        style={{
          display: "flex",
          alignItems: "center",
          gap: 6,
          padding: "4px 8px",
          cursor: "pointer",
          userSelect: "none",
        }}
      >
        <span style={{ fontSize: 10, color: "#999", width: 10 }}>
          {expanded ? <DownOutlined /> : <RightOutlined />}
        </span>
        <span style={{ flexShrink: 0 }}>{cfg.icon}</span>
        <span style={{ flex: 1, fontWeight: 500 }}>{label}</span>
        {isSkillJob && (
          <Tag color="blue" style={{ fontSize: 10, margin: 0, lineHeight: "16px", padding: "0 4px" }}>
            {skills!.length} skill(s)
          </Tag>
        )}
        <span style={{ color: "#999", fontSize: 11, fontFamily: "monospace" }}>
          {job.duration_ms.toFixed(0)}ms
        </span>
      </div>
      {expanded && (
        <div
          style={{
            padding: "6px 8px 6px 32px",
            background: "#fafafa",
            borderTop: "1px solid #f0f0f0",
            fontSize: 11,
            color: "#666",
            lineHeight: 1.6,
          }}
        >
          <div style={{ fontFamily: "monospace", wordBreak: "break-all", whiteSpace: "pre-wrap", marginBottom: isSkillJob ? 6 : 0 }}>
            {job.detail || "—"}
          </div>
          {isSkillJob && onViewDoc && (
            <SkillListPanel skills={skills!} onViewDoc={onViewDoc} />
          )}
        </div>
      )}
    </div>
  );
}

function SystemPromptSection({ prompt }: { prompt: string }) {
  const [expanded, setExpanded] = useState(false);

  if (!prompt) return null;

  const skillMatch = prompt.match(/<available_skills>([\s\S]*?)<\/available_skills>/);
  const hasSkills = !!skillMatch;
  const skillBlock = skillMatch ? skillMatch[1].trim() : "";
  const skillNames = skillBlock.match(/name="([^"]+)"/g)?.map((m) => m.slice(6, -1)) || [];

  return (
    <div
      style={{
        borderRadius: 4,
        background: "#fff",
        border: "1px solid #f0f0f0",
        fontSize: 12,
        overflow: "hidden",
      }}
    >
      <div
        onClick={() => setExpanded(!expanded)}
        style={{
          display: "flex",
          alignItems: "center",
          gap: 6,
          padding: "4px 8px",
          cursor: "pointer",
          userSelect: "none",
        }}
      >
        <span style={{ fontSize: 10, color: "#999", width: 10 }}>
          {expanded ? <DownOutlined /> : <RightOutlined />}
        </span>
        <FileTextOutlined style={{ color: "#722ed1", fontSize: 13 }} />
        <span style={{ flex: 1, fontWeight: 500, color: "#722ed1" }}>
          Assembled System Prompt
        </span>
        {hasSkills && (
          <span style={{ display: "flex", gap: 2 }}>
            {skillNames.map((n) => (
              <Tag key={n} color="purple" style={{ fontSize: 10, margin: 0, lineHeight: "16px", padding: "0 4px" }}>
                {n}
              </Tag>
            ))}
          </span>
        )}
      </div>
      {expanded && (
        <div
          style={{
            padding: "8px 12px",
            background: "#fafbfc",
            borderTop: "1px solid #f0f0f0",
            fontSize: 11,
            color: "#333",
            fontFamily: "monospace",
            lineHeight: 1.7,
            whiteSpace: "pre-wrap",
            wordBreak: "break-word",
            maxHeight: 400,
            overflow: "auto",
          }}
        >
          {prompt}
        </div>
      )}
    </div>
  );
}

interface Props {
  jobs: InitJob[];
  skills?: InitSkillInfo[];
  systemPrompt?: string;
}

export default function InitJobsSection({ jobs, skills, systemPrompt }: Props) {
  const [viewingSkill, setViewingSkill] = useState<string | null>(null);

  if (jobs.length === 0 && !systemPrompt) return null;

  const allSuccess = jobs.every((j) => j.status === "success");
  const hasError = jobs.some((j) => j.status === "error");
  const hasWarning = jobs.some((j) => j.status === "warning");

  return (
    <div style={{ marginBottom: 8 }}>
      <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 6 }}>
        <Text strong style={{ fontSize: 12, color: "#888", textTransform: "uppercase", letterSpacing: 0.5 }}>
          Initialization
        </Text>
        {jobs.length > 0 && (
          <Text style={{ fontSize: 11, color: allSuccess ? "#52c41a" : hasError ? "#ff4d4f" : "#faad14" }}>
            {allSuccess ? `${jobs.length}/${jobs.length} passed` : hasError ? "has errors" : "has warnings"}
          </Text>
        )}
      </div>
      <div style={{ display: "flex", flexDirection: "column", gap: 2 }}>
        {jobs.map((job) => (
          <JobRow
            key={job.name}
            job={job}
            skills={job.name === "discover_skills" ? skills : undefined}
            onViewDoc={job.name === "discover_skills" ? setViewingSkill : undefined}
          />
        ))}
        {systemPrompt && <SystemPromptSection prompt={systemPrompt} />}
      </div>
      <SkillDocModal skillName={viewingSkill} onClose={() => setViewingSkill(null)} />
    </div>
  );
}
