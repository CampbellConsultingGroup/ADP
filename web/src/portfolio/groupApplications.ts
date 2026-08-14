// ADP-8xo: Application Portfolio pivot -- the bucketing logic behind the
// "Group by" dropdown, pulled out of PortfolioPage.tsx (unlike
// RationalizationView.tsx's inline single-dimension bucketing) specifically so
// it's independently unit-testable across all 5 dimensions.
//
// Dimension/DIMENSION_LABELS/ALL_DIMENSIONS mirror
// web/src/insights/ApplicationsHeatMap.tsx's own Dimension/DIMENSION_LABELS/
// ALL_DIMENSIONS shape and role -- a string-literal union driving a native
// <select>, ordered array for the option list.
//
// None of these 5 dimensions carry a READ_APPLICATION_* permission gate
// (confirmed against src/adp/authz/permissions.py), so unlike the heat map's
// cost dimension, no permission-aware pruning is needed here.

import type { Application } from "../api/application";
import type { ApplicationCapabilityGroupLink } from "../api/portfolio";

export type Dimension = "capability" | "time" | "r_strategy" | "business_unit" | "criticality";

export const DIMENSION_LABELS: Record<Dimension, string> = {
  capability: "Business Capability",
  time: "TIME Disposition",
  r_strategy: "7R Strategy",
  business_unit: "Ownership / Business Unit",
  criticality: "Criticality / Risk Tier",
};

// Business capability first (the primary EA-native axis), matching the
// requester's own numbered ordering.
export const ALL_DIMENSIONS: Dimension[] = [
  "capability",
  "time",
  "r_strategy",
  "business_unit",
  "criticality",
];

export interface Bucket {
  key: string;
  label: string;
  apps: Application[];
}

export interface GroupedResult {
  buckets: Bucket[];
  unclassified: Application[];
  unclassifiedReason: string;
}

function bucketize<K extends string>(
  apps: Application[],
  order: readonly K[],
  labelFor: (key: K) => string,
  valueOf: (app: Application) => K | null,
  unclassifiedReason: string,
): GroupedResult {
  const byKey = new Map<K, Application[]>(order.map((k) => [k, []]));
  const unclassified: Application[] = [];
  for (const app of apps) {
    const key = valueOf(app);
    if (key === null || !byKey.has(key)) {
      unclassified.push(app);
      continue;
    }
    byKey.get(key)!.push(app);
  }
  const buckets: Bucket[] = order.map((key) => ({
    key,
    label: labelFor(key),
    apps: byKey.get(key)!,
  }));
  return { buckets, unclassified, unclassifiedReason };
}

const TIME_ORDER = ["Tolerate", "Invest", "Migrate", "Eliminate"] as const;

export function groupByTime(apps: Application[]): GroupedResult {
  return bucketize(
    apps,
    TIME_ORDER,
    (k) => k,
    (app) => app.time_classification,
    "missing a TIME disposition",
  );
}

const R_STRATEGY_ORDER = [
  "Rehost",
  "Replatform",
  "Repurchase",
  "Refactor",
  "Retire",
  "Retain",
  "Relocate",
] as const;

export function groupByRStrategy(apps: Application[]): GroupedResult {
  return bucketize(
    apps,
    R_STRATEGY_ORDER,
    (k) => k,
    (app) => app.r_strategy,
    "missing a 7R lifecycle strategy",
  );
}

// Highest tier first -- mirrors ApplicationsHeatMap.tsx's own "invert" convention
// for this field: higher criticality reads as more prominent, not "better".
const CRITICALITY_ORDER = ["5", "4", "3", "2", "1"] as const;

export function groupByCriticality(apps: Application[]): GroupedResult {
  return bucketize(
    apps,
    CRITICALITY_ORDER,
    (k) => `Tier ${k}`,
    (app) =>
      app.business_criticality === null
        ? null
        : (String(app.business_criticality) as (typeof CRITICALITY_ORDER)[number]),
    "missing a criticality score",
  );
}

// The one dimension with a dynamic, data-driven bucket set rather than a fixed,
// known enum -- owning_business_unit is free text on the Application model.
export function groupByBusinessUnit(apps: Application[]): GroupedResult {
  const order = Array.from(
    new Set(apps.map((a) => a.owning_business_unit).filter((v): v is string => v !== null)),
  ).sort((a, b) => a.localeCompare(b));
  return bucketize(
    apps,
    order,
    (k) => k,
    (app) => app.owning_business_unit,
    "missing an owning business unit",
  );
}

