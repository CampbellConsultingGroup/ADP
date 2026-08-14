// ADP-8xo: pure unit tests for the Application Portfolio pivot's bucketing
// logic -- one describe block per groupBy* function, covering fixed-order
// bucketing, the dynamic business-unit bucket set, the multi-membership
// capability case, and the null -> unclassified case for every dimension.

import { describe, expect, it } from "vitest";
import type { Application } from "../api/application";
import type { ApplicationCapabilityGroupLink } from "../api/portfolio";
import {
  crossTabApplications,
  filterApplications,
  groupByBusinessUnit,
  groupByCapability,
  groupByCriticality,
  groupByHostingModel,
  groupByLifecycleStatus,
  groupByPaceLayer,
  groupByRStrategy,
  groupByTime,
  groupApplications,
} from "./groupApplications";

function app(overrides: Partial<Application> & { id: string; name: string }): Application {
  return {
    description: null,
    vendor: null,
    primary_owner: null,
    time_classification: null,
    r_strategy: null,
    pace_layer: null,
    health_score: null,
    business_value: null,
    business_criticality: null,
    owning_business_unit: null,
    business_owner: null,
    technical_owner: null,
    lifecycle_status: "active",
    hosting_model: null,
    architecture_pattern: null,
    tech_debt_flags: [],
    created_at: "2026-01-01T00:00:00Z",
    updated_at: "2026-01-01T00:00:00Z",
    ...overrides,
  };
}

describe("groupByTime", () => {
  it("places apps into the 4 fixed buckets, in Tolerate/Invest/Migrate/Eliminate order", () => {
    const apps = [
      app({ id: "1", name: "A", time_classification: "Migrate" }),
      app({ id: "2", name: "B", time_classification: "Invest" }),
    ];

    const result = groupByTime(apps);

    expect(result.buckets.map((b) => b.key)).toEqual(["Tolerate", "Invest", "Migrate", "Eliminate"]);
    expect(result.buckets.find((b) => b.key === "Invest")!.apps.map((a) => a.id)).toEqual(["2"]);
    expect(result.buckets.find((b) => b.key === "Migrate")!.apps.map((a) => a.id)).toEqual(["1"]);
  });

  it("renders all 4 buckets even when empty", () => {
    const result = groupByTime([]);
    expect(result.buckets).toHaveLength(4);
    expect(result.buckets.every((b) => b.apps.length === 0)).toBe(true);
  });

  it("puts a null time_classification into unclassified, not a bucket", () => {
    const apps = [app({ id: "1", name: "A", time_classification: null })];

    const result = groupByTime(apps);

    expect(result.unclassified.map((a) => a.id)).toEqual(["1"]);
    expect(result.buckets.every((b) => b.apps.length === 0)).toBe(true);
    expect(result.unclassifiedReason).toMatch(/TIME disposition/);
  });
});

describe("groupByRStrategy", () => {
  it("places apps into all 7 fixed buckets in the documented order", () => {
    const result = groupByRStrategy([]);
    expect(result.buckets.map((b) => b.key)).toEqual([
      "Rehost", "Replatform", "Repurchase", "Refactor", "Retire", "Retain", "Relocate",
    ]);
  });

  it("groups by the app's r_strategy value", () => {
    const apps = [app({ id: "1", name: "A", r_strategy: "Refactor" })];
    const result = groupByRStrategy(apps);
    expect(result.buckets.find((b) => b.key === "Refactor")!.apps.map((a) => a.id)).toEqual(["1"]);
  });

  it("puts a null r_strategy into unclassified", () => {
    const apps = [app({ id: "1", name: "A", r_strategy: null })];
    const result = groupByRStrategy(apps);
    expect(result.unclassified.map((a) => a.id)).toEqual(["1"]);
  });
});

