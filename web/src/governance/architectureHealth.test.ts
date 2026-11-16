// 939-governance-architecture-health: the pure derivations shared by the tiles and the sections,
// so their counts can't disagree (SC-002).

import { describe, expect, it } from "vitest";
import type { Adoption, ConformanceStatus } from "../api/patterns";
import type { CapabilityFindings, CapabilityRollup, CapabilityRollupResponse, LifecycleBand } from "../api/capAnalysis";
import { adoptionsNeedingAttention, exposedCapabilities, gapCount, overlapCounts } from "./architectureHealth";

function adoption(name: string, status: ConformanceStatus | null): Adoption {
  return {
    id: name, pattern_key: "p", pattern_name: "P", kind: "reference-architecture", name,
    scope_type: "business_domain", scope_ref: "d", scope_name: "D", member_ids: [],
    pinned_version: null, resolved_version: "1.0.0", pins: [], created_at: "", created_by: "", updated_at: "", status,
  };
}

function cap(name: string, level: number, band: LifecycleBand | null): CapabilityRollup {
  return {
    capability_id: name, name, level, contributing_apps: [], excluded_retired_apps: [],
    health: { worst: null, spread: {} }, risk: null, cost: null,
    exposure: { worst: band, spread: {} },
  };
}

const rollup = (items: CapabilityRollup[]): CapabilityRollupResponse => ({
  as_of: "2026-11-15", risk_available: true, cost_available: true, items,
});

describe("adoptionsNeedingAttention", () => {
  it("orders by status, then name, and summarizes the rest", () => {
    const result = adoptionsNeedingAttention([
      adoption("b-warn", "conformant_with_warnings"),
      adoption("z-bad", "non_conformant"),
      adoption("ok", "conformant"),
      adoption("a-bad", "non_conformant"),
      adoption("unknown", "indeterminate"),
      adoption("n/a", "not_applicable"),
      adoption("no-status", null),
    ]);
    expect(result.attention.map((a) => a.name)).toEqual(["a-bad", "z-bad", "unknown", "b-warn"]);
    expect(result.nonConformant).toBe(2);
    expect(result.indeterminate).toBe(1);
    expect(result.conformant).toBe(1);
    expect(result.notApplicable).toBe(1);
  });

  it("accepts undefined", () => {
    expect(adoptionsNeedingAttention(undefined)).toEqual({
      attention: [], nonConformant: 0, indeterminate: 0, conformant: 0, notApplicable: 0,
    });
  });
});

describe("exposedCapabilities", () => {
  it("keeps only Level 3s that are past end of life or retiring, worst first, then by name", () => {
    const items = exposedCapabilities(
      rollup([
        cap("Sales", 1, "retiring"),
        cap("In-Store", 2, "retiring"),
        cap("Zeta", 3, "retiring"),
        cap("Alpha", 3, "retiring"),
        cap("Old", 3, "past_end_of_life"),
        cap("Contained", 3, "contained"),
        cap("Fine", 3, "current"),
        cap("Nothing", 3, null),
      ]),
    );
    expect(items.map((i) => i.name)).toEqual(["Old", "Alpha", "Zeta"]);
  });

  it("accepts undefined", () => {
    expect(exposedCapabilities(undefined)).toEqual([]);
  });
});

describe("gapCount", () => {
  it("totals the three gap lists", () => {
    const ref = (id: string) => ({ id, name: id, level: 3, path: [] });
    const findings: CapabilityFindings = {
      overlaps: [],
      gaps: {
        business_without_app_capability: [ref("a"), ref("b")],
        app_capability_without_business: [ref("c")],
        app_capability_without_application: [ref("d"), ref("e"), ref("f")],
      },
      shared: [],
      shared_threshold: 3,
      redundant: [],
    };
    expect(gapCount(findings)).toBe(6);
    expect(gapCount(undefined)).toBe(0);
  });
});

describe("overlapCounts (943)", () => {
  it("counts overlaps needing attention and explained ones separately", () => {
    const o = (status: "needs_attention" | "explained") => ({
      business: { id: status, name: status, level: 3, path: [] },
      applications: [],
      status,
      reasons: [],
    });
    const findings = {
      overlaps: [o("needs_attention"), o("needs_attention"), o("explained")],
      gaps: { business_without_app_capability: [], app_capability_without_business: [], app_capability_without_application: [] },
      shared: [],
      shared_threshold: 3,
      redundant: [],
    };
    expect(overlapCounts(findings)).toEqual({ needsAttention: 2, explained: 1 });
    expect(overlapCounts(undefined)).toEqual({ needsAttention: 0, explained: 0 });
  });
});
