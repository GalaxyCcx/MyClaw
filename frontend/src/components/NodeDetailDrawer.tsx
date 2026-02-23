import { Drawer, Tag, Typography, Collapse, Descriptions, Divider } from "antd";
import { Prism as SyntaxHighlighter } from "react-syntax-highlighter";
import { oneLight } from "react-syntax-highlighter/dist/esm/styles/prism";
import MarkdownRenderer from "./MarkdownRenderer";
import type { GraphNode } from "../types";

const { Text, Paragraph } = Typography;

interface Props {
  node: GraphNode | null;
  onClose: () => void;
}

function analyzeSkillContext(messages: Record<string, unknown>[]) {
  const skillMap = new Map<number, string>();
  let currentSkill: string | null = null;

  for (let i = 0; i < messages.length; i++) {
    const m = messages[i];
    const role = (m.role as string) || "";
    const toolCalls = m.tool_calls as { name: string; args: Record<string, unknown> }[] | undefined;
    const name = m.name as string | undefined;

    if (role === "ai" && toolCalls) {
      for (const tc of toolCalls) {
        if (tc.name === "read_skill_doc") {
          currentSkill = (tc.args?.skill_name as string) || null;
        }
      }
      if (currentSkill) skillMap.set(i, currentSkill);
    } else if (role === "tool") {
      if (name === "read_skill_doc" && currentSkill) {
        skillMap.set(i, currentSkill);
      } else if (currentSkill && (name === "python_executor" || name === "shell_executor")) {
        skillMap.set(i, currentSkill);
      }
    } else if (role === "ai" && !toolCalls) {
      currentSkill = null;
    }
  }
  return skillMap;
}

