import React, { useState } from "react";
import { useLLMConfig, useUpdateLLMConfig, useAvailableModels, type ModelInfo } from "../api/config";

export default function LLMSettings(): React.ReactElement {
  const { data: config, isLoading } = useLLMConfig();
  const { data: models } = useAvailableModels();
  const update = useUpdateLLMConfig();

  const [apiKeyDraft, setApiKeyDraft] = useState("");
  const [keySaved, setKeySaved] = useState(false);

  if (isLoading) return <div style={{ padding: 16, fontSize: 13 }}>Loading...</div>;

  const connected = config?.api_key_configured ?? false;
  const statusColor = connected ? "var(--good)" : "var(--crit)";
  const statusText = connected ? `Connected (${config?.provider})` : "API key not configured";

  function handleSaveKey() {
    if (!apiKeyDraft.trim()) return;
    update.mutate(
      { api_key: apiKeyDraft.trim() },
      {
        onSuccess: () => {
          setApiKeyDraft("");
          setKeySaved(true);
          setTimeout(() => setKeySaved(false), 3000);
        },
      }
    );
  }

  return (
    <div style={{ padding: 16 }}>
      <h3 style={{ margin: "0 0 12px", fontSize: 14, fontWeight: 600 }}>LLM Settings</h3>

      <div style={{ marginBottom: 14, padding: 10, background: "var(--surface-2)", borderRadius: 6 }}>
        <div style={{ fontSize: 12, color: "var(--ink-2)", marginBottom: 4 }}>Provider</div>
        <div style={{ fontSize: 13, fontWeight: 600 }}>Anthropic</div>
        <div style={{ fontSize: 12, color: statusColor, marginTop: 4 }}>
          ● {statusText}
        </div>
      </div>

      <div style={{ marginBottom: 14 }}>
        <label style={{ fontSize: 12, fontWeight: 600, display: "block", marginBottom: 4 }}>
          {connected ? "Update API Key" : "API Key"}
        </label>
        <div style={{ display: "flex", gap: 6 }}>
          <input
            type="password"
            value={apiKeyDraft}
            onChange={(e) => setApiKeyDraft(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && handleSaveKey()}
            placeholder={connected ? "Enter new key to replace…" : "sk-ant-…"}
            style={{
              flex: 1,
              padding: "6px 8px",
              fontSize: 13,
              border: "1px solid var(--border)",
              borderRadius: 4,
              background: "var(--surface)",
              color: "var(--ink)",
              fontFamily: "var(--mono)",
            }}
          />
          <button
            onClick={handleSaveKey}
            disabled={!apiKeyDraft.trim() || update.isPending}
            style={{
              padding: "6px 12px",
              fontSize: 13,
              background: "var(--accent)",
              color: "var(--surface)",
              border: "none",
              borderRadius: 4,
              cursor: apiKeyDraft.trim() ? "pointer" : "not-allowed",
              opacity: apiKeyDraft.trim() ? 1 : 0.5,
            }}
          >
            {update.isPending ? "Saving…" : "Save"}
          </button>
        </div>
        {keySaved && (
          <div style={{ fontSize: 12, color: "var(--good)", marginTop: 4 }}>✓ API key updated</div>
        )}
        {update.isError && (
          <div style={{ fontSize: 12, color: "var(--crit)", marginTop: 4 }}>Failed to save key</div>
        )}
      </div>

      <div style={{ marginBottom: 12 }}>
        <label style={{ fontSize: 12, fontWeight: 600, display: "block", marginBottom: 4 }}>
          Extraction Model
        </label>
        <select
          value={config?.extraction_model ?? "claude-sonnet-4-6"}
          onChange={(e) => update.mutate({ extraction_model: e.target.value })}
          disabled={!connected}
          style={{ width: "100%", padding: "6px 8px", fontSize: 13, border: "1px solid var(--border)", borderRadius: 4, background: "var(--surface)", color: "var(--ink)" }}
        >
          {(models?.models ?? []).map((m: ModelInfo) => (
            <option key={m.id} value={m.id}>
              {m.name} — {m.tier}
            </option>
          ))}
        </select>
        <div style={{ fontSize: 11, color: "var(--ink-3)", marginTop: 3 }}>
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
          disabled={!connected}
          style={{ width: "100%", padding: "6px 8px", fontSize: 13, border: "1px solid var(--border)", borderRadius: 4, background: "var(--surface)", color: "var(--ink)" }}
        >
          {(models?.models ?? []).map((m: ModelInfo) => (
            <option key={m.id} value={m.id}>
              {m.name} — {m.tier}
            </option>
          ))}
        </select>
        <div style={{ fontSize: 11, color: "var(--ink-3)", marginTop: 3 }}>
          {models?.models.find((m: ModelInfo) => m.id === config?.recommendation_model)?.description}
        </div>
      </div>

      {update.isSuccess && !keySaved && (
        <div style={{ fontSize: 12, color: "var(--good)", marginTop: 8 }}>✓ Model preferences saved</div>
      )}
    </div>
  );
}
