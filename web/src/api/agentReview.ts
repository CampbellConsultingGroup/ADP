/** Generic Agent Review toolkit hooks (ADP-SPEC-039).
 *
 * Adapter-agnostic: parameterized by `basePath` (e.g.
 * `/api/v1/business/capabilities/{id}/agent-review`) so a future adapter for
 * a different screen can reuse these hooks/components unmodified -- only the
 * concrete suggestion shape (extending AgentSuggestionBase) is adapter-specific.
 */

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { apiGet, apiMutation } from "./client";

export interface GroundingCitation {
  entity_type: string;
  entity_id: string;
}

export type AgentSuggestionStatus = "pending" | "accepted" | "rejected";
export type AgentReviewOperationStatus = "pending" | "running" | "completed" | "failed";

export interface AgentSuggestionBase {
  suggestion_id: string;
  rationale: string;
  citations: GroundingCitation[];
  advisory: boolean;
  status: AgentSuggestionStatus;
}

export interface AgentReviewStatusResponse<S extends AgentSuggestionBase = AgentSuggestionBase> {
  operation_id: string;
  status: AgentReviewOperationStatus;
  suggestions: S[];
  error_description?: string | null;
}

export interface SubmitAgentReviewResponse {
  operation_id: string;
}

export function useSubmitAgentReview(basePath: string) {
  const qc = useQueryClient();
  return useMutation<SubmitAgentReviewResponse, Error, void>({
    mutationFn: () => apiMutation<SubmitAgentReviewResponse>("POST", basePath),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ["agent-review-status", basePath] });
    },
  });
}

export function useAgentReviewStatus<S extends AgentSuggestionBase = AgentSuggestionBase>(
  basePath: string,
  operationId: string | null,
) {
  return useQuery<AgentReviewStatusResponse<S>>({
    queryKey: ["agent-review-status", basePath, operationId],
    queryFn: () => apiGet<AgentReviewStatusResponse<S>>(`${basePath}/${operationId}`),
    enabled: !!operationId,
    // Mirrors useIntakeStatus's polling idiom: keep polling while pending/running,
    // stop at completed/failed.
    refetchInterval: (query) => {
      const s = query.state.data?.status;
      return !s || s === "completed" || s === "failed" ? false : 2000;
    },
  });
}

export function useAcceptSuggestion(basePath: string, operationId: string) {
  const qc = useQueryClient();
  return useMutation<
    unknown,
    Error,
    { suggestionId: string; advisoryAcknowledged?: boolean }
  >({
    mutationFn: ({ suggestionId, advisoryAcknowledged }) =>
      apiMutation("POST", `${basePath}/${operationId}/suggestions/${suggestionId}/accept`, {
        // Deterministic, non-empty per-suggestion confirmation token (ART-VIII) --
        // mirrors AcceptDialog's `CONFIRM-${option.option_id}` pattern; not a
        // user-typed field.
        confirmation_id: `CONFIRM-${suggestionId}`,
        advisory_acknowledged: advisoryAcknowledged ?? false,
      }),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ["agent-review-status", basePath, operationId] });
    },
  });
}

export function useRejectSuggestion(basePath: string, operationId: string) {
  const qc = useQueryClient();
  return useMutation<unknown, Error, { suggestionId: string }>({
    mutationFn: ({ suggestionId }) =>
      apiMutation("POST", `${basePath}/${operationId}/suggestions/${suggestionId}/reject`),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ["agent-review-status", basePath, operationId] });
    },
  });
}
