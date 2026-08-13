import { describe, it, expect } from "vitest";
import { filterElementsForLevel, filterRelationshipsForLevel } from "./c4-filter";
import type { Element, Relationship } from "../types";

const elements: Element[] = [
  { id: "p1", name: "User", kind: "person" },
  { id: "s1", name: "Web App", kind: "system" },
  { id: "c1", name: "API Gateway", kind: "container" },
  { id: "c2", name: "Auth Service", kind: "container" },
  { id: "co1", name: "JWT Handler", kind: "component" },
];

describe("filterElementsForLevel", () => {
  it("test_c4_filter_context_level — returns only person + system", () => {
    const result = filterElementsForLevel(elements, "context");
    expect(result.map((e) => e.id).sort()).toEqual(["p1", "s1"].sort());
  });

  it("test_c4_filter_container_level — returns system + container", () => {
    const result = filterElementsForLevel(elements, "container");
    expect(result.map((e) => e.id).sort()).toEqual(["c1", "c2", "s1"].sort());
  });

  it("test_c4_filter_component_level — returns container + component", () => {
    const result = filterElementsForLevel(elements, "component");
    expect(result.map((e) => e.id).sort()).toEqual(["c1", "c2", "co1"].sort());
  });
});

describe("filterRelationshipsForLevel", () => {
  it("test_relationship_filter_hides_cross_level_edges", () => {
    // person → container: at context level, only person+system visible → container hidden → edge hidden
    const rels: Relationship[] = [
      { id: "r1", source: "p1", target: "c1" }, // person→container: cross-level
      { id: "r2", source: "p1", target: "s1" }, // person→system: both in context
    ];
    const visibleAtContext = new Set(["p1", "s1"]);
    const result = filterRelationshipsForLevel(rels, visibleAtContext);
    expect(result.map((r) => r.id)).toEqual(["r2"]);
  });

  it("shows relationships where both endpoints are visible", () => {
    const rels: Relationship[] = [{ id: "r1", source: "c1", target: "c2" }];
    const visible = new Set(["c1", "c2"]);
    expect(filterRelationshipsForLevel(rels, visible)).toHaveLength(1);
  });
});
