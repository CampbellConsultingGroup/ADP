import React from "react";
import {
  useHealthAssessment,
  useSaveHealthAssessment,
  type HealthDimension,
  type HealthAssessmentSubmit,
} from "../api/application";
import AssessmentModal, { type AssessmentRubricRow } from "./AssessmentModal";

interface Props {
  appId: string;
  onClose: () => void;
}

/** Transcribed verbatim from docs/health-table.md -- if that file changes,
 * this constant (and the popup's copy) must be updated together
 * (docs/application-health-assessment-spec.md §3/§7). */
const SCORE_LABELS = ["1 — Critical", "2 — At Risk", "3 — Fair / Watch", "4 — Healthy", "5 — Thriving"];

const RUBRIC: AssessmentRubricRow[] = [
  {
    dimension: "stability_incidents" satisfies HealthDimension,
    label: "Stability & Incidents",
    options: [
      "Severe or continuous outages; core function is unreliable or unusable.",
      "Frequent or high-impact incidents; SLA regularly missed; user-facing disruption.",
      "Recurring minor incidents or occasional workarounds; SLA occasionally missed.",
      "Rare, low-impact incidents; quickly resolved; SLA met.",
      "No incidents; consistently meets or exceeds uptime/SLA targets.",
    ],
  },
  {
    dimension: "technical_currency_debt" satisfies HealthDimension,
    label: "Technical Currency & Debt",
    options: [
      "Running on end-of-life or unsupported infrastructure with no upgrade path.",
      "Key platform(s) or dependencies unsupported or nearing end-of-life; no funded upgrade plan.",
      "Some components aging without a firm upgrade plan; moderate accumulated debt.",
      "Mostly current; minor debt with a funded or scheduled upgrade path.",
      "All platforms and dependencies on current, vendor-supported versions; minimal debt.",
    ],
  },
  {
    dimension: "security_posture" satisfies HealthDimension,
    label: "Security Posture",
    options: [
      "Known exploitable or critical vulnerabilities; failing compliance requirements.",
      "Known unpatched high-severity vulnerabilities or overdue audit findings.",
      "Some medium-severity findings open past target remediation date.",
      "Only low-severity findings open, with remediation on track.",
      "No known vulnerabilities; passes current audits; patching is current.",
    ],
  },
  {
    dimension: "support_team_capacity" satisfies HealthDimension,
    label: "Support & Team Capacity",
    options: [
      "No one able to support it; original team or vendor is gone.",
      "No dedicated owner or team; support is ad hoc or purely reactive.",
      "Owner identified but thinly resourced; single point of failure on key knowledge.",
      "Clear owner; adequately resourced; minor bus-factor risk.",
      "Clear owner; well-resourced team; more than one person can support it.",
    ],
  },
  {
    dimension: "documentation_knowledge" satisfies HealthDimension,
    label: "Documentation & Knowledge",
    options: [
      "No usable documentation; knowledge is effectively lost.",
      "Documentation is sparse; knowledge lives mostly in a few people's heads.",
      "Documentation exists but is outdated or incomplete in key areas.",
      "Good documentation with minor gaps.",
      "Comprehensive, current documentation; onboarding is straightforward.",
    ],
  },
  {
    dimension: "business_value_criticality" satisfies HealthDimension,
    label: "Business Value & Criticality Alignment",
    options: [
      "Value no longer justifies its cost, risk, or existence; candidate for retirement.",
      "Cost or risk is starting to outweigh the value delivered.",
      "Value is unclear, declining, or only partially understood.",
      "Solid, understood value; cost and risk are justified.",
      "Clearly delivers strong, well-understood business value relative to its cost and risk.",
    ],
  },
];

export default function HealthAssessmentModal({ appId, onClose }: Props): React.ReactElement {
  const { data, isLoading } = useHealthAssessment(appId);
  const save = useSaveHealthAssessment(appId);

  return (
    <AssessmentModal
      title="Health Assessment"
      description="Pick the description that best matches this application for each dimension. The overall health score is the lowest of the six selections."
      scoreLabels={SCORE_LABELS}
      rubric={RUBRIC}
      entries={data?.entries}
      isLoading={isLoading}
      resultText={(selections) => {
        const min = Math.min(...Object.values(selections));
        return `Resulting health score: ${min} (lowest of the six selections)`;
      }}
      onSave={(selections) =>
        save.mutate(selections as unknown as HealthAssessmentSubmit, { onSuccess: onClose })
      }
      saving={save.isPending}
      saveError={save.isError ? (save.error instanceof Error ? save.error.message : "Failed to save") : null}
      onClose={onClose}
    />
  );
}
