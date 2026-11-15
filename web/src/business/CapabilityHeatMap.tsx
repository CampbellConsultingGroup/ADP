/** CapabilityHeatMap — every business capability as one heat-map cell, in the
 * same flat L1/L2/L3 hierarchy as the capability tree (043-capability-heat-map,
 * FR-002 resolved: no domain grouping). Shaded by a user-selectable metric
 * (maturity level, default, or strategic relevance) — both already present on
 * every capability fetched via useCapabilities(), so switching metrics is a
 * pure client-side recolor (research.md Decision 1/919's own SC-002 shape).
 * Reuses the already-exported buildTree() rather than a second hierarchy
 * builder (research.md Decision 2).
 *
 * 938-capability-model-analysis (ADP-6et.2, US1/US4): four more metrics rolled up from the
 * three-layer capability model -- application health, risk, cost and technology exposure. They
 * come from ONE roll-up fetch (useCapabilityRollup), made the first time one of them is chosen and
 * cached after, so switching between metrics never refetches (FR-019). L2/L1 cells show the worst
 * leaf value plus the spread over leaves. Cost and risk show as "not available to you" (never as
 * zero or best-case) when the caller lacks the read permission (FR-008). */

import React, { useState } from "react";
import {
  useCapabilities,
  MATURITY_LEVEL_LABEL,
  STRATEGIC_RELEVANCE_LABEL,
  type BusinessCapability,
} from "../api/business";
import {
  LIFECYCLE_BANDS,
  LIFECYCLE_BAND_LABEL,
  RISK_BANDS,
  RISK_BAND_LABEL,
  useCapabilityRollup,
  type CapabilityRollup,
  type CapabilityRollupResponse,
} from "../api/capAnalysis";
import { LIFECYCLE_BAND_SWATCH } from "../application/capAnalysisUi";
import { buildTree, type CapabilityTreeNode } from "./CapabilityTree";

type BaseMetric = "maturity_level" | "strategic_relevance";
type RollupMetric = "health" | "risk" | "cost" | "exposure";
type Metric = BaseMetric | RollupMetric;

const METRIC_LABELS: Record<Metric, string> = {
  maturity_level: "Maturity",
  strategic_relevance: "Strategic relevance",
  health: "Application health",
  risk: "Application risk",
  cost: "Application cost",
  exposure: "Technology exposure",
};

const ROLLUP_METRICS: ReadonlySet<Metric> = new Set<Metric>(["health", "risk", "cost", "exposure"]);
const isRollup = (m: Metric): m is RollupMetric => ROLLUP_METRICS.has(m);

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

const RISK_SWATCH: Record<(typeof RISK_BANDS)[number], Swatch> = {
  high: FIVE_STEP[0],
  medium: FIVE_STEP[1],
  low: FIVE_STEP[4],
};

// Cost is not good or bad, so a sequential accent scale (quartiles of the L3 totals).
const COST_STEPS: Swatch[] = [
  { bg: "color-mix(in srgb, var(--accent) 15%, var(--surface))", fg: "var(--ink)" },
  { bg: "color-mix(in srgb, var(--accent) 35%, var(--surface))", fg: "var(--ink)" },
  { bg: "color-mix(in srgb, var(--accent) 60%, var(--surface))", fg: "#ffffff" },
  { bg: "var(--accent)", fg: "#ffffff" },
];

const UNCLASSIFIED: Swatch = { bg: "var(--surface-2)", fg: "var(--ink-3)" };
const NO_DATA = "No data";

const money = (v: string | null): string =>
  v === null ? "" : Number(v).toLocaleString(undefined, { style: "currency", currency: "USD", maximumFractionDigits: 0 });

interface Cell {
  swatch: Swatch;
  label: string;
  /** Spread summary for parents (and L3s with several applications). */
  spread?: string;
  dashed: boolean;
}

