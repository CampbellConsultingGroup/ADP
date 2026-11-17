/** An agent's compliance (944-agent-traceability, ADP-12x, US2): the status derived from its own
 * control mappings (worst wins, never stored), then each mapping. Mappings are edited on the
 * control (Compliance screen), so this section is read only. */

import type React from "react";
import { useAgentComplianceMappings, useAllControls } from "../api/compliance";
import { ComplianceStatusText } from "./ComplianceStatusText";
import { Loading } from "../ui/primitives";

export default function AgentCompliance({ agentId }: { agentId: string }): React.ReactElement {
  const { data, isLoading } = useAgentComplianceMappings(agentId);
  const controls = useAllControls();

  if (isLoading || !data) return <Loading />;

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 6, fontSize: 13 }}>
      <div style={{ display: "flex", gap: 8, alignItems: "center" }}>
        <span style={{ color: "var(--ink-3)", fontSize: 12.5 }}>Derived status</span>
        <ComplianceStatusText status={data.status} />
      </div>
      {data.items.length === 0 ? (
        <div style={{ fontSize: 12.5, color: "var(--ink-3)" }}>No controls mapped.</div>
      ) : (
        <ul style={{ margin: 0, paddingLeft: 18 }}>
          {data.items.map((m) => {
            const c = controls.byId.get(m.control_id);
            return (
              <li key={m.control_id}>
                {c ? (
                  <>
                    <span style={{ color: "var(--ink-3)" }}>{c.framework_name} · </span>
                    {c.code} {c.title}
                  </>
                ) : (
                  m.control_id
                )}
                {" — "}
                <ComplianceStatusText status={m.compliance_status} />
                {m.evidence_ref && <span style={{ color: "var(--ink-3)" }}> · evidence {m.evidence_ref}</span>}
              </li>
            );
          })}
        </ul>
      )}
      <div style={{ fontSize: 11, color: "var(--ink-3)" }}>
        Mapped on the control (Compliance). Kept separate from the solution's own compliance.
      </div>
    </div>
  );
}
