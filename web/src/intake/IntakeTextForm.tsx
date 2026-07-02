import React, { useState } from "react";
import { useSubmitIntake } from "../api/intake";

interface IntakeTextFormProps {
  designId: string;
  onOperationCreated: (operationId: string) => void;
}

export default function IntakeTextForm({ designId, onOperationCreated }: IntakeTextFormProps): React.ReactElement {
  const [text, setText] = useState("");
  const submit = useSubmitIntake(designId);

  const tooShort = text.length < 20 && text.length > 0;
  const canSubmit = text.length >= 20 && !submit.isPending;

  const handleSubmit = () => {
    submit.mutate({ mode: "bulk_text", text }, {
      onSuccess: (data) => onOperationCreated(data.operation_id),
    });
  };

  return (
    <div>
      <textarea
        value={text}
        onChange={(e) => setText(e.target.value)}
        placeholder="Paste requirements, user stories, or notes... (minimum 20 characters)"
        rows={8}
        style={{ width: "100%", padding: 10, fontSize: 13, border: "1px solid #ccc", borderRadius: 4, resize: "vertical", boxSizing: "border-box" }}
      />
      {tooShort && <div style={{ fontSize: 12, color: "#c0392b", marginTop: 4 }}>Text must be at least 20 characters.</div>}
      <div style={{ marginTop: 8, padding: "8px 10px", background: "#FEF9C3", border: "1px solid #FDE68A", borderRadius: 4, fontSize: 12, color: "#92400E" }}>
        ⚠ Source text is not stored after extraction
      </div>
      <button
        disabled={!canSubmit}
        onClick={handleSubmit}
        style={{ marginTop: 10, padding: "8px 18px", background: canSubmit ? "#1168BD" : "#ccc", color: "#fff", border: "none", borderRadius: 4, cursor: canSubmit ? "pointer" : "not-allowed", fontSize: 14, fontWeight: 600 }}
      >
        {submit.isPending ? "Extracting..." : "Extract Requirements"}
      </button>
      {submit.isError && <div style={{ marginTop: 8, color: "#c0392b", fontSize: 13 }}>Extraction failed. Please try again.</div>}
    </div>
  );
}
