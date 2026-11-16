// 940-org-units-geography (ADP-55k.1): hooks for /api/v1/business/{org-units,geographies}.
// Uses the shared client so a 409/422 carries the server's rule message (errorDetail).

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { apiGet, apiMutation } from "./client";

const BASE = "/api/v1/business";
export const ORG_KEY = ["organization"] as const;

export type OrgUnitKind = "enterprise" | "division" | "function";
export type GeographyKind = "global" | "region" | "country";

export const ORG_UNIT_KIND_LABEL: Record<OrgUnitKind, string> = {
  enterprise: "Enterprise",
  division: "Division / BU",
  function: "Function / department",
};

export interface Ref {
  id: string;
  name: string;
  level: number;
}

export interface OrgUnit {
  id: string;
  name: string;
  description: string | null;
  parent_id: string | null;
  level: number;
  kind: OrgUnitKind;
  primary_geography_id: string | null;
  geography_ids: string[];
  path: Ref[];
  application_count: number;
  created_at: string;
  updated_at: string;
}

export interface OrgUnitDetail extends OrgUnit {
  applications: Ref[];
  geographies: Ref[];
}

export interface Geography {
  id: string;
  name: string;
  code: string | null;
  m49: string | null;
  parent_id: string | null;
  level: number;
  kind: GeographyKind;
  path: Ref[];
  org_unit_count: number;
}

export interface UnmatchedValue {
  value: string;
  application_count: number;
  sample_applications: Ref[];
}

export interface ResolveBody {
  value: string;
  org_unit_id?: string;
  create?: { name: string; description?: string | null; parent_id?: string | null };
}

export interface ResolveResult {
  org_unit: OrgUnit;
  updated_count: number;
}

export function useOrgUnits() {
  return useQuery<{ items: OrgUnit[]; total: number }>({
    queryKey: [...ORG_KEY, "org-units"],
    queryFn: () => apiGet(`${BASE}/org-units`),
  });
}

export function useOrgUnit(id: string | null) {
  return useQuery<OrgUnitDetail>({
    queryKey: [...ORG_KEY, "org-unit", id],
    queryFn: () => apiGet(`${BASE}/org-units/${id}`),
    enabled: !!id,
  });
}

export function useGeographies() {
  return useQuery<{ items: Geography[]; total: number }>({
    queryKey: [...ORG_KEY, "geographies"],
    queryFn: () => apiGet(`${BASE}/geographies`),
    staleTime: 5 * 60 * 1000, // seeded reference data, changes rarely
  });
}

export function useUnmatched() {
  return useQuery<{ items: UnmatchedValue[]; total: number }>({
    queryKey: [...ORG_KEY, "unmatched"],
    queryFn: () => apiGet(`${BASE}/org-units/unmatched`),
  });
}

/** Org-unit and application data both change on these writes. */
function useOrgMutation<V, R>(fn: (v: V) => Promise<R>) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: fn,
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ORG_KEY });
      void qc.invalidateQueries({ queryKey: ["applications"] });
    },
  });
}

export function useCreateOrgUnit() {
  return useOrgMutation((body: { name: string; description?: string | null; parent_id?: string | null }) =>
    apiMutation<OrgUnit>("POST", `${BASE}/org-units`, body),
  );
}

export function useUpdateOrgUnit() {
  return useOrgMutation(
    ({ id, body }: { id: string; body: { name?: string; description?: string | null; primary_geography_id?: string | null } }) =>
      apiMutation<OrgUnit>("PATCH", `${BASE}/org-units/${id}`, body),
  );
}

export function useDeleteOrgUnit() {
  return useOrgMutation((id: string) => apiMutation<void>("DELETE", `${BASE}/org-units/${id}`));
}

export function useLinkGeography() {
  return useOrgMutation(({ id, geographyId }: { id: string; geographyId: string }) =>
    apiMutation<OrgUnit>("POST", `${BASE}/org-units/${id}/geographies`, { geography_id: geographyId }),
  );
}

export function useUnlinkGeography() {
  return useOrgMutation(({ id, geographyId }: { id: string; geographyId: string }) =>
    apiMutation<void>("DELETE", `${BASE}/org-units/${id}/geographies/${geographyId}`),
  );
}

