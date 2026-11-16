// 943-mapping-rationale: labels and chip colours for a realization's rationale, shared by the
// realization editor and the findings views. The TIME-consistency hint comes from the server.

import type { Rationale } from "../api/appCapabilities";

export const RATIONALES: Rationale[] = ["target", "tactical", "transitional", "redundant"];

export const RATIONALE_LABEL: Record<Rationale, string> = {
  target: "Target",
  tactical: "Tactical",
  transitional: "Transitional",
  redundant: "Redundant",
};

export const RATIONALE_HELP: Record<Rationale, string> = {
  target: "Strategic: keep and invest",
  tactical: "Tolerated for a regional or functional reason",
  transitional: "Being retired or replaced",
  redundant: "No justification: a rationalization candidate",
};

/** Chip colours: [text, background]. Unclassified uses the muted pair. */
export function rationaleColors(r: Rationale | null | undefined): [string, string] {
  switch (r) {
    case "target":
      return ["var(--good)", "var(--good-wash)"];
    case "tactical":
      return ["var(--accent-2)", "var(--accent-wash)"];
    case "transitional":
      return ["var(--warn)", "var(--warn-wash)"];
    case "redundant":
      return ["var(--crit)", "var(--crit-wash)"];
    default:
      return ["var(--ink-3)", "var(--surface-2)"];
  }
}

export function rationaleLabel(r: Rationale | null | undefined): string {
  return r ? RATIONALE_LABEL[r] : "Unclassified";
}
