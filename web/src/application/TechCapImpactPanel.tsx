// 938-capability-model-analysis US3: what a technical capability's end of life affects. A lazy
// expander on each technical capability row: the application capabilities that depend on it (or,
// for an L2, on it or its children), the applications realizing them, and the business
// capabilities they support with their L1 › L2 path. Derived on the server, never stored.

import { useState } from "react";
import type React from "react";
import { useTechCapImpact } from "../api/capAnalysis";
import { CapLink, CapWithPath, muted } from "./capAnalysisUi";

const h5: React.CSSProperties = { fontSize: 11, fontWeight: 600, color: "var(--ink-2)", margin: "6px 0 2px" };
const ul: React.CSSProperties = { listStyle: "none", margin: 0, padding: 0, fontSize: 12 };

function ImpactBody({ tcId }: { tcId: string }): React.ReactElement {
  const { data, isLoading, error } = useTechCapImpact(tcId);
  if (isLoading) return <div style={muted}>Loading…</div>;
  if (error || !data) return <div role="alert" style={{ ...muted, color: "var(--crit)" }}>Failed to load impact.</div>;
  if (data.application_capabilities.length === 0) {
    return <div style={muted}>Nothing depends on this technical capability.</div>;
  }
  const covered = data.covered_technical.length > 1;
  return (
    <div aria-label={`Impact of ${data.technical_capability.name}`}>
      <div style={h5}>Business capabilities exposed ({data.business_capabilities.length})</div>
      {data.business_capabilities.length === 0 ? (
        <div style={muted}>None — no business capability is linked to these application capabilities.</div>
      ) : (
        <ul style={ul}>
          {data.business_capabilities.map((b) => (
            <li key={b.id}>
              <CapWithPath kind="business" cap={b} />
              {b.routes.length > 1 && <span style={{ ...muted, fontSize: 11 }}> · {b.routes.length} routes</span>}
            </li>
          ))}
        </ul>
      )}
      <div style={h5}>Application capabilities ({data.application_capabilities.length})</div>
      <ul style={ul}>
        {data.application_capabilities.map((a) => (
          <li key={a.id}>
            <CapWithPath kind="app-capability" cap={a} />
            {covered && (
              <span style={{ ...muted, fontSize: 11 }}> · via {a.via_technical.map((t) => t.name).join(", ")}</span>
            )}
          </li>
        ))}
      </ul>
      <div style={h5}>Applications ({data.applications.length})</div>
      {data.applications.length === 0 ? (
        <div style={muted}>No application realizes these application capabilities yet.</div>
      ) : (
        <ul style={ul}>
          {data.applications.map((a) => (
            <li key={a.id}>
              <CapLink kind="application" id={a.id}>{a.name}</CapLink>
              {a.lifecycle_status === "retired" && (
                <span style={{ ...muted, fontSize: 11 }}> (retired)</span>
              )}
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

export default function TechCapImpactPanel({ tcId }: { tcId: string }): React.ReactElement {
  const [open, setOpen] = useState(false);
  return (
    <div style={{ marginLeft: 26, marginBottom: 2 }}>
      <button
        type="button"
        onClick={() => setOpen((o) => !o)}
        aria-expanded={open}
        style={{ background: "none", border: "none", padding: 0, cursor: "pointer", fontSize: 11, color: "var(--ink-3)" }}
      >
        {open ? "▾" : "▸"} Impact
      </button>
      {open && (
        <div style={{ marginLeft: 12 }}>
          <ImpactBody tcId={tcId} />
        </div>
      )}
    </div>
  );
}