// Multi-membership: an app linked to N capabilities appears in N buckets
// (intentional -- the underlying application_capability_links table is
// genuinely many-to-many, there is no "primary capability" concept to force a
// single bucket). Unclassified is a Set-membership check against the links
// list, since this dimension has no scalar field on Application itself.
export function groupByCapability(
  apps: Application[],
  links: ApplicationCapabilityGroupLink[],
): GroupedResult {
  const byId = new Map(apps.map((a) => [a.id, a]));
  const bucketMap = new Map<string, Bucket>();
  const linkedAppIds = new Set<string>();

  for (const link of links) {
    const app = byId.get(link.app_id);
    if (!app) continue; // link references an app not in the current app list
    linkedAppIds.add(app.id);
    let bucket = bucketMap.get(link.capability_id);
    if (!bucket) {
      bucket = { key: link.capability_id, label: link.capability_name, apps: [] };
      bucketMap.set(link.capability_id, bucket);
    }
    bucket.apps.push(app);
  }

  const buckets = Array.from(bucketMap.values()).sort((a, b) => a.label.localeCompare(b.label));
  const unclassified = apps.filter((a) => !linkedAppIds.has(a.id));

  return { buckets, unclassified, unclassifiedReason: "not linked to any business capability" };
}

export function groupApplications(
  dimension: Dimension,
  apps: Application[],
  capabilityLinks: ApplicationCapabilityGroupLink[],
): GroupedResult {
  switch (dimension) {
    case "capability":
      return groupByCapability(apps, capabilityLinks);
    case "time":
      return groupByTime(apps);
    case "r_strategy":
      return groupByRStrategy(apps);
    case "business_unit":
      return groupByBusinessUnit(apps);
    case "criticality":
      return groupByCriticality(apps);
  }
}

// ── Cross-tab (two dimensions at once) ──────────────────────────────────────
//
// Deliberately does NOT reimplement bucketing for two dimensions at once: each
// axis is built by calling groupApplications() for that one dimension, then a
// cell is just the intersection of a row bucket's apps and a column bucket's
// apps. Every dimension's existing behavior -- fixed vs. dynamic bucket sets,
// and capability's multi-membership -- is inherited for free and already
// covered by groupApplications' own tests; this file only tests the
// intersection logic itself.

export interface CrossTabAxis {
  key: string;
  label: string;
}

export interface CrossTabResult {
  rows: CrossTabAxis[];
  columns: CrossTabAxis[];
  cellApps: (rowKey: string, colKey: string) => Application[];
}

const UNCLASSIFIED_KEY = "__unclassified__";

export interface AxisBucket {
  axis: CrossTabAxis;
  apps: Application[];
}

// Shared by cross-tab axes (Dimension only) and filter value buckets
// (FilterField, 3 more fields) -- both just need "a GroupedResult turned into
// a flat list of {key,label,apps}, with Unclassified appended only when
// non-empty" (an empty Unclassified row/column/option is clutter, unlike the
// 1D view's footer, which is a one-time "every application is classified"
// confirmation, not a whole empty line).
function bucketsFromResult(result: GroupedResult): AxisBucket[] {
  const entries: AxisBucket[] = result.buckets.map((b) => ({
    axis: { key: b.key, label: b.label },
    apps: b.apps,
  }));
  if (result.unclassified.length > 0) {
    entries.push({ axis: { key: UNCLASSIFIED_KEY, label: "Unclassified" }, apps: result.unclassified });
  }
  return entries;
}

function axisBuckets(
  dimension: Dimension,
  apps: Application[],
  links: ApplicationCapabilityGroupLink[],
): AxisBucket[] {
  return bucketsFromResult(groupApplications(dimension, apps, links));
}