describe("groupByCriticality", () => {
  it("orders buckets highest tier first (5 down to 1)", () => {
    const result = groupByCriticality([]);
    expect(result.buckets.map((b) => b.key)).toEqual(["5", "4", "3", "2", "1"]);
  });

  it("groups by the app's business_criticality value", () => {
    const apps = [app({ id: "1", name: "A", business_criticality: 5 })];
    const result = groupByCriticality(apps);
    expect(result.buckets.find((b) => b.key === "5")!.apps.map((a) => a.id)).toEqual(["1"]);
  });

  it("puts a null business_criticality into unclassified", () => {
    const apps = [app({ id: "1", name: "A", business_criticality: null })];
    const result = groupByCriticality(apps);
    expect(result.unclassified.map((a) => a.id)).toEqual(["1"]);
  });
});

describe("groupByBusinessUnit (dynamic bucket set)", () => {
  it("derives the bucket set from the distinct values actually present, sorted alphabetically", () => {
    const apps = [
      app({ id: "1", name: "A", owning_business_unit: "Claims" }),
      app({ id: "2", name: "B", owning_business_unit: "Underwriting" }),
      app({ id: "3", name: "C", owning_business_unit: "Claims" }),
    ];

    const result = groupByBusinessUnit(apps);

    expect(result.buckets.map((b) => b.key)).toEqual(["Claims", "Underwriting"]);
    expect(result.buckets.find((b) => b.key === "Claims")!.apps.map((a) => a.id)).toEqual(["1", "3"]);
  });

  it("does not invent a bucket for a business unit with no apps (no fixed enum)", () => {
    const apps = [app({ id: "1", name: "A", owning_business_unit: "Claims" })];
    const result = groupByBusinessUnit(apps);
    expect(result.buckets).toHaveLength(1);
  });

  it("puts a null owning_business_unit into unclassified", () => {
    const apps = [app({ id: "1", name: "A", owning_business_unit: null })];
    const result = groupByBusinessUnit(apps);
    expect(result.unclassified.map((a) => a.id)).toEqual(["1"]);
  });
});

describe("groupByCapability (multi-membership)", () => {
  it("an app linked to 2 capabilities appears in both resulting buckets", () => {
    const apps = [app({ id: "1", name: "Claims Core" })];
    const links: ApplicationCapabilityGroupLink[] = [
      { app_id: "1", capability_id: "cap-1", capability_name: "Claims Processing", fit_score: 4 },
      { app_id: "1", capability_id: "cap-2", capability_name: "Fraud Detection", fit_score: 2 },
    ];

    const result = groupByCapability(apps, links);

    expect(result.buckets).toHaveLength(2);
    expect(result.buckets.every((b) => b.apps.map((a) => a.id).includes("1"))).toBe(true);
  });

  it("an app with zero capability links lands in unclassified, not a bucket", () => {
    const apps = [app({ id: "1", name: "Unlinked App" })];

    const result = groupByCapability(apps, []);

    expect(result.buckets).toHaveLength(0);
    expect(result.unclassified.map((a) => a.id)).toEqual(["1"]);
    expect(result.unclassifiedReason).toMatch(/not linked to any business capability/);
  });

  it("orders buckets alphabetically by capability name", () => {
    const apps = [app({ id: "1", name: "A" })];
    const links: ApplicationCapabilityGroupLink[] = [
      { app_id: "1", capability_id: "cap-2", capability_name: "Zeta", fit_score: 3 },
      { app_id: "1", capability_id: "cap-1", capability_name: "Alpha", fit_score: 3 },
    ];

    const result = groupByCapability(apps, links);

    expect(result.buckets.map((b) => b.label)).toEqual(["Alpha", "Zeta"]);
  });
});

describe("groupApplications dispatcher", () => {
  it("dispatches to the correct groupBy* function per dimension", () => {
    const apps = [app({ id: "1", name: "A", time_classification: "Invest" })];
    const result = groupApplications("time", apps, []);
    expect(result.buckets.find((b) => b.key === "Invest")!.apps.map((a) => a.id)).toEqual(["1"]);
  });
});

