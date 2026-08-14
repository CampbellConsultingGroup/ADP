import { describe, expect, it } from "vitest";
import { checkMetricFields } from "./objectiveMetric";

describe("checkMetricFields", () => {
  it("is valid (no metric) when all four fields are blank", () => {
    expect(checkMetricFields("", "", "", "")).toEqual({ error: null, hasMetric: false });
  });

  it("is valid (has metric) when all four fields are filled in", () => {
    expect(checkMetricFields("Claims cycle time", "40", "%", "decrease")).toEqual({
      error: null,
      hasMetric: true,
    });
  });

  it("errors when only direction is set (the reported bug's exact repro)", () => {
    const result = checkMetricFields("", "", "", "decrease");
    expect(result.error).toBeTruthy();
    expect(result.hasMetric).toBe(false);
  });

  it("errors when only metric name is set", () => {
    const result = checkMetricFields("Claims cycle time", "", "", "");
    expect(result.error).toBeTruthy();
    expect(result.hasMetric).toBe(false);
  });

  it("errors when three of four fields are set", () => {
    const result = checkMetricFields("Claims cycle time", "40", "%", "");
    expect(result.error).toBeTruthy();
    expect(result.hasMetric).toBe(false);
  });

  it("treats whitespace-only input as blank", () => {
    expect(checkMetricFields("   ", "", "", "")).toEqual({ error: null, hasMetric: false });
  });
});
