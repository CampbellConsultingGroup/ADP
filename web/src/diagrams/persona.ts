// ADP-914.6: persona -> default diagram-type mapping (steering only, never a
// restriction -- WRITE_DIAGRAM already grants all 3 architect roles equal
// creation rights for all 5 types; see data-model.md and spec.md Assumptions).
//
// Mirrors the ROLE_LABELS/ROLE_COLORS constant pattern already established in
// web/src/auth/AuthProvider.tsx. Roles absent from this table (reviewer,
// platform_admin, unrecognized/undefined) intentionally have no entry --
// getRecommendedDiagramType returns undefined for those, and callers fall
// back to today's pre-feature default ("flowchart").

import type { DiagramType } from "./api";

export const PERSONA_DEFAULT_TYPE: Record<string, DiagramType> = {
  enterprise_architect: "architecture",
  solution_architect: "flowchart",
  technical_architect: "sequence",
};

export function getRecommendedDiagramType(role: string | undefined): DiagramType | undefined {
  if (!role) return undefined;
  return PERSONA_DEFAULT_TYPE[role];
}
