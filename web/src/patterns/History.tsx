/** A version's persisted lifecycle history (935 FR-011). */

import React from "react";
import type { LifecycleEvent } from "../api/patterns";
import { LIFECYCLE_LABELS } from "./labels";

const cell: React.CSSProperties = { padding: "5px 8px", borderBottom: "1px solid var(--border)", fontSize: 12, textAlign: "left", verticalAlign: "top" };

export default function History({ events }: { events: LifecycleEvent[] }) {
  if (events.length === 0) {
    return <div style={{ fontSize: 13, color: "var(--ink-3)" }}>No lifecycle changes yet; this version is still the draft it was imported as.</div>;
  }
  return (
    <table aria-label="Lifecycle history" style={{ borderCollapse: "collapse", width: "100%" }}>
      <thead>
        <tr>
          {["When", "Change", "Reason", "By", "Confirmation"].map((h) => (
            <th key={h} style={{ ...cell, color: "var(--ink-3)", fontWeight: 600 }}>{h}</th>
          ))}
        </tr>
      </thead>
      <tbody>
        {events.map((e) => (
          <tr key={e.id}>
            <td style={{ ...cell, whiteSpace: "nowrap" }}>{new Date(e.at).toLocaleString()}</td>
            <td style={cell}>
              {LIFECYCLE_LABELS[e.from_state]} → {LIFECYCLE_LABELS[e.to_state]}
              {e.caused_by_event_id ? " (automatic, superseded)" : ""}
            </td>
            <td style={cell}>{e.reason}</td>
            <td style={cell}>{e.actor}</td>
            <td style={{ ...cell, fontFamily: "var(--mono, monospace)", fontSize: 11 }}>{e.confirmation_id}</td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}
