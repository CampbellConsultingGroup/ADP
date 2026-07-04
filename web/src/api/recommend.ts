/** TypeScript interfaces and TanStack Query hooks for the Recommendation API (ADP-SPEC-018). */

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { apiGet, apiMutation } from "./client";

export type RecommendStatus = "pending" | "running" | "completed" | "failed";
export type OptionStatus = "pending" | "accepted" | "rejected";
export type TradeOffStance = "meets" | "partially_meets" | "does_not_meet";

export interface RecommendRequest {
  requirement_ids: string[];
  model?: string;
}

export interface TradeOffEntry {
  criterion: string;
  stance: TradeOffStance;
  rationale: string;
}

export interface ProposedElement {
  name: string;
  kind: string;
  description?: string | null;
  satisfies: string[];
}

export interface SolutionOption {
  option_id: string;
  rank: number;
  title: string;
  rationale: string;
  advisory: boolean;
  satisfies: string[];
  trade_offs: TradeOffEntry[];
  proposed_elements: ProposedElement[];
  grounded_on: string[];
  ranking_score: number;
  status: OptionStatus;
  knowledge_source: string;  // ADP-SPEC-019: "knowledge_base" | "requirements_only"
}

export interface RecommendStatusResponse {
  operation_id: string;
  design_id: string;
  status: RecommendStatus;
  options: SolutionOption[];
  result_summary?: string | null;
  error_description?: string | null;
}

export interface AcceptOptionRequest {
  confirmation_id: string;
  advisory_acknowledged: boolean;
  acceptance_reason?: string;  // ADP-SPEC-019: optional reason stored in KB
}

export interface RejectOptionRequest {
  rejection_reason: string;  // ADP-SPEC-019: required reason stored as KB anti-pattern
}

export interface ElementSummary {
  id: string;
  name: string;
  kind: string;
}

export interface AcceptOptionResponse {
  option_id: string;
  elements_created: ElementSummary[];
  audit_entry_id: string;
}

// ── TanStack Query hooks ──────────────────────────────────────────────────────

export function useStartRecommendation(designId: string) {
  return useMutation<RecommendStatusResponse, Error, RecommendRequest>({
    mutationFn: (body) =>
      apiMutation<RecommendStatusResponse, RecommendRequest>(
        "POST",
        `/api/v1/designs/${designId}/recommend`,
        body,
      ),
  });
}

export function useRecommendStatus(designId: string, operationId: string | null) {
  return useQuery<RecommendStatusResponse>({
    queryKey: ["recommend-status", designId, operationId],
    queryFn: () =>
      apiGet<RecommendStatusResponse>(
        `/api/v1/designs/${designId}/recommend/${operationId}`,
      ),
    enabled: !!operationId,
    refetchInterval: (query) => {
      const s = query.state.data?.status;
      return !s || s === "completed" || s === "failed" ? false : 2000;
    },
  });
}

export function useAcceptOption(designId: string, operationId: string) {
  const qc = useQueryClient();
  return useMutation<
    AcceptOptionResponse,
    Error,
    { optionId: string } & AcceptOptionRequest
  >({
    mutationFn: ({ optionId, confirmation_id, advisory_acknowledged, acceptance_reason }) =>
      apiMutation<AcceptOptionResponse, AcceptOptionRequest>(
        "POST",
        `/api/v1/designs/${designId}/recommend/${operationId}/options/${optionId}/accept`,
        { confirmation_id, advisory_acknowledged, acceptance_reason },
      ),
    onSuccess: () => {
      // Refresh design so canvas shows the new elements
      void qc.invalidateQueries({ queryKey: ["design", designId] });
    },
  });
}

export function useRejectOption(designId: string, operationId: string) {
  const qc = useQueryClient();
  return useMutation<
    { option_id: string; status: string },
    Error,
    { optionId: string } & RejectOptionRequest
  >({
    mutationFn: ({ optionId, rejection_reason }) =>
      apiMutation<{ option_id: string; status: string }, RejectOptionRequest>(
        "POST",
        `/api/v1/designs/${designId}/recommend/${operationId}/options/${optionId}/reject`,
        { rejection_reason },
      ),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ["recommend-status", designId, operationId] });
    },
  });
}
