/** TypeScript interfaces and TanStack Query hooks for the Compliance Framework & Control Registry
 * API (COMPLY-01) and the Control Mappings (Traceability Links) API (COMPLY-02). */

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { apiGet, apiMutation } from "./client";

// ── Types ─────────────────────────────────────────────────────────────────────

export interface RegulatoryFramework {
  id: string;
  name: string;
  jurisdiction: string;
  authority: string;
  version: string;
  effective_date: string | null;
  source_url: string | null;
  created_at: string;
  updated_at: string;
}

export interface Control {
  id: string;
  framework_id: string;
  parent_id: string | null;
  code: string;
  title: string;
  description: string | null;
  position: number;
  created_at: string;
  updated_at: string;
}

export interface ControlNode extends Control {
  children: ControlNode[];
}

export interface RegulatoryFrameworkDetail extends RegulatoryFramework {
  controls: ControlNode[];
}

export interface RegulatoryFrameworkCreate {
  name: string;
  jurisdiction: string;
  authority: string;
  version: string;
  effective_date?: string | null;
  source_url?: string | null;
}

export interface RegulatoryFrameworkUpdate {
  name?: string;
  jurisdiction?: string;
  authority?: string;
  version?: string;
  effective_date?: string | null;
  source_url?: string | null;
}

export interface RegulatoryFrameworkListResponse {
  items: RegulatoryFramework[];
  total: number;
}

export interface ControlCreate {
  parent_id?: string | null;
  code: string;
  title: string;
  description: string;
  position?: number;
}

export interface ControlUpdate {
  parent_id?: string | null;
  code?: string;
  title?: string;
  description?: string;
  position?: number;
}

// ── Framework hooks (US1) ────────────────────────────────────────────────────

export function useFrameworks() {
  return useQuery<RegulatoryFrameworkListResponse>({
    queryKey: ["compliance-frameworks"],
    queryFn: () => apiGet("/api/v1/compliance/frameworks"),
  });
}

export function useFramework(id: string | null) {
  return useQuery<RegulatoryFrameworkDetail>({
    queryKey: ["compliance-framework", id],
    queryFn: () => apiGet(`/api/v1/compliance/frameworks/${id}`),
    enabled: !!id,
  });
}

export function useCreateFramework() {
  const qc = useQueryClient();
  return useMutation<RegulatoryFramework, Error, RegulatoryFrameworkCreate>({
    mutationFn: (body) =>
      apiMutation<RegulatoryFramework, RegulatoryFrameworkCreate>(
        "POST",
        "/api/v1/compliance/frameworks",
        body,
      ),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ["compliance-frameworks"] });
    },
  });
}

export function useUpdateFramework(frameworkId: string) {
  const qc = useQueryClient();
  return useMutation<RegulatoryFramework, Error, RegulatoryFrameworkUpdate>({
    mutationFn: (body) =>
      apiMutation<RegulatoryFramework, RegulatoryFrameworkUpdate>(
        "PATCH",
        `/api/v1/compliance/frameworks/${frameworkId}`,
        body,
      ),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ["compliance-frameworks"] });
      void qc.invalidateQueries({ queryKey: ["compliance-framework", frameworkId] });
    },
  });
}

export function useDeleteFramework() {
  const qc = useQueryClient();
  return useMutation<void, Error & { status?: number }, string>({
    mutationFn: (frameworkId) =>
      apiMutation<void>("DELETE", `/api/v1/compliance/frameworks/${frameworkId}`),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ["compliance-frameworks"] });
    },
  });
}

// ── Control hooks (US2/US3) ──────────────────────────────────────────────────

export function useCreateControl(frameworkId: string) {
  const qc = useQueryClient();
  return useMutation<Control, Error, ControlCreate>({
    mutationFn: (body) =>
      apiMutation<Control, ControlCreate>(
        "POST",
        `/api/v1/compliance/frameworks/${frameworkId}/controls`,
        body,
      ),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ["compliance-framework", frameworkId] });
    },
  });
}

export function useUpdateControl(controlId: string, frameworkId: string) {
  const qc = useQueryClient();
  return useMutation<Control, Error, ControlUpdate>({
    mutationFn: (body) =>
      apiMutation<Control, ControlUpdate>("PATCH", `/api/v1/compliance/controls/${controlId}`, body),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ["compliance-framework", frameworkId] });
    },
  });
}

export function useDeleteControl(frameworkId: string) {
  const qc = useQueryClient();
  return useMutation<void, Error & { status?: number }, string>({
    mutationFn: (controlId) => apiMutation<void>("DELETE", `/api/v1/compliance/controls/${controlId}`),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ["compliance-framework", frameworkId] });
    },
  });
}

// ── Control Mapping types (COMPLY-02) ────────────────────────────────────────

export type ComplianceStatus =
  | "compliant"
  | "partial"
  | "non_compliant"
  | "not_assessed"
  | "not_applicable";

export type MappingTargetType = "capability" | "application" | "design" | "pattern" | "organization";

export interface ControlMapping {
  control_id: string;
  target_type: MappingTargetType;
  target_id: string | null;
  compliance_status: ComplianceStatus;
  evidence_ref: string | null;
  assessed_at: string | null;
  assessed_by: string | null;
  created_at: string;
}

export interface ControlMappingWrite {
  compliance_status: ComplianceStatus;
  evidence_ref?: string | null;
  assessed_at?: string | null;
  assessed_by?: string | null;
}

export interface ControlMappingListResponse {
  items: ControlMapping[];
  total: number;
}

