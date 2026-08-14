/** PortfolioPage — the Application Portfolio (ADP-8xo). Two "Group by"
 * dropdowns pivot the Application registry across 5 dimensions (business
 * capability, TIME disposition, 7R strategy, ownership/business unit,
 * criticality/risk tier), mirroring web/src/insights/ApplicationsHeatMap.tsx's
 * dimension-selector pattern and web/src/application/RationalizationView.tsx's
 * grouped-bucket/"Unclassified" pattern. Replaces this screen's former
 * Design-scoped content entirely (technology landscape, design list,
 * dependency search) -- ground-truth correction confirmed with the user before
 * planning: Portfolio's identity flips to Application Portfolio, not a
 * Designs+Applications merge.
 *
 * ADP-3wa: a second dropdown lets both dimensions be viewed "at the same
 * time" as a 2D cross-tab (CrossTabGrid.tsx). Both default to "capability",
 * so the page's default render is identical to the single-dimension view
 * that shipped first; picking two DIFFERENT dimensions is what turns the
 * cross-tab on. Picking the same dimension in both -- including the default
 * -- always renders the original flat card grid, never a degenerate
 * diagonal-only table.
 *
 * ADP-9ye: a third pair ("Filter by" field + value) narrows WHICH
 * applications are shown before either Group By/Then By bucket them --
 * filtering applies uniformly to both the flat grid and the cross-tab.
 * Field list (8) is deliberately wider than Group By's (5): the same 5
 * dimensions plus 3 more bounded-enum fields (lifecycle_status,
 * hosting_model, pace_layer) not otherwise surfaced on this screen. v1 is
 * equality-only, per the user's own explicit phasing request -- comparison/
 * string operators are follow-on work (ADP-6w4). */
import React, { useEffect, useMemo, useState } from "react";
import { useApplications } from "../api/application";
import { useApplicationCapabilityGroups } from "../api/portfolio";
import {
  ALL_DIMENSIONS,
  ALL_FILTER_FIELDS,
  DIMENSION_LABELS,
  FILTER_FIELD_LABELS,
  crossTabApplications,
  filterApplications,
  filterFieldBuckets,
  groupApplications,
  type Dimension,
  type FilterField,
} from "./groupApplications";
import BucketCard, { AppChip } from "./BucketCard";
import CrossTabGrid from "./CrossTabGrid";