function baseCell(node: BusinessCapability, metric: BaseMetric): Cell {
  const value = node[metric];
  if (value === null) return { swatch: UNCLASSIFIED, label: "Unclassified", dashed: true };
  if (metric === "maturity_level") {
    return { swatch: FIVE_STEP[value - 1], label: MATURITY_LEVEL_LABEL[value as 1 | 2 | 3 | 4 | 5], dashed: false };
  }
  return { swatch: THREE_STEP[value - 1], label: STRATEGIC_RELEVANCE_LABEL[value as 1 | 2 | 3], dashed: false };
}

const SPREAD_LABEL: Record<string, string> = {
  ...RISK_BAND_LABEL,
  ...LIFECYCLE_BAND_LABEL,
  "1": "at health 1",
  "2": "at health 2",
  "3": "at health 3",
  "4": "at health 4",
  "5": "at health 5",
  unassessed: "unassessed",
  no_data: "no data",
};

/** "5 leaves at health 2 · 1 leaf no data" for L1/L2; L3s count apps (or technical capabilities). */
function spreadText(spread: Record<string, number>, level: number, l3Unit: [string, string] = ["app", "apps"]): string {
  const [one, many] = level === 3 ? l3Unit : ["leaf", "leaves"];
  const parts = Object.entries(spread)
    .filter(([k, n]) => n > 0 && !(level === 3 && k === "no_data"))
    .map(([k, n]) => `${n} ${n === 1 ? one : many} ${SPREAD_LABEL[k] ?? k}`);
  return parts.join(" · ");
}

function rollupCell(item: CapabilityRollup | undefined, metric: RollupMetric, costSteps: number[]): Cell {
  const none: Cell = { swatch: UNCLASSIFIED, label: NO_DATA, dashed: true };
  if (!item) return none;
  if (metric === "health") {
    const w = item.health.worst;
    const spread = spreadText(item.health.spread, item.level);
    if (w === null) return { ...none, label: item.health.spread.unassessed ? "Unassessed" : NO_DATA, spread };
    return { swatch: FIVE_STEP[w - 1], label: `Health ${w}`, spread, dashed: false };
  }
  if (metric === "risk") {
    if (!item.risk) return none;
    const w = item.risk.worst;
    const spread = spreadText(item.risk.spread, item.level);
    if (w === null || w === "unknown") return { ...none, label: item.risk.spread.unknown ? "Unknown" : NO_DATA, spread };
    return { swatch: RISK_SWATCH[w], label: `${RISK_BAND_LABEL[w]} risk`, spread, dashed: false };
  }
  if (metric === "cost") {
    if (!item.cost || item.cost.total_tco === null) {
      return { ...none, spread: item.cost?.apps_without_cost ? `${item.cost.apps_without_cost} without cost` : undefined };
    }
    const v = Number(item.cost.total_tco);
    const step = costSteps.filter((t) => v > t).length;
    const missing = item.cost.apps_without_cost ? ` · ${item.cost.apps_without_cost} without cost` : "";
    return {
      swatch: COST_STEPS[Math.min(step, COST_STEPS.length - 1)],
      label: money(item.cost.total_tco),
      spread: `${item.contributing_apps.length} app${item.contributing_apps.length === 1 ? "" : "s"}${missing}`,
      dashed: false,
    };
  }
  const w = item.exposure.worst;
  const spread = spreadText(item.exposure.spread, item.level, ["technical capability", "technical capabilities"]);
  if (w === null) return { ...none, spread };
  return { swatch: LIFECYCLE_BAND_SWATCH[w], label: LIFECYCLE_BAND_LABEL[w], spread, dashed: false };
}

/** Quartile thresholds of the L3 cost totals. */
function costThresholds(data: CapabilityRollupResponse | undefined): number[] {
  const values = (data?.items ?? [])
    .filter((i) => i.level === 3 && i.cost?.total_tco != null)
    .map((i) => Number(i.cost!.total_tco))
    .sort((a, b) => a - b);
  if (values.length === 0) return [];
  return [0.25, 0.5, 0.75].map((q) => values[Math.floor(q * (values.length - 1))]);
}

