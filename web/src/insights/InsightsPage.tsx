/** InsightsPage — the non-architect insights dashboard (919-insights-dashboard).
 * Top-level, general-audience screen (nav sibling to Overview, not under the
 * Architecture section) holding pre-defined visualizations: the TIME quadrant
 * bubble chart (ADP-v2n) and the applications heat map. */
import React from "react";
import ApplicationsHeatMap from "./ApplicationsHeatMap";
import TimeQuadrantChart from "./TimeQuadrantChart";
import { PageHeader, Panel } from "../ui/primitives";

export default function InsightsPage(): React.ReactElement {
  return (
    <div style={{ display: "flex", flexDirection: "column", height: "100%" }}>
      <div style={{ flex: 1, overflowY: "auto", padding: 20, maxWidth: 1100, width: "100%", margin: "0 auto" }}>
        <PageHeader title="Insights" lede="At-a-glance visualizations of the portfolio — no architecture background required." />

        <Panel title="TIME quadrant" caption="Where each application sits on business value and technical health, and what it has been classified as." style={{ marginBottom: 20 }}>
          <TimeQuadrantChart />
        </Panel>

        <Panel title="Applications heat map" caption="One cell per application, coloured by the dimension you choose.">
          <ApplicationsHeatMap />
        </Panel>
      </div>
    </div>
  );
}
