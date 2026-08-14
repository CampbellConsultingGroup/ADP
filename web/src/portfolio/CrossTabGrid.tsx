/** CrossTabGrid — the 2D pivot table for PortfolioPage.tsx's two "Group by"
 * dropdowns (ADP-3wa). Mirrors web/src/strategy/StrategyHeatMap.tsx's own
 * matrix precedent (the only other 2D-grid UI in this codebase): same
 * overflowX wrapper, borderCollapse, header/cell padding. Each cell lists the
 * actual application names (stacked, one per line) rather than just a count. */
import React from "react";
import type { CrossTabResult } from "./groupApplications";

export default function CrossTabGrid({
  crossTab,
  rowLabel,
}: {
  crossTab: CrossTabResult;
  rowLabel: string;
}): React.ReactElement {
  return (
    <div style={{ overflowX: "auto" }}>
      <table style={{ borderCollapse: "collapse", width: "100%", fontSize: 13 }}>
        <thead>
          <tr>
            <th style={{ textAlign: "left", padding: "8px 12px", borderBottom: "2px solid var(--border)", color: "var(--ink-3)" }}>
              {rowLabel}
            </th>
            {crossTab.columns.map((col) => (
              <th
                key={col.key}
                style={{ textAlign: "center", padding: "8px 12px", borderBottom: "2px solid var(--border)", color: "var(--ink-3)", fontWeight: 600 }}
              >
                {col.label}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {crossTab.rows.map((row) => (
            <tr key={row.key}>
              <td style={{ padding: "8px 12px", borderBottom: "1px solid var(--border)", fontWeight: 600, color: "var(--ink)" }}>
                {row.label}
              </td>
              {crossTab.columns.map((col) => {
                const cellApps = crossTab.cellApps(row.key, col.key);
                return (
                  <td
                    key={col.key}
                    style={{
                      textAlign: "left",
                      verticalAlign: "top",
                      padding: "8px 12px",
                      borderBottom: "1px solid var(--border)",
                      background: cellApps.length > 0 ? "var(--accent-wash)" : undefined,
                      color: "var(--ink)",
                    }}
                  >
                    {cellApps.length === 0 ? (
                      <span style={{ color: "var(--ink-3)" }}>—</span>
                    ) : (
                      <div style={{ display: "flex", flexDirection: "column", gap: 4 }}>
                        {cellApps.map((app) => (
                          <div
                            key={app.id}
                            title={app.name}
                            style={{ overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}
                          >
                            {app.name}
                          </div>
                        ))}
                      </div>
                    )}
                  </td>
                );
              })}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