export function useCreateGeography() {
  return useOrgMutation((body: { name: string; code?: string | null; parent_id: string }) =>
    apiMutation<Geography>("POST", `${BASE}/geographies`, body),
  );
}

export function useUpdateGeography() {
  return useOrgMutation(({ id, body }: { id: string; body: { name?: string; code?: string | null } }) =>
    apiMutation<Geography>("PATCH", `${BASE}/geographies/${id}`, body),
  );
}

export function useDeleteGeography() {
  return useOrgMutation((id: string) => apiMutation<void>("DELETE", `${BASE}/geographies/${id}`));
}

export function useResolveUnmatched() {
  return useOrgMutation((body: ResolveBody) =>
    apiMutation<ResolveResult>("POST", `${BASE}/org-units/unmatched/resolve`, body),
  );
}

// ── 941-capability-org-mappings (ADP-55k.2) ──────────────────────────────────
// Owner (L1/L2, one per capability), performer (L3, optional geography), contributor (L3).
// Effective owner, findings and footprints are derived by the server on every read.

export type CapabilityOrgRole = "owner" | "performer" | "contributor";

export interface CapabilityOrgMapping {
  id: string;
  capability_id: string;
  org_unit: Ref;
  role: CapabilityOrgRole;
  geography: Ref | null;
  outside_operating_geographies: boolean;
}

export interface CapabilityOrgView {
  capability_id: string;
  level: number;
  owner: Ref | null;
  effective_owner: Ref | null;
  owner_inherited_from: Ref | null;
  performers: CapabilityOrgMapping[];
  contributors: CapabilityOrgMapping[];
}

export interface FindingCapability {
  id: string;
  name: string;
  level: number;
  path: Ref[];
}

export interface SharedServicePerformer {
  org_unit: Ref;
  org_unit_path: Ref[];
  geographies: Ref[];
  folded_into: Ref | null;
}

export interface SharedServiceCandidate {
  capability: FindingCapability;
  branches: number;
  performers: SharedServicePerformer[];
}

export interface CapabilityOrgFindings {
  no_owner: FindingCapability[];
  shared_service: SharedServiceCandidate[];
  unmapped: FindingCapability[];
  owned_no_performer: FindingCapability[];
  counts: {
    no_owner: number;
    shared_service: number;
    unmapped: number;
    owned_no_performer: number;
    l1_l2_total: number;
    l3_total: number;
  };
}

export interface FootprintPerformer {
  org_unit: Ref;
  geographies: Ref[];
}

export interface OrgUnitFootprint {
  org_unit: Ref;
  includes_descendants: boolean;
  performs: {
    capability: Ref;
    l3_count: number;
    l2s: { capability: Ref; l3_count: number; l3s: { capability: Ref; performed_by: FootprintPerformer[] }[] }[];
  }[];
  l3_total: number;
  owns: { capability: FindingCapability; org_unit: Ref }[];
  contributes: { capability: FindingCapability; org_unit: Ref }[];
}

const MAPPINGS = `${BASE}/capability-org-mappings`;

/** One request for the whole Capabilities tab; rows read their own entry via capabilityOrgView. */
export function useCapabilityOrgMappings() {
  return useQuery<{ items: CapabilityOrgView[] }>({
    queryKey: [...ORG_KEY, "capability-org-mappings"],
    queryFn: () => apiGet(MAPPINGS),
  });
}

export function capabilityOrgView(
  data: { items: CapabilityOrgView[] } | undefined,
  capabilityId: string,
): CapabilityOrgView | undefined {
  return data?.items.find((v) => v.capability_id === capabilityId);
}

export function useCapabilityOrgFindings(enabled = true) {
  return useQuery<CapabilityOrgFindings>({
    queryKey: [...ORG_KEY, "capability-org-findings"],
    queryFn: () => apiGet(`${MAPPINGS}/findings`),
    enabled,
  });
}

export function useOrgUnitFootprint(id: string | null) {
  return useQuery<OrgUnitFootprint>({
    queryKey: [...ORG_KEY, "footprint", id],
    queryFn: () => apiGet(`${BASE}/org-units/${id}/footprint`),
    enabled: id !== null,
  });
}