function legendEntries(metric: Metric): { label: string; swatch: Swatch }[] {
  switch (metric) {
    case "maturity_level":
      return ([1, 2, 3, 4, 5] as const).map((v) => ({ label: MATURITY_LEVEL_LABEL[v], swatch: FIVE_STEP[v - 1] }));
    case "strategic_relevance":
      return ([1, 2, 3] as const).map((v) => ({ label: STRATEGIC_RELEVANCE_LABEL[v], swatch: THREE_STEP[v - 1] }));
    case "health":
      return ([1, 2, 3, 4, 5] as const).map((v) => ({ label: `Health ${v}`, swatch: FIVE_STEP[v - 1] }));
    case "risk":
      return RISK_BANDS.map((b) => ({ label: RISK_BAND_LABEL[b], swatch: RISK_SWATCH[b] }));
    case "cost":
      return [
        { label: "Lowest quarter", swatch: COST_STEPS[0] },
        { label: "Highest quarter", swatch: COST_STEPS[3] },
      ];
    case "exposure":
      return LIFECYCLE_BANDS.map((b) => ({ label: LIFECYCLE_BAND_LABEL[b], swatch: LIFECYCLE_BAND_SWATCH[b] }));
  }
}

interface CapabilityHeatMapProps {
  /** 043-capability-heat-map US3: clicking a cell drills through to that
   *  capability's existing row in the Capabilities tab (research.md Decision
   *  3 — no separate detail screen exists for capabilities to navigate to). */
  onDrillThrough?: (capabilityId: string) => void;
}

interface CellContext {
  metric: Metric;
  rollup: Map<string, CapabilityRollup>;
  costSteps: number[];
  unavailable: boolean;
  onDrillThrough: ((id: string) => void) | undefined;
  onActivate: (id: string) => void;
}

function renderNodes(nodes: CapabilityTreeNode[], ctx: CellContext): React.ReactElement[] {
  return nodes.flatMap((node) => [
    <CapabilityCell key={node.id} node={node} ctx={ctx} />,
    ...renderNodes(node.children, ctx),
  ]);
}

function cellFor(node: CapabilityTreeNode, ctx: CellContext): Cell {
  if (!isRollup(ctx.metric)) return baseCell(node, ctx.metric);
  if (ctx.unavailable) return { swatch: UNCLASSIFIED, label: "Not available to you", dashed: true };
  return rollupCell(ctx.rollup.get(node.id), ctx.metric, ctx.costSteps);
}

function CapabilityCell({ node, ctx }: { node: CapabilityTreeNode; ctx: CellContext }): React.ReactElement {
  const cell = cellFor(node, ctx);
  const indent = (node.level - 1) * 20;
  const item = isRollup(ctx.metric) ? ctx.rollup.get(node.id) : undefined;
  const apps = item?.contributing_apps.map((a) => `${a.name} (via ${a.via.map((v) => v.name).join(", ")})`) ?? [];
  const title = [
    `${node.name}: ${cell.label}`,
    cell.spread,
    apps.length > 0 ? `Applications: ${apps.join("; ")}` : undefined,
    item && item.excluded_retired_apps.length > 0
      ? `Excluded (retired): ${item.excluded_retired_apps.map((a) => a.name).join(", ")}`
      : undefined,
  ]
    .filter(Boolean)
    .join("\n");

  return (
    <div
      title={title}
      role={ctx.onDrillThrough ? "button" : undefined}
      tabIndex={isRollup(ctx.metric) || ctx.onDrillThrough ? 0 : undefined}
      onClick={ctx.onDrillThrough ? () => ctx.onDrillThrough!(node.id) : undefined}
      onKeyDown={(e) => {
        if (e.key === "Enter" && ctx.onDrillThrough) ctx.onDrillThrough(node.id);
      }}
      onMouseEnter={() => ctx.onActivate(node.id)}
      onFocus={() => ctx.onActivate(node.id)}
      data-heatmap-cell={node.id}
      style={{
        marginLeft: indent,
        marginBottom: 4,
        padding: "6px 10px",
        borderRadius: 5,
        background: cell.swatch.bg,
        color: cell.swatch.fg,
        border: cell.dashed ? "1px dashed var(--border-strong)" : "1px solid var(--border)",
        cursor: ctx.onDrillThrough ? "pointer" : "default",
        display: "flex",
        justifyContent: "space-between",
        alignItems: "center",
        gap: 8,
      }}
    >
      <span style={{ fontSize: 13, fontWeight: node.level === 1 ? 700 : 500 }}>{node.name}</span>
      <span style={{ fontSize: 11, opacity: 0.9, textAlign: "right" }}>
        {cell.label}
        {cell.spread && node.level !== 3 && <span style={{ display: "block", fontSize: 10 }}>{cell.spread}</span>}
      </span>
    </div>
  );
}

