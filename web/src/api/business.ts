/** TypeScript interfaces and TanStack Query hooks for the Business Architecture API (ADP-SPEC-033/034). */

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { apiGet, apiMutation } from "./client";

// ── Types ─────────────────────────────────────────────────────────────────────

// ADP-33v: strategic classification (1=Strategic, 2=Core, 3=Supporting).
// Applies to both business and technical capabilities; null = unclassified.
export type StrategicRelevance = 1 | 2 | 3;

export const STRATEGIC_RELEVANCE_LABEL: Record<StrategicRelevance, string> = {
  1: "Strategic",
  2: "Core",
  3: "Supporting",
};

// ADP-4ga: CMMI-style maturity ladder (business capabilities only).
// null = not yet assessed (distinct from 1 = "Ad hoc", an active assessment).
export type MaturityLevel = 1 | 2 | 3 | 4 | 5;

export const MATURITY_LEVEL_LABEL: Record<MaturityLevel, string> = {
  1: "Ad hoc",
  2: "Emerging",
  3: "Established",
  4: "Advanced",
  5: "World Class",
};

export interface BusinessCapability {
  id: string;
  name: string;
  description: string | null;
  level: 1 | 2 | 3;
  parent_id: string | null;
  position: number;
  created_at: string;
  updated_at: string;
  domain_id: string | null;
  domain_name: string | null;
  strategic_relevance: StrategicRelevance | null;
  maturity_level: MaturityLevel | null;
}

export interface BusinessCapabilityCreate {
  name: string;
  description?: string | null;
  level: 1 | 2 | 3;
  parent_id?: string | null;
  position?: number;
  strategic_relevance?: StrategicRelevance | null;
  maturity_level?: MaturityLevel | null;
}

export interface BusinessCapabilityUpdate {
  name?: string;
  description?: string | null;
  position?: number;
  strategic_relevance?: StrategicRelevance | null;
  maturity_level?: MaturityLevel | null;
}

export interface ValueStreamStage {
  id: string;
  value_stream_id: string;
  name: string;
  description: string | null;
  position: number;
}

export interface ValueStream {
  id: string;
  name: string;
  description: string | null;
  stakeholder: string | null;
  position: number;
  created_at: string;
  updated_at: string;
}

export interface ValueStreamDetail extends ValueStream {
  stages: ValueStreamStage[];
}

export interface ValueStreamCreate {
  name: string;
  description?: string | null;
  stakeholder?: string | null;
}

export interface ValueStreamUpdate {
  name?: string;
  description?: string | null;
  stakeholder?: string | null;
}

export interface ValueStreamStageCreate {
  name: string;
  description?: string | null;
  position?: number;
}

export interface ValueStreamStageUpdate {
  name?: string;
  description?: string | null;
  position?: number;
}

export interface StageReorderItem {
  id: string;
  name: string;
  description: string | null;
}

export interface ValueStreamStagesReorder {
  stages: StageReorderItem[];
}

// ── Capability hooks ──────────────────────────────────────────────────────────

export function useCapabilities() {
  return useQuery<{ items: BusinessCapability[]; total: number }>({
    queryKey: ["business-capabilities"],
    queryFn: () => apiGet("/api/v1/business/capabilities"),
  });
}

export function useCapability(id: string | null) {
  return useQuery<BusinessCapability>({
    queryKey: ["business-capability", id],
    queryFn: () => apiGet(`/api/v1/business/capabilities/${id}`),
    enabled: !!id,
  });
}

export function useCreateCapability() {
  const qc = useQueryClient();
  return useMutation<BusinessCapability, Error, BusinessCapabilityCreate>({
    mutationFn: (body) =>
      apiMutation<BusinessCapability, BusinessCapabilityCreate>("POST", "/api/v1/business/capabilities", body),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ["business-capabilities"] });
    },
  });
}

export function useUpdateCapability(capId: string) {
  const qc = useQueryClient();
  return useMutation<BusinessCapability, Error, BusinessCapabilityUpdate>({
    mutationFn: (body) =>
      apiMutation<BusinessCapability, BusinessCapabilityUpdate>(
        "PUT",
        `/api/v1/business/capabilities/${capId}`,
        body,
      ),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ["business-capabilities"] });
    },
  });
}

