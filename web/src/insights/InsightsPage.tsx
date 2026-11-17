/** InsightsPage — the non-architect insights dashboard (919-insights-dashboard).
 * Top-level, general-audience screen (nav sibling to Overview, not under the
 * Architecture section) holding pre-defined, dimension-selectable
 * visualizations. Launch scope is exactly one: the applications heat map. */
import React from "react";
import ApplicationsHeatMap from "./ApplicationsHeatMap";
import { PageHeader } from "../ui/primitives";

export default function InsightsPage(): React.ReactElement {
  return (
    <div style={{ display: "flex", flexDirection: "column", height: "100%" }}>
      <div style={{ flex: 1, overflowY: "auto", padding: 20, maxWidth: 1100, width: "100%", margin: "0 auto" }}>
        <PageHeader title="Insights" lede="At-a-glance visualizations of the portfolio — no architecture background required." />

        <ApplicationsHeatMap />
      </div>
    </div>
  );
}
