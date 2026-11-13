/** Create/edit an agent (933-agent-registry, US1). Autonomy is shown with each level's meaning
 * (FR-005); the prompt field is a version reference, never prompt text (FR-006); cost inputs are
 * hidden when the caller cannot see cost (Clarification Q2). */

import React, { useState } from "react";
import type {
  Agent,
  AgentLifecycle,
  AgentWrite,
  DataClassification,
  HumanApproval,
} from "../api/agentic";
import {
  AUTONOMY_LEVELS,
  DATA_CLASSIFICATION_LABELS,
  HUMAN_APPROVAL_LABELS,
  LIFECYCLE_LABELS,
} from "./autonomy";

interface Props {
  initial?: Agent;
  onSubmit: (body: AgentWrite) => void;
  onCancel: () => void;
  saving?: boolean;
  error?: string | null;
}

const labelStyle: React.CSSProperties = { fontSize: 13, display: "flex", flexDirection: "column", gap: 2 };
const inputStyle: React.CSSProperties = { width: "100%" };
const rowStyle: React.CSSProperties = { display: "grid", gridTemplateColumns: "1fr 1fr", gap: 10 };

function orNull(value: string): string | null {
  const trimmed = value.trim();
  return trimmed === "" ? null : trimmed;
}

export default function AgentForm({ initial, onSubmit, onCancel, saving, error }: Props) {
  const costVisible = initial ? initial.cost_visible : true;
  const [name, setName] = useState(initial?.name ?? "");
  const [description, setDescription] = useState(initial?.description ?? "");
  const [owner, setOwner] = useState(initial?.owner ?? "");
  const [lifecycle, setLifecycle] = useState<AgentLifecycle>(initial?.lifecycle_status ?? "active");
  const [modelProvider, setModelProvider] = useState(initial?.model_provider ?? "");
  const [modelId, setModelId] = useState(initial?.model_id ?? "");
  const [modelVersion, setModelVersion] = useState(initial?.model_version ?? "");
  const [framework, setFramework] = useState(initial?.framework ?? "");
  const [promptRef, setPromptRef] = useState(initial?.prompt_ref ?? "");
  const [autonomy, setAutonomy] = useState<number>(initial?.autonomy_level ?? 1);
  const [approval, setApproval] = useState<HumanApproval>(initial?.human_approval ?? "on_write");
  const [classification, setClassification] = useState<DataClassification | "">(
    initial?.data_classification_max ?? "",
  );
  const [cardUrl, setCardUrl] = useState(initial?.a2a_card_url ?? "");
  const [cost, setCost] = useState(initial?.est_cost_per_run ?? "");
  const [runs, setRuns] = useState(initial?.runs_per_month != null ? String(initial.runs_per_month) : "");
  const [externalRef, setExternalRef] = useState(initial?.external_registry_ref ?? "");
  const [localError, setLocalError] = useState<string | null>(null);

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!name.trim()) {
      setLocalError("Name is required");
      return;
    }
    const url = cardUrl.trim();
    if (url && !/^https?:\/\//i.test(url)) {
      setLocalError("Agent Card URL must start with http:// or https://");
      return;
    }
    if (costVisible && runs.trim() && !/^\d+$/.test(runs.trim())) {
      setLocalError("Runs per month must be a whole number");
      return;
    }
    setLocalError(null);
    const body: AgentWrite = {
      name: name.trim(),
      description: orNull(description),
      owner: orNull(owner),
      lifecycle_status: lifecycle,
      model_provider: orNull(modelProvider),
      model_id: orNull(modelId),
      model_version: orNull(modelVersion),
      framework: orNull(framework),
      prompt_ref: orNull(promptRef),
      autonomy_level: autonomy,
      human_approval: approval,
      data_classification_max: classification === "" ? null : classification,
      a2a_card_url: orNull(cardUrl),
      external_registry_ref: orNull(externalRef),
    };
    if (costVisible) {
      // Only send cost when it is set or being cleared, so callers without cost-write
      // permission can still save an agent that never had estimates.
      const costValue = orNull(String(cost));
      const runsValue = runs.trim() === "" ? null : Number(runs.trim());
      if (costValue !== null || initial?.est_cost_per_run != null) body.est_cost_per_run = costValue;
      if (runsValue !== null || initial?.runs_per_month != null) body.runs_per_month = runsValue;
    }
    onSubmit(body);
  }

  const selected = AUTONOMY_LEVELS.find((d) => d.level === autonomy);
  const shownError = localError ?? error ?? null;

  return (
    <form onSubmit={handleSubmit} style={{ display: "flex", flexDirection: "column", gap: 10, maxWidth: 720 }}>
      {shownError && <div role="alert" style={{ color: "var(--crit)", fontSize: 13 }}>{shownError}</div>}
      <label style={labelStyle}>
        Name *
        <input value={name} onChange={(e) => setName(e.target.value)} maxLength={255} style={inputStyle} />
      </label>
      <label style={labelStyle}>
        Description
        <textarea value={description} onChange={(e) => setDescription(e.target.value)} rows={2} style={inputStyle} />
      </label>
      <div style={rowStyle}>
        <label style={labelStyle}>
          Owner
          <input value={owner} onChange={(e) => setOwner(e.target.value)} maxLength={255} style={inputStyle} />
        </label>
        <label style={labelStyle}>
          Lifecycle
          <select value={lifecycle} onChange={(e) => setLifecycle(e.target.value as AgentLifecycle)}>
            {Object.entries(LIFECYCLE_LABELS).map(([value, label]) => (
              <option key={value} value={value}>{label}</option>
            ))}
          </select>
        </label>
      </div>

      <div style={rowStyle}>
        <label style={labelStyle}>
          Autonomy level *
          <select
            aria-label="Autonomy level"
            value={autonomy}
            onChange={(e) => setAutonomy(Number(e.target.value))}
          >
            {AUTONOMY_LEVELS.map((d) => (
              <option key={d.level} value={d.level}>L{d.level} {d.name}</option>
            ))}
          </select>
          {selected && <span style={{ fontSize: 11, color: "var(--ink-3)" }}>{selected.meaning}</span>}
        </label>
        <label style={labelStyle}>
          Human approval *
          <select value={approval} onChange={(e) => setApproval(e.target.value as HumanApproval)}>
            {Object.entries(HUMAN_APPROVAL_LABELS).map(([value, label]) => (
              <option key={value} value={value}>{label}</option>
            ))}
          </select>
        </label>
      </div>

      <div style={rowStyle}>
        <label style={labelStyle}>
          Model provider
          <input value={modelProvider} onChange={(e) => setModelProvider(e.target.value)} maxLength={100} placeholder="Anthropic" style={inputStyle} />
        </label>
        <label style={labelStyle}>
          Model
          <input value={modelId} onChange={(e) => setModelId(e.target.value)} maxLength={200} placeholder="claude-sonnet-5-5" style={inputStyle} />
        </label>
        <label style={labelStyle}>
          Model version
          <input value={modelVersion} onChange={(e) => setModelVersion(e.target.value)} maxLength={100} style={inputStyle} />
        </label>
        <label style={labelStyle}>
          Agent framework
          <input value={framework} onChange={(e) => setFramework(e.target.value)} maxLength={100} placeholder="Claude Agent SDK, LangGraph…" style={inputStyle} />
        </label>
      </div>

      <label style={labelStyle}>
        Prompt version reference
        <input value={promptRef} onChange={(e) => setPromptRef(e.target.value)} maxLength={200} placeholder="claims-triage@v7" style={inputStyle} />
        <span style={{ fontSize: 11, color: "var(--ink-3)" }}>
          A version identifier only — do not paste prompt text here.
        </span>
      </label>

      <div style={rowStyle}>
        <label style={labelStyle}>
          Max data classification
          <select value={classification} onChange={(e) => setClassification(e.target.value as DataClassification | "")}>
            <option value="">—</option>
            {Object.entries(DATA_CLASSIFICATION_LABELS).map(([value, label]) => (
              <option key={value} value={value}>{label}</option>
            ))}
          </select>
        </label>
        <label style={labelStyle}>
          Agent Card URL (A2A)
          <input value={cardUrl} onChange={(e) => setCardUrl(e.target.value)} placeholder="https://…/.well-known/agent-card.json" style={inputStyle} />
        </label>
      </div>

      {costVisible ? (
        <div style={rowStyle}>
          <label style={labelStyle}>
            Est. cost per run (USD)
            <input type="number" min={0} step="0.0001" value={cost} onChange={(e) => setCost(e.target.value)} style={inputStyle} />
          </label>
          <label style={labelStyle}>
            Est. runs per month
            <input type="number" min={0} step={1} value={runs} onChange={(e) => setRuns(e.target.value)} style={inputStyle} />
          </label>
        </div>
      ) : (
        <div style={{ fontSize: 12, color: "var(--ink-3)" }}>Cost estimates are restricted for your role.</div>
      )}

      <label style={labelStyle}>
        External registry reference
        <input value={externalRef} onChange={(e) => setExternalRef(e.target.value)} maxLength={255} placeholder="Runtime registry id (optional)" style={inputStyle} />
      </label>

      <div style={{ display: "flex", gap: 8, marginTop: 4 }}>
        <button type="submit" disabled={saving} className="ui-btn ui-btn-primary ui-btn-sm">
          {saving ? "Saving…" : "Save"}
        </button>
        <button type="button" onClick={onCancel} className="ui-btn ui-btn-sm">Cancel</button>
      </div>
    </form>
  );
}
