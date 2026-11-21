/** TypeScript interfaces and TanStack Query hooks for the Compliance Framework & Control Registry
 * API (COMPLY-01) and the Control Mappings (Traceability Links) API (COMPLY-02). */

import { useMutation, useQueries, useQuery, useQueryClient } from "@tanstack/react-query";
import { apiGet, apiMutation } from "./client";
import type { components } from "./generated/schema";
import { QK } from "./queryKeys";

// ── Types ─────────────────────────────────────────────────────────────────────

/** 932-regulatory-framework-tags (ADP-bkg): status was added to the backend model by 926
 * (COMPLY-01a) but never added to this frontend type, since 926 was data-model-and-API-only.
 * Added here because the Application Risk & Compliance picker needs it to filter selectable
 * frameworks (spec.md FR-001) — the other still-missing 926 fields are not needed by this
 * feature and are left for a future pass (research.md D8). */
export type FrameworkStatus = "in_force" | "amended" | "repealed" | "not_yet_applicable";

export interface RegulatoryFramework {
  id: string;
  name: string;
  jurisdiction: string;
  authority: string;
  version: string;
  effective_date: string | null;
  source_url: string | null;
  status: FrameworkStatus;
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
    queryKey: [QK.complianceFrameworks],
    queryFn: () => apiGet("/api/v1/compliance/frameworks"),
  });
}

export function useFramework(id: string | null) {
  return useQuery<RegulatoryFrameworkDetail>({
    queryKey: [QK.complianceFramework, id],
    queryFn: () => apiGet(`/api/v1/compliance/frameworks/${id}`),
    enabled: !!id,
  });
}

/** A control flattened out of its framework's tree, for pickers (ADP-w7z). */
export interface ControlOption {
  id: string;
  framework_id: string;
  framework_name: string;
  code: string;
  title: string;
  depth: number;
}

/** Depth-first flattening of a framework's control tree, keeping tree order. */
export function flattenControls(fw: RegulatoryFrameworkDetail): ControlOption[] {
  const out: ControlOption[] = [];
  const walk = (nodes: ControlNode[], depth: number) => {
    for (const n of nodes) {
      out.push({ id: n.id, framework_id: fw.id, framework_name: fw.name, code: n.code, title: n.title, depth });
      walk(n.children, depth + 1);
    }
  };
  walk(fw.controls, 0);
  return out;
}

/** Every control across every framework, by id. Shares the per-framework query cache with
 * `useFramework`; there is no flat "list all controls" endpoint. */
export function useAllControls(): { byId: Map<string, ControlOption>; isLoading: boolean } {
  const frameworks = useFrameworks();
  const details = useQueries({
    queries: (frameworks.data?.items ?? []).map((f) => ({
      queryKey: [QK.complianceFramework, f.id],
      queryFn: () => apiGet<RegulatoryFrameworkDetail>(`/api/v1/compliance/frameworks/${f.id}`),
    })),
  });
  const byId = new Map<string, ControlOption>();
  for (const d of details) if (d.data) for (const c of flattenControls(d.data)) byId.set(c.id, c);
  return { byId, isLoading: frameworks.isLoading || details.some((d) => d.isLoading) };
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
      void qc.invalidateQueries({ queryKey: [QK.complianceFrameworks] });
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
      void qc.invalidateQueries({ queryKey: [QK.complianceFrameworks] });
      void qc.invalidateQueries({ queryKey: [QK.complianceFramework, frameworkId] });
    },
  });
}

export function useDeleteFramework() {
  const qc = useQueryClient();
  return useMutation<void, Error & { status?: number }, string>({
    mutationFn: (frameworkId) =>
      apiMutation<void>("DELETE", `/api/v1/compliance/frameworks/${frameworkId}`),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: [QK.complianceFrameworks] });
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
      void qc.invalidateQueries({ queryKey: [QK.complianceFramework, frameworkId] });
    },
  });
}

export function useUpdateControl(controlId: string, frameworkId: string) {
  const qc = useQueryClient();
  return useMutation<Control, Error, ControlUpdate>({
    mutationFn: (body) =>
      apiMutation<Control, ControlUpdate>("PATCH", `/api/v1/compliance/controls/${controlId}`, body),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: [QK.complianceFramework, frameworkId] });
    },
  });
}

export function useDeleteControl(frameworkId: string) {
  const qc = useQueryClient();
  return useMutation<void, Error & { status?: number }, string>({
    mutationFn: (controlId) => apiMutation<void>("DELETE", `/api/v1/compliance/controls/${controlId}`),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: [QK.complianceFramework, frameworkId] });
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

export type MappingTargetType = "capability" | "application" | "design" | "pattern" | "organization" | "agent";

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
  agent: "agents",
};

function mappingUrl(controlId: string, targetType: MappingTargetType, targetId?: string | null): string {
  const segment = MAPPING_PATH_SEGMENT[targetType];
  const base = `/api/v1/compliance/controls/${controlId}/mappings/${segment}`;
  return targetType === "organization" ? base : `${base}/${targetId}`;
}

// ── Control Mapping hooks (COMPLY-02, US1/US2/Polish) ────────────────────────

export function useControlMappings(controlId: string | null) {
  return useQuery<ControlMappingListResponse>({
    queryKey: [QK.controlMappings, controlId],
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
      void qc.invalidateQueries({ queryKey: [QK.controlMappings, controlId] });
      void qc.invalidateQueries({ queryKey: [QK.agentCompliance] });
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
      void qc.invalidateQueries({ queryKey: [QK.controlMappings, controlId] });
      void qc.invalidateQueries({ queryKey: [QK.agentCompliance] });
    },
  });
}

