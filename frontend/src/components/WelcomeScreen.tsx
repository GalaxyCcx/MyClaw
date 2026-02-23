import { Typography, Space } from "antd";
import {
  RobotOutlined,
  FileTextOutlined,
  GlobalOutlined,
  CodeOutlined,
} from "@ant-design/icons";

const { Title, Text } = Typography;

const EXAMPLES = [
  { icon: <CodeOutlined />, text: "用 Python 计算斐波那契数列前 10 项" },
  { icon: <FileTextOutlined />, text: "帮我读取 backend/.env 文件内容" },
  { icon: <GlobalOutlined />, text: "抓取 https://example.com 的网页内容" },
];

interface Props {
  onExampleClick: (text: string) => void;
}

export default function WelcomeScreen({ onExampleClick }: Props) {
  return (
    <div
      style={{
        flex: 1,
        display: "flex",
        flexDirection: "column",
        alignItems: "center",
        justifyContent: "center",
        padding: 32,
        gap: 24,
      }}
    >
      <RobotOutlined style={{ fontSize: 48, color: "#52c41a" }} />
      <Title level={3} style={{ margin: 0, color: "#333" }}>
        MyClaw AI Agent
      </Title>
      <Text type="secondary" style={{ fontSize: 15 }}>
        我是一个通用 AI 助手，可以帮你读写文件、抓取网页、执行代码等。试试下面的示例：
      </Text>
      <Space direction="vertical" size={12} style={{ width: "100%", maxWidth: 480 }}>
        {EXAMPLES.map((ex) => (
          <div
            key={ex.text}
            onClick={() => onExampleClick(ex.text)}
            style={{
              display: "flex",
              alignItems: "center",
              gap: 12,
              padding: "12px 16px",
              background: "#fff",
              border: "1px solid #e8e8e8",
              borderRadius: 8,
              cursor: "pointer",
              transition: "all 0.2s",
            }}
            onMouseEnter={(e) => {
              e.currentTarget.style.borderColor = "#1677ff";
              e.currentTarget.style.background = "#f0f5ff";
            }}
            onMouseLeave={(e) => {
              e.currentTarget.style.borderColor = "#e8e8e8";
              e.currentTarget.style.background = "#fff";
            }}
          >
            <span style={{ fontSize: 18, color: "#1677ff" }}>{ex.icon}</span>
            <Text style={{ fontSize: 14 }}>{ex.text}</Text>
          </div>
        ))}
      </Space>
    </div>
  );
}
