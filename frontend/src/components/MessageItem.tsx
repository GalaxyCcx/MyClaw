import { Typography } from "antd";
import type {
  MessageItem as MessageItemType,
  UserInputData,
  FinalAnswerData,
  ToolCallData,
  ToolResultData,
  ErrorData,
} from "../types";
import UserMessage from "./UserMessage";
import AssistantMessage from "./AssistantMessage";
import ToolCallCard from "./ToolCallCard";
import ToolResultCard from "./ToolResultCard";
import ErrorMessage from "./ErrorMessage";

const { Text } = Typography;

interface Props {
  message: MessageItemType;
}

function formatTime(ts: string): string {
  try {
    const d = new Date(ts);
    return d.toLocaleTimeString("zh-CN", { hour: "2-digit", minute: "2-digit", second: "2-digit" });
  } catch {
    return "";
  }
}

export default function MessageItem({ message }: Props) {
  const showTimestamp = message.type === "tool_call" || message.type === "tool_result";
  const time = showTimestamp ? formatTime(message.timestamp) : null;

  let content: React.ReactNode = null;
  switch (message.type) {
    case "user_input":
      content = <UserMessage data={message.data as UserInputData} />;
      break;
    case "final_answer":
      content = <AssistantMessage data={message.data as FinalAnswerData} />;
      break;
    case "tool_call":
      content = <ToolCallCard data={message.data as ToolCallData} />;
      break;
    case "tool_result":
      content = <ToolResultCard data={message.data as ToolResultData} />;
      break;
    case "error":
      content = <ErrorMessage data={message.data as ErrorData} />;
      break;
    default:
      return null;
  }

  return (
    <div>
      {time && (
        <div style={{ textAlign: "center", padding: "2px 0" }}>
          <Text type="secondary" style={{ fontSize: 11 }}>
            {time}
          </Text>
        </div>
      )}
      {content}
    </div>
  );
}
