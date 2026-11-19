// ADP-v2n: layout of the TIME quadrant bubble chart.

import { describe, expect, it } from "vitest";
import type { RationalizationEntry } from "../api/application";
import type { ApplicationHeatmapEntry } from "../api/portfolio";
import { R_DEFAULT, R_MAX, R_MIN, SPLIT, layoutBubbles, radiusFor, spreadOffset, xFor, yFor } from "./timeQuadrant";

function rat(app_id: string, business_value: number, health_score: number): RationalizationEntry {
  const high = business_value >= 3;
  const healthy = health_score >= 3;
  const quadrant = high ? (healthy ? "invest" : "migrate") : healthy ? "tolerate" : "eliminate";
  return { app_id, name: app_id, business_value, health_score, quadrant };
}

function heat(id: string, time: ApplicationHeatmapEntry["time_classification"], cost: number | null): ApplicationHeatmapEntry {
  return { id, name: id, health_score: null, business_criticality: null, time_classification: time, cost };
}

describe("axes", () => {
  it("puts the quadrant split between 2 and 3 on both axes", () => {
    expect(xFor(2) < xFor(SPLIT) && xFor(SPLIT) < xFor(3)).toBe(true);
    // SVG y grows downwards: a higher business value is nearer the top.
    expect(yFor(3) < yFor(SPLIT) && yFor(SPLIT) < yFor(2)).toBe(true);
  });
});

describe("radiusFor", () => {
  it("is the same for every bubble when cost is not shown", () => {
    expect(radiusFor(1_000_000, 1_000_000, false)).toBe(R_DEFAULT);
  });

  it("scales by area, with a floor, and uses the default for a missing cost", () => {
    expect(radiusFor(100, 100, true)).toBe(R_MAX);
    expect(radiusFor(25, 100, true)).toBeCloseTo(R_MAX / 2);
    expect(radiusFor(0, 100, true)).toBe(R_MIN);
    expect(radiusFor(null, 100, true)).toBe(R_DEFAULT);
  });
});

describe("spreadOffset", () => {
  it("keeps the first application on the point and moves the rest off it", () => {
    expect(spreadOffset(0, 10)).toEqual({ dx: 0, dy: 0 });
    const second = spreadOffset(1, 10);
    expect(Math.hypot(second.dx, second.dy)).toBeCloseTo(10);
  });
});

describe("layoutBubbles", () => {
  it("joins TIME classification and cost by application id", () => {
    const [b] = layoutBubbles([rat("a", 5, 5)], [heat("a", "Invest", 500)], true);
    expect(b).toMatchObject({ id: "a", quadrant: "invest", time: "Invest", cost: 500, mismatch: false });
  });

  it("flags a TIME classification that differs from the quadrant", () => {
    const [b] = layoutBubbles([rat("a", 5, 1)], [heat("a", "Invest", null)], false);
    expect(b.quadrant).toBe("migrate");
    expect(b.mismatch).toBe(true);
  });

  it("does not flag an application with no TIME classification", () => {
    const [b] = layoutBubbles([rat("a", 1, 1)], [], false);
    expect(b.time).toBeNull();
    expect(b.mismatch).toBe(false);
  });

  it("hides cost when the caller may not read it", () => {
    const [b] = layoutBubbles([rat("a", 4, 4)], [heat("a", "Invest", 900)], false);
    expect(b.cost).toBeNull();
    expect(b.r).toBe(R_DEFAULT);
  });

  it("spreads applications with the same scores so none sit exactly on top of another", () => {
    const bubbles = layoutBubbles([rat("a", 4, 4), rat("b", 4, 4), rat("c", 4, 4)], [], false);
    const points = new Set(bubbles.map((b) => `${b.cx.toFixed(2)},${b.cy.toFixed(2)}`));
    expect(points.size).toBe(3);
  });

  it("draws larger bubbles first so smaller ones stay on top", () => {
    const bubbles = layoutBubbles(
      [rat("small", 4, 4), rat("big", 2, 2)],
      [heat("small", "Invest", 10), heat("big", "Eliminate", 1000)],
      true,
    );
    expect(bubbles.map((b) => b.id)).toEqual(["big", "small"]);
  });

  it("skips entries without both scores", () => {
    const partial: RationalizationEntry = { app_id: "x", name: "x", business_value: 3, health_score: null, quadrant: null };
    expect(layoutBubbles([partial], [], false)).toEqual([]);
  });
});
