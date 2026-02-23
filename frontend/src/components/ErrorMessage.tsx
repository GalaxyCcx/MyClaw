import { Alert } from "antd";
import type { ErrorData } from "../types";

interface Props {
  data: ErrorData;
}

export default function ErrorMessage({ data }: Props) {
  return (
    <div style={{ padding: "8px 56px" }}>
      <Alert
        type="error"
        message={data.message}
        description={data.detail}
        showIcon
        style={{ borderRadius: 8 }}
      />
    </div>
  );
}
