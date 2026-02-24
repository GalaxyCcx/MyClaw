import { useCallback, useRef, useState } from "react";
import type {
  AgentEvent,
  GraphEdge,
  GraphNode,
  InitJob,
  InitSkillInfo,
  NodeEnterData,
  NodeExitData,
  InitStatusData,
  ToolCallData,
  ToolResultData,
  FinalAnswerData,
  TokenUsage,
  ContextPrunedData,
  ContextCompactedData,
  OverflowRecoveredData,
} from "../types";

let edgeCounter = 0;

function addEdge(edges: GraphEdge[], source: string, target: string): GraphEdge[] {
  const id = `e-${++edgeCounter}`;
  return [...edges, { id, source, target }];
}

export function useGraph() {
  const [initJobs, setInitJobs] = useState<InitJob[]>([]);
  const [initTools, setInitTools] = useState<{ name: string; source: string }[]>([]);
  const [initSkills, setInitSkills] = useState<InitSkillInfo[]>([]);
  const [systemPrompt, setSystemPrompt] = useState<string>("");
  const [modelName, setModelName] = useState<string>("");
  const [contextLimit, setContextLimit] = useState<number>(131072);
  const [tokenUsage, setTokenUsage] = useState<TokenUsage>({ prompt_tokens: 0, completion_tokens: 0, total_tokens: 0 });
  const [graphNodes, setGraphNodes] = useState<GraphNode[]>([]);
  const [graphEdges, setGraphEdges] = useState<GraphEdge[]>([]);
  const [selectedNode, setSelectedNode] = useState<GraphNode | null>(null);
  const [, setLastNodeId] = useState<string | null>(null);
  const turnRef = useRef(0);
  const activeSkillRef = useRef<string | null>(null);

  const handleGraphEvent = useCallback((event: AgentEvent) => {
    const patchLastActiveNode = (patch: Record<string, unknown>) => {
      setGraphNodes((prev) => {
        if (prev.length === 0) return prev;
        const next = [...prev];
        for (let i = next.length - 1; i >= 0; i--) {
          if (next[i].status === "running" || next[i].type === "llm" || next[i].type === "tool") {
            next[i] = { ...next[i], data: { ...next[i].data, ...patch } };
            break;
          }
        }
        return next;
      });
    };

    switch (event.type) {
      case "init_status": {
        const d = event.data as unknown as InitStatusData;
        setInitJobs(d.jobs);
        setInitTools(d.tools);
        setInitSkills(d.skills || []);
        setSystemPrompt(d.system_prompt || "");
        setModelName(d.model_name || "");
        setContextLimit(d.context_limit || 131072);
        setTokenUsage({ prompt_tokens: 0, completion_tokens: 0, total_tokens: 0 });
        setGraphNodes([]);
        setGraphEdges([]);
        setLastNodeId(null);
        setSelectedNode(null);
        turnRef.current = 0;
        edgeCounter = 0;
        break;
      }

      case "graph_reset": {
        turnRef.current += 1;
        const turn = turnRef.current;
        const userNode: GraphNode = {
          id: `user_${Date.now()}`,
          type: "user_input",
          label: "User Input",
          status: "completed",
          step: 0,
          data: { turn },
        };
        setGraphNodes((prev) => [...prev, userNode]);
        setLastNodeId((prevLast) => {
          if (prevLast) {
            setGraphEdges((prevEdges) => addEdge(prevEdges, prevLast, userNode.id));
          }
          return userNode.id;
        });
        break;
      }

      case "user_input": {
        const content = (event.data as { content?: string }).content || "";
        const preview = content.length > 30 ? content.slice(0, 30) + "..." : content;
        setGraphNodes((prev) => {
          const lastUserIdx = prev.length - 1;
          if (lastUserIdx >= 0 && prev[lastUserIdx].type === "user_input") {
            const updated = [...prev];
            updated[lastUserIdx] = {
              ...updated[lastUserIdx],
              label: `User: ${preview}`,
              data: { ...updated[lastUserIdx].data, content },
            };
            return updated;
          }
          return prev;
        });
        break;
      }

      case "node_enter": {
        const d = event.data as unknown as NodeEnterData;
        let label: string;
        let nodeType = d.node_type;
        const skill = activeSkillRef.current;

        if (d.node_type === "llm") {
          label = `LLM Call #${d.step}`;
        } else if (d.tool_name === "read_skill_doc") {
          label = skill ? `📖 读取 Skill: ${skill}` : "📖 Read Skill Doc";
          nodeType = "tool";
        } else if (skill && (d.tool_name === "python_executor" || d.tool_name === "shell_executor")) {
          const executor = d.tool_name === "python_executor" ? "Python" : "Shell";
          label = `⚙️ ${skill} → ${executor}`;
          nodeType = "tool";
        } else {
          label = `Run: ${d.tool_name || "tool"}`;
        }

        const newNode: GraphNode = {
          id: d.node_id,
          type: nodeType,
          label,
          status: "running",
          step: d.step,
          data: {
            ...(event.data as Record<string, unknown>),
            turn: turnRef.current,
            ...(skill ? { active_skill: skill } : {}),
          },
        };
        setGraphNodes((prev) => [...prev, newNode]);
        setLastNodeId((prevLast) => {
          if (prevLast) {
            setGraphEdges((prevEdges) => addEdge(prevEdges, prevLast, d.node_id));
          }
          return d.node_id;
        });
        break;
      }

      case "node_exit": {
        const d = event.data as unknown as NodeExitData;
        const evtData = event.data as Record<string, unknown>;
        const tu = evtData.token_usage as TokenUsage | undefined;
        if (tu && d.node_type === "llm") {
          setTokenUsage((prev) => ({
            prompt_tokens: tu.prompt_tokens || prev.prompt_tokens,
            completion_tokens: prev.completion_tokens + (tu.completion_tokens || 0),
            total_tokens: tu.total_tokens || prev.total_tokens,
          }));
        }
        setGraphNodes((prev) =>
          prev.map((n) => {
            if (n.id !== d.node_id) return n;
            const updated = {
              ...n,
              status: (d.status === "error" ? "error" : "completed") as GraphNode["status"],
              data: { ...n.data, ...event.data },
            };
            if (d.node_type === "llm") {
              updated.label = d.has_tool_calls
                ? `LLM #${d.step} → tool_call`
                : `LLM #${d.step} → answer`;
            }
            if (d.node_type === "tool") {
              const resultStatus = d.status === "error" ? "FAIL" : "OK";
              updated.label = `${n.label} [${resultStatus}]`;
            }
            return updated;
          }),
        );
        break;
      }

      case "tool_call": {
        const d = event.data as unknown as ToolCallData;
        if (d.name === "read_skill_doc") {
          const args = d.arguments as Record<string, unknown>;
          activeSkillRef.current = (args?.skill_name as string) || null;
        }
        setGraphNodes((prev) =>
          prev.map((n) => {
            if (n.type === "llm" && n.status === "running") {
              return {
                ...n,
                data: {
                  ...n.data,
                  tool_call_name: d.name,
                  tool_call_args: d.arguments,
                  tool_call_id: d.tool_call_id,
                },
              };
            }
            if (n.status === "running" && n.type === "tool") {
              return { ...n, data: { ...n.data, arguments: d.arguments, tool_call_id: d.tool_call_id } };
            }
            return n;
          }),
        );
        break;
      }

      case "tool_result": {
        const d = event.data as unknown as ToolResultData;
        setGraphNodes((prev) =>
          prev.map((n) => {
            if (n.type === "tool" && n.status === "running") {
              return {
                ...n,
                data: { ...n.data, result_content: d.content, result_status: d.status },
              };
            }
            return n;
          }),
        );
        break;
      }

      case "final_answer": {
        activeSkillRef.current = null;
        const d = event.data as unknown as FinalAnswerData;
        const ansNode: GraphNode = {
          id: `answer_${Date.now()}`,
          type: "answer",
          label: "Final Answer",
          status: "completed",
          step: event.step,
          data: { content: d.content, turn: turnRef.current },
        };
        setGraphNodes((prev) => [...prev, ansNode]);
        setLastNodeId((prevLast) => {
          if (prevLast) {
            setGraphEdges((prevEdges) => addEdge(prevEdges, prevLast, ansNode.id));
          }
          return ansNode.id;
        });
        break;
      }

      case "context_pruned": {
        const d = event.data as unknown as ContextPrunedData;
        patchLastActiveNode({
          context_pruned: {
            before_tokens: d.before_tokens,
            after_tokens: d.after_tokens,
            dropped_messages: d.dropped_messages,
            truncated_messages: d.truncated_messages || 0,
          },
        });
        break;
      }

      case "context_compacted": {
        const d = event.data as unknown as ContextCompactedData;
        patchLastActiveNode({
          context_compacted: {
            before_tokens: d.before_tokens,
            after_tokens: d.after_tokens,
            summary_chars: d.summary_chars,
            compacted_turns: d.compacted_turns || 0,
          },
        });
        break;
      }

      case "overflow_recovered": {
        const d = event.data as unknown as OverflowRecoveredData;
        patchLastActiveNode({
          overflow_recovered: {
            retry_count: d.retry_count,
            success: d.success,
            reason: d.reason,
          },
        });
        break;
      }
    }
  }, []);

  return {
    initJobs,
    initTools,
    initSkills,
    systemPrompt,
    modelName,
    contextLimit,
    tokenUsage,
    graphNodes,
    graphEdges,
    selectedNode,
    setSelectedNode,
    handleGraphEvent,
  };
}
