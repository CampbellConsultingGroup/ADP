/** Display labels and badge tones for the pattern registry UI (935). */

import type { BadgeTone } from "../ui";
import type { ConformanceStatus, PatternKind, PatternLifecycle, ScopeType } from "../api/patterns";

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
  // ADP-blp.49: an ended state, not a failure -- red is kept for things that need attention.
  decommissioned: "neutral",
};

/** Verb shown on the button that moves a version to the given state. */
export const TRANSITION_VERBS: Record<PatternLifecycle, string> = {
  draft: "Return to draft",
  proposed: "Propose",
  current: "Promote to current",
  deprecated: "Deprecate",
  decommissioned: "Decommission",
};

// 936: adoptions and conformance

export const STATUS_LABELS: Record<ConformanceStatus, string> = {
  conformant: "Conformant",
  conformant_with_warnings: "Conformant with warnings",
  non_conformant: "Non-conformant",
  indeterminate: "Indeterminate",
  not_applicable: "Not applicable",
};

export const STATUS_TONES: Record<ConformanceStatus, BadgeTone> = {
  conformant: "good",
  conformant_with_warnings: "warn",
  non_conformant: "crit",
  indeterminate: "info",
  not_applicable: "neutral",
};

export const SCOPE_LABELS: Record<ScopeType, string> = {
  business_domain: "Business domain",
  application_set: "Application set",
  portfolio: "Whole portfolio",
};