export function useDeleteCapability() {
  const qc = useQueryClient();
  return useMutation<void, Error & { status?: number }, string>({
    mutationFn: (capId) => apiMutation<void>("DELETE", `/api/v1/business/capabilities/${capId}`),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ["business-capabilities"] });
    },
  });
}

// ── Value Stream hooks ────────────────────────────────────────────────────────

export function useValueStreams() {
  return useQuery<{ items: ValueStream[]; total: number }>({
    queryKey: ["business-value-streams"],
    queryFn: () => apiGet("/api/v1/business/value-streams"),
  });
}

export function useValueStream(id: string | null) {
  return useQuery<ValueStreamDetail>({
    queryKey: ["business-value-stream", id],
    queryFn: () => apiGet(`/api/v1/business/value-streams/${id}`),
    enabled: !!id,
  });
}

export function useCreateValueStream() {
  const qc = useQueryClient();
  return useMutation<ValueStream, Error, ValueStreamCreate>({
    mutationFn: (body) =>
      apiMutation<ValueStream, ValueStreamCreate>("POST", "/api/v1/business/value-streams", body),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ["business-value-streams"] });
    },
  });
}

export function useUpdateValueStream(vsId: string) {
  const qc = useQueryClient();
  return useMutation<ValueStream, Error, ValueStreamUpdate>({
    mutationFn: (body) =>
      apiMutation<ValueStream, ValueStreamUpdate>("PUT", `/api/v1/business/value-streams/${vsId}`, body),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ["business-value-streams"] });
      void qc.invalidateQueries({ queryKey: ["business-value-stream", vsId] });
    },
  });
}

export function useDeleteValueStream() {
  const qc = useQueryClient();
  return useMutation<void, Error, string>({
    mutationFn: (vsId) => apiMutation<void>("DELETE", `/api/v1/business/value-streams/${vsId}`),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ["business-value-streams"] });
    },
  });
}

export function useAddStage(vsId: string) {
  const qc = useQueryClient();
  return useMutation<ValueStreamStage, Error, ValueStreamStageCreate>({
    mutationFn: (body) =>
      apiMutation<ValueStreamStage, ValueStreamStageCreate>(
        "POST",
        `/api/v1/business/value-streams/${vsId}/stages`,
        body,
      ),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ["business-value-stream", vsId] });
    },
  });
}

export function useUpdateStage(vsId: string, stageId: string) {
  const qc = useQueryClient();
  return useMutation<ValueStreamStage, Error, ValueStreamStageUpdate>({
    mutationFn: (body) =>
      apiMutation<ValueStreamStage, ValueStreamStageUpdate>(
        "PUT",
        `/api/v1/business/value-streams/${vsId}/stages/${stageId}`,
        body,
      ),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ["business-value-stream", vsId] });
    },
  });
}

export function useDeleteStage(vsId: string) {
  const qc = useQueryClient();
  return useMutation<void, Error, string>({
    mutationFn: (stageId) =>
      apiMutation<void>("DELETE", `/api/v1/business/value-streams/${vsId}/stages/${stageId}`),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ["business-value-stream", vsId] });
    },
  });
}

export function useReorderStages(vsId: string) {
  const qc = useQueryClient();
  return useMutation<ValueStreamDetail, Error, ValueStreamStagesReorder>({
    mutationFn: (body) =>
      apiMutation<ValueStreamDetail, ValueStreamStagesReorder>(
        "PUT",
        `/api/v1/business/value-streams/${vsId}/stages`,
        body,
      ),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ["business-value-stream", vsId] });
    },
  });
}

// ── Traceability types (ADP-SPEC-034) ────────────────────────────────────────

export interface DesignRef {
  design_id: string;
  title: string;
  lifecycle_status: string;
}

export interface CapabilityRef {
  capability_id: string;
  name: string;
  level: number;
}

export interface ValueStreamRef {
  value_stream_id: string;
  name: string;
  stakeholder: string | null;
}

export interface LinkedDesignsResponse {
  items: DesignRef[];
}

export interface BusinessContextResponse {
  design_id: string;
  capabilities: CapabilityRef[];
  value_streams: ValueStreamRef[];
}

export interface DesignPickerItem {
  id: string;
  title: string;
  lifecycle_status: string;
}

// ── Design-picker hook (for DesignLinkEditor) ─────────────────────────────────

