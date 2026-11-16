// Shared 5-step maturity scale (942-regional-assessments): extracted from CapabilityHeatMap so the
// capability heat map and the regional heat map colour maturity identically. Same diverging scale
// as web/src/insights/ApplicationsHeatMap.tsx (919-insights-dashboard).

export interface Swatch {
  bg: string;
  fg: string;
}

export const FIVE_STEP: Swatch[] = [
  { bg: "var(--crit)", fg: "#ffffff" },
  { bg: "var(--warn)", fg: "#1a1400" },
  { bg: "var(--surface-3)", fg: "var(--ink)" },
  { bg: "var(--good-wash)", fg: "var(--ink)" },
  { bg: "var(--good)", fg: "#ffffff" },
];

/** Swatch for a 1-5 maturity score. */
export function maturitySwatch(level: number): Swatch {
  return FIVE_STEP[Math.min(Math.max(level, 1), 5) - 1];
}
