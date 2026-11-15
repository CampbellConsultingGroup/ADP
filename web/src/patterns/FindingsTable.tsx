/** Conformance / discovery findings: code, kind, severity, rule, elements (936 FR-016). */

import React from "react";
import type { Finding } from "../api/patterns";
import { StatusBadge } from "../ui";

const cell: React.CSSProperties = { padding: "5px 8px", borderBottom: "1px solid var(--border)", fontSize: 12, textAlign: "left", verticalAlign: "top" };

const KIND_LABELS: Record<Finding["kind"], string> = {
  violation: "Violation",
  match: "Match",
  binding: "Binding",
  evaluation_error: "Evaluation error",
  field_unavailable: "Data not visible to you",
  unverifiable: "Unverifiable",
  limit: "Limit reached",
};

export default function FindingsTable({ findings, empty = "No findings." }: { findings: Finding[]; empty?: string }) {
  if (findings.length === 0) return <div style={{ fontSize: 13, color: "var(--ink-3)" }}>{empty}</div>;
  return (
    <table aria-label="Findings" style={{ borderCollapse: "collapse", width: "100%" }}>
      <thead>
        <tr>
          {["Code", "Finding", "Severity", "Rule", "Elements"].map((h) => (
            <th key={h} style={{ ...cell, color: "var(--ink-3)", fontWeight: 600 }}>{h}</th>
          ))}
        </tr>
      </thead>
      <tbody>
        {findings.map((f, i) => (
          <tr key={`${f.code}-${f.kind}-${i}`}>
            <td style={{ ...cell, fontFamily: "var(--mono, monospace)", whiteSpace: "nowrap" }}>{f.code}</td>
            <td style={cell}>{KIND_LABELS[f.kind]}</td>
            <td style={cell}>
              <StatusBadge tone={f.severity === "error" ? "crit" : f.severity === "warning" ? "warn" : "info"}>{f.severity}</StatusBadge>
            </td>
            <td style={cell}>{f.rule}</td>
            <td style={cell}>
              {f.element_refs.map((e) => e.name).join(", ") || "—"}
              {f.truncated ? ` (+${f.element_count - f.element_refs.length} more)` : ""}
            </td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}
