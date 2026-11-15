/** Display labels and badge tones for the pattern registry UI (935). */

import type { BadgeTone } from "../ui";
import type { PatternKind, PatternLifecycle } from "../api/patterns";

export const KIND_LABELS: Record<PatternKind, string> = {
  "reference-architecture": "Reference architecture",
  "portfolio-rule": "Portfolio rule",
  transition: "Transition",
  "anti-pattern": "Anti-pattern",
};

export const LIFECYCLE_LABELS: Record<PatternLifecycle, string> = {
  draft: "Draft",
  proposed: "Proposed",
  current: "Current",
  deprecated: "Deprecated",
  decommissioned: "Decommissioned",
};

export const LIFECYCLE_TONES: Record<PatternLifecycle, BadgeTone> = {
  draft: "neutral",
  proposed: "info",
  current: "good",
  deprecated: "warn",
  decommissioned: "crit",
};

/** Verb shown on the button that moves a version to the given state. */
export const TRANSITION_VERBS: Record<PatternLifecycle, string> = {
  draft: "Return to draft",
  proposed: "Propose",
  current: "Promote to current",
  deprecated: "Deprecate",
  decommissioned: "Decommission",
};