describe("crossTabApplications (ADP-3wa)", () => {
  it("crosses two fixed dimensions with correct cell intersections", () => {
    const apps = [
      app({ id: "1", name: "A", time_classification: "Invest", r_strategy: "Refactor" }),
      app({ id: "2", name: "B", time_classification: "Invest", r_strategy: "Retire" }),
      app({ id: "3", name: "C", time_classification: "Migrate", r_strategy: "Refactor" }),
    ];

    const result = crossTabApplications("time", "r_strategy", apps, []);

    expect(result.rows.map((r) => r.key)).toEqual(["Tolerate", "Invest", "Migrate", "Eliminate"]);
    expect(result.columns.map((c) => c.key)).toEqual([
      "Rehost", "Replatform", "Repurchase", "Refactor", "Retire", "Retain", "Relocate",
    ]);
    expect(result.cellApps("Invest", "Refactor").map((a) => a.id)).toEqual(["1"]);
    expect(result.cellApps("Invest", "Retire").map((a) => a.id)).toEqual(["2"]);
    expect(result.cellApps("Migrate", "Refactor").map((a) => a.id)).toEqual(["3"]);
    expect(result.cellApps("Tolerate", "Rehost")).toEqual([]);
  });

  it("an app linked to 2 capabilities appears in both row cells' intersections", () => {
    const apps = [app({ id: "1", name: "Claims Core", time_classification: "Invest" })];
    const links: ApplicationCapabilityGroupLink[] = [
      { app_id: "1", capability_id: "cap-1", capability_name: "Claims Processing", fit_score: 4 },
      { app_id: "1", capability_id: "cap-2", capability_name: "Fraud Detection", fit_score: 2 },
    ];

    const result = crossTabApplications("capability", "time", apps, links);

    expect(result.rows.map((r) => r.key)).toEqual(["cap-1", "cap-2"]);
    expect(result.cellApps("cap-1", "Invest").map((a) => a.id)).toEqual(["1"]);
    expect(result.cellApps("cap-2", "Invest").map((a) => a.id)).toEqual(["1"]);
  });

  it("a dynamic dimension (business unit) as an axis produces only the columns present in data", () => {
    const apps = [
      app({ id: "1", name: "A", owning_business_unit: "Claims", time_classification: "Invest" }),
      app({ id: "2", name: "B", owning_business_unit: "Underwriting", time_classification: "Invest" }),
    ];

    const result = crossTabApplications("time", "business_unit", apps, []);

    expect(result.columns.map((c) => c.key)).toEqual(["Claims", "Underwriting"]);
    expect(result.cellApps("Invest", "Claims").map((a) => a.id)).toEqual(["1"]);
  });

  it("includes an Unclassified row/column only when non-empty", () => {
    const classified = [app({ id: "1", name: "A", time_classification: "Invest", r_strategy: "Retire" })];
    const withUnclassified = [
      ...classified,
      app({ id: "2", name: "B", time_classification: null, r_strategy: "Retire" }),
    ];

    const allClassified = crossTabApplications("time", "r_strategy", classified, []);
    expect(allClassified.rows.some((r) => r.key === "__unclassified__")).toBe(false);

    const someUnclassified = crossTabApplications("time", "r_strategy", withUnclassified, []);
    expect(someUnclassified.rows.some((r) => r.key === "__unclassified__")).toBe(true);
    expect(someUnclassified.cellApps("__unclassified__", "Retire").map((a) => a.id)).toEqual(["2"]);
  });

  it("the same dimension on both axes still computes correctly (non-zero only on the diagonal)", () => {
    const apps = [
      app({ id: "1", name: "A", time_classification: "Invest" }),
      app({ id: "2", name: "B", time_classification: "Migrate" }),
    ];

    const result = crossTabApplications("time", "time", apps, []);

    expect(result.cellApps("Invest", "Invest").map((a) => a.id)).toEqual(["1"]);
    expect(result.cellApps("Invest", "Migrate")).toEqual([]);
    expect(result.cellApps("Migrate", "Migrate").map((a) => a.id)).toEqual(["2"]);
  });
});

