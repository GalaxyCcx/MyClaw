import { useEffect, useState } from "react";
import { Modal, Spin, Alert } from "antd";
import MarkdownRenderer from "./MarkdownRenderer";

interface Props {
  skillName: string | null;
  onClose: () => void;
}

export default function SkillDocModal({ skillName, onClose }: Props) {
  const [doc, setDoc] = useState<string>("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string>("");

  useEffect(() => {
    if (!skillName) {
      setDoc("");
      setError("");
      return;
    }
    setLoading(true);
    setError("");
    fetch(`/api/skills/${encodeURIComponent(skillName)}/doc`)
      .then((r) => {
        if (!r.ok) throw new Error(`HTTP ${r.status}`);
        return r.json();
      })
      .then((data) => {
        setDoc(data.doc || "(empty)");
      })
      .catch((e) => {
        setError(e.message);
      })
      .finally(() => setLoading(false));
  }, [skillName]);

  return (
    <Modal
      title={`Skill 文档 — ${skillName}`}
      open={!!skillName}
      onCancel={onClose}
      footer={null}
      width={640}
      styles={{ body: { maxHeight: "70vh", overflow: "auto", padding: "16px 24px" } }}
    >
      {loading && (
        <div style={{ textAlign: "center", padding: 40 }}>
          <Spin tip="加载文档中..." />
        </div>
      )}
      {error && <Alert type="error" message={`加载失败: ${error}`} />}
      {!loading && !error && doc && (
        <MarkdownRenderer content={doc} fontSize={13} />
      )}
    </Modal>
  );
}
