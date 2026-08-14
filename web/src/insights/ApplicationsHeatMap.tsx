/** ApplicationsHeatMap — one cell per application, colored by a user-selectable
 * dimension (919-insights-dashboard). Every dimension's data arrives in a single
 * fetch (research.md Decision 3), so switching dimensions is a client-side
 * recolor with no network round-trip (SC-002). */

import React, { useEffect, useState } from "react";
import { useApplicationsHeatmap, type ApplicationHeatmapEntry } from "../api/portfolio";

type Dimension = "health_score" | "business_criticality" | "time_classification" | "cost";

const DIMENSION_LABELS: Record<Dimension, string> = {
  health_score: "Health score",
  business_criticality: "Business criticality",
  time_classification: "TIME classification",
  cost: "Cost (TCO)",
};

const ALL_DIMENSIONS: Dimension[] = [
  "health_score",
  "business_criticality",
  "time_classification",
  "cost",
];

interface Swatch {
  bg: string;
  fg: string;
}

// A 5-step diverging scale (worst/lowest -> best/highest), reused across every
// ordinal dimension so the heat map reads consistently regardless of which one
// is selected.
const FIVE_STEP: Swatch[] = [
  { bg: "var(--crit)", fg: "#ffffff" },
  { bg: "var(--warn)", fg: "#1a1400" },
  { bg: "var(--surface-3)", fg: "var(--ink)" },
  { bg: "var(--good-wash)", fg: "var(--ink)" },
  { bg: "var(--good)", fg: "#ffffff" },
];

// FR-005: unscored/unclassified applications must never look like an actual value —
// a distinct dashed treatment, not a color anywhere in FIVE_STEP.
const UNCLASSIFIED: Swatch = { bg: "var(--surface-2)", fg: "var(--ink-3)" };

const TIME_SWATCHES: Record<string, Swatch> = {
  Invest: { bg: "var(--good)", fg: "#ffffff" },
  Tolerate: { bg: "var(--surface-3)", fg: "var(--ink)" },
  Migrate: { bg: "var(--warn)", fg: "#1a1400" },
  Eliminate: { bg: "var(--crit)", fg: "#ffffff" },
};

function stepFor(rank: number, invert: boolean): Swatch {
  const idx = invert ? 4 - rank : rank;
  return FIVE_STEP[Math.min(4, Math.max(0, idx))];
}

/** 1-5 ordinal fields. `invert`: true when a *higher* value should read as
 * "hotter" (e.g. business criticality) rather than "better" (e.g. health score). */
function scoreSwatch(value: number | null, invert: boolean): Swatch {
  if (value === null) return UNCLASSIFIED;
  return stepFor(Math.min(4, Math.max(0, value - 1)), invert);
}

function timeSwatch(value: string | null): Swatch {
  if (!value) return UNCLASSIFIED;
  return TIME_SWATCHES[value] ?? UNCLASSIFIED;
}

/** Cost has no fixed 1-5 scale, so it's bucketed by rank among the currently
 * visible, permitted cost values -- higher relative cost reads as hotter. */
function costSwatch(value: number | null, allCosts: number[]): Swatch {
  if (value === null || allCosts.length === 0) return UNCLASSIFIED;
  const sorted = [...allCosts].sort((a, b) => a - b);
  const position = sorted.filter((v) => v <= value).length - 1;
  const rank = Math.round((position / Math.max(1, sorted.length - 1)) * 4);
  return stepFor(rank, true);
}

function swatchFor(
  item: ApplicationHeatmapEntry,
  dimension: Dimension,
  allCosts: number[],
): Swatch {
  switch (dimension) {
    case "health_score":
      return scoreSwatch(item.health_score, false);
    case "business_criticality":
      return scoreSwatch(item.business_criticality, true);
    case "time_classification":
      return timeSwatch(item.time_classification);
    case "cost":
      return costSwatch(item.cost, allCosts);
  }
}

function valueLabel(item: ApplicationHeatmapEntry, dimension: Dimension): string {
  switch (dimension) {
    case "health_score":
      return item.health_score === null ? "Unclassified" : String(item.health_score);
    case "business_criticality":
      return item.business_criticality === null ? "Unclassified" : String(item.business_criticality);
    case "time_classification":
      return item.time_classification ?? "Unclassified";
    case "cost":
      return item.cost === null ? "Unclassified" : `$${Math.round(item.cost).toLocaleString()}`;
  }
}

export default function ApplicationsHeatMap(): React.ReactElement {
  const { data, isLoading, error } = useApplicationsHeatmap();
  const [dimension, setDimension] = useState<Dimension>("health_score");

  const costPermitted = data?.cost_permitted ?? false;

  // Edge case: if the caller's permission changes mid-session (or the initial
  // fetch resolves to cost_permitted=false after "cost" was already selected),
  // fall back to the default dimension rather than continuing to request data
  // the user can no longer read.
  useEffect(() => {
    if (dimension === "cost" && !costPermitted) {
      setDimension("health_score");
    }
  }, [dimension, costPermitted]);

  if (isLoading) return <div style={{ padding: 16, color: "var(--ink-3)" }}>Loading applications…</div>;
  if (error) return <div className="ui-alert crit">Failed to load applications heat map</div>;

  const items = data?.items ?? [];
  const availableDimensions = ALL_DIMENSIONS.filter((d) => d !== "cost" || costPermitted);
  const costs = items.map((i) => i.cost).filter((c): c is number => c !== null);

  return (
    <div>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 12 }}>
        <span style={{ fontSize: 13, color: "var(--ink-3)" }}>
          {items.length} application{items.length === 1 ? "" : "s"}
        </span>
        <select
          aria-label="Color by"
          value={dimension}
          onChange={(e) => setDimension(e.target.value as Dimension)}
          style={{ fontSize: 13, padding: "4px 8px", border: "1px solid var(--border)", borderRadius: 4 }}
        >
          {availableDimensions.map((d) => (
            <option key={d} value={d}>
              Color by: {DIMENSION_LABELS[d]}
            </option>
          ))}
        </select>
      </div>

      {items.length === 0 && (
        <div style={{ padding: 40, textAlign: "center", color: "var(--ink-3)", fontSize: 14, border: "2px dashed var(--border)", borderRadius: 8 }}>
          No applications in the portfolio yet.
        </div>
      )}

      {items.length > 0 && (
        <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(160px, 1fr))", gap: 10 }}>
          {items.map((item) => {
            const swatch = swatchFor(item, dimension, costs);
            const label = valueLabel(item, dimension);
            const unclassified = label === "Unclassified";
            return (
              <div
                key={item.id}
                title={`${item.name}: ${label}`}
                style={{
                  padding: "14px 12px",
                  borderRadius: 6,
                  background: swatch.bg,
                  color: swatch.fg,
                  border: unclassified ? "1px dashed var(--border-strong)" : "1px solid var(--border)",
                }}
              >
                <div style={{ fontSize: 13, fontWeight: 600, marginBottom: 6, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                  {item.name}
                </div>
                <div style={{ fontSize: 12, opacity: 0.9 }}>{label}</div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
