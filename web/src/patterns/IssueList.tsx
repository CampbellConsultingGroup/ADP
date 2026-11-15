/** Pattern validation / resolution issues, each with its stable code and document path (935). */

import React from "react";
import type { PatternIssue } from "../api/patterns";
import { StatusBadge } from "../ui";

const cell: React.CSSProperties = { padding: "5px 8px", borderBottom: "1px solid var(--border)", fontSize: 12, textAlign: "left", verticalAlign: "top" };

export default function IssueList({ issues, title }: { issues: PatternIssue[]; title?: string }) {
  if (issues.length === 0) return null;
  const errors = issues.filter((i) => i.severity === "error").length;
  return (
    <div role="region" aria-label={title ?? "Issues"} style={{ border: "1px solid var(--border)", borderRadius: 6, overflow: "hidden" }}>
      <div style={{ padding: "6px 8px", fontSize: 12.5, fontWeight: 600, background: "var(--surface-2, transparent)" }}>
        {title ?? "Issues"} — {errors} error{errors === 1 ? "" : "s"}, {issues.length - errors} other
      </div>
      <table style={{ borderCollapse: "collapse", width: "100%" }}>
        <tbody>
          {issues.map((i, n) => (
            <tr key={`${i.code}-${i.path}-${n}`}>
              <td style={{ ...cell, width: 80 }}>
                <StatusBadge tone={i.severity === "error" ? "crit" : i.severity === "warning" ? "warn" : "info"}>{i.severity}</StatusBadge>
              </td>
              <td style={{ ...cell, fontFamily: "var(--mono, monospace)", whiteSpace: "nowrap" }}>{i.code}</td>
              <td style={{ ...cell, fontFamily: "var(--mono, monospace)", whiteSpace: "nowrap" }}>{i.path || "(document)"}</td>
              <td style={cell}>{i.message}{i.line ? ` (line ${i.line}${i.column ? `, col ${i.column}` : ""})` : ""}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