/** What produced the active cell's value (FR-010): contributing apps, via, excluded retired apps. */
function CellDetail({ item, metric }: { item: CapabilityRollup; metric: RollupMetric }): React.ReactElement {
  return (
    <div
      aria-label="Cell detail"
      aria-live="polite"
      style={{ fontSize: 12, color: "var(--ink-2)", border: "1px solid var(--border)", borderRadius: 6, padding: "8px 10px", marginBottom: 12 }}
    >
      <div style={{ fontWeight: 600, marginBottom: 4 }}>
        {item.name} — {METRIC_LABELS[metric]}
      </div>
      {item.contributing_apps.length === 0 ? (
        <div style={{ color: "var(--ink-3)" }}>No application realizes the application capabilities behind this capability.</div>
      ) : (
        <ul style={{ margin: 0, paddingLeft: 16 }}>
          {item.contributing_apps.map((a) => (
            <li key={a.id}>
              {a.name} <span style={{ color: "var(--ink-3)" }}>via {a.via.map((v) => v.name).join(", ")}</span>
            </li>
          ))}
        </ul>
      )}
      {item.excluded_retired_apps.length > 0 && (
        <div style={{ color: "var(--ink-3)", marginTop: 4 }}>
          Excluded (retired): {item.excluded_retired_apps.map((a) => a.name).join(", ")}
        </div>
      )}
    </div>
  );
}

