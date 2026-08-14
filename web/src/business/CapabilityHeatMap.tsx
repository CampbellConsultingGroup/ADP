/** CapabilityHeatMap — every business capability as one heat-map cell, in the
 * same flat L1/L2/L3 hierarchy as the capability tree (043-capability-heat-map,
 * FR-002 resolved: no domain grouping). Shaded by a user-selectable metric
 * (maturity level, default, or strategic relevance) — both already present on
 * every capability fetched via useCapabilities(), so switching metrics is a
 * pure client-side recolor (research.md Decision 1/919's own SC-002 shape).
 * Reuses the already-exported buildTree() rather than a second hierarchy
 * builder (research.md Decision 2). */

import React, { useState } from "react";
import {
  useCapabilities,
  MATURITY_LEVEL_LABEL,
  STRATEGIC_RELEVANCE_LABEL,
  type BusinessCapability,
} from "../api/business";
import { buildTree, type CapabilityTreeNode } from "./CapabilityTree";

type Metric = "maturity_level" | "strategic_relevance";

const METRIC_LABELS: Record<Metric, string> = {
  maturity_level: "Maturity",
  strategic_relevance: "Strategic relevance",
};

interface Swatch {
  bg: string;
  fg: string;
}

// Same 5-step diverging scale as web/src/insights/ApplicationsHeatMap.tsx
// (919-insights-dashboard) -- kept visually consistent across both heat maps.
const FIVE_STEP: Swatch[] = [
  { bg: "var(--crit)", fg: "#ffffff" },
  { bg: "var(--warn)", fg: "#1a1400" },
  { bg: "var(--surface-3)", fg: "var(--ink)" },
  { bg: "var(--good-wash)", fg: "var(--ink)" },
  { bg: "var(--good)", fg: "#ffffff" },
];

// strategic_relevance is a genuine 3-value scale (Strategic/Core/Supporting),
// not a stretched subset of the 5-step array (research.md Decision 4).
const THREE_STEP: Swatch[] = [
  { bg: "var(--good)", fg: "#ffffff" }, // 1 = Strategic
  { bg: "var(--surface-3)", fg: "var(--ink)" }, // 2 = Core
  { bg: "var(--warn)", fg: "#1a1400" }, // 3 = Supporting
];

const UNCLASSIFIED: Swatch = { bg: "var(--surface-2)", fg: "var(--ink-3)" };

function swatchFor(node: BusinessCapability, metric: Metric): Swatch {
  const value = node[metric];
  if (value === null) return UNCLASSIFIED;
  if (metric === "maturity_level") return FIVE_STEP[value - 1];
  return THREE_STEP[value - 1];
}

function valueLabel(node: BusinessCapability, metric: Metric): string {
  const value = node[metric];
  if (value === null) return "Unclassified";
  return metric === "maturity_level"
    ? MATURITY_LEVEL_LABEL[value as 1 | 2 | 3 | 4 | 5]
    : STRATEGIC_RELEVANCE_LABEL[value as 1 | 2 | 3];
}

function legendEntries(metric: Metric): { label: string; swatch: Swatch }[] {
  if (metric === "maturity_level") {
    return ([1, 2, 3, 4, 5] as const).map((v) => ({
      label: MATURITY_LEVEL_LABEL[v],
      swatch: FIVE_STEP[v - 1],
    }));
  }
  return ([1, 2, 3] as const).map((v) => ({
    label: STRATEGIC_RELEVANCE_LABEL[v],
    swatch: THREE_STEP[v - 1],
  }));
}

interface CapabilityHeatMapProps {
  /** 043-capability-heat-map US3: clicking a cell drills through to that
   *  capability's existing row in the Capabilities tab (research.md Decision
   *  3 — no separate detail screen exists for capabilities to navigate to). */
  onDrillThrough?: (capabilityId: string) => void;
}

function renderNodes(
  nodes: CapabilityTreeNode[],
  metric: Metric,
  onDrillThrough: ((id: string) => void) | undefined,
): React.ReactElement[] {
  return nodes.flatMap((node) => [
    <CapabilityCell key={node.id} node={node} metric={metric} onDrillThrough={onDrillThrough} />,
    ...renderNodes(node.children, metric, onDrillThrough),
  ]);
}

