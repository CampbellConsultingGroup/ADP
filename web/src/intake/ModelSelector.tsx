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
  lite: "var(--ink-3)",
  standard: "var(--accent)",
  premium: "var(--biz)",
};

export default function ModelSelector({ purpose, value, onChange }: ModelSelectorProps): React.ReactElement {
  const { data: modelsData, isLoading } = useAvailableModels();
  const { data: config } = useLLMConfig();

  if (isLoading) return <span style={{ fontSize: 12, color: "var(--ink-3)" }}>Loading models...</span>;

  const models = (modelsData?.models ?? []).filter(
    (m: ModelInfo) => m.recommended_for.includes(purpose)
  );

  if (!config?.api_key_configured) {
    return (
      <span style={{ fontSize: 12, color: "var(--crit)" }}>
        ⚠ ADP_LLM_API_KEY not set
      </span>
    );
  }

  return (
    <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
      <label style={{ fontSize: 12, color: "var(--ink-2)", whiteSpace: "nowrap" }}>
        Model:
      </label>
      <select
        value={value}
        onChange={(e) => onChange(e.target.value)}
        style={{ fontSize: 12, padding: "3px 6px", border: "1px solid var(--border)", borderRadius: 4, background: "var(--surface)", color: "var(--ink)" }}
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
            background: TIER_BADGE[models.find((m: ModelInfo) => m.id === value)?.tier ?? "standard"] ?? "var(--ink-3)",
            color: "var(--surface)",
          }}
        >
          {models.find((m: ModelInfo) => m.id === value)?.tier ?? ""}
        </span>
      )}
    </div>
  );
}
