/** Display constants for the agent registry (933-agent-registry, spec.md FR-005). */

import type { AgentLifecycle, DataClassification, HumanApproval, SolutionRole } from "../api/agentic";

export interface AutonomyLevelDef {
  level: number;
  name: string;
  meaning: string;
}

/** ADP's own autonomy scale (docs/agentic-solutions-plan.md section 4). */
export const AUTONOMY_LEVELS: AutonomyLevelDef[] = [
  { level: 0, name: "Assistive", meaning: "Suggests only; a human acts" },
  { level: 1, name: "Supervised", meaning: "Acts only after explicit human approval each time" },
  { level: 2, name: "Conditional", meaning: "Acts alone on reversible / low-risk actions; escalates the rest" },
  { level: 3, name: "Bounded", meaning: "Acts alone within its stated scope; reviewed after the fact" },
  { level: 4, name: "Autonomous", meaning: "Acts alone with monitoring only" },
];

export function autonomyLabel(level: number): string {
  const def = AUTONOMY_LEVELS.find((d) => d.level === level);
  return def ? `L${level} ${def.name}` : `L${level}`;
}

export const HUMAN_APPROVAL_LABELS: Record<HumanApproval, string> = {
  none: "None",
  on_write: "On write actions",
  on_irreversible: "On irreversible actions",
  always: "Always",
};

export const LIFECYCLE_LABELS: Record<AgentLifecycle, string> = {
  planned: "Planned",
  active: "Active",
  sunset: "Sunset",
  retired: "Retired",
};

export const DATA_CLASSIFICATION_LABELS: Record<DataClassification, string> = {
  public: "Public",
  internal: "Internal",
  confidential: "Confidential",
  restricted: "Restricted",
};

export const ROLE_LABELS: Record<SolutionRole, string> = {
  orchestrator: "Orchestrator",
  worker: "Worker",
  reviewer: "Reviewer",
  router: "Router",
};

/** "not estimated" (null, visible) vs "restricted" (hidden by permission) -- spec Edge Cases. */
export function costLabel(cost: string | number | null, visible: boolean, unit = ""): string {
  if (!visible) return "Restricted";
  if (cost === null || cost === "") return "Not estimated";
  return `${unit}${cost}`;
}
