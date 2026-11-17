import type { BadgeTone } from "./primitives";

/**
 * What each status colour means, and which tone every status in the app uses (ADP-blp.49).
 *
 * These maps lived in seven feature files, each written on its own, so the same idea could end
 * up in different colours on different screens. They are all here now, against one definition:
 *
 *   good     on track, healthy, in force            (green)
 *   warn     needs attention soon                   (amber)
 *   crit     failing or blocked now: act on it      (red)
 *   info     in progress, or cannot be judged yet   (blue)
 *   neutral  inactive or ended: nothing to do       (grey)
 *
 * An ended state (decommissioned, abandoned, retired) is neutral, never crit. The feature
 * modules re-export their map from here under its old name. See docs/ui-glossary.md.
 */
type Tones = Record<string, BadgeTone>;

/** Design lifecycle (Designs, Governance). */
export const DESIGN_LIFECYCLE_TONES = {
  draft: "neutral",
  proposed: "info",
  current: "good",
  complete: "good",
  deprecated: "warn",
  decommissioned: "neutral",
} as const satisfies Tones;

/** Pattern version lifecycle (Patterns). */
export const PATTERN_LIFECYCLE_TONES = {
  draft: "neutral",
  proposed: "info",
  current: "good",
  deprecated: "warn",
  decommissioned: "neutral",
} as const satisfies Tones;

/** Pattern conformance of an adoption. */
export const CONFORMANCE_TONES = {
  conformant: "good",
  conformant_with_warnings: "warn",
  non_conformant: "crit",
  indeterminate: "info",
  not_applicable: "neutral",
} as const satisfies Tones;

/** Strategic objective status. "proposed" has not started, so it is neutral, not info. */
export const OBJECTIVE_STATUS_TONES = {
  proposed: "neutral",
  active: "info",
  at_risk: "warn",
  achieved: "good",
  abandoned: "neutral",
} as const satisfies Tones;

/** Agentic risk band. */
export const RISK_BAND_TONES = { high: "crit", medium: "warn", low: "good" } as const satisfies Tones;

/** TIME disposition of an application. */
export const TIME_TONES = {
  Invest: "good",
  Migrate: "warn",
  Eliminate: "crit",
  Tolerate: "neutral",
} as const satisfies Tones;

/** Strategic classification of a business capability. */
export const CLASSIFICATION_TONES = {
  strategic: "good",
  differentiating: "warn",
  commodity: "neutral",
} as const satisfies Tones;

/** Design validation verdict. */
export const VERDICT_TONES = {
  pass: "good",
  fail: "crit",
  // Could not be judged: the same tone as an indeterminate conformance result.
  indeterminate: "info",
  overridden: "info",
} as const satisfies Tones;
