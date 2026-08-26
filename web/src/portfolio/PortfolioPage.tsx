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
 * Field list (8 in v1, 13 as of ADP-6w4) is deliberately wider than Group
 * By's (5): the same 5 dimensions plus bounded-enum/free-text/numeric fields
 * not otherwise surfaced on this screen.
 *
 * ADP-6w4: comparison operators (>, <, >=, <=) for numeric/score fields
 * (Health Score, Business Value, and Criticality/Risk Tier) and string
 * operators (contains, starts with) for free-text fields (Name, Vendor,
 * Description, and Ownership/Business Unit), layered onto v1's equality-only
 * bucket dropdown rather than replacing it -- see groupApplications.ts's own
 * "Filter by: comparison/string operators" section for the full design. An
 * operator dropdown appears only for fields that have more than one operator
 * (fieldHasBuckets()'s pure-bucket fields, e.g. Business Capability, never
 * show one); the value control swaps from the v1 bucket <select> to a
 * free-form number/text <input> whenever the field has no bucket set at all,
 * or the chosen operator isn't "=". */
import React, { useEffect, useMemo, useState } from "react";
import { useApplications } from "../api/application";
import { useApplicationCapabilityGroups } from "../api/portfolio";
import {
  ALL_DIMENSIONS,
  ALL_FILTER_FIELDS,
  DIMENSION_LABELS,
  FILTER_FIELD_LABELS,
  OPERATOR_LABELS,
  crossTabApplications,
  fieldHasBuckets,
  filterApplications,
  filterFieldBuckets,
  groupApplications,
  isNumericFilterField,
  operatorsForField,
  type Dimension,
  type FilterField,
  type FilterOperator,
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
  const [filterOperator, setFilterOperator] = useState<FilterOperator>("eq");
  const [filterValue, setFilterValue] = useState<string>("");

  const appItems = apps.data?.items ?? [];
  const links = capabilityGroups.data?.items ?? [];
  const sameDimension = dimensionA === dimensionB;

  const filterOperatorOptions = filterField ? operatorsForField(filterField) : [];
  const usingBucketValue = !!filterField && filterOperator === "eq" && fieldHasBuckets(filterField);

  const filterValueOptions = useMemo(
    () => (filterField && usingBucketValue ? filterFieldBuckets(filterField, appItems, links) : []),
    [filterField, usingBucketValue, appItems, links],
  );

  // Whenever the filter field changes (including being cleared), land on a
  // sensible default operator/value rather than a dead intermediate state --
  // mirrors ApplicationsHeatMap.tsx's own "reset selection when it becomes
  // invalid" precedent. Operator always resets to "=" (v1's original
  // behavior for every field that only ever had one), so switching fields
  // never strands the picker on an operator the new field doesn't support.
  useEffect(() => {
    setFilterOperator("eq");
  }, [filterField]);

  useEffect(() => {
    setFilterValue(usingBucketValue ? (filterValueOptions[0]?.axis.key ?? "") : "");
  }, [filterField, filterOperator, usingBucketValue, filterValueOptions]);

  const filteredApps = useMemo(
    () =>
      filterField && filterValue
        ? filterApplications(filterField, filterValue, appItems, links, filterOperator)
        : appItems,
    [filterField, filterValue, filterOperator, appItems, links],
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
  // Bucket mode shows the bucket's own label (e.g. "On-Prem"); free-form mode
  // shows the operator + typed value together (e.g. "> 3", "contains kong"),
  // since there's no bucket label to look up.
  const filterValueLabel = usingBucketValue
    ? filterValueOptions.find((b) => b.axis.key === filterValue)?.axis.label
    : `${OPERATOR_LABELS[filterOperator]} ${filterValue}`;

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
            {filterField && filterOperatorOptions.length > 1 && (
              <select
                aria-label="Filter operator"
                value={filterOperator}
                onChange={(e) => setFilterOperator(e.target.value as FilterOperator)}
                style={{ fontSize: 13, padding: "4px 8px", border: "1px solid var(--border)", borderRadius: 4 }}
              >
                {filterOperatorOptions.map((op) => (
                  <option key={op} value={op}>
                    {OPERATOR_LABELS[op]}
                  </option>
                ))}
              </select>
            )}
            {filterField && usingBucketValue && (
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
            {filterField && !usingBucketValue && (
              <input
                aria-label="Filter value"
                type={isNumericFilterField(filterField) ? "number" : "text"}
                value={filterValue}
                onChange={(e) => setFilterValue(e.target.value)}
                placeholder={isNumericFilterField(filterField) ? "value…" : "text…"}
                style={{ fontSize: 13, padding: "4px 8px", border: "1px solid var(--border)", borderRadius: 4, width: 100 }}
              />
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
