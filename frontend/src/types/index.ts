export type EventType =
  | "user_input"
  | "llm_token"
  | "tool_call"
  | "tool_result"
  | "final_answer"
  | "error"
  | "init_status"
  | "graph_reset"
  | "node_enter"
  | "node_exit"
  | "context_pruned"
  | "context_compacted"
  | "overflow_recovered";

export interface AgentEvent {
  type: EventType;
  step: number;
  timestamp: string;
  data: Record<string, unknown>;
}

export interface UserInputData {
  content: string;
}

export interface LLMTokenData {
  token: string;
}

export interface ToolCallData {
  tool_call_id: string;
  name: string;
  arguments: Record<string, unknown>;
}

export interface ToolResultData {
  tool_call_id: string;
  name: string;
  status: "success" | "error";
  content: string;
}

export interface FinalAnswerData {
  content: string;
}

export interface ErrorData {
  message: string;
  detail?: string;
}

export interface MessageItem {
  id: string;
  type: EventType;
  step: number;
  timestamp: string;
  data: Record<string, unknown>;
}

// --- Graph types ---

export interface InitJob {
  name: string;
  status: "success" | "error" | "warning";
  detail: string;
  duration_ms: number;
}

export interface InitSkillInfo {
  name: string;
  description: string;
  scripts: string[];
}

export interface TokenUsage {
  prompt_tokens: number;
  completion_tokens: number;
  total_tokens: number;
}

export interface InitStatusData {
  jobs: InitJob[];
  tools: { name: string; source: string }[];
  skills?: InitSkillInfo[];
  system_prompt?: string;
  model_name?: string;
  context_limit?: number;
}

export interface NodeEnterData {
  node_type: "llm" | "tool";
  node_id: string;
  step: number;
  messages_snapshot?: Record<string, unknown>[];
  tool_name?: string;
}

export interface NodeExitData {
  node_type: "llm" | "tool";
  node_id: string;
  step: number;
  has_tool_calls?: boolean;
  status?: string;
  duration_ms: number;
}

export interface ContextPrunedData {
  before_tokens: number;
  after_tokens: number;
  dropped_messages: number;
  truncated_messages?: number;
}

export interface ContextCompactedData {
  before_tokens: number;
  after_tokens: number;
  summary_chars: number;
  compacted_turns?: number;
}

export interface OverflowRecoveredData {
  retry_count: number;
  success: boolean;
  reason: string;
}

export type GraphNodeStatus = "waiting" | "running" | "completed" | "error";

export interface GraphNode {
  id: string;
  type: "user_input" | "llm" | "tool" | "answer" | "error";
  label: string;
  status: GraphNodeStatus;
  step: number;
  data: Record<string, unknown>;
}

export interface GraphEdge {
  id: string;
  source: string;
  target: string;
}
