/** Admin Scoring Rubric Management API client (ADP-68z).
 *
 * See specs/931-admin-ui-editing/contracts/scoring-rubrics-api.md. Mirrors
 * adminPrompts.ts almost verbatim, substituting a validated dict[string, number]
 * weight set for a free-text prompt string.
 */

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { apiGet, apiMutation } from "./client";

const BASE_PATH = "/api/v1/admin/scoring-rubrics";

export interface RubricView {
  rubric_id: string;
  display_name: string;
  dimension_labels: Record<string, string>;
  active_weights: Record<string, number>;
  is_override: boolean;
  version: number;
}

export interface RubricListResponse {
  items: RubricView[];
}

export interface RubricHistoryEntry {
  id: number;
  rubric_id: string;
  actor: string;
  changed_at: string;
  change_type: "edit" | "restore";
  prior_weights: Record<string, number>;
  new_weights: Record<string, number>;
}

export interface RubricHistoryResponse {
  items: RubricHistoryEntry[];
}

export interface RubricChangeResult {
  rubric_id: string;
  active_weights: Record<string, number>;
  version: number;
}

export function useRubrics() {
  return useQuery<RubricListResponse>({
    queryKey: ["admin-scoring-rubrics"],
    queryFn: () => apiGet<RubricListResponse>(BASE_PATH),
  });
}

export function useRubricHistory(rubricId: string | null) {
  return useQuery<RubricHistoryResponse>({
    queryKey: ["admin-scoring-rubric-history", rubricId],
    queryFn: () => apiGet<RubricHistoryResponse>(`${BASE_PATH}/${rubricId}/history`),
    enabled: !!rubricId,
  });
}

export function useConfirmRubricEdit(rubricId: string) {
  const qc = useQueryClient();
  return useMutation<
    RubricChangeResult,
    Error,
    { weights: Record<string, number>; expectedVersion: number; confirmationId: string }
  >({
    mutationFn: ({ weights, expectedVersion, confirmationId }) =>
      apiMutation<RubricChangeResult>("POST", `${BASE_PATH}/${rubricId}/confirm`, {
        weights,
        expected_version: expectedVersion,
        confirmation_id: confirmationId,
      }),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ["admin-scoring-rubrics"] });
      void qc.invalidateQueries({ queryKey: ["admin-scoring-rubric-history", rubricId] });
    },
  });
}

export function useRestoreRubricVersion(rubricId: string) {
  const qc = useQueryClient();
  return useMutation<
    RubricChangeResult,
    Error,
    { historyId: number; expectedVersion: number; confirmationId: string }
  >({
    mutationFn: ({ historyId, expectedVersion, confirmationId }) =>
      apiMutation<RubricChangeResult>(
        "POST",
        `${BASE_PATH}/${rubricId}/restore/${historyId}`,
        { expected_version: expectedVersion, confirmation_id: confirmationId },
      ),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ["admin-scoring-rubrics"] });
      void qc.invalidateQueries({ queryKey: ["admin-scoring-rubric-history", rubricId] });
    },
  });
}