export default function CapabilityHeatMap({ onDrillThrough }: CapabilityHeatMapProps): React.ReactElement {
  const { data, isLoading, error } = useCapabilities();
  const [metric, setMetric] = useState<Metric>("maturity_level");
  const [rollupWanted, setRollupWanted] = useState(false);
  const [activeId, setActiveId] = useState<string | null>(null);
  const rollupQuery = useCapabilityRollup(rollupWanted);
  const rollupData = rollupQuery.data;

  if (isLoading) return <div style={{ padding: 16, color: "var(--ink-3)" }}>Loading capabilities…</div>;
  if (error) return <div className="ui-alert crit">Failed to load capability heat map</div>;

  const items = data?.items ?? [];
  const tree = buildTree(items);
  const rollup = new Map((rollupData?.items ?? []).map((i) => [i.capability_id, i]));
  const unavailableMetric = (m: Metric): boolean =>
    !!rollupData && ((m === "risk" && !rollupData.risk_available) || (m === "cost" && !rollupData.cost_available));
  const rollupPending = isRollup(metric) && rollupQuery.isLoading;
  const rollupFailed = isRollup(metric) && !!rollupQuery.error;
  const ctx: CellContext = {
    metric,
    rollup,
    costSteps: costThresholds(rollupData),
    unavailable: unavailableMetric(metric),
    onDrillThrough,
    onActivate: setActiveId,
  };
  const activeItem = isRollup(metric) && !ctx.unavailable && activeId ? rollup.get(activeId) : undefined;

  return (
    <div>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 12 }}>
        <span style={{ fontSize: 13, color: "var(--ink-3)" }}>
          {items.length} {items.length === 1 ? "capability" : "capabilities"}
        </span>
        <select
          aria-label="Color by"
          value={metric}
          onChange={(e) => {
            const m = e.target.value as Metric;
            if (isRollup(m)) setRollupWanted(true);
            setMetric(m);
          }}
          style={{ fontSize: 13, padding: "4px 8px", border: "1px solid var(--border)", borderRadius: 4 }}
        >
          {(Object.keys(METRIC_LABELS) as Metric[]).map((m) => (
            <option key={m} value={m} disabled={unavailableMetric(m)}>
              Color by: {METRIC_LABELS[m]}
              {unavailableMetric(m) ? " (not available to you)" : ""}
            </option>
          ))}
        </select>
      </div>

      {isRollup(metric) && (
        <div style={{ fontSize: 12, color: "var(--ink-3)", marginBottom: 10 }}>
          {metric === "exposure"
            ? "Worst lifecycle of the technical capabilities each business capability depends on, through its application capabilities."
            : "Rolled up from the applications that realize each Level 3's application capabilities (retired applications excluded). Level 1 and 2 show the worst leaf and the spread."}
        </div>
      )}
      {rollupPending && <div style={{ fontSize: 12, color: "var(--ink-3)", marginBottom: 10 }}>Loading roll-up…</div>}
      {rollupFailed && <div role="alert" className="ui-alert crit" style={{ marginBottom: 10 }}>Failed to load the capability roll-up.</div>}
      {ctx.unavailable && (
        <div role="note" style={{ fontSize: 12, color: "var(--ink-2)", marginBottom: 10 }}>
          {METRIC_LABELS[metric]} is not available to you.
        </div>
      )}

      {items.length === 0 && (
        <div style={{ padding: 40, textAlign: "center", color: "var(--ink-3)", fontSize: 14, border: "2px dashed var(--border)", borderRadius: 8 }}>
          No business capabilities yet — create some on the Capabilities tab to see the heat map.
        </div>
      )}

      {items.length > 0 && (
        <>
          <div style={{ maxHeight: 520, overflowY: "auto", marginBottom: 14 }}>{renderNodes(tree, ctx)}</div>

          {activeItem && isRollup(metric) && <CellDetail item={activeItem} metric={metric} />}

          <div
            role="list"
            aria-label="Legend"
            style={{ display: "flex", flexWrap: "wrap", gap: 10, alignItems: "center", fontSize: 12, color: "var(--ink-3)" }}
          >
            <span style={{ fontWeight: 600 }}>Legend:</span>
            {!ctx.unavailable &&
              legendEntries(metric).map(({ label, swatch }) => (
                <span key={label} role="listitem" style={{ display: "flex", alignItems: "center", gap: 4 }}>
                  <span style={{ width: 12, height: 12, borderRadius: 3, background: swatch.bg, border: "1px solid var(--border)", display: "inline-block" }} />
                  {label}
                </span>
              ))}
            <span role="listitem" style={{ display: "flex", alignItems: "center", gap: 4 }}>
              <span style={{ width: 12, height: 12, borderRadius: 3, background: UNCLASSIFIED.bg, border: "1px dashed var(--border-strong)", display: "inline-block" }} />
              {isRollup(metric) ? NO_DATA : "Unclassified"}
            </span>
          </div>
          {metric === "cost" && !ctx.unavailable && (
            <div style={{ fontSize: 11, color: "var(--ink-3)", marginTop: 6 }}>
              Cost is the full TCO of the applications involved, not allocated across capabilities, so Level 3 totals don't add up to their parent.
            </div>
          )}
        </>
      )}
    </div>
  );
}
