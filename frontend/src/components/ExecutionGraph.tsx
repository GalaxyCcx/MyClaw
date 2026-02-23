import { useMemo, useCallback, useEffect } from "react";
import {
  ReactFlow,
  Background,
  type Node,
  type Edge,
  useNodesState,
  useEdgesState,
  useReactFlow,
  ReactFlowProvider,
  type NodeTypes,
  Handle,
  Position,
} from "@xyflow/react";
import dagre from "dagre";
import type { GraphNode, GraphEdge, GraphNodeStatus } from "../types";

import "@xyflow/react/dist/style.css";

const NODE_W = 180;
const NODE_H = 44;
const COLUMN_GAP = 60;

const TYPE_STYLES: Record<
  string,
  { bg: string; border: string; label: string }
> = {
  user_input: { bg: "#e6f7ff", border: "#1890ff", label: "User" },
  llm: { bg: "#f9f0ff", border: "#722ed1", label: "LLM" },
  tool: { bg: "#fff7e6", border: "#fa8c16", label: "Tool" },
  skill_doc: { bg: "#f0f5ff", border: "#2f54eb", label: "Skill Doc" },
  skill_tool: { bg: "#e8f5e9", border: "#388e3c", label: "Skill" },
  answer: { bg: "#f6ffed", border: "#52c41a", label: "Answer" },
  error: { bg: "#fff2f0", border: "#ff4d4f", label: "Error" },
};

const STATUS_STYLES: Record<GraphNodeStatus, React.CSSProperties> = {
  waiting: { borderStyle: "dashed", opacity: 0.5 },
  running: { boxShadow: "0 0 8px rgba(114,46,209,0.5)", animation: "pulse 1.2s infinite" },
  completed: { borderStyle: "solid" },
  error: { borderStyle: "solid", borderColor: "#ff4d4f" },
};

function CustomNode({ data }: { data: { label: string; nodeType: string; status: GraphNodeStatus } }) {
  const style = TYPE_STYLES[data.nodeType] || TYPE_STYLES.llm;
  const statusStyle = STATUS_STYLES[data.status] || {};

  const isToolShape = data.nodeType === "tool" || data.nodeType === "skill_doc" || data.nodeType === "skill_tool";
  const isLlm = data.nodeType === "llm";
  const isAnswer = data.nodeType === "answer";
  const isSkillDoc = data.nodeType === "skill_doc";
  const isSkillTool = data.nodeType === "skill_tool";

  const icon = isSkillDoc ? "📖" : isSkillTool ? "⚙️" : isLlm ? "🧠" : data.nodeType === "tool" ? "🔧" : isAnswer ? "💬" : data.nodeType === "user_input" ? "👤" : "";

  return (
    <div
      style={{
        padding: "6px 12px",
        borderRadius: isToolShape ? 4 : 8,
        background: style.bg,
        border: `2px ${statusStyle.borderStyle || "solid"} ${statusStyle.borderColor || style.border}`,
        fontSize: 11,
        fontWeight: 600,
        color: style.border,
        minWidth: 100,
        textAlign: "center",
        position: "relative",
        lineHeight: 1.4,
        ...statusStyle,
      }}
    >
      <Handle type="target" position={Position.Top} style={{ opacity: 0 }} />
      <div>{icon} {data.label}</div>
      {data.status === "completed" && (
        <span style={{ fontSize: 9, opacity: 0.7 }}> ✓</span>
      )}
      {data.status === "running" && (
        <span style={{ fontSize: 9, opacity: 0.7 }}> ...</span>
      )}
      <Handle type="source" position={Position.Bottom} style={{ opacity: 0 }} />
    </div>
  );
}

const nodeTypes: NodeTypes = {
  custom: CustomNode,
};

/**
 * Layout nodes per-turn as separate columns.
 * Each turn is a vertical dagre sub-graph, columns are placed left-to-right.
 * Cross-turn edges (Answer→UserInput) connect the columns.
 */