// ── Agent compliance (944-agent-traceability, US2) ────────────────────────────
// An agent's own mappings and derived status. Never folded into its solution's status (FR-009a).

export interface AgentComplianceMappings {
  items: ControlMapping[];
  total: number;
  status: ComplianceStatus;
}

export function useAgentComplianceMappings(agentId: string | null) {
  return useQuery<AgentComplianceMappings>({
    queryKey: [QK.agentCompliance, "mappings", agentId],
    queryFn: () => apiGet(`/api/v1/compliance/agents/${agentId}/mappings`),
    enabled: !!agentId,
  });
}

/** One request for many agents' derived statuses (a solution's Agents tab). */
export function useAgentComplianceStatuses(agentIds: string[]) {
  const ids = agentIds.join(",");
  return useQuery<{ items: { agent_id: string; status: ComplianceStatus }[] }>({
    queryKey: [QK.agentCompliance, "statuses", ids],
    queryFn: () => apiGet(`/api/v1/compliance/agents/statuses?ids=${encodeURIComponent(ids)}`),
    enabled: agentIds.length > 0,
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

/**
 * The objectives linked to every control of a framework, in one request (ADP-blp.35). The control
 * tree shows them on each row; asking per control fired one request for every control.
 */
export function useFrameworkControlObjectives(frameworkId: string | null) {
  return useQuery<Map<string, { id: string; statement: string }[]>>({
    queryKey: [QK.controlObjectives, "framework", frameworkId],
    queryFn: async () => {
      const data = await apiGet<{
        items: { control_id: string; objectives: { id: string; statement: string }[] }[];
      }>(`/api/v1/compliance/frameworks/${frameworkId}/control-objectives`);
      return new Map(data.items.map((item) => [item.control_id, item.objectives]));
    },
    enabled: !!frameworkId,
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
    queryKey: [QK.controlMappingInitiatives, controlId, targetType, targetId],
    queryFn: () => apiGet(path),
    enabled: !!controlId && (targetType === "organization" || !!targetId),
  });
}

// ── Reverse-lookup hooks (COMPLY-02, US3) ─────────────────────────────────────

export function useCapabilityComplianceMappings(capabilityId: string | null) {
  return useQuery<ControlMappingListResponse>({
    queryKey: [QK.capabilityComplianceMappings, capabilityId],
    queryFn: () => apiGet(`/api/v1/business/capabilities/${capabilityId}/compliance-mappings`),
    enabled: !!capabilityId,
  });
}

export function useApplicationComplianceMappings(applicationId: string | null) {
  return useQuery<ControlMappingListResponse>({
    queryKey: [QK.applicationComplianceMappings, applicationId],
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
    queryKey: [QK.complianceFrameworkRollup, frameworkId],
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
    queryKey: [QK.complianceSummary],
    queryFn: () => apiGet("/api/v1/compliance/summary"),
  });
}


// ── 948 GEO-03: framework jurisdiction and derived applicability ─────────────

export type FrameworkJurisdiction = components["schemas"]["FrameworkJurisdiction"];
export type JurisdictionTrigger = components["schemas"]["JurisdictionTrigger"];
export type Applicability = components["schemas"]["Applicability"];
export type ApplicabilityEvidence = components["schemas"]["ApplicabilityEvidence"];
export type ApplicabilityStatus = Applicability["status"];
export type FrameworkApplicability = components["schemas"]["FrameworkApplicabilityResponse"];
export type SubjectApplicability = components["schemas"]["SubjectApplicabilityResponse"];

export const APPLICABILITY_LABEL: Record<ApplicabilityStatus, string> = {
  applies: "Applies",
  does_not_apply: "Does not apply",
  unknown: "Unknown",
};

function asOfQuery(asOf: string | null): string {
  return asOf ? `?as_of=${encodeURIComponent(asOf)}` : "";
}

export function useFrameworkJurisdiction(frameworkId: string | null) {
  return useQuery<FrameworkJurisdiction>({
    queryKey: [QK.complianceJurisdiction, frameworkId],
    queryFn: () => apiGet(`/api/v1/compliance/frameworks/${frameworkId}/jurisdiction`),
    enabled: !!frameworkId,
  });
}

export function useSetFrameworkJurisdiction(frameworkId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (body: { geography_ids: string[]; triggers: { subject_type: JurisdictionTrigger["subject_type"]; relation: string }[] }) =>
      apiMutation<FrameworkJurisdiction>("PUT", `/api/v1/compliance/frameworks/${frameworkId}/jurisdiction`, body),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: [QK.complianceJurisdiction, frameworkId] });
      void qc.invalidateQueries({ queryKey: [QK.complianceApplicability] });
    },
  });
}

export function useFrameworkApplicability(frameworkId: string | null, asOf: string | null) {
  return useQuery<FrameworkApplicability>({
    queryKey: [QK.complianceApplicability, "framework", frameworkId, asOf ?? "today"],
    queryFn: () => apiGet(`/api/v1/compliance/frameworks/${frameworkId}/applicability${asOfQuery(asOf)}`),
    enabled: !!frameworkId,
    placeholderData: (previous) => previous,
  });
}

export function useSubjectApplicability(subject: "application" | "legal_entity", id: string | null, asOf: string | null) {
  const path = subject === "application" ? "applications" : "legal-entities";
  return useQuery<SubjectApplicability>({
    queryKey: [QK.complianceApplicability, subject, id, asOf ?? "today"],
    queryFn: () => apiGet(`/api/v1/compliance/${path}/${id}/applicability${asOfQuery(asOf)}`),
    enabled: !!id,
    placeholderData: (previous) => previous,
  });
}
