import { Typography, Divider } from "antd";
import type { GraphEdge, GraphNode, InitJob, InitSkillInfo } from "../types";
import InitJobsSection from "./InitJobsSection";
import MCPSection from "./MCPSection";
import ExecutionGraph from "./ExecutionGraph";
import NodeDetailDrawer from "./NodeDetailDrawer";

const { Text } = Typography;

interface Props {
  initJobs: InitJob[];
  initTools: { name: string; source: string }[];
  initSkills: InitSkillInfo[];
  systemPrompt: string;
  graphNodes: GraphNode[];
  graphEdges: GraphEdge[];
  selectedNode: GraphNode | null;
  onSelectNode: (node: GraphNode | null) => void;
}

export default function GraphPanel({
  initJobs,
  initSkills,
  systemPrompt,
  graphNodes,
  graphEdges,
  selectedNode,
  onSelectNode,
}: Props) {
  return (
    <div
      style={{
        height: "100%",
        display: "flex",
        flexDirection: "column",
        background: "#fafafa",
        borderLeft: "1px solid #e8e8e8",
        overflow: "hidden",
      }}
    >
      <div style={{ padding: "12px 16px 0", flexShrink: 0 }}>
        <InitJobsSection jobs={initJobs} skills={initSkills} systemPrompt={systemPrompt} />
        <MCPSection />
        {initJobs.length > 0 && graphNodes.length > 0 && (
          <Divider style={{ margin: "8px 0" }} />
        )}
      </div>
      <div style={{ flex: 1, position: "relative" }}>
        {graphNodes.length === 0 ? (
          <div style={{ display: "flex", alignItems: "center", justifyContent: "center", height: "100%" }}>
            <Text type="secondary" style={{ fontSize: 13 }}>
              发送消息后，执行图将在此显示
            </Text>
          </div>
        ) : (
          <ExecutionGraph
            graphNodes={graphNodes}
            graphEdges={graphEdges}
            onNodeClick={onSelectNode}
          />
        )}
      </div>
      <NodeDetailDrawer
        node={selectedNode}
        onClose={() => onSelectNode(null)}
      />
    </div>
  );
}