function getColumnLayout(
  nodes: Node[],
  edges: Edge[],
  graphNodes: GraphNode[],
): { nodes: Node[]; edges: Edge[] } {
  if (nodes.length === 0) return { nodes, edges };

  const turnMap = new Map<number, string[]>();
  const nodeById = new Map<string, Node>();
  nodes.forEach((n) => nodeById.set(n.id, n));

  const gnById = new Map<string, GraphNode>();
  graphNodes.forEach((gn) => gnById.set(gn.id, gn));

  for (const gn of graphNodes) {
    const turn = (gn.data.turn as number) || 1;
    if (!turnMap.has(turn)) turnMap.set(turn, []);
    turnMap.get(turn)!.push(gn.id);
  }

  const turns = Array.from(turnMap.keys()).sort((a, b) => a - b);
  if (turns.length === 0) turns.push(1);

  const positioned: Node[] = [];
  let xOffset = 0;

  for (const turn of turns) {
    const turnNodeIds = new Set(turnMap.get(turn) || []);
    const turnNodes = nodes.filter((n) => turnNodeIds.has(n.id));
    const turnEdges = edges.filter((e) => turnNodeIds.has(e.source) && turnNodeIds.has(e.target));

    if (turnNodes.length === 0) continue;

    const g = new dagre.graphlib.Graph();
    g.setDefaultEdgeLabel(() => ({}));
    g.setGraph({ rankdir: "TB", nodesep: 30, ranksep: 50 });

    turnNodes.forEach((n) => g.setNode(n.id, { width: NODE_W, height: NODE_H }));
    turnEdges.forEach((e) => g.setEdge(e.source, e.target));
    dagre.layout(g);

    let turnWidth = 0;
    for (const n of turnNodes) {
      const pos = g.node(n.id);
      const x = pos.x - NODE_W / 2 + xOffset;
      const y = pos.y - NODE_H / 2;
      positioned.push({ ...n, position: { x, y } });
      turnWidth = Math.max(turnWidth, pos.x + NODE_W / 2);
    }

    xOffset += turnWidth + COLUMN_GAP;
  }

  return { nodes: positioned, edges };
}

function ExecutionGraphInner({
  graphNodes,
  graphEdges,
  onNodeClick,
}: {
  graphNodes: GraphNode[];
  graphEdges: GraphEdge[];
  onNodeClick: (node: GraphNode) => void;
}) {
  const rfNodes: Node[] = useMemo(
    () =>
      graphNodes.map((n) => {
        const isSkillDoc = n.type === "tool" && n.id.includes("read_skill_doc");
        const hasActiveSkill = n.data?.active_skill;
        const isSkillTool = !isSkillDoc && n.type === "tool" && hasActiveSkill;

        let nodeType = n.type;
        if (isSkillDoc) nodeType = "skill_doc";
        else if (isSkillTool) nodeType = "skill_tool";

        return {
          id: n.id,
          type: "custom",
          position: { x: 0, y: 0 },
          data: {
            label: n.label,
            nodeType,
            status: n.status,
          },
        };
      }),
    [graphNodes],
  );

  const rfEdges: Edge[] = useMemo(
    () =>
      graphEdges.map((e) => ({
        id: e.id,
        source: e.source,
        target: e.target,
        animated: true,
        style: { stroke: "#999" },
      })),
    [graphEdges],
  );

  const { nodes: layoutedNodes, edges: layoutedEdges } = useMemo(
    () => getColumnLayout(rfNodes, rfEdges, graphNodes),
    [rfNodes, rfEdges, graphNodes],
  );

  const [nodes, setNodes, onNodesChange] = useNodesState(layoutedNodes);
  const [edges, setEdges, onEdgesChange] = useEdgesState(layoutedEdges);
  const { fitView } = useReactFlow();

  useEffect(() => {
    setNodes(layoutedNodes);
    setEdges(layoutedEdges);
    setTimeout(() => fitView({ padding: 0.3 }), 50);
  }, [layoutedNodes, layoutedEdges, setNodes, setEdges, fitView]);

  const handleNodeClick = useCallback(
    (_: unknown, node: Node) => {
      const gn = graphNodes.find((n) => n.id === node.id);
      if (gn) onNodeClick(gn);
    },
    [graphNodes, onNodeClick],
  );

  return (
    <ReactFlow
      nodes={nodes}
      edges={edges}
      onNodesChange={onNodesChange}
      onEdgesChange={onEdgesChange}
      onNodeClick={handleNodeClick}
      nodeTypes={nodeTypes}
      fitView
      proOptions={{ hideAttribution: true }}
      style={{ background: "#fafafa" }}
      nodesDraggable={false}
      nodesConnectable={false}
      elementsSelectable
      minZoom={0.2}
      maxZoom={2}
    >
      <Background gap={16} size={1} color="#e8e8e8" />
    </ReactFlow>
  );
}

interface Props {
  graphNodes: GraphNode[];
  graphEdges: GraphEdge[];
  onNodeClick: (node: GraphNode) => void;
}

export default function ExecutionGraph({ graphNodes, graphEdges, onNodeClick }: Props) {
  if (graphNodes.length === 0) return null;

  return (
    <ReactFlowProvider>
      <ExecutionGraphInner
        graphNodes={graphNodes}
        graphEdges={graphEdges}
        onNodeClick={onNodeClick}
      />
    </ReactFlowProvider>
  );
}
