// 941-capability-org-mappings US4: an org unit's capability footprint, shown in its detail panel.
// Derived by the server on every read: the L3s it and its sub-units perform, grouped L1 -> L2 -> L3
// with counts and attributed to the unit doing the work, plus what it owns and contributes to.

import type React from "react";
import type { FootprintPerformer } from "../api/organization";
import { useOrgUnitFootprint } from "../api/organization";

const muted: React.CSSProperties = { fontSize: 12, color: "var(--ink-3)" };
// Same heading style as the rest of the org-unit detail panel (OrganizationTab.tsx).
const h4: React.CSSProperties = { fontSize: 13, margin: "14px 0 6px", color: "var(--ink-2)" };
const link: React.CSSProperties = {
  background: "none",
  border: "none",
  padding: 0,
  color: "var(--accent)",
  cursor: "pointer",
  fontSize: 13,
  textAlign: "left",
};

function who(p: FootprintPerformer, self: string): string {
  const name = p.org_unit.id === self ? "" : p.org_unit.name;
  const where = p.geographies.map((g) => g.name).join(", ");
  return [name, where].filter(Boolean).join(" — ");
}

export default function OrgUnitFootprint({
  orgUnitId,
  onOpenCapability,
}: {
  orgUnitId: string;
  onOpenCapability?: (id: string) => void;
}): React.ReactElement {
  const { data, isLoading, error } = useOrgUnitFootprint(orgUnitId);
  const open = (id: string, name: string) => (
    <button type="button" style={link} onClick={() => onOpenCapability?.(id)} title="Open on the Capabilities tab">
      {name}
    </button>
  );

  if (isLoading) return <div style={muted}>Loading footprint…</div>;
  if (error || !data) return <div role="alert" style={{ ...muted, color: "var(--crit)" }}>Failed to load the footprint.</div>;
  const nothing = data.l3_total === 0 && data.owns.length === 0 && data.contributes.length === 0;

  return (
    <section aria-label="Capability footprint">
      <h4 style={h4}>
        Performs ({data.l3_total} L3 {data.l3_total === 1 ? "capability" : "capabilities"}, including sub-units)
      </h4>
      {nothing ? (
        <div style={muted}>This org unit and its sub-units have no capability mappings yet.</div>
      ) : data.performs.length === 0 ? (
        <div style={muted}>Performs no L3 capabilities.</div>
      ) : (
        <ul style={{ margin: 0, paddingLeft: 18, fontSize: 13 }}>
          {data.performs.map((l1) => (
            <li key={l1.capability.id}>
              {open(l1.capability.id, l1.capability.name)} <span style={muted}>({l1.l3_count})</span>
              <ul style={{ margin: 0, paddingLeft: 18 }}>
                {l1.l2s.map((l2) => (
                  <li key={l2.capability.id}>
                    {open(l2.capability.id, l2.capability.name)} <span style={muted}>({l2.l3_count})</span>
                    <ul style={{ margin: 0, paddingLeft: 18 }}>
                      {l2.l3s.map((l3) => {
                        const by = l3.performed_by.map((p) => who(p, data.org_unit.id)).filter(Boolean);
                        return (
                          <li key={l3.capability.id}>
                            {open(l3.capability.id, l3.capability.name)}
                            {by.length > 0 && <span style={muted}> — {by.join("; ")}</span>}
                          </li>
                        );
                      })}
                    </ul>
                  </li>
                ))}
              </ul>
            </li>
          ))}
        </ul>
      )}

      {data.owns.length > 0 && (
        <>
          <h4 style={h4}>Owns ({data.owns.length})</h4>
          <ul style={{ margin: 0, paddingLeft: 18, fontSize: 13 }}>
            {data.owns.map((e) => (
              <li key={`${e.capability.id}-${e.org_unit.id}`}>
                {open(e.capability.id, e.capability.name)}
                {e.org_unit.id !== data.org_unit.id && <span style={muted}> — {e.org_unit.name}</span>}
              </li>
            ))}
          </ul>
        </>
      )}
      {data.contributes.length > 0 && (
        <>
          <h4 style={h4}>Contributes to ({data.contributes.length})</h4>
          <ul style={{ margin: 0, paddingLeft: 18, fontSize: 13 }}>
            {data.contributes.map((e) => (
              <li key={`${e.capability.id}-${e.org_unit.id}`}>
                {open(e.capability.id, e.capability.name)}
                {e.org_unit.id !== data.org_unit.id && <span style={muted}> — {e.org_unit.name}</span>}
              </li>
            ))}
          </ul>
        </>
      )}
    </section>
  );
}