export function crossTabApplications(
  rowDimension: Dimension,
  colDimension: Dimension,
  apps: Application[],
  links: ApplicationCapabilityGroupLink[],
): CrossTabResult {
  const rowBuckets = axisBuckets(rowDimension, apps, links);
  const colBuckets = axisBuckets(colDimension, apps, links);

  const cellMap = new Map<string, Application[]>();
  for (const row of rowBuckets) {
    const rowIds = new Set(row.apps.map((a) => a.id));
    for (const col of colBuckets) {
      cellMap.set(`${row.axis.key}::${col.axis.key}`, col.apps.filter((a) => rowIds.has(a.id)));
    }
  }

  return {
    rows: rowBuckets.map((r) => r.axis),
    columns: colBuckets.map((c) => c.axis),
    cellApps: (rowKey, colKey) => cellMap.get(`${rowKey}::${colKey}`) ?? [],
  };
}

// ── Filter by (ADP-9ye) ──────────────────────────────────────────────────────
//
// "Limited to values that limit the selection" (the requester's own framing):
// FilterField is deliberately WIDER than Dimension (8 fields vs. 5) -- Group
// By/Then By stay exactly as they were, untouched. The 3 extra fields
// (lifecycle_status, hosting_model, pace_layer) are bounded enums on
// Application not currently used for grouping, but well suited to narrowing.
// v1 is equality-only (pick field, pick exact value) -- comparison/string
// operators are explicit, pre-authorized follow-on work (ADP-6w4), not
// attempted here.

export type FilterField = Dimension | "lifecycle_status" | "hosting_model" | "pace_layer";

export const FILTER_FIELD_LABELS: Record<FilterField, string> = {
  ...DIMENSION_LABELS,
  lifecycle_status: "Lifecycle Status",
  hosting_model: "Hosting Model",
  pace_layer: "Pace Layer",
};

export const ALL_FILTER_FIELDS: FilterField[] = [...ALL_DIMENSIONS, "lifecycle_status", "hosting_model", "pace_layer"];

const LIFECYCLE_STATUS_ORDER = ["planned", "active", "sunset", "retired"] as const;
const LIFECYCLE_STATUS_LABELS: Record<(typeof LIFECYCLE_STATUS_ORDER)[number], string> = {
  planned: "Planned",
  active: "Active",
  sunset: "Sunset",
  retired: "Retired",
};

export function groupByLifecycleStatus(apps: Application[]): GroupedResult {
  return bucketize(
    apps,
    LIFECYCLE_STATUS_ORDER,
    (k) => LIFECYCLE_STATUS_LABELS[k],
    (app) => app.lifecycle_status,
    "missing a lifecycle status",
  );
}

const HOSTING_MODEL_ORDER = ["on_prem", "cloud", "saas", "hybrid"] as const;
const HOSTING_MODEL_LABELS: Record<(typeof HOSTING_MODEL_ORDER)[number], string> = {
  on_prem: "On-Prem",
  cloud: "Cloud",
  saas: "SaaS",
  hybrid: "Hybrid",
};

export function groupByHostingModel(apps: Application[]): GroupedResult {
  return bucketize(
    apps,
    HOSTING_MODEL_ORDER,
    (k) => HOSTING_MODEL_LABELS[k],
    (app) => app.hosting_model,
    "missing a hosting model",
  );
}

const PACE_LAYER_ORDER = ["Record", "Differentiation", "Innovation"] as const;

export function groupByPaceLayer(apps: Application[]): GroupedResult {
  return bucketize(
    apps,
    PACE_LAYER_ORDER,
    (k) => k,
    (app) => app.pace_layer,
    "missing a pace layer",
  );
}

export function groupByField(
  field: FilterField,
  apps: Application[],
  capabilityLinks: ApplicationCapabilityGroupLink[],
): GroupedResult {
  switch (field) {
    case "lifecycle_status":
      return groupByLifecycleStatus(apps);
    case "hosting_model":
      return groupByHostingModel(apps);
    case "pace_layer":
      return groupByPaceLayer(apps);
    default:
      return groupApplications(field, apps, capabilityLinks);
  }
}

export function filterFieldBuckets(
  field: FilterField,
  apps: Application[],
  links: ApplicationCapabilityGroupLink[],
): AxisBucket[] {
  return bucketsFromResult(groupByField(field, apps, links));
}

export function filterApplications(
  field: FilterField,
  valueKey: string,
  apps: Application[],
  links: ApplicationCapabilityGroupLink[],
): Application[] {
  const bucket = filterFieldBuckets(field, apps, links).find((b) => b.axis.key === valueKey);
  return bucket?.apps ?? [];
}
