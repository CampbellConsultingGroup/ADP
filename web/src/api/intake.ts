/** TypeScript interfaces and TanStack Query hooks for the Intake API (ADP-SPEC-014). */

import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { apiGet, apiMutation } from "./client";

export type IntakeMode = "bulk_text" | "structured_form";
export type OperationStatus = "pending" | "running" | "completed" | "failed";
export type ProposalStatus = "pending" | "confirmed" | "edited_confirmed" | "rejected" | "expired";
export type RequirementKind = "functional" | "non_functional" | "constraint" | "driver";

export interface IntakeSubmitRequest {
  mode: IntakeMode;
  text?: string;  // known-requirements free-text; optional (empty => no extraction)
  kind?: RequirementKind;
  model?: string;  // optional model override; uses server-configured default if omitted
  // ADP-SPEC intake framing — persisted to the canonical model; required in the UI.
  business_problem?: string;
  desired_outcome?: string;
}

export interface IntakeSubmitResponse {
  operation_id: string;
  design_id: string;
  mode: string;
  status: OperationStatus;
}

export interface ProposalResponse {
  proposal_id: string;
  draft_statement: string;
  kind: RequirementKind;
  source_excerpt: string;
  confidence: number;
  verification_status: "verified" | "unverified";
  status: ProposalStatus;
  confirmed_statement?: string | null;
}

export interface IntakeStatusResponse {
  operation_id: string;
  design_id: string;
  status: OperationStatus;
  proposals: ProposalResponse[];
  result_summary?: string | null;
  error_description?: string | null;
}

export interface ConfirmProposalRequest {
  edited_statement?: string | null;
}

export interface ConfirmProposalResponse {
  requirement_id: string;
  title: string;
  description: string;
  kind: RequirementKind;
  proposal_id: string | null;
}

export interface DirectRequirementRequest {
  statement: string;
  kind: RequirementKind;
  description?: string | null;
}

export interface RequirementItem {
  id: string;
  title: string;
  description: string;
  kind: RequirementKind;
  satisfies: string[];
}

export interface RequirementListResponse {
  design_id: string;
  requirements: RequirementItem[];
  total: number;
}

// ── TanStack Query hooks ──────────────────────────────────────────────────────

// designId is a mutate-time argument (not fixed at hook-creation time) so
// intake can be submitted before a design exists yet -- IntakeTextForm
// creates the design lazily on first submit and passes its id straight
// through, in the same call, rather than waiting on a prop to update.
export function useSubmitIntake() {
  return useMutation<IntakeSubmitResponse, Error, IntakeSubmitRequest & { designId: string }>({
    mutationFn: ({ designId, ...body }) =>
      apiMutation<IntakeSubmitResponse, IntakeSubmitRequest>(
        "POST",
        `/api/v1/designs/${designId}/intake`,
        body,
      ),
  });
}

export function useIntakeStatus(designId: string, operationId: string | null) {
  return useQuery<IntakeStatusResponse>({
    queryKey: ["intake-status", designId, operationId],
    queryFn: () =>
      apiGet<IntakeStatusResponse>(`/api/v1/designs/${designId}/intake/${operationId}`),
    enabled: !!operationId,
    refetchInterval: (query) => {
      const s = query.state.data?.status;
      return !s || s === "completed" || s === "failed" ? false : 2000;
    },
  });
}

export function useConfirmProposal(designId: string, operationId: string) {
  const qc = useQueryClient();
  return useMutation<ConfirmProposalResponse, Error, { proposalId: string; editedStatement?: string | null }>({
    mutationFn: ({ proposalId, editedStatement }) =>
      apiMutation<ConfirmProposalResponse, ConfirmProposalRequest>(
        "POST",
        `/api/v1/designs/${designId}/intake/${operationId}/proposals/${proposalId}/confirm`,
        { edited_statement: editedStatement ?? null },
      ),
    onSuccess: () => {
      // Refresh confirmed requirements sidebar AND the proposals list (FR-001)
      void qc.invalidateQueries({ queryKey: ["requirements", designId] });
      void qc.invalidateQueries({ queryKey: ["intake-status", designId, operationId] });
    },
  });
}

export function useRejectProposal(designId: string, operationId: string) {
  const qc = useQueryClient();
  return useMutation<{ proposal_id: string; status: string }, Error, { proposalId: string }>({
    mutationFn: ({ proposalId }) =>
      apiMutation(
        "POST",
        `/api/v1/designs/${designId}/intake/${operationId}/proposals/${proposalId}/reject`,
        {},
      ),
    onSuccess: () => {
      // Refresh the proposals list so rejected proposal disappears (FR-001)
      void qc.invalidateQueries({ queryKey: ["intake-status", designId, operationId] });
    },
  });
}

// designId is a mutate-time argument (not fixed at hook-creation time) so a
// batch of requirements can be added right after a design is created in the
// same submit action, without waiting on a prop to catch up. Mirrors
// useSubmitIntake's same fix.
export function useAddRequirement() {
  const qc = useQueryClient();
  return useMutation<ConfirmProposalResponse, Error, DirectRequirementRequest & { designId: string }>({
    mutationFn: ({ designId, ...body }) =>
      apiMutation<ConfirmProposalResponse, DirectRequirementRequest>(
        "POST",
        `/api/v1/designs/${designId}/requirements`,
        body,
      ),
    onSuccess: (_data, variables) => {
      void qc.invalidateQueries({ queryKey: ["requirements", variables.designId] });
    },
  });
}

export function useRequirements(designId: string) {
  return useQuery<RequirementListResponse>({
    queryKey: ["requirements", designId],
    queryFn: () =>
      apiGet<RequirementListResponse>(`/api/v1/designs/${designId}/requirements`),
    staleTime: 0,
  });
}

// ── Capability gap analysis (ADP-zg3.4) ───────────────────────────────────────
// Advisory only: compares confirmed requirements against the business/
// technical capability registries. Does not create or modify any records.

export interface CapabilityMatchItem {
  requirement_id: string;
  requirement_title: string;
  capability_id: string;
  capability_name: string;
  relevance: number;
}

export interface CapabilityGapItem {
  requirement_id: string;
  requirement_title: string;
}

export interface CapabilityGapSection {
  present: CapabilityMatchItem[];
  missing: CapabilityGapItem[];
}

export interface CapabilityGapAnalysisResponse {
  design_id: string;
  business_capabilities: CapabilityGapSection;
  technical_capabilities: CapabilityGapSection;
}

export function useCapabilityGaps(designId: string) {
  return useQuery<CapabilityGapAnalysisResponse>({
    queryKey: ["capability-gaps", designId],
    queryFn: () =>
      apiGet<CapabilityGapAnalysisResponse>(`/api/v1/designs/${designId}/capability-gaps`),
    enabled: !!designId,
  });
}