export function useDesigns() {
  return useQuery<{ designs: DesignPickerItem[]; total: number }>({
    queryKey: ["designs-picker"],
    queryFn: () => apiGet("/api/v1/designs?page=1&page_size=100"),
    staleTime: 30_000,
  });
}

// ── Capability–Design link hooks ──────────────────────────────────────────────

export function useLinkedCapabilityDesigns(capabilityId: string | null) {
  return useQuery<LinkedDesignsResponse>({
    queryKey: ["cap-designs", capabilityId],
    queryFn: () => apiGet(`/api/v1/business/capabilities/${capabilityId}/designs`),
    enabled: !!capabilityId,
  });
}

export function useLinkDesignToCapability(capabilityId: string) {
  const qc = useQueryClient();
  return useMutation<LinkedDesignsResponse, Error & { status?: number }, string>({
    mutationFn: (designId) =>
      apiMutation<LinkedDesignsResponse, { design_id: string }>(
        "POST",
        `/api/v1/business/capabilities/${capabilityId}/designs`,
        { design_id: designId },
      ),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ["cap-designs", capabilityId] });
    },
  });
}

export function useUnlinkDesignFromCapability(capabilityId: string) {
  const qc = useQueryClient();
  return useMutation<void, Error, string>({
    mutationFn: (designId) =>
      apiMutation<void>("DELETE", `/api/v1/business/capabilities/${capabilityId}/designs/${designId}`),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ["cap-designs", capabilityId] });
    },
  });
}

// ── Value-Stream–Design link hooks ────────────────────────────────────────────

export function useLinkedValueStreamDesigns(valueStreamId: string | null) {
  return useQuery<LinkedDesignsResponse>({
    queryKey: ["vs-designs", valueStreamId],
    queryFn: () => apiGet(`/api/v1/business/value-streams/${valueStreamId}/designs`),
    enabled: !!valueStreamId,
  });
}

export function useLinkDesignToValueStream(valueStreamId: string) {
  const qc = useQueryClient();
  return useMutation<LinkedDesignsResponse, Error & { status?: number }, string>({
    mutationFn: (designId) =>
      apiMutation<LinkedDesignsResponse, { design_id: string }>(
        "POST",
        `/api/v1/business/value-streams/${valueStreamId}/designs`,
        { design_id: designId },
      ),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ["vs-designs", valueStreamId] });
    },
  });
}

export function useUnlinkDesignFromValueStream(valueStreamId: string) {
  const qc = useQueryClient();
  return useMutation<void, Error, string>({
    mutationFn: (designId) =>
      apiMutation<void>("DELETE", `/api/v1/business/value-streams/${valueStreamId}/designs/${designId}`),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ["vs-designs", valueStreamId] });
    },
  });
}

// ── Design Business Context hook ──────────────────────────────────────────────

export function useDesignBusinessContext(designId: string | null) {
  return useQuery<BusinessContextResponse>({
    queryKey: ["design-business-context", designId],
    queryFn: () => apiGet(`/api/v1/business/designs/${designId}/context`),
    enabled: !!designId,
  });
}

// ── Business Domain types (ADP-SPEC-035) ─────────────────────────────────────

export interface BusinessDomain {
  id: string;
  name: string;
  scope_statement: string | null;
  classification: "strategic" | "differentiating" | "commodity";
  org_unit: string | null;
  risk_flags: string[];
  created_at: string;
  updated_at: string;
}

export interface DomainSummary extends Omit<BusinessDomain, "scope_statement"> {
  capability_count: number;
}

export interface DomainDetail extends BusinessDomain {
  capabilities: CapabilityRef[];
}

export interface DomainListResponse {
  items: DomainSummary[];
  total: number;
}

export interface StageCapabilityRef {
  capability_id: string;
  name: string;
  level: number;
  domain_id: string | null;
  domain_name: string | null;
}

export interface StageCapabilitiesResponse {
  items: StageCapabilityRef[];
}

// ── Domain CRUD hooks ─────────────────────────────────────────────────────────

export function useDomains() {
  return useQuery<DomainListResponse>({
    queryKey: ["domains"],
    queryFn: () => apiGet("/api/v1/business/domains"),
  });
}

export function useDomain(domainId: string | null) {
  return useQuery<DomainDetail>({
    queryKey: ["domain", domainId],
    queryFn: () => apiGet(`/api/v1/business/domains/${domainId}`),
    enabled: !!domainId,
  });
}

