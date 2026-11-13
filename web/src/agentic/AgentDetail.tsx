/** One agent: its attributes and every solution it belongs to (933-agent-registry, US2). */

import React, { useState } from "react";
import { errorDetail, useAgent, useDeleteAgent, useUpdateAgent } from "../api/agentic";
import type { AgentWrite } from "../api/agentic";
import { Button, StatusBadge } from "../ui";
import { isHttpUrl } from "../ui/url";
import AgentForm from "./AgentForm";
import {
  AUTONOMY_LEVELS,
  DATA_CLASSIFICATION_LABELS,
  HUMAN_APPROVAL_LABELS,
  LIFECYCLE_LABELS,
  ROLE_LABELS,
  autonomyLabel,
  costLabel,
} from "./autonomy";

interface Props {
  agentId: string;
  onBack: () => void;
  onOpenSolution?: (appId: string) => void;
}

function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div style={{ display: "flex", gap: 8, fontSize: 12.5 }}>
      <span style={{ width: 190, flexShrink: 0, color: "var(--ink-3)" }}>{label}</span>
      <span style={{ color: "var(--ink)" }}>{children}</span>
    </div>
  );
}

export default function AgentDetail({ agentId, onBack, onOpenSolution }: Props) {
  const { data: agent, isLoading } = useAgent(agentId);
  const update = useUpdateAgent(agentId);
  const del = useDeleteAgent();
  const [editing, setEditing] = useState(false);
  const [error, setError] = useState<string | null>(null);

  if (isLoading) return <div style={{ padding: 24, fontSize: 13, color: "var(--ink-3)" }}>Loading…</div>;
  if (!agent) return <div style={{ padding: 24, fontSize: 13, color: "var(--ink-3)" }}>Agent not found</div>;

  const handleSave = async (body: AgentWrite) => {
    setError(null);
    try {
      await update.mutateAsync(body);
      setEditing(false);
    } catch (err) {
      setError(errorDetail(err));
    }
  };

  const handleDelete = async () => {
    const n = agent.solution_count;
    const scope = n > 0 ? ` It will be removed from ${n} solution${n === 1 ? "" : "s"}.` : "";
    if (!confirm(`Delete agent "${agent.name}"?${scope}`)) return;
    await del.mutateAsync(agentId);
    onBack();
  };

  const level = AUTONOMY_LEVELS.find((d) => d.level === agent.autonomy_level);

  return (
    <div style={{ padding: "16px 20px", display: "flex", flexDirection: "column", gap: 14, overflow: "auto", height: "100%" }}>
      <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
        <button type="button" className="ui-btn ui-btn-sm" onClick={onBack}>← Agents</button>
        <h2 style={{ margin: 0, fontSize: 17, fontWeight: 700 }}>{agent.name}</h2>
        <StatusBadge tone={agent.lifecycle_status === "active" ? "good" : agent.lifecycle_status === "retired" ? "neutral" : "info"}>
          {LIFECYCLE_LABELS[agent.lifecycle_status]}
        </StatusBadge>
        <div style={{ flex: 1 }} />
        {!editing && <Button size="sm" onClick={() => setEditing(true)}>Edit</Button>}
        {!editing && <Button size="sm" variant="danger" onClick={() => void handleDelete()}>Delete</Button>}
      </div>

      {editing ? (
        <AgentForm
          initial={agent}
          onSubmit={(body) => void handleSave(body)}
          onCancel={() => { setEditing(false); setError(null); }}
          saving={update.isPending}
          error={error}
        />
      ) : (
        <>
          {agent.description && <p style={{ margin: 0, fontSize: 13, color: "var(--ink-2)" }}>{agent.description}</p>}
          <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
            <Field label="Owner">{agent.owner ?? "—"}</Field>
            <Field label="Autonomy">
              {autonomyLabel(agent.autonomy_level)}
              {level && <span style={{ color: "var(--ink-3)" }}> — {level.meaning}</span>}
            </Field>
            <Field label="Human approval">{HUMAN_APPROVAL_LABELS[agent.human_approval]}</Field>
            <Field label="Model">
              {[agent.model_provider, agent.model_id, agent.model_version].filter(Boolean).join(" · ") || "—"}
            </Field>
            <Field label="Framework">{agent.framework ?? "—"}</Field>
            <Field label="Prompt version reference">{agent.prompt_ref ?? "—"}</Field>
            <Field label="Max data classification">
              {agent.data_classification_max ? DATA_CLASSIFICATION_LABELS[agent.data_classification_max] : "—"}
            </Field>
            <Field label="Agent Card">
              {agent.a2a_card_url && isHttpUrl(agent.a2a_card_url) ? (
                <a href={agent.a2a_card_url} target="_blank" rel="noopener noreferrer">{agent.a2a_card_url}</a>
              ) : (
                agent.a2a_card_url ?? "—"
              )}
            </Field>
            <Field label="Est. cost per run">{costLabel(agent.est_cost_per_run, agent.cost_visible, "$")}</Field>
            <Field label="Est. runs per month">{costLabel(agent.runs_per_month, agent.cost_visible)}</Field>
            <Field label="External registry reference">{agent.external_registry_ref ?? "—"}</Field>
          </div>
        </>
      )}

      <div>
        <h3 style={{ fontSize: 14, margin: "8px 0 6px" }}>Solutions ({agent.solutions.length})</h3>
        {agent.solutions.length === 0 ? (
          <div style={{ fontSize: 13, color: "var(--ink-3)" }}>Unassigned — not part of any agentic solution.</div>
        ) : (
          <ul style={{ margin: 0, paddingLeft: 18, fontSize: 13 }}>
            {agent.solutions.map((s) => (
              <li key={s.app_id}>
                {onOpenSolution ? (
                  <button
                    type="button"
                    onClick={() => onOpenSolution(s.app_id)}
                    style={{ background: "none", border: "none", padding: 0, color: "var(--accent)", cursor: "pointer", fontSize: 13 }}
                  >
                    {s.app_name}
                  </button>
                ) : (
                  s.app_name
                )}
                <span style={{ color: "var(--ink-3)" }}> — {ROLE_LABELS[s.role]}</span>
              </li>
            ))}
          </ul>
        )}
      </div>
    </div>
  );
}
