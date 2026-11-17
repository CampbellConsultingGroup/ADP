/** Read-only "Automated by agents" lists (944-agent-traceability, ADP-12x, US1, FR-006), shown on
 * business capability L3 rows and value stream stages. Links are edited on the agent; each agent
 * here opens it on the Agents screen when the shell provides navigation. */

import { useState } from "react";
import type React from "react";
import { useAutomatedBy, type AgentSummary, type AutomatesKind } from "../api/agentic";
import { useCapabilityNav } from "../application/appCapNav";
import { RiskBadge } from "./agenticRisk";
import { Loading } from "../ui/primitives";

export function AutomatedByItems({ items }: { items: AgentSummary[] }): React.ReactElement {
  const open = useCapabilityNav()?.openAgent;
  if (items.length === 0) return <div style={{ fontSize: 12, color: "var(--ink-3)" }}>No agents.</div>;
  return (
    <ul style={{ listStyle: "none", margin: 0, padding: 0 }}>
      {items.map((a) => (
        <li key={a.id} style={{ fontSize: 12, padding: "1px 0", display: "flex", gap: 6, alignItems: "center" }}>
          {open ? (
            <button
              type="button"
              onClick={() => open(a.id)}
              title="Open in Agents"
              style={{ background: "none", border: "none", padding: 0, cursor: "pointer", color: "var(--accent)", fontSize: 12 }}
            >
              {a.name}
            </button>
          ) : (
            <span>{a.name}</span>
          )}
          <span style={{ color: "var(--ink-3)", fontSize: 11 }}>L{a.autonomy_level}</span>
          <RiskBadge band={a.agentic_risk.band} />
        </li>
      ))}
    </ul>
  );
}

function Loaded({ kind, targetId }: { kind: AutomatesKind; targetId: string }) {
  const { data, isLoading } = useAutomatedBy(kind, targetId);
  if (isLoading) return <Loading />;
  return <AutomatedByItems items={data?.items ?? []} />;
}

/** Expand-to-load list for a business capability L3 row (the 937/938 expander convention). */
export function CapabilityAutomatedBy({ capId }: { capId: string }): React.ReactElement {
  const [open, setOpen] = useState(false);
  return (
    <div style={{ marginLeft: 26, marginBottom: 2 }}>
      <button
        type="button"
        onClick={() => setOpen((o) => !o)}
        aria-expanded={open}
        style={{ background: "none", border: "none", padding: 0, cursor: "pointer", fontSize: 11, color: "var(--ink-3)" }}
      >
        {open ? "▾" : "▸"} Automated by agents
      </button>
      {open && (
        <div style={{ marginLeft: 12 }}>
          <Loaded kind="capability" targetId={capId} />
        </div>
      )}
    </div>
  );
}

/** Inline list for a value stream stage: shown only when some agent automates it. */
export function StageAutomatedBy({ stageId }: { stageId: string }): React.ReactElement | null {
  const { data } = useAutomatedBy("stage", stageId);
  const items = data?.items ?? [];
  if (items.length === 0) return null;
  return (
    <div style={{ fontSize: 11.5, color: "var(--ink-3)", display: "flex", gap: 4, alignItems: "center", flexWrap: "wrap" }}>
      <span>Automated by:</span>
      <AutomatedByItems items={items} />
    </div>
  );
}