export function useSetCapabilityOwner() {
  return useOrgMutation(({ capabilityId, orgUnitId }: { capabilityId: string; orgUnitId: string | null }) =>
    apiMutation<CapabilityOrgView>("PUT", `${MAPPINGS}/${capabilityId}/owner`, { org_unit_id: orgUnitId }),
  );
}

export function useAddCapabilityMapping() {
  return useOrgMutation(
    (body: { capability_id: string; org_unit_id: string; role: "performer" | "contributor"; geography_id?: string | null }) =>
      apiMutation<CapabilityOrgMapping>("POST", MAPPINGS, body),
  );
}

export function useRemoveCapabilityMapping() {
  return useOrgMutation((mappingId: string) => apiMutation<void>("DELETE", `${MAPPINGS}/${mappingId}`));
}

// ── 942-regional-assessments (ADP-55k.3) ─────────────────────────────────────
// Capability x region/country maturity (1-5) and/or a note; the capability's own maturity_level
// is the baseline. Applicability and heat map cells are derived by the server on every read.

export interface GeoRef {
  id: string;
  name: string;
  level: number;
  code: string | null;
}

export interface RegionalAssessment {
  id: string;
  capability_id: string;
  geography: GeoRef;
  maturity_level: number | null;
  note: string | null;
  updated_at: string;
}

export interface RegionScope {
  capability_id: string;
  region_specific: boolean;
  geographies: GeoRef[];
  scope_needs_update: boolean;
}

export type HeatmapCellState = "assessed" | "not_assessed" | "not_applicable";

export interface HeatmapCell {
  geography_id: string;
  state: HeatmapCellState;
  maturity_level: number | null;
  note: string | null;
  delta: number | null;
}

export interface HeatmapRow {
  capability: { id: string; name: string; level: number; parent_id: string | null };
  baseline: number | null;
  region_specific: boolean;
  scope_needs_update: boolean;
  cells: HeatmapCell[];
}

export interface RegionalHeatmap {
  columns: GeoRef[];
  rows: HeatmapRow[];
  max_columns: number;
}

export const REGIONAL_NOTE_MAX = 1000;

export function useRegionalAssessments(capabilityId?: string) {
  return useQuery<{ items: RegionalAssessment[]; total: number }>({
    queryKey: [...ORG_KEY, "regional-assessments", capabilityId ?? "all"],
    queryFn: () =>
      apiGet(`${BASE}/regional-assessments${capabilityId ? `?capability_id=${encodeURIComponent(capabilityId)}` : ""}`),
  });
}

/** `geographyIds` null = the server's default columns (the regions). */
export function useRegionalHeatmap(geographyIds: string[] | null) {
  const query = geographyIds && geographyIds.length > 0 ? `?geography_ids=${geographyIds.map(encodeURIComponent).join(",")}` : "";
  return useQuery<RegionalHeatmap>({
    queryKey: [...ORG_KEY, "regional-heatmap", query],
    queryFn: () => apiGet(`${BASE}/regional-heatmap${query}`),
  });
}

export function useRegionScope(capabilityId: string) {
  return useQuery<RegionScope>({
    queryKey: [...ORG_KEY, "region-scope", capabilityId],
    queryFn: () => apiGet(`${BASE}/capability-region-scope/${capabilityId}`),
  });
}

export function useSetRegionalAssessment() {
  return useOrgMutation(
    ({ capabilityId, geographyId, maturity_level, note }: { capabilityId: string; geographyId: string; maturity_level: number | null; note: string | null }) =>
      apiMutation<RegionalAssessment>("PUT", `${BASE}/regional-assessments/${capabilityId}/${geographyId}`, { maturity_level, note }),
  );
}

export function useRemoveRegionalAssessment() {
  return useOrgMutation(({ capabilityId, geographyId }: { capabilityId: string; geographyId: string }) =>
    apiMutation<void>("DELETE", `${BASE}/regional-assessments/${capabilityId}/${geographyId}`),
  );
}

export function useSetRegionScope() {
  return useOrgMutation(
    ({ capabilityId, region_specific, geography_ids }: { capabilityId: string; region_specific: boolean; geography_ids: string[] }) =>
      apiMutation<RegionScope>("PUT", `${BASE}/capability-region-scope/${capabilityId}`, { region_specific, geography_ids }),
  );
}
