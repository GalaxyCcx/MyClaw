import { useEffect, useState } from "react";
import { Modal, Input, Button, message, Spin, Alert, Typography } from "antd";

const { Text } = Typography;

interface Props {
  open: boolean;
  onClose: () => void;
}

export default function PromptManagerModal({ open, onClose }: Props) {
  const [content, setContent] = useState("");
  const [originalContent, setOriginalContent] = useState("");
  const [loading, setLoading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");
  const [updatedAt, setUpdatedAt] = useState<string | null>(null);

  useEffect(() => {
    if (!open) return;
    setLoading(true);
    setError("");
    fetch("/api/prompts/system")
      .then((r) => {
        if (!r.ok) throw new Error(`HTTP ${r.status}`);
        return r.json();
      })
      .then((data) => {
        setContent(data.content || "");
        setOriginalContent(data.content || "");
        setUpdatedAt(data.updated_at || null);
      })
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false));
  }, [open]);

  const handleSave = async () => {
    setSaving(true);
    try {
      const r = await fetch("/api/prompts/system", {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ content }),
      });
      if (!r.ok) throw new Error(`HTTP ${r.status}`);
      message.success("已保存，新对话将使用更新后的 Prompt");
      setOriginalContent(content);
      setUpdatedAt(new Date().toISOString());
    } catch (e) {
      message.error(`保存失败: ${e instanceof Error ? e.message : e}`);
    } finally {
      setSaving(false);
    }
  };

  const hasChanges = content !== originalContent;

  return (
    <Modal
      title="System Prompt 管理"
      open={open}
      onCancel={onClose}
      width={700}
      footer={
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
          <div>
            {updatedAt && (
              <Text type="secondary" style={{ fontSize: 11 }}>
                文件: prompts/system.md | 更新于: {new Date(updatedAt).toLocaleString()}
              </Text>
            )}
          </div>
          <div style={{ display: "flex", gap: 8 }}>
            <Button onClick={onClose}>取消</Button>
            <Button
              type="primary"
              onClick={handleSave}
              loading={saving}
              disabled={!hasChanges || loading}
            >
              保存
            </Button>
          </div>
        </div>
      }
      styles={{ body: { padding: "16px 24px" } }}
    >
      {loading && (
        <div style={{ textAlign: "center", padding: 40 }}>
          <Spin tip="加载中..." />
        </div>
      )}
      {error && <Alert type="error" message={`加载失败: ${error}`} style={{ marginBottom: 12 }} />}
      {!loading && !error && (
        <>
          <div style={{ marginBottom: 8, display: "flex", alignItems: "center", gap: 8 }}>
            <Text type="secondary" style={{ fontSize: 12 }}>
              编辑后保存，新对话将使用更新后的 Prompt。注意：skill 元数据由系统自动注入，无需手动添加。
            </Text>
            {hasChanges && (
              <Text style={{ fontSize: 11, color: "#fa8c16" }}>* 未保存</Text>
            )}
          </div>
          <Input.TextArea
            value={content}
            onChange={(e) => setContent(e.target.value)}
            rows={18}
            style={{
              fontFamily: "monospace",
              fontSize: 12,
              lineHeight: 1.6,
            }}
          />
        </>
      )}
    </Modal>
  );
}