export function useCreateDomain() {
  const qc = useQueryClient();
  return useMutation<BusinessDomain, Error, Partial<BusinessDomain>>({
    mutationFn: (body) =>
      apiMutation<BusinessDomain, Partial<BusinessDomain>>("POST", "/api/v1/business/domains", body),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ["domains"] });
    },
  });
}

export function useUpdateDomain(domainId: string) {
  const qc = useQueryClient();
  return useMutation<BusinessDomain, Error, Partial<BusinessDomain>>({
    mutationFn: (body) =>
      apiMutation<BusinessDomain, Partial<BusinessDomain>>(
        "PUT",
        `/api/v1/business/domains/${domainId}`,
        body,
      ),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ["domains"] });
      void qc.invalidateQueries({ queryKey: ["domain", domainId] });
    },
  });
}

export function useDeleteDomain() {
  const qc = useQueryClient();
  return useMutation<void, Error, string>({
    mutationFn: (id) => apiMutation<void>("DELETE", `/api/v1/business/domains/${id}`),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ["domains"] });
    },
  });
}

// ── Capability-Domain assignment hook (ADP-SPEC-035 US2) ─────────────────────

export function useAssignCapabilityDomain(capabilityId: string) {
  const qc = useQueryClient();
  return useMutation<BusinessCapability, Error, string | null>({
    mutationFn: (domainId) =>
      apiMutation<BusinessCapability, { domain_id: string | null }>(
        "PATCH",
        `/api/v1/business/capabilities/${capabilityId}/domain`,
        { domain_id: domainId },
      ),
    onSuccess: () => {
      // "capabilities" was a stale key -- useCapabilities() actually queries
      // under "business-capabilities", so this never invalidated anything
      // (bug report, 2026-08-15). Also missing: ["domain", id] (the detail
      // query DomainDetail.tsx reads via useDomain) was never invalidated at
      // all, only the ["domains"] list -- so a currently-open domain's
      // Assigned/Unassigned lists never refreshed after Assign/Remove. Both
      // together made assignment look like it silently did nothing; the PATCH
      // itself always worked. queryKey: ["domain"] prefix-matches every
      // cached ["domain", id] query (default partial matching), covering
      // both the newly- and previously-assigned domain without needing to
      // track which ids are affected.
      void qc.invalidateQueries({ queryKey: ["business-capabilities"] });
      void qc.invalidateQueries({ queryKey: ["domains"] });
      void qc.invalidateQueries({ queryKey: ["domain"] });
    },
  });
}

// ── Stage-capability hooks (ADP-SPEC-035 US3) ─────────────────────────────────

export function useStageCapabilities(vsId: string | null, stageId: string | null) {
  return useQuery<StageCapabilitiesResponse>({
    queryKey: ["stage-caps", vsId, stageId],
    queryFn: () =>
      apiGet(`/api/v1/business/value-streams/${vsId}/stages/${stageId}/capabilities`),
    enabled: !!(vsId && stageId),
  });
}

export function useLinkCapabilityToStage(vsId: string, stageId: string) {
  const qc = useQueryClient();
  return useMutation<StageCapabilitiesResponse, Error & { status?: number }, string>({
    mutationFn: (capabilityId) =>
      apiMutation<StageCapabilitiesResponse, { capability_id: string }>(
        "POST",
        `/api/v1/business/value-streams/${vsId}/stages/${stageId}/capabilities`,
        { capability_id: capabilityId },
      ),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ["stage-caps", vsId, stageId] });
    },
  });
}

export function useUnlinkCapabilityFromStage(vsId: string, stageId: string) {
  const qc = useQueryClient();
  return useMutation<void, Error, string>({
    mutationFn: (capabilityId) =>
      apiMutation<void>(
        "DELETE",
        `/api/v1/business/value-streams/${vsId}/stages/${stageId}/capabilities/${capabilityId}`,
      ),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ["stage-caps", vsId, stageId] });
    },
  });
}

// ── Orphan report (918-strategy-rollups) ────────────────────────────────────────

export interface OrphanReportResponse {
  orphan_capabilities: BusinessCapability[];
  orphan_value_streams: ValueStream[];
}

export function useOrphanReport() {
  return useQuery<OrphanReportResponse>({
    queryKey: ["business-orphans"],
    queryFn: () => apiGet("/api/v1/business/orphans"),
  });
}
