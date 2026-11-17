/** Agentic risk display (944-agent-traceability, ADP-12x, US3). The band is derived on the server
 * from autonomy, human approval and data classification, and never stored. Tool side effects are
 * not considered yet (they arrive with P2, ADP-a00); every band says so. */

import type React from "react";
import type { AgenticRisk, RiskBand, SolutionAgenticRisk } from "../api/agentic";
import { StatusBadge, type BadgeTone } from "../ui";

export const RISK_LABEL: Record<RiskBand, string> = { high: "High", medium: "Medium", low: "Low" };
const RISK_TONE: Record<RiskBand, BadgeTone> = { high: "crit", medium: "warn", low: "good" };

export const NOT_CONSIDERED_NOTE = "Tool side effects are not yet considered.";

export function RiskBadge({ band }: { band: RiskBand | null }): React.ReactElement {
  if (band === null) return <StatusBadge tone="neutral">No agents</StatusBadge>;
  return <StatusBadge tone={RISK_TONE[band]}>{`${RISK_LABEL[band]} risk`}</StatusBadge>;
}

/** The factors that set an agent's band, plus missing inputs and what isn't considered. */
export function RiskFactors({ risk }: { risk: AgenticRisk }): React.ReactElement {
  const parts = risk.factors.map((f) => f.label);
  return (
    <span style={{ fontSize: 12, color: "var(--ink-3)" }}>
      {parts.length > 0 ? parts.join(", ") : "no elevating factors"}
      {risk.missing.includes("data_classification") && " · data classification not recorded"}
      {risk.not_considered.length > 0 && ` · ${NOT_CONSIDERED_NOTE}`}
    </span>
  );
}

/** A solution's band: the highest among its non-retired agents, naming the agents that set it. */
export function SolutionRiskBanner({ risk }: { risk: SolutionAgenticRisk }): React.ReactElement {
  return (
    <div
      role="status"
      aria-label="Solution agentic risk"
      style={{ display: "flex", alignItems: "center", gap: 8, flexWrap: "wrap", fontSize: 12.5 }}
    >
      <span style={{ color: "var(--ink-2)", fontWeight: 600 }}>Agentic risk</span>
      <RiskBadge band={risk.band} />
      {risk.band !== null && risk.agents.length > 0 && (
        <span style={{ color: "var(--ink-3)" }}>set by {risk.agents.map((a) => a.name).join(", ")}</span>
      )}
      <span style={{ color: "var(--ink-3)", fontSize: 11.5 }}>{NOT_CONSIDERED_NOTE}</span>
    </div>
  );
}