function CapabilityCell({
  node,
  metric,
  onDrillThrough,
}: {
  node: CapabilityTreeNode;
  metric: Metric;
  onDrillThrough: ((id: string) => void) | undefined;
}): React.ReactElement {
  const swatch = swatchFor(node, metric);
  const label = valueLabel(node, metric);
  const indent = (node.level - 1) * 20;

  return (
    <div
      title={`${node.name}: ${label}`}
      onClick={onDrillThrough ? () => onDrillThrough(node.id) : undefined}
      style={{
        marginLeft: indent,
        marginBottom: 4,
        padding: "6px 10px",
        borderRadius: 5,
        background: swatch.bg,
        color: swatch.fg,
        border: label === "Unclassified" ? "1px dashed var(--border-strong)" : "1px solid var(--border)",
        cursor: onDrillThrough ? "pointer" : "default",
        display: "flex",
        justifyContent: "space-between",
        alignItems: "center",
        gap: 8,
      }}
    >
      <span style={{ fontSize: 13, fontWeight: node.level === 1 ? 700 : 500 }}>{node.name}</span>
      <span style={{ fontSize: 11, opacity: 0.9 }}>{label}</span>
    </div>
  );
}

export default function CapabilityHeatMap({ onDrillThrough }: CapabilityHeatMapProps): React.ReactElement {
  const { data, isLoading, error } = useCapabilities();
  const [metric, setMetric] = useState<Metric>("maturity_level");

  if (isLoading) return <div style={{ padding: 16, color: "var(--ink-3)" }}>Loading capabilities…</div>;
  if (error) return <div className="ui-alert crit">Failed to load capability heat map</div>;

  const items = data?.items ?? [];
  const tree = buildTree(items);

  return (
    <div>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 12 }}>
        <span style={{ fontSize: 13, color: "var(--ink-3)" }}>
          {items.length} {items.length === 1 ? "capability" : "capabilities"}
        </span>
        <select
          aria-label="Color by"
          value={metric}
          onChange={(e) => setMetric(e.target.value as Metric)}
          style={{ fontSize: 13, padding: "4px 8px", border: "1px solid var(--border)", borderRadius: 4 }}
        >
          {(Object.keys(METRIC_LABELS) as Metric[]).map((m) => (
            <option key={m} value={m}>
              Color by: {METRIC_LABELS[m]}
            </option>
          ))}
        </select>
      </div>

      {items.length === 0 && (
        <div style={{ padding: 40, textAlign: "center", color: "var(--ink-3)", fontSize: 14, border: "2px dashed var(--border)", borderRadius: 8 }}>
          No business capabilities yet — create some on the Capabilities tab to see the heat map.
        </div>
      )}

      {items.length > 0 && (
        <>
          <div style={{ maxHeight: 520, overflowY: "auto", marginBottom: 14 }}>
            {renderNodes(tree, metric, onDrillThrough)}
          </div>

          <div
            role="list"
            aria-label="Legend"
            style={{ display: "flex", flexWrap: "wrap", gap: 10, alignItems: "center", fontSize: 12, color: "var(--ink-3)" }}
          >
            <span style={{ fontWeight: 600 }}>Legend:</span>
            {legendEntries(metric).map(({ label, swatch }) => (
              <span key={label} style={{ display: "flex", alignItems: "center", gap: 4 }}>
                <span style={{ width: 12, height: 12, borderRadius: 3, background: swatch.bg, border: "1px solid var(--border)", display: "inline-block" }} />
                {label}
              </span>
            ))}
            <span style={{ display: "flex", alignItems: "center", gap: 4 }}>
              <span style={{ width: 12, height: 12, borderRadius: 3, background: UNCLASSIFIED.bg, border: "1px dashed var(--border-strong)", display: "inline-block" }} />
              Unclassified
            </span>
          </div>
        </>
      )}
    </div>
  );
}
