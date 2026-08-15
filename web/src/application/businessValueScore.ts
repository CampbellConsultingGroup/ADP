import type { BusinessValueDimension } from "../api/application";

/** Client-side mirror of adp.application.store.compute_business_value_score()
 * (docs/application-business-value-assessment-spec.md §5) -- used only for
 * the live preview text in the popup before Save; the server remains the
 * authoritative computation on save (PUT .../business-value-assessment),
 * so any drift here is a display-only staleness risk, not a data-integrity
 * one. Keep the weights/cap table in sync with the Python constants
 * (BUSINESS_VALUE_WEIGHTS/BUSINESS_VALUE_EVIDENCE_CAP in
 * src/adp/application/models.py) if either ever changes. */

export const BUSINESS_VALUE_WEIGHTS: Record<BusinessValueDimension, number> = {
  strategic_alignment: 0.25,
  revenue_cost_impact: 0.25,
  customer_stakeholder_impact: 0.15,
  risk_compliance_contribution: 0.15,
  competitive_differentiation: 0.10,
  evidence_measurability: 0.10,
};

const EVIDENCE_CAP: Record<number, number | null> = { 1: 2, 2: 3, 3: 4, 4: null, 5: null };

export interface BusinessValueResult {
  businessValue: number;
  weightedAverage: number;
  evidenceScore: number;
  cap: number | null;
  capped: boolean;
}

export function computeBusinessValueScore(
  scores: Record<BusinessValueDimension, number>,
): BusinessValueResult {
  const dimensions = Object.keys(BUSINESS_VALUE_WEIGHTS) as BusinessValueDimension[];
  const rawScore = dimensions.reduce(
    (sum, dim) => sum + scores[dim] * BUSINESS_VALUE_WEIGHTS[dim],
    0,
  );
  const evidenceScore = scores.evidence_measurability;
  const cap = EVIDENCE_CAP[evidenceScore] ?? null;
  const cappedValue = cap !== null ? Math.min(rawScore, cap) : rawScore;
  // Round-half-up, not JS's own Math.round (which *is* round-half-up for
  // positive numbers, so this matches -- kept explicit to mirror the
  // Python side's own explicit implementation, spec §5.4).
  let businessValue = Math.floor(cappedValue + 0.5);
  businessValue = Math.max(1, Math.min(5, businessValue));
  return {
    businessValue,
    weightedAverage: Math.round(rawScore * 100) / 100,
    evidenceScore,
    cap,
    capped: cap !== null && rawScore > cap,
  };
}
