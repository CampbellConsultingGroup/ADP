import React from "react";
import { useAvailableModels, useLLMConfig, type ModelInfo } from "../api/config";

interface ModelSelectorProps {
  /** Which pipeline this selector controls */
  purpose: "extraction" | "recommendations";
  /** Currently selected model id (controlled) */
  value: string;
  onChange: (modelId: string) => void;
}

const TIER_BADGE: Record<string, string> = {
  lite: "#6B7280",
  standard: "#1D4ED8",
  premium: "#7C3AED",
};

export default function ModelSelector({ purpose, value, onChange }: ModelSelectorProps): React.ReactElement {
  const { data: modelsData, isLoading } = useAvailableModels();
  const { data: config } = useLLMConfig();

  if (isLoading) return <span style={{ fontSize: 12, color: "#888" }}>Loading models...</span>;

  const models = (modelsData?.models ?? []).filter(
    (m: ModelInfo) => m.recommended_for.includes(purpose)
  );

  if (!config?.api_key_configured) {
    return (
      <span style={{ fontSize: 12, color: "#c0392b" }}>
        ⚠ ADP_LLM_API_KEY not set
      </span>
    );
  }

  return (
    <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
      <label style={{ fontSize: 12, color: "#555", whiteSpace: "nowrap" }}>
        Model:
      </label>
      <select
        value={value}
        onChange={(e) => onChange(e.target.value)}
        style={{ fontSize: 12, padding: "3px 6px", border: "1px solid #ccc", borderRadius: 4 }}
      >
        {(modelsData?.models ?? []).map((m: ModelInfo) => (
          <option key={m.id} value={m.id}>
            {m.name} {m.recommended_for.includes(purpose) ? "" : "(not recommended)"}
          </option>
        ))}
      </select>
      {models.find((m: ModelInfo) => m.id === value) && (
        <span
          style={{
            fontSize: 10,
            fontWeight: "bold",
            padding: "1px 5px",
            borderRadius: 3,
            background: TIER_BADGE[models.find((m: ModelInfo) => m.id === value)?.tier ?? "standard"] ?? "#888",
            color: "#fff",
          }}
        >
          {models.find((m: ModelInfo) => m.id === value)?.tier ?? ""}
        </span>
      )}
    </div>
  );
}
