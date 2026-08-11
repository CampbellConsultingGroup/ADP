// ADP-914.6: unit tests for the persona -> default-diagram-type mapping
// (data-model.md). Pure lookup, no rendering, no mocking needed.

import { describe, expect, it } from "vitest";
import { getRecommendedDiagramType } from "./persona";

describe("getRecommendedDiagramType", () => {
  it("maps enterprise_architect to architecture", () => {
    expect(getRecommendedDiagramType("enterprise_architect")).toBe("architecture");
  });

  it("maps solution_architect to flowchart", () => {
    expect(getRecommendedDiagramType("solution_architect")).toBe("flowchart");
  });

  it("maps technical_architect to sequence", () => {
    expect(getRecommendedDiagramType("technical_architect")).toBe("sequence");
  });

  it("returns undefined for reviewer (cannot reach diagram creation anyway)", () => {
    expect(getRecommendedDiagramType("reviewer")).toBeUndefined();
  });

  it("returns undefined for platform_admin (not an architect persona)", () => {
    expect(getRecommendedDiagramType("platform_admin")).toBeUndefined();
  });

  it("returns undefined for an unrecognized role string", () => {
    expect(getRecommendedDiagramType("some_future_role")).toBeUndefined();
  });

  it("returns undefined when role is undefined", () => {
    expect(getRecommendedDiagramType(undefined)).toBeUndefined();
  });
});
