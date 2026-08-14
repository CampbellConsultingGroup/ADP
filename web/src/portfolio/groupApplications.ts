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
