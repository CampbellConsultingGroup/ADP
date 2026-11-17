import type { BadgeTone } from "../ui";
import { DESIGN_LIFECYCLE_TONES } from "../ui/tones";

/** Design lifecycle status → semantic badge tone + label. */
export const LIFECYCLE_TONE: Record<string, BadgeTone> = DESIGN_LIFECYCLE_TONES; // ADP-blp.49

export const LIFECYCLE_LABEL: Record<string, string> = {
  draft: "Draft",
  proposed: "Proposed",
  current: "Current",
  complete: "Complete",
  deprecated: "Deprecated",
  decommissioned: "Decommissioned",
};
