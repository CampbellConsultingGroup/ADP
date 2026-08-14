/** InsightsPage — the non-architect insights dashboard (919-insights-dashboard).
 * Top-level, general-audience screen (nav sibling to Overview, not under the
 * Architecture section) holding pre-defined, dimension-selectable
 * visualizations. Launch scope is exactly one: the applications heat map. */
import React from "react";
import ApplicationsHeatMap from "./ApplicationsHeatMap";

export default function InsightsPage(): React.ReactElement {
  return (
    <div style={{ display: "flex", flexDirection: "column", height: "100%", fontFamily: "Arial, sans-serif" }}>
      <div style={{ flex: 1, overflowY: "auto", padding: 20, maxWidth: 1100, width: "100%", margin: "0 auto" }}>
        <div style={{ marginBottom: 20 }}>
          <h2 style={{ fontSize: 20, fontWeight: 700, color: "var(--ink)", margin: "0 0 4px" }}>Insights</h2>
          <p style={{ fontSize: 13, color: "var(--ink-3)", margin: 0 }}>
            At-a-glance visualizations of the portfolio — no architecture background required.
          </p>
        </div>

        <ApplicationsHeatMap />
      </div>
    </div>
  );
}
