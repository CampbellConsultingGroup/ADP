import React from "react";
import { useLLMConfig, useUpdateLLMConfig, useAvailableModels, type ModelInfo } from "../api/config";

export default function LLMSettings(): React.ReactElement {
  const { data: config, isLoading } = useLLMConfig();
  const { data: models } = useAvailableModels();
  const update = useUpdateLLMConfig();

  if (isLoading) return <div style={{ padding: 16, fontSize: 13 }}>Loading...</div>;

  const statusColor = config?.api_key_configured ? "#166534" : "#c0392b";
  const statusText = config?.api_key_configured
    ? `Connected (${config.provider})`
    : "API key not configured";

  return (
    <div style={{ padding: 16 }}>
      <h3 style={{ margin: "0 0 12px", fontSize: 14, fontWeight: 600 }}>LLM Settings</h3>

      <div style={{ marginBottom: 14, padding: 10, background: "#f5f5f5", borderRadius: 6 }}>
        <div style={{ fontSize: 12, color: "#555", marginBottom: 4 }}>Provider</div>
        <div style={{ fontSize: 13, fontWeight: 600 }}>Anthropic</div>
        <div style={{ fontSize: 12, color: statusColor, marginTop: 4 }}>
          ● {statusText}
        </div>
        {!config?.api_key_configured && (
          <div style={{ fontSize: 11, color: "#666", marginTop: 6 }}>
            Set <code style={{ background: "#e5e7eb", padding: "1px 4px", borderRadius: 3 }}>ADP_LLM_API_KEY</code> and restart the server.
          </div>
        )}
      </div>

      <div style={{ marginBottom: 12 }}>
        <label style={{ fontSize: 12, fontWeight: 600, display: "block", marginBottom: 4 }}>
          Extraction Model
        </label>
        <select
          value={config?.extraction_model ?? "claude-sonnet-4-6"}
          onChange={(e) => update.mutate({ extraction_model: e.target.value })}
          disabled={!config?.api_key_configured}
          style={{ width: "100%", padding: "6px 8px", fontSize: 13, border: "1px solid #ccc", borderRadius: 4 }}
        >
          {(models?.models ?? []).map((m: ModelInfo) => (
            <option key={m.id} value={m.id}>
              {m.name} — {m.tier}
            </option>
          ))}
        </select>
        <div style={{ fontSize: 11, color: "#888", marginTop: 3 }}>
          {models?.models.find((m: ModelInfo) => m.id === config?.extraction_model)?.description}
        </div>
      </div>

      <div style={{ marginBottom: 12 }}>
        <label style={{ fontSize: 12, fontWeight: 600, display: "block", marginBottom: 4 }}>
          Recommendation Model
        </label>
        <select
          value={config?.recommendation_model ?? "claude-sonnet-4-6"}
          onChange={(e) => update.mutate({ recommendation_model: e.target.value })}
          disabled={!config?.api_key_configured}
          style={{ width: "100%", padding: "6px 8px", fontSize: 13, border: "1px solid #ccc", borderRadius: 4 }}
        >
          {(models?.models ?? []).map((m: ModelInfo) => (
            <option key={m.id} value={m.id}>
              {m.name} — {m.tier}
            </option>
          ))}
        </select>
        <div style={{ fontSize: 11, color: "#888", marginTop: 3 }}>
          {models?.models.find((m: ModelInfo) => m.id === config?.recommendation_model)?.description}
        </div>
      </div>

      {update.isSuccess && (
        <div style={{ fontSize: 12, color: "#166534", marginTop: 8 }}>✓ Model preferences saved</div>
      )}
    </div>
  );
}
