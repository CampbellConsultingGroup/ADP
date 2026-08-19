import type { BadgeTone } from "../ui";

/** Design lifecycle status → semantic badge tone + label. */
export const LIFECYCLE_TONE: Record<string, BadgeTone> = {
  draft: "neutral",
  proposed: "info",
  current: "good",
  complete: "good",
  deprecated: "warn",
  decommissioned: "crit",
};

export const LIFECYCLE_LABEL: Record<string, string> = {
  draft: "Draft",
  proposed: "Proposed",
  current: "Current",
  complete: "Complete",
  deprecated: "Deprecated",
  decommissioned: "Decommissioned",
};
