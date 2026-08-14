/** PortfolioPage — the Application Portfolio (ADP-8xo). A "Group by" dropdown
 * pivots the Application registry across 5 dimensions at a time (business
 * capability, TIME disposition, 7R strategy, ownership/business unit,
 * criticality/risk tier), mirroring web/src/insights/ApplicationsHeatMap.tsx's
 * dimension-selector pattern and web/src/application/RationalizationView.tsx's
 * grouped-bucket/"Unclassified" pattern. Replaces this screen's former
 * Design-scoped content entirely (technology landscape, design list,
 * dependency search) -- ground-truth correction confirmed with the user before
 * planning: Portfolio's identity flips to Application Portfolio, not a
 * Designs+Applications merge. */
import React, { useMemo, useState } from "react";
import { useApplications } from "../api/application";
import { useApplicationCapabilityGroups } from "../api/portfolio";
import {
  ALL_DIMENSIONS,
  DIMENSION_LABELS,
  groupApplications,
  type Dimension,
} from "./groupApplications";
import BucketCard, { AppChip } from "./BucketCard";

export default function PortfolioPage(): React.ReactElement {
  // useSuspenseQuery, consumed directly with no local <Suspense> wrapper --
  // mirrors OverviewPage.tsx's own usage of useApplications() at the same
  // top-level-nav-view depth.
  const apps = useApplications();
  const capabilityGroups = useApplicationCapabilityGroups();
  const [dimension, setDimension] = useState<Dimension>("capability");

  const appItems = apps.data?.items ?? [];
  const links = capabilityGroups.data?.items ?? [];

  const grouped = useMemo(
    () => groupApplications(dimension, appItems, links),
    [dimension, appItems, links],
  );

  return (
    <div style={{ display: "flex", flexDirection: "column", height: "100%" }}>
      <div style={{ flex: 1, overflowY: "auto", padding: "20px 24px", maxWidth: 1200, margin: "0 auto", width: "100%" }}>
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 16 }}>
          <span style={{ fontSize: 13, color: "var(--ink-3)" }}>
            {appItems.length} application{appItems.length === 1 ? "" : "s"}
          </span>
          <select
            aria-label="Group by"
            value={dimension}
            onChange={(e) => setDimension(e.target.value as Dimension)}
            style={{ fontSize: 13, padding: "4px 8px", border: "1px solid var(--border)", borderRadius: 4 }}
          >
            {ALL_DIMENSIONS.map((d) => (
              <option key={d} value={d}>
                Group by: {DIMENSION_LABELS[d]}
              </option>
            ))}
          </select>
        </div>

        {appItems.length === 0 ? (
          <div style={{ padding: 40, textAlign: "center", color: "var(--ink-3)", fontSize: 14, border: "2px dashed var(--border)", borderRadius: 8 }}>
            No applications in the portfolio yet.
          </div>
        ) : (
          <>
            <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(260px, 1fr))", gap: 12 }}>
              {grouped.buckets.map((bucket) => (
                <BucketCard key={bucket.key} bucket={bucket} dimension={dimension} />
              ))}
            </div>

            <div style={{ marginTop: 24 }}>
              <div style={{ fontSize: 12, color: "var(--ink-3)", textTransform: "uppercase", letterSpacing: "0.06em", marginBottom: 8 }}>
                Unclassified ({grouped.unclassified.length}) — {grouped.unclassifiedReason}
              </div>
              {grouped.unclassified.length === 0 ? (
                <div style={{ fontSize: 13, color: "var(--ink-3)" }}>Every application is classified.</div>
              ) : (
                <div style={{ display: "flex", flexWrap: "wrap", gap: 8 }}>
                  {grouped.unclassified.map((app) => (
                    <div key={app.id} style={{ minWidth: 160, maxWidth: 240 }}>
                      <AppChip name={app.name} />
                    </div>
                  ))}
                </div>
              )}
            </div>
          </>
        )}
      </div>
    </div>
  );
}

