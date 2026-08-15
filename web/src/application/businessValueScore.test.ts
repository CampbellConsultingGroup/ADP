// Mirrors tests/unit/application/test_business_value_score.py's coverage
// for the Python original -- this is the client-side copy used only for
// the popup's live preview text (docs/application-business-value-
// assessment-spec.md §5), so it must stay in sync with the same
// weights/cap-table/rounding behavior.

import { describe, expect, it } from "vitest";
import { computeBusinessValueScore } from "./businessValueScore";
import type { BusinessValueDimension } from "../api/application";

const UNIFORM: Record<BusinessValueDimension, number> = {
  strategic_alignment: 3,
  revenue_cost_impact: 3,
  customer_stakeholder_impact: 3,
  competitive_differentiation: 3,
  risk_compliance_contribution: 3,
  evidence_measurability: 3,
};

function scores(overrides: Partial<Record<BusinessValueDimension, number>>): Record<BusinessValueDimension, number> {
  return { ...UNIFORM, ...overrides };
}

describe("computeBusinessValueScore", () => {
  it("a uniform score across all six never gets capped tighter than itself", () => {
    expect(computeBusinessValueScore(scores({})).businessValue).toBe(3);
    const allOnes = Object.fromEntries(Object.keys(UNIFORM).map((k) => [k, 1])) as Record<BusinessValueDimension, number>;
    expect(computeBusinessValueScore(allOnes).businessValue).toBe(1);
    const allFives = Object.fromEntries(Object.keys(UNIFORM).map((k) => [k, 5])) as Record<BusinessValueDimension, number>;
    const result = computeBusinessValueScore(allFives);
    expect(result.businessValue).toBe(5);
    expect(result.cap).toBeNull();
  });

  it("matches the spec's own worked example: high scores but low evidence gets capped", () => {
    const result = computeBusinessValueScore(
      scores({
        strategic_alignment: 5,
        revenue_cost_impact: 5,
        customer_stakeholder_impact: 4,
        competitive_differentiation: 4,
        risk_compliance_contribution: 3,
        evidence_measurability: 1,
      }),
    );
    expect(result.weightedAverage).toBe(4.05);
    expect(result.cap).toBe(2);
    expect(result.capped).toBe(true);
    expect(result.businessValue).toBe(2);
  });

  it.each([
    [1, 2],
    [2, 3],
    [3, 4],
    [4, null],
    [5, null],
  ])("evidence score %i caps the overall at %s", (evidence, expectedCap) => {
    const result = computeBusinessValueScore(
      scores({ evidence_measurability: evidence, strategic_alignment: 5, revenue_cost_impact: 5 }),
    );
    expect(result.cap).toBe(expectedCap);
  });

  it("a present cap that isn't binding is not flagged as capped", () => {
    const result = computeBusinessValueScore(scores({ evidence_measurability: 3 }));
    expect(result.cap).toBe(4);
    expect(result.weightedAverage).toBe(3.0);
    expect(result.capped).toBe(false);
    expect(result.businessValue).toBe(3);
  });

  it("strategic alignment and revenue carry more weight than competitive differentiation", () => {
    const lowWeightBoost = computeBusinessValueScore(
      scores({ competitive_differentiation: 5, evidence_measurability: 5 }),
    );
    const highWeightBoost = computeBusinessValueScore(
      scores({ strategic_alignment: 5, evidence_measurability: 5 }),
    );
    expect(highWeightBoost.weightedAverage).toBeGreaterThan(lowWeightBoost.weightedAverage);
  });

  it("business value always lands within 1-5", () => {
    for (let uniform = 1; uniform <= 5; uniform++) {
      const allSame = Object.fromEntries(Object.keys(UNIFORM).map((k) => [k, uniform])) as Record<BusinessValueDimension, number>;
      const result = computeBusinessValueScore(allSame);
      expect(result.businessValue).toBeGreaterThanOrEqual(1);
      expect(result.businessValue).toBeLessThanOrEqual(5);
    }
  });
});