function MessageSnapshot({ messages }: { messages: Record<string, unknown>[] }) {
  if (!messages || messages.length === 0) {
    return <Text type="secondary">No messages</Text>;
  }

  const skillMap = analyzeSkillContext(messages);

  const items = messages.map((m, i) => {
    const role = (m.role as string) || "unknown";
    const content = (m.content as string) || "";
    const toolCalls = m.tool_calls as { name: string; args: Record<string, unknown> }[] | undefined;
    const name = m.name as string | undefined;
    const toolCallId = m.tool_call_id as string | undefined;
    const relatedSkill = skillMap.get(i);

    let label = role;
    let tagColor = "default";
    if (role === "human" || role === "user") {
      label = "User";
      tagColor = "blue";
    } else if (role === "ai") {
      label = toolCalls ? "AI → tool_call" : "AI → answer";
      tagColor = toolCalls ? "geekblue" : "purple";
    } else if (role === "tool") {
      if (name === "read_skill_doc") {
        label = `📖 读取 Skill 文档`;
        tagColor = "blue";
      } else if (relatedSkill) {
        label = `⚙️ ${relatedSkill} → ${name}`;
        tagColor = "green";
      } else {
        label = `Tool: ${name || "?"}`;
        tagColor = "orange";
      }
    } else if (role === "system") {
      label = "System Prompt";
      tagColor = "cyan";
    }

    const borderLeft = relatedSkill ? "3px solid #52c41a" : undefined;

    return {
      key: String(i),
      label: (
        <span style={{ display: "flex", alignItems: "center", gap: 6, flexWrap: "wrap" }}>
          <Tag color={tagColor} style={{ fontSize: 10, margin: 0 }}>{label}</Tag>
          {relatedSkill && role === "ai" && (
            <Tag color="green" style={{ fontSize: 9, margin: 0 }}>📦 {relatedSkill}</Tag>
          )}
          {toolCallId && <Tag color="default" style={{ fontSize: 9, margin: 0 }}>id: {toolCallId.slice(0, 12)}</Tag>}
          <span style={{ fontSize: 11, color: "#666", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap", maxWidth: 200 }}>
            {content ? content.slice(0, 50) + (content.length > 50 ? "..." : "") : "(no content)"}
          </span>
        </span>
      ),
      children: (
        <div style={{ fontSize: 12, borderLeft, paddingLeft: borderLeft ? 8 : 0 }}>
          {relatedSkill && (
            <div style={{ marginBottom: 6, padding: "2px 0" }}>
              <Tag color="green" style={{ fontSize: 10 }}>📦 Skill: {relatedSkill}</Tag>
              {role === "tool" && name === "read_skill_doc" && (
                <Text type="secondary" style={{ fontSize: 10 }}> — 渐进式披露：读取完整文档</Text>
              )}
              {role === "tool" && name !== "read_skill_doc" && (
                <Text type="secondary" style={{ fontSize: 10 }}> — 基于文档执行 Skill 能力</Text>
              )}
              {role === "ai" && toolCalls && (
                <Text type="secondary" style={{ fontSize: 10 }}> — LLM 决策调用 Skill</Text>
              )}
            </div>
          )}
          {content && (
            <div style={{ marginBottom: 8 }}>
              <MarkdownRenderer content={content} fontSize={12} />
            </div>
          )}
          {toolCalls && toolCalls.length > 0 && (
            <div>
              <Text strong style={{ fontSize: 11 }}>Tool Calls:</Text>
              {toolCalls.map((tc, j) => {
                const isSkillRead = tc.name === "read_skill_doc";
                const skillName = isSkillRead ? (tc.args?.skill_name as string) : null;
                const isSkillExec = !isSkillRead && relatedSkill && (tc.name === "python_executor" || tc.name === "shell_executor");
                return (
                  <div key={j} style={{ marginTop: 4 }}>
                    <div style={{ display: "flex", alignItems: "center", gap: 4, marginBottom: 2, flexWrap: "wrap" }}>
                      <Tag color={isSkillRead ? "blue" : isSkillExec ? "green" : "orange"}>{tc.name}</Tag>
                      {skillName && (
                        <Tag color="green" style={{ fontSize: 10 }}>📖 Skill: {skillName}</Tag>
                      )}
                      {isSkillExec && (
                        <Tag color="green" style={{ fontSize: 10 }}>📦 via {relatedSkill}</Tag>
                      )}
                    </div>
                    <SyntaxHighlighter language="json" style={oneLight} customStyle={{ fontSize: 11, padding: 8 }}>
                      {JSON.stringify(tc.args, null, 2)}
                    </SyntaxHighlighter>
                  </div>
                );
              })}
            </div>
          )}
        </div>
      ),
    };
  });

  return <Collapse items={items} size="small" />;
}

function LLMNodeDetail({ node }: { node: GraphNode }) {
  const snap = node.data.messages_snapshot as Record<string, unknown>[] | undefined;
  const hasToolCalls = node.data.has_tool_calls as boolean | undefined;
  const durationMs = node.data.duration_ms as number | undefined;

  const toolCallName = node.data.tool_call_name as string | undefined;
  const toolCallArgs = node.data.tool_call_args as Record<string, unknown> | undefined;

  return (
    <div>
      <Descriptions size="small" column={1} bordered style={{ marginBottom: 12 }}>
        <Descriptions.Item label="Node ID">{node.id}</Descriptions.Item>
        <Descriptions.Item label="Step">{node.step}</Descriptions.Item>
        <Descriptions.Item label="Decision">
          {hasToolCalls ? (
            <Tag color="orange">Call Tool: {toolCallName || "?"}</Tag>
          ) : (
            <Tag color="green">Generate Answer</Tag>
          )}
        </Descriptions.Item>
        {durationMs !== undefined && (
          <Descriptions.Item label="Duration">{durationMs.toFixed(1)}ms</Descriptions.Item>
        )}
      </Descriptions>

      {hasToolCalls && toolCallName && (
        <>
          <Divider orientation="left" style={{ margin: "8px 0", fontSize: 12 }}>
            LLM 工具调用决策
          </Divider>
          <div style={{ background: "#f0f5ff", border: "1px solid #adc6ff", borderRadius: 4, padding: 8, marginBottom: 12 }}>
            <div style={{ marginBottom: 4, display: "flex", alignItems: "center", gap: 6, flexWrap: "wrap" }}>
              <Tag color="geekblue">{toolCallName}</Tag>
              {toolCallName === "read_skill_doc" && toolCallArgs?.skill_name && (
                <Tag color="green" icon={<span style={{ marginRight: 2 }}>📖</span>}>
                  Skill: {toolCallArgs.skill_name as string}
                </Tag>
              )}
              {toolCallName !== "read_skill_doc" && node.data.active_skill && (
                <Tag color="green" icon={<span style={{ marginRight: 2 }}>📦</span>}>
                  via {node.data.active_skill as string}
                </Tag>
              )}
            </div>
            {toolCallArgs && (
              <SyntaxHighlighter language="json" style={oneLight} customStyle={{ fontSize: 11, padding: 8, margin: 0 }}>
                {JSON.stringify(toolCallArgs, null, 2)}
              </SyntaxHighlighter>
            )}
          </div>
        </>
      )}

      <Divider orientation="left" style={{ margin: "8px 0", fontSize: 12 }}>
        Messages Snapshot ({snap?.length || 0})
      </Divider>
      {snap && <MessageSnapshot messages={snap} />}
    </div>
  );
}

function ToolNodeDetail({ node }: { node: GraphNode }) {
  const toolName = node.data.tool_name as string | undefined;
  const args = node.data.arguments as Record<string, unknown> | undefined;
  const toolCallArgs = node.data.tool_call_args as Record<string, unknown> | undefined;
  const resultContent = node.data.result_content as string | undefined;
  const resultStatus = node.data.result_status as string | undefined;
  const durationMs = node.data.duration_ms as number | undefined;
  const activeSkill = node.data.active_skill as string | undefined;

  const effectiveArgs = args || toolCallArgs;
  const isSkillDoc = toolName === "read_skill_doc";
  const isSkillDriven = !!activeSkill && !isSkillDoc;

  return (
    <div>
      <Descriptions size="small" column={1} bordered style={{ marginBottom: 12 }}>
        <Descriptions.Item label="Tool">
          {isSkillDoc ? (
            <Tag color="blue" icon={<span style={{ marginRight: 4 }}>📖</span>}>
              {toolName} (渐进式披露)
            </Tag>
          ) : (
            <Tag color={isSkillDriven ? "green" : "orange"}>{toolName || node.label}</Tag>
          )}
        </Descriptions.Item>
        {(isSkillDoc || isSkillDriven) && (
          <Descriptions.Item label="关联 Skill">
            <Tag color="green" icon={<span style={{ marginRight: 4 }}>📦</span>}>
              {activeSkill || (effectiveArgs?.skill_name as string) || "?"}
            </Tag>
            {isSkillDoc && <Text type="secondary" style={{ fontSize: 11, marginLeft: 4 }}>读取 Skill 文档</Text>}
            {isSkillDriven && <Text type="secondary" style={{ fontSize: 11, marginLeft: 4 }}>执行 Skill 能力</Text>}
          </Descriptions.Item>
        )}
        <Descriptions.Item label="Node ID">{node.id}</Descriptions.Item>
        <Descriptions.Item label="Status">
          <Tag color={resultStatus === "success" ? "green" : "red"}>
            {resultStatus || node.status}
          </Tag>
        </Descriptions.Item>
        {durationMs !== undefined && (
          <Descriptions.Item label="Duration">{durationMs.toFixed(1)}ms</Descriptions.Item>
        )}
      </Descriptions>

      {effectiveArgs && (
        <>
          <Divider orientation="left" style={{ margin: "8px 0", fontSize: 12 }}>
            Tool Call Arguments
          </Divider>
          <div style={{ background: "#fff7e6", border: "1px solid #ffd591", borderRadius: 4, padding: 8, marginBottom: 12 }}>
            <SyntaxHighlighter language="json" style={oneLight} customStyle={{ fontSize: 11, padding: 8, margin: 0 }}>
              {JSON.stringify(effectiveArgs, null, 2)}
            </SyntaxHighlighter>
          </div>
        </>
      )}

      {resultContent && (
        <>
          <Divider orientation="left" style={{ margin: "8px 0", fontSize: 12 }}>
            Tool Result
          </Divider>
          <div style={{
            background: resultStatus === "success" ? "#f6ffed" : "#fff2f0",
            border: `1px solid ${resultStatus === "success" ? "#b7eb8f" : "#ffa39e"}`,
            borderRadius: 4,
            padding: 8,
          }}>
            <Paragraph
              style={{ fontSize: 12, maxHeight: 400, overflow: "auto", margin: 0, whiteSpace: "pre-wrap" }}
            >
              {resultContent}
            </Paragraph>
          </div>
        </>
      )}
    </div>
  );
}

function AnswerNodeDetail({ node }: { node: GraphNode }) {
  const content = node.data.content as string | undefined;
  return (
    <div>
      <Text strong style={{ display: "block", marginBottom: 8 }}>Final Answer</Text>
      {content ? <MarkdownRenderer content={content} fontSize={13} /> : <Text type="secondary">No content</Text>}
    </div>
  );
}

export default function NodeDetailDrawer({ node, onClose }: Props) {
  const isSkillDoc = node?.type === "tool" && node.id.includes("read_skill_doc");
  const activeSkill = node?.data?.active_skill as string | undefined;
  const isSkillDriven = !!activeSkill && !isSkillDoc;

  const title = node
    ? `${
        node.type === "llm"
          ? "LLM"
          : isSkillDoc
            ? "📖 Skill 文档读取"
            : isSkillDriven
              ? `📦 Skill: ${activeSkill}`
              : node.type === "tool"
                ? "Tool"
                : node.type === "answer"
                  ? "Answer"
                  : node.type
      } — ${node.label}`
    : "";

  return (
    <Drawer
      title={title}
      open={!!node}
      onClose={onClose}
      width={520}
      styles={{ body: { padding: 16 } }}
    >
      {node?.type === "llm" && <LLMNodeDetail node={node} />}
      {node?.type === "tool" && <ToolNodeDetail node={node} />}
      {node?.type === "answer" && <AnswerNodeDetail node={node} />}
      {node?.type === "user_input" && (
        <Text type="secondary">User input node — click LLM or Tool nodes for details.</Text>
      )}
    </Drawer>
  );
}
