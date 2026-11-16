// 939-governance-architecture-health: pure derivations for the Architecture Health tab. The tiles and
// the sections both use these, so a tile's count always matches its list (SC-002). Nothing here is
// stored: every input is already derived on the server (936 conformance, 938 findings/exposure).

import type { CapabilityFindings, CapabilityRollup, CapabilityRollupResponse, LifecycleBand } from "../api/capAnalysis";
import type { Adoption, ConformanceStatus } from "../api/patterns";

/** Statuses listed as needing attention, in display order (FR-003). */
const ATTENTION_ORDER: ConformanceStatus[] = ["non_conformant", "indeterminate", "conformant_with_warnings"];

export interface AdoptionAttention {
  attention: Adoption[];
  nonConformant: number;
  indeterminate: number;
  conformant: number;
  notApplicable: number;
}

export function adoptionsNeedingAttention(adoptions: Adoption[] | undefined): AdoptionAttention {
  const list = adoptions ?? [];
  const count = (s: ConformanceStatus) => list.filter((a) => a.status === s).length;
  const attention = list
    .filter((a) => a.status !== null && ATTENTION_ORDER.includes(a.status))
    .sort(
      (a, b) =>
        ATTENTION_ORDER.indexOf(a.status!) - ATTENTION_ORDER.indexOf(b.status!) || a.name.localeCompare(b.name),
    );
  return {
    attention,
    nonConformant: count("non_conformant"),
    indeterminate: count("indeterminate"),
    conformant: count("conformant"),
    notApplicable: count("not_applicable"),
  };
}

/** Exposure bands flagged on the governance view; "contained" is a deliberate holding state. */
const EXPOSED: LifecycleBand[] = ["past_end_of_life", "retiring"];

/** Business L3s exposed to retiring or past-end-of-life technology, worst first, then by name. */
export function exposedCapabilities(rollup: CapabilityRollupResponse | undefined): CapabilityRollup[] {
  return (rollup?.items ?? [])
    .filter((i) => i.level === 3 && i.exposure.worst !== null && EXPOSED.includes(i.exposure.worst))
    .sort(
      (a, b) =>
        EXPOSED.indexOf(a.exposure.worst!) - EXPOSED.indexOf(b.exposure.worst!) || a.name.localeCompare(b.name),
    );
}

export function gapCount(findings: CapabilityFindings | undefined): number {
  if (!findings) return 0;
  const g = findings.gaps;
  return (
    g.business_without_app_capability.length +
    g.app_capability_without_business.length +
    g.app_capability_without_application.length
  );
}
