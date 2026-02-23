import { Button, Input } from "antd";
import { SendOutlined } from "@ant-design/icons";
import { useState } from "react";

interface InputBarProps {
  onSend: (content: string) => void;
  disabled?: boolean;
}

export default function InputBar({ onSend, disabled }: InputBarProps) {
  const [value, setValue] = useState("");

  const handleSend = () => {
    const trimmed = value.trim();
    if (!trimmed) return;
    onSend(trimmed);
    setValue("");
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  return (
    <div
      style={{
        display: "flex",
        gap: 8,
        padding: "12px 16px",
        background: "#fff",
        borderTop: "1px solid #e8e8e8",
      }}
    >
      <Input.TextArea
        value={value}
        onChange={(e) => setValue(e.target.value)}
        onKeyDown={handleKeyDown}
        placeholder={disabled ? "Agent 正在思考..." : "输入消息，按 Enter 发送"}
        disabled={disabled}
        autoSize={{ minRows: 1, maxRows: 4 }}
        style={{ flex: 1 }}
      />
      <Button
        type="primary"
        icon={<SendOutlined />}
        onClick={handleSend}
        disabled={disabled || !value.trim()}
        style={{ alignSelf: "flex-end" }}
      >
        发送
      </Button>
    </div>
  );
}
