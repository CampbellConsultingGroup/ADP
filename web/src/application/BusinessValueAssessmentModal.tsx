import React from "react";
import {
  useBusinessValueAssessment,
  useSaveBusinessValueAssessment,
  type BusinessValueDimension,
  type BusinessValueAssessmentSubmit,
} from "../api/application";
import AssessmentModal, { type AssessmentRubricRow } from "./AssessmentModal";
import { computeBusinessValueScore } from "./businessValueScore";

interface Props {
  appId: string;
  onClose: () => void;
}

/** Transcribed verbatim from docs/business_value.md -- if that file
 * changes, this constant (and the popup's copy) must be updated together
 * (docs/application-business-value-assessment-spec.md §3/§8). */
const SCORE_LABELS = ["1 — Minimal", "2 — Marginal", "3 — Moderate", "4 — Strong", "5 — Exceptional"];

const RUBRIC: AssessmentRubricRow[] = [
  {
    dimension: "strategic_alignment" satisfies BusinessValueDimension,
    label: "Strategic Alignment",
    options: [
      "No connection to any stated strategic objective or theme.",
      "Loosely related to strategy; connection is inferred, not documented.",
      "Supports a secondary or lower-priority objective.",
      "Directly supports a stated strategic objective.",
      "Directly and measurably drives a top-priority strategic objective.",
    ],
  },
  {
    dimension: "revenue_cost_impact" satisfies BusinessValueDimension,
    label: "Revenue / Cost Impact",
    options: [
      "No identifiable financial impact, or net negative with no offsetting benefit.",
      "Financial impact is assumed but unquantified.",
      "Modest, quantified impact on revenue or cost.",
      "Clear, quantified impact with a credible business case.",
      "Material, quantified impact validated against actuals, not just projections.",
    ],
  },
  {
    dimension: "customer_stakeholder_impact" satisfies BusinessValueDimension,
    label: "Customer / Stakeholder Impact",
    options: [
      "No identifiable customer or stakeholder benefit.",
      "Benefit is anecdotal or affects a very narrow group.",
      "Improves experience or outcomes for a defined segment.",
      "Measurably improves experience/outcomes for a broad or key segment.",
      "Materially changes a key customer/stakeholder metric (satisfaction, retention, adoption) at scale.",
    ],
  },
  {
    dimension: "competitive_differentiation" satisfies BusinessValueDimension,
    label: "Competitive Differentiation",
    options: [
      "Table stakes at best; absence would go unnoticed by the market.",
      "Keeps pace with competitors; no distinct advantage.",
      "Provides a modest edge in specific situations.",
      "Provides a clear, defensible advantage in the market or industry.",
      "Establishes a durable differentiator competitors can't easily replicate.",
    ],
  },
  {
    dimension: "risk_compliance_contribution" satisfies BusinessValueDimension,
    label: "Risk / Compliance Contribution",
    options: [
      "Increases risk exposure or compliance burden with no offsetting value.",
      "Neutral; neither reduces nor materially adds risk.",
      "Modestly reduces a known risk or compliance gap.",
      "Meaningfully reduces risk or closes a compliance gap.",
      "Eliminates a significant risk or is required for regulatory/compliance standing.",
    ],
  },
  {
    dimension: "evidence_measurability" satisfies BusinessValueDimension,
    label: "Evidence & Measurability",
    options: [
      "Value is asserted with no supporting data or metric.",
      "A metric exists but isn't tracked or reported.",
      "Tracked informally; not reviewed on a regular cadence.",
      "Tracked with a defined metric, reviewed on a regular cadence.",
      "Tracked, reviewed, and tied to a target with demonstrated trend evidence.",
    ],
  },
];

export default function BusinessValueAssessmentModal({ appId, onClose }: Props): React.ReactElement {
  const { data, isLoading } = useBusinessValueAssessment(appId);
  const save = useSaveBusinessValueAssessment(appId);

  return (
    <AssessmentModal
      title="Business Value Assessment"
      description="Pick the description that best matches this application for each dimension. The overall business value is a weighted average of the six selections, capped by how well-evidenced the value claim is."
      scoreLabels={SCORE_LABELS}
      rubric={RUBRIC}
      entries={data?.entries}
      isLoading={isLoading}
      resultText={(selections) => {
        const result = computeBusinessValueScore(
          selections as unknown as Record<BusinessValueDimension, number>,
        );
        // Cap math is always shown, whether or not it's currently binding
        // (spec §4/§9 Q3, resolved 2026-08-15).
        const capText = result.cap === null
          ? "no cap applied — Evidence & Measurability scored 4+"
          : result.capped
            ? `capped by Evidence & Measurability (score ${result.evidenceScore}) at ${result.cap}`
            : `Evidence & Measurability caps at ${result.cap}, but the weighted average is already at or below that`;
        return `Resulting business value: ${result.businessValue} — weighted average ${result.weightedAverage}, ${capText}`;
      }}
      onSave={(selections) =>
        save.mutate(selections as unknown as BusinessValueAssessmentSubmit, { onSuccess: onClose })
      }
      saving={save.isPending}
      saveError={save.isError ? (save.error instanceof Error ? save.error.message : "Failed to save") : null}
      onClose={onClose}
    />
  );
}
