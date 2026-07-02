import React, { useState } from "react";
import { useSubmitIntake } from "../api/intake";
import { useLLMConfig } from "../api/config";
import ModelSelector from "./ModelSelector";

interface IntakeTextFormProps {
  designId: string;
  onOperationCreated: (operationId: string) => void;
}

export default function IntakeTextForm({ designId, onOperationCreated }: IntakeTextFormProps): React.ReactElement {
  const [text, setText] = useState("");
  const { data: llmConfig } = useLLMConfig();
  const [selectedModel, setSelectedModel] = useState<string>(llmConfig?.extraction_model ?? "claude-sonnet-4-6");
  const submit = useSubmitIntake(designId);

  // Sync selected model with global config default when it loads
  React.useEffect(() => {
    if (llmConfig?.extraction_model && !submit.isPending) {
      setSelectedModel(llmConfig.extraction_model);
    }
  }, [llmConfig?.extraction_model]);

  const tooShort = text.length < 20 && text.length > 0;
  const hasApiKey = llmConfig?.api_key_configured ?? false;
  const canSubmit = text.length >= 20 && !submit.isPending;

  const handleSubmit = () => {
    submit.mutate(
      { mode: "bulk_text", text, model: selectedModel },
      { onSuccess: (data) => onOperationCreated(data.operation_id) },
    );
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

      {/* Model selector + Extract button row */}
      <div style={{ display: "flex", alignItems: "center", gap: 12, marginTop: 10, flexWrap: "wrap" }}>
        <button
          disabled={!canSubmit || !hasApiKey}
          onClick={handleSubmit}
          title={!hasApiKey ? "Set ADP_LLM_API_KEY to enable extraction" : undefined}
          style={{
            padding: "8px 18px",
            background: canSubmit && hasApiKey ? "#1168BD" : "#ccc",
            color: "#fff",
            border: "none",
            borderRadius: 4,
            cursor: canSubmit && hasApiKey ? "pointer" : "not-allowed",
            fontSize: 14,
            fontWeight: 600,
            flexShrink: 0,
          }}
        >
          {submit.isPending ? "Extracting..." : "Extract Requirements"}
        </button>
        <ModelSelector purpose="extraction" value={selectedModel} onChange={setSelectedModel} />
      </div>

      <div style={{ marginTop: 8, padding: "7px 10px", background: "#FEF9C3", border: "1px solid #FDE68A", borderRadius: 4, fontSize: 12, color: "#92400E" }}>
        ⚠ Source text is not stored after extraction
      </div>

      {submit.isError && <div style={{ marginTop: 8, color: "#c0392b", fontSize: 13 }}>Extraction failed. Check the server logs.</div>}
    </div>
  );
}
