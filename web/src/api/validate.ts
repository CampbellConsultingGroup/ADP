/** TypeScript interfaces and TanStack Query hooks for the LLM-as-Judge Validation
 * API (ADP-SPEC-008 / ADP-3ei). Mirrors api/recommend.ts's shape. */

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { apiGet, apiMutation } from "./client";

export type ValidationStatus = "pending" | "running" | "completed" | "failed";
export type VerdictStatusValue = "pass" | "fail" | "indeterminate" | "overridden";

export interface ValidateRequest {
  model?: string;
  design_version?: number;
}

export interface FindingSummary {
  finding_id: string;
  critic_name: string;
  severity: "critical" | "major" | "minor" | "advisory";
  description: string;
  element_id?: string | null;
  score?: number | null;
}

export interface VerdictSummary {
  verdict_id: string;
  status: VerdictStatusValue;
  composite_score: number | null;
  design_version: number;
  citations_present: boolean;
  findings: FindingSummary[];
  overridden_by?: string | null;
  override_justification?: string | null;
}

export interface ValidateStatusResponse {
  operation_id: string;
  design_id: string;
  status: ValidationStatus;
  verdict: VerdictSummary | null;
  result_summary?: string | null;
  error_description?: string | null;
}

export interface OverrideVerdictRequest {
  justification: string;
}

// ── TanStack Query hooks ──────────────────────────────────────────────────────

export function useStartValidation(designId: string) {
  return useMutation<ValidateStatusResponse, Error, ValidateRequest>({
    mutationFn: (body) =>
      apiMutation<ValidateStatusResponse, ValidateRequest>(
        "POST",
        `/api/v1/designs/${designId}/validate`,
        body,
      ),
  });
}

export function useValidationStatus(designId: string, operationId: string | null) {
  return useQuery<ValidateStatusResponse>({
    queryKey: ["validate-status", designId, operationId],
    queryFn: () =>
      apiGet<ValidateStatusResponse>(
        `/api/v1/designs/${designId}/validate/${operationId}`,
      ),
    enabled: !!operationId,
    refetchInterval: (query) => {
      const s = query.state.data?.status;
      return !s || s === "completed" || s === "failed" ? false : 2000;
    },
  });
}

export function useOverrideVerdict(designId: string, operationId: string) {
  const qc = useQueryClient();
  return useMutation<ValidateStatusResponse, Error, OverrideVerdictRequest>({
    mutationFn: (body) =>
      apiMutation<ValidateStatusResponse, OverrideVerdictRequest>(
        "POST",
        `/api/v1/designs/${designId}/validate/${operationId}/override`,
        body,
      ),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ["validate-status", designId, operationId] });
    },
  });
}