describe("groupByLifecycleStatus (ADP-9ye)", () => {
  it("places apps into all 4 fixed buckets in the documented order", () => {
    const result = groupByLifecycleStatus([]);
    expect(result.buckets.map((b) => b.key)).toEqual(["planned", "active", "sunset", "retired"]);
  });

  it("groups by the app's lifecycle_status value", () => {
    const apps = [app({ id: "1", name: "A", lifecycle_status: "retired" })];
    const result = groupByLifecycleStatus(apps);
    expect(result.buckets.find((b) => b.key === "retired")!.apps.map((a) => a.id)).toEqual(["1"]);
  });
});

describe("groupByHostingModel (ADP-9ye)", () => {
  it("places apps into all 4 fixed buckets in the documented order", () => {
    const result = groupByHostingModel([]);
    expect(result.buckets.map((b) => b.key)).toEqual(["on_prem", "cloud", "saas", "hybrid"]);
  });

  it("groups by the app's hosting_model value", () => {
    const apps = [app({ id: "1", name: "A", hosting_model: "saas" })];
    const result = groupByHostingModel(apps);
    expect(result.buckets.find((b) => b.key === "saas")!.apps.map((a) => a.id)).toEqual(["1"]);
  });

  it("puts a null hosting_model into unclassified", () => {
    const apps = [app({ id: "1", name: "A", hosting_model: null })];
    const result = groupByHostingModel(apps);
    expect(result.unclassified.map((a) => a.id)).toEqual(["1"]);
  });
});

describe("groupByPaceLayer (ADP-9ye)", () => {
  it("places apps into all 3 fixed buckets in the documented order", () => {
    const result = groupByPaceLayer([]);
    expect(result.buckets.map((b) => b.key)).toEqual(["Record", "Differentiation", "Innovation"]);
  });

  it("groups by the app's pace_layer value", () => {
    const apps = [app({ id: "1", name: "A", pace_layer: "Innovation" })];
    const result = groupByPaceLayer(apps);
    expect(result.buckets.find((b) => b.key === "Innovation")!.apps.map((a) => a.id)).toEqual(["1"]);
  });
});

describe("filterApplications (ADP-9ye)", () => {
  it("filters by one of the original 5 Group By fields", () => {
    const apps = [
      app({ id: "1", name: "A", time_classification: "Invest" }),
      app({ id: "2", name: "B", time_classification: "Migrate" }),
    ];

    expect(filterApplications("time", "Invest", apps, []).map((a) => a.id)).toEqual(["1"]);
  });

  it("filters by one of the 3 new fields not used for grouping", () => {
    const apps = [
      app({ id: "1", name: "A", hosting_model: "cloud" }),
      app({ id: "2", name: "B", hosting_model: "on_prem" }),
    ];

    expect(filterApplications("hosting_model", "cloud", apps, []).map((a) => a.id)).toEqual(["1"]);
  });

  it("filtering to Unclassified returns exactly the apps missing that field", () => {
    const apps = [
      app({ id: "1", name: "A", pace_layer: "Record" }),
      app({ id: "2", name: "B", pace_layer: null }),
    ];

    expect(filterApplications("pace_layer", "__unclassified__", apps, []).map((a) => a.id)).toEqual(["2"]);
  });

  it("a capability filter independently matches every app linked to that capability, including multi-membership apps", () => {
    const apps = [
      app({ id: "1", name: "Claims Core" }),
      app({ id: "2", name: "Other App" }),
    ];
    const links: ApplicationCapabilityGroupLink[] = [
      { app_id: "1", capability_id: "cap-1", capability_name: "Claims Processing", fit_score: 4 },
      { app_id: "1", capability_id: "cap-2", capability_name: "Fraud Detection", fit_score: 2 },
      { app_id: "2", capability_id: "cap-2", capability_name: "Fraud Detection", fit_score: 3 },
    ];

    // app-1 is linked to both capabilities -- filtering by either independently includes it.
    expect(filterApplications("capability", "cap-1", apps, links).map((a) => a.id)).toEqual(["1"]);
    expect(filterApplications("capability", "cap-2", apps, links).map((a) => a.id).sort()).toEqual(["1", "2"]);
  });
});