/** Path segment per target type -- "organization" mappings have no target-id segment. Exported
 * for reuse by web/src/api/strategy.ts's own InitiativeControlMapping link URLs
 * (925-strategy-compliance-linkage), which address a ControlMapping the same three-part way. */
export const MAPPING_PATH_SEGMENT: Record<MappingTargetType, string> = {
  capability: "capabilities",
  application: "applications",
  design: "designs",
  pattern: "patterns",
  organization: "organization",
};

function mappingUrl(controlId: string, targetType: MappingTargetType, targetId?: string | null): string {
  const segment = MAPPING_PATH_SEGMENT[targetType];
  const base = `/api/v1/compliance/controls/${controlId}/mappings/${segment}`;
  return targetType === "organization" ? base : `${base}/${targetId}`;
}

// ── Control Mapping hooks (COMPLY-02, US1/US2/Polish) ────────────────────────

export function useControlMappings(controlId: string | null) {
  return useQuery<ControlMappingListResponse>({
    queryKey: ["control-mappings", controlId],
    queryFn: () => apiGet(`/api/v1/compliance/controls/${controlId}/mappings`),
    enabled: !!controlId,
  });
}

export interface UpsertMappingArgs {
  targetType: MappingTargetType;
  targetId?: string | null;
  data: ControlMappingWrite;
}

export function useUpsertMapping(controlId: string) {
  const qc = useQueryClient();
  return useMutation<ControlMapping, Error & { status?: number }, UpsertMappingArgs>({
    mutationFn: ({ targetType, targetId, data }) =>
      apiMutation<ControlMapping, ControlMappingWrite>(
        "PUT",
        mappingUrl(controlId, targetType, targetId),
        data,
      ),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ["control-mappings", controlId] });
    },
  });
}

export interface DeleteMappingArgs {
  targetType: MappingTargetType;
  targetId?: string | null;
}

export function useDeleteMapping(controlId: string) {
  const qc = useQueryClient();
  return useMutation<void, Error & { status?: number }, DeleteMappingArgs>({
    mutationFn: ({ targetType, targetId }) =>
      apiMutation<void>("DELETE", mappingUrl(controlId, targetType, targetId)),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ["control-mappings", controlId] });
    },
  });
}

// ── Reverse-lookup hooks — Strategy domain (925-strategy-compliance-linkage, COMPLY-05) ─────────
// A minimal local ref shape, not the full StrategyInitiative from ../api/strategy (which itself
// embeds control_mappings pointing back into this domain) -- this read-only "Linked Initiatives"
// line only ever needs id/name/status.

export interface InitiativeRef {
  id: string;
  name: string;
  status: string;
}

export interface InitiativeRefListResponse {
  items: InitiativeRef[];
  total: number;
}

export function useControlObjectives(controlId: string | null) {
  return useQuery<{ items: { id: string; statement: string }[]; total: number }>({
    queryKey: ["control-objectives", controlId],
    queryFn: () => apiGet(`/api/v1/compliance/controls/${controlId}/objectives`),
    enabled: !!controlId,
  });
}

export function useControlMappingInitiatives(
  controlId: string | null,
  targetType: MappingTargetType,
  targetId?: string | null,
) {
  const segment = MAPPING_PATH_SEGMENT[targetType];
  const path =
    targetType === "organization"
      ? `/api/v1/compliance/controls/${controlId}/mappings/organization/initiatives`
      : `/api/v1/compliance/controls/${controlId}/mappings/${segment}/${targetId}/initiatives`;
  return useQuery<InitiativeRefListResponse>({
    queryKey: ["control-mapping-initiatives", controlId, targetType, targetId],
    queryFn: () => apiGet(path),
    enabled: !!controlId && (targetType === "organization" || !!targetId),
  });
}

// ── Reverse-lookup hooks (COMPLY-02, US3) ─────────────────────────────────────

export function useCapabilityComplianceMappings(capabilityId: string | null) {
  return useQuery<ControlMappingListResponse>({
    queryKey: ["capability-compliance-mappings", capabilityId],
    queryFn: () => apiGet(`/api/v1/business/capabilities/${capabilityId}/compliance-mappings`),
    enabled: !!capabilityId,
  });
}

export function useApplicationComplianceMappings(applicationId: string | null) {
  return useQuery<ControlMappingListResponse>({
    queryKey: ["application-compliance-mappings", applicationId],
    queryFn: () => apiGet(`/api/v1/applications/${applicationId}/compliance-mappings`),
    enabled: !!applicationId,
  });
}

// ── Compliance Rollup Reporting (COMPLY-04) ─────────────────────────────────

export interface EntityStatusCounts {
  compliant_count: number;
  partial_count: number;
  non_compliant_count: number;
  not_assessed_count: number;
  not_applicable_count: number;
}

export interface FrameworkCoverageRollup {
  framework_id: string;
  entity_counts: EntityStatusCounts;
  organization_status: ComplianceStatus | null;
}

export function useFrameworkRollup(frameworkId: string | null) {
  return useQuery<FrameworkCoverageRollup>({
    queryKey: ["compliance-framework-rollup", frameworkId],
    queryFn: () => apiGet(`/api/v1/compliance/frameworks/${frameworkId}/rollup`),
    enabled: !!frameworkId,
  });
}

export interface ComplianceSummaryResponse {
  framework_count: number;
  coverage_percent: number | null;
  at_risk_count: number;
}

export function useComplianceSummary() {
  return useQuery<ComplianceSummaryResponse>({
    queryKey: ["compliance-summary"],
    queryFn: () => apiGet("/api/v1/compliance/summary"),
  });
}