export default function PortfolioPage(): React.ReactElement {
  // useSuspenseQuery, consumed directly with no local <Suspense> wrapper --
  // mirrors OverviewPage.tsx's own usage of useApplications() at the same
  // top-level-nav-view depth.
  const apps = useApplications();
  const capabilityGroups = useApplicationCapabilityGroups();
  const [dimensionA, setDimensionA] = useState<Dimension>("capability");
  const [dimensionB, setDimensionB] = useState<Dimension>("capability");
  const [filterField, setFilterField] = useState<FilterField | "">("");
  const [filterValue, setFilterValue] = useState<string>("");

  const appItems = apps.data?.items ?? [];
  const links = capabilityGroups.data?.items ?? [];
  const sameDimension = dimensionA === dimensionB;

  const filterValueOptions = useMemo(
    () => (filterField ? filterFieldBuckets(filterField, appItems, links) : []),
    [filterField, appItems, links],
  );

  // Whenever the filter field changes (including being cleared), land on a
  // sensible default value rather than a dead intermediate state -- mirrors
  // ApplicationsHeatMap.tsx's own "reset selection when it becomes invalid"
  // precedent.
  useEffect(() => {
    setFilterValue(filterValueOptions[0]?.axis.key ?? "");
  }, [filterField, filterValueOptions]);

  const filteredApps = useMemo(
    () => (filterField && filterValue ? filterApplications(filterField, filterValue, appItems, links) : appItems),
    [filterField, filterValue, appItems, links],
  );

  const grouped = useMemo(
    () => groupApplications(dimensionA, filteredApps, links),
    [dimensionA, filteredApps, links],
  );
  const crossTab = useMemo(
    () => (sameDimension ? null : crossTabApplications(dimensionA, dimensionB, filteredApps, links)),
    [sameDimension, dimensionA, dimensionB, filteredApps, links],
  );

  const isFiltered = filteredApps.length !== appItems.length;
  const filterValueLabel = filterValueOptions.find((b) => b.axis.key === filterValue)?.axis.label;

  return (
    <div style={{ display: "flex", flexDirection: "column", height: "100%" }}>
      <div style={{ flex: 1, overflowY: "auto", padding: "20px 24px", maxWidth: 1200, margin: "0 auto", width: "100%" }}>
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 16, flexWrap: "wrap", gap: 8 }}>
          <span style={{ fontSize: 13, color: "var(--ink-3)" }}>
            {filteredApps.length}
            {isFiltered && ` of ${appItems.length}`} application{filteredApps.length === 1 ? "" : "s"}
            {!sameDimension && ` — ${DIMENSION_LABELS[dimensionA]} × ${DIMENSION_LABELS[dimensionB]}`}
            {isFiltered && filterField && ` · filtered to ${FILTER_FIELD_LABELS[filterField]}: ${filterValueLabel}`}
          </span>
          <div style={{ display: "flex", gap: 8, alignItems: "center" }}>
            <select
              aria-label="Filter by"
              value={filterField}
              onChange={(e) => setFilterField(e.target.value as FilterField | "")}
              style={{ fontSize: 13, padding: "4px 8px", border: "1px solid var(--border)", borderRadius: 4 }}
            >
              <option value="">Filter by: (none)</option>
              {ALL_FILTER_FIELDS.map((f) => (
                <option key={f} value={f}>
                  Filter by: {FILTER_FIELD_LABELS[f]}
                </option>
              ))}
            </select>
            {filterField && (
              <select
                aria-label="Filter value"
                value={filterValue}
                onChange={(e) => setFilterValue(e.target.value)}
                style={{ fontSize: 13, padding: "4px 8px", border: "1px solid var(--border)", borderRadius: 4 }}
              >
                {filterValueOptions.map((b) => (
                  <option key={b.axis.key} value={b.axis.key}>
                    {b.axis.label}
                  </option>
                ))}
              </select>
            )}
            {filterField && (
              <button
                onClick={() => setFilterField("")}
                style={{
                  fontSize: 12,
                  color: "var(--ink-3)",
                  background: "none",
                  border: "none",
                  cursor: "pointer",
                  textDecoration: "underline",
                }}
              >
                Clear filter
              </button>
            )}
            <select
              aria-label="Group by"
              value={dimensionA}
              onChange={(e) => setDimensionA(e.target.value as Dimension)}
              style={{ fontSize: 13, padding: "4px 8px", border: "1px solid var(--border)", borderRadius: 4 }}
            >
              {ALL_DIMENSIONS.map((d) => (
                <option key={d} value={d}>
                  Group by: {DIMENSION_LABELS[d]}
                </option>
              ))}
            </select>
            <select
              aria-label="Then by"
              value={dimensionB}
              onChange={(e) => setDimensionB(e.target.value as Dimension)}
              style={{ fontSize: 13, padding: "4px 8px", border: "1px solid var(--border)", borderRadius: 4 }}
            >
              {ALL_DIMENSIONS.map((d) => (
                <option key={d} value={d}>
                  Then by: {DIMENSION_LABELS[d]}
                </option>
              ))}
            </select>
          </div>
        </div>

        {filteredApps.length === 0 ? (
          <div style={{ padding: 40, textAlign: "center", color: "var(--ink-3)", fontSize: 14, border: "2px dashed var(--border)", borderRadius: 8 }}>
            {appItems.length === 0 ? "No applications in the portfolio yet." : "No applications match the current filter."}
          </div>
        ) : sameDimension ? (
          <>
            <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(260px, 1fr))", gap: 12 }}>
              {grouped.buckets.map((bucket) => (
                <BucketCard key={bucket.key} bucket={bucket} dimension={dimensionA} />
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
        ) : (
          crossTab && <CrossTabGrid crossTab={crossTab} rowLabel={DIMENSION_LABELS[dimensionA]} />
        )}
      </div>
    </div>
  );
}
