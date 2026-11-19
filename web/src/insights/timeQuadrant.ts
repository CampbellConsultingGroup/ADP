/** Layout for the TIME quadrant bubble chart (ADP-v2n). Pure: no React, no I/O.
 *
 * Position comes from the rationalization projection (business value x technical health,
 * both 1-5; GET /applications/rationalization), so a bubble's quadrant is exactly the one the
 * Applications screen shows. Colour is the application's own TIME classification, which is
 * set by hand, so a bubble whose colour does not match its quadrant is worth a second look.
 * Size is total cost of ownership, only when the caller may read cost. */

import type { Quadrant, RationalizationEntry, TimeClassification } from "../api/application";
import type { ApplicationHeatmapEntry } from "../api/portfolio";

export interface Bubble {
  id: string;
  name: string;
  businessValue: number;
  health: number;
  quadrant: Quadrant;
  time: TimeClassification | null;
  cost: number | null;
  /** Centre and radius in chart (SVG) units. */
  cx: number;
  cy: number;
  r: number;
  /** The hand-set TIME classification names a different quadrant than the scores give. */
  mismatch: boolean;
}

export const CHART = { width: 640, height: 440, left: 56, right: 16, top: 16, bottom: 48 } as const;
export const PLOT_W = CHART.width - CHART.left - CHART.right;
export const PLOT_H = CHART.height - CHART.top - CHART.bottom;

/** Scores run 1-5; the axis runs 0.5-5.5 so a score sits in the middle of its band. */
const MIN = 0.5;
const SPAN = 5;
/** rationalization.py: a score >= 3 is "high", so the quadrant line falls at 2.5. */
export const SPLIT = 2.5;

export const R_DEFAULT = 9;
export const R_MIN = 6;
export const R_MAX = 22;

export function xFor(health: number): number {
  return CHART.left + ((health - MIN) / SPAN) * PLOT_W;
}

export function yFor(businessValue: number): number {
  return CHART.top + PLOT_H - ((businessValue - MIN) / SPAN) * PLOT_H;
}

/** Area-proportional radius: a bubble twice the cost has twice the area. */
export function radiusFor(cost: number | null, maxCost: number, costShown: boolean): number {
  if (!costShown || cost === null || maxCost <= 0) return R_DEFAULT;
  return Math.max(R_MIN, R_MAX * Math.sqrt(Math.max(0, cost) / maxCost));
}

/** Applications with the same two scores share a point; spread them on a sunflower spiral so
 * every one stays visible and clickable. The first sits on the point itself. */
export function spreadOffset(index: number, step: number): { dx: number; dy: number } {
  if (index === 0) return { dx: 0, dy: 0 };
  const angle = index * 2.399963; // golden angle, radians
  const dist = step * Math.sqrt(index);
  return { dx: dist * Math.cos(angle), dy: dist * Math.sin(angle) };
}

export function layoutBubbles(
  assessed: RationalizationEntry[],
  heatmap: ApplicationHeatmapEntry[],
  costShown: boolean,
): Bubble[] {
  const byId = new Map(heatmap.map((h) => [h.id, h]));
  const placed = assessed.filter(
    (a): a is RationalizationEntry & { business_value: number; health_score: number; quadrant: Quadrant } =>
      a.business_value !== null && a.health_score !== null && a.quadrant !== null,
  );
  const costs = placed.map((a) => byId.get(a.app_id)?.cost ?? null).filter((c): c is number => c !== null);
  const maxCost = costs.length ? Math.max(...costs) : 0;

  // Largest first, so small bubbles are drawn on top and stay clickable.
  const withSize = placed
    .map((a) => {
      const h = byId.get(a.app_id);
      const cost = costShown ? (h?.cost ?? null) : null;
      return { a, h, cost, r: radiusFor(cost, maxCost, costShown) };
    })
    .sort((p, q) => q.r - p.r || p.a.name.localeCompare(q.a.name));

  const seen = new Map<string, number>();
  return withSize.map(({ a, h, cost, r }) => {
    const key = `${a.health_score}:${a.business_value}`;
    const index = seen.get(key) ?? 0;
    seen.set(key, index + 1);
    const { dx, dy } = spreadOffset(index, R_DEFAULT * 1.6);
    const time = (h?.time_classification ?? null) as TimeClassification | null;
    return {
      id: a.app_id,
      name: a.name,
      businessValue: a.business_value,
      health: a.health_score,
      quadrant: a.quadrant,
      time,
      cost,
      cx: xFor(a.health_score) + dx,
      cy: yFor(a.business_value) + dy,
      r,
      mismatch: time !== null && time.toLowerCase() !== a.quadrant,
    };
  });
}
