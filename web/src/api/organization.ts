// 940-org-units-geography (ADP-55k.1): hooks for /api/v1/business/{org-units,geographies}.
// Uses the shared client so a 409/422 carries the server's rule message (errorDetail).

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { apiGet, apiMutation } from "./client";
import type { components } from "./generated/schema";
import { QK } from "./queryKeys";

const BASE = "/api/v1/business";
export const ORG_KEY = [QK.organization] as const;

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
  /** 946 GEO-01: a place (country) or a node of one hierarchy. `parent_id`/`path` are the UN M49 ones. */
  entity?: "place" | "node";
  hierarchy_id?: string | null;
  hierarchy_name?: string | null;
  hierarchy_kind?: HierarchyKind | null;
  /** 949 GEO-04: country | subdivision | authority | residual (places). A subdivision's or
   * authority's country is `parent_place_id` (and `parent_id`). */
  place_type?: PlaceType | null;
  parent_place_id?: string | null;
}

export type PlaceType = "country" | "subdivision" | "authority" | "residual";

/** One label for a geography in every picker: "France (FR)", "Europe", "APAC · Sales". */
export function geographyLabel(
  g: { name: string; code?: string | null; hierarchy_kind?: string | null; hierarchy_name?: string | null } | null | undefined,
  fallback = "Everywhere",
): string {
  if (!g) return fallback;
  if (g.code) return `${g.name} (${g.code})`;
  if (g.hierarchy_name && g.hierarchy_kind && g.hierarchy_kind !== "reference") return `${g.name} · ${g.hierarchy_name}`;
  return g.name;
}

// ── 946 GEO-01: hierarchies, nodes, dated memberships ─────────────────────────

export type HierarchyKind =
  | "reference"
  | "regulatory"
  | "data_residency"
  | "infrastructure"
  | "sales"
  | "tax"
  | "operational"
  | "custom";
export type HierarchyShape = "strict_tree" | "dag";

export const HIERARCHY_KIND_LABEL: Record<HierarchyKind, string> = {
  reference: "Reference",
  regulatory: "Regulatory",
  data_residency: "Data residency",
  infrastructure: "Infrastructure",
  sales: "Sales",
  tax: "Tax",
  operational: "Operational",
  custom: "Custom",
};
/** Writes to these kinds also need write_compliance (they drive compliance applicability). */
export const COMPLIANCE_KINDS: ReadonlySet<HierarchyKind> = new Set(["regulatory", "data_residency", "tax"]);

export interface GeoHierarchy {
  id: string;
  name: string;
  kind: HierarchyKind;
  shape: HierarchyShape;
  system_of_record: string | null;
  description: string | null;
  read_only: boolean;
  node_count: number;
  membership_count: number;
  created_at: string;
  updated_at: string;
}

export interface GeoMembership {
  id: string;
  hierarchy_id: string;
  parent_id: string;
  child_id: string;
  child_entity: "place" | "node";
  valid_from: string | null;
  valid_to: string | null;
  active: boolean;
}

export interface GeoHierarchyDetail extends GeoHierarchy {
  as_of: string;
  nodes: { id: string; name: string }[];
  memberships: GeoMembership[];
}

export function useGeoHierarchies() {
  return useQuery<{ items: GeoHierarchy[]; total: number }>({
    queryKey: [...ORG_KEY, "geo-hierarchies"],
    queryFn: () => apiGet(`${BASE}/geo-hierarchies`),
  });
}

export function useGeoHierarchy(id: string | null, asOf: string | null) {
  const q = asOf ? `?as_of=${encodeURIComponent(asOf)}` : "";
  return useQuery<GeoHierarchyDetail>({
    queryKey: [...ORG_KEY, "geo-hierarchy", id, asOf ?? "today"],
    queryFn: () => apiGet(`${BASE}/geo-hierarchies/${id}${q}`),
    enabled: !!id,
    // Changing the "as of" date keeps the tree (and what is expanded) on screen while it loads.
    placeholderData: (previous) => (previous && previous.id === id ? previous : undefined),
  });
}

export function useCreateGeoHierarchy() {
  return useOrgMutation((body: { name: string; kind: Exclude<HierarchyKind, "reference">; shape: HierarchyShape; description?: string | null }) =>
    apiMutation<GeoHierarchy>("POST", `${BASE}/geo-hierarchies`, body),
  );
}

export function useUpdateGeoHierarchy() {
  return useOrgMutation(({ id, body }: { id: string; body: { name?: string; shape?: HierarchyShape; description?: string | null } }) =>
    apiMutation<GeoHierarchy>("PATCH", `${BASE}/geo-hierarchies/${id}`, body),
  );
}

export function useDeleteGeoHierarchy() {
  return useOrgMutation((id: string) => apiMutation<void>("DELETE", `${BASE}/geo-hierarchies/${id}`));
}

export function useCreateGeoNode() {
  return useOrgMutation(({ hierarchyId, name, parentId }: { hierarchyId: string; name: string; parentId?: string | null }) =>
    apiMutation<Geography>("POST", `${BASE}/geo-hierarchies/${hierarchyId}/nodes`, { name, parent_id: parentId ?? null }),
  );
}

export function useAddGeoMemberships() {
  return useOrgMutation(
    ({ hierarchyId, parentId, childIds, validFrom, validTo }: { hierarchyId: string; parentId: string; childIds: string[]; validFrom?: string | null; validTo?: string | null }) =>
      apiMutation<GeoMembership[]>("POST", `${BASE}/geo-hierarchies/${hierarchyId}/memberships`, {
        parent_id: parentId,
        child_ids: childIds,
        valid_from: validFrom || null,
        valid_to: validTo || null,
      }),
  );
}

export function useUpdateGeoMembership() {
  return useOrgMutation(({ id, validFrom, validTo }: { id: string; validFrom: string | null; validTo: string | null }) =>
    apiMutation<GeoMembership>("PATCH", `${BASE}/geo-memberships/${id}`, { valid_from: validFrom, valid_to: validTo }),
  );
}

export function useDeleteGeoMembership() {
  return useOrgMutation((id: string) => apiMutation<void>("DELETE", `${BASE}/geo-memberships/${id}`));
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
      void qc.invalidateQueries({ queryKey: [QK.applications] });
      // 948: links, legal entities and hierarchies all feed derived framework applicability.
      void qc.invalidateQueries({ queryKey: [QK.complianceApplicability] });
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

/** Rename a node (places are read-only). */
export function useUpdateGeography() {
  return useOrgMutation(({ id, body }: { id: string; body: { name?: string } }) =>
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

// ADP-blp.38: every capability row asks for its view, so the list is indexed once per response
// instead of searched once per row.
const viewIndex = new WeakMap<CapabilityOrgView[], Map<string, CapabilityOrgView>>();

export function capabilityOrgView(
  data: { items: CapabilityOrgView[] } | undefined,
  capabilityId: string,
): CapabilityOrgView | undefined {
  if (!data) return undefined;
  let index = viewIndex.get(data.items);
  if (!index) {
    index = new Map(data.items.map((v) => [v.capability_id, v]));
    viewIndex.set(data.items, index);
  }
  return index.get(capabilityId);
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


// ── 947 GEO-02: legal entities and typed, dated geography links ──────────────

export type LegalEntity = components["schemas"]["LegalEntity"];
export type LegalEntityDetail = components["schemas"]["LegalEntityDetail"];
export type GeoLink = components["schemas"]["GeoLink"];
export type GeoLinkList = components["schemas"]["GeoLinkListResponse"];
export type RelationRule = components["schemas"]["RelationRule"];
export type GeoLinkSubject = GeoLink["subject_type"];

/** Where a subject's links live: applications ride their own route prefix (WRITE_APPLICATION). */
export function geoLinkBase(subject: GeoLinkSubject, id: string): string {
  if (subject === "application") return `/api/v1/applications/${id}/geo-links`;
  return `${BASE}/${subject === "legal_entity" ? "legal-entities" : "org-units"}/${id}/geo-links`;
}

export function useGeoLinkRelations() {
  return useQuery<components["schemas"]["GeoLinkRelations"]>({
    queryKey: [...ORG_KEY, "geo-link-relations"],
    queryFn: () => apiGet(`${BASE}/geo-link-relations`),
    staleTime: Infinity,
  });
}

export function useGeoLinks(subject: GeoLinkSubject, id: string | null, asOf: string | null, all: boolean) {
  const params = new URLSearchParams();
  if (asOf) params.set("as_of", asOf);
  if (all) params.set("all", "true");
  const q = params.toString() ? `?${params}` : "";
  return useQuery<GeoLinkList>({
    queryKey: [...ORG_KEY, "geo-links", subject, id, asOf ?? "today", all],
    queryFn: () => apiGet(`${geoLinkBase(subject, id ?? "")}${q}`),
    enabled: !!id,
    placeholderData: (previous) => previous,
  });
}

export function useAddGeoLink() {
  return useOrgMutation(
    ({ subject, id, relation, geographyId, validFrom, validTo }: { subject: GeoLinkSubject; id: string; relation: string; geographyId: string; validFrom?: string | null; validTo?: string | null }) =>
      apiMutation<GeoLink>("POST", geoLinkBase(subject, id), {
        relation,
        geography_id: geographyId,
        valid_from: validFrom || null,
        valid_to: validTo || null,
      }),
  );
}

export function useUpdateGeoLink() {
  return useOrgMutation(
    ({ subject, id, linkId, validFrom, validTo }: { subject: GeoLinkSubject; id: string; linkId: string; validFrom: string | null; validTo: string | null }) =>
      apiMutation<GeoLink>("PATCH", `${geoLinkBase(subject, id)}/${linkId}`, { valid_from: validFrom, valid_to: validTo }),
  );
}

export function useDeleteGeoLink() {
  return useOrgMutation(({ subject, id, linkId }: { subject: GeoLinkSubject; id: string; linkId: string }) =>
    apiMutation<void>("DELETE", `${geoLinkBase(subject, id)}/${linkId}`),
  );
}

export function useLegalEntities() {
  return useQuery<components["schemas"]["LegalEntityListResponse"]>({
    queryKey: [...ORG_KEY, "legal-entities"],
    queryFn: () => apiGet(`${BASE}/legal-entities`),
  });
}

export function useLegalEntity(id: string | null) {
  return useQuery<LegalEntityDetail>({
    queryKey: [...ORG_KEY, "legal-entity", id],
    queryFn: () => apiGet(`${BASE}/legal-entities/${id}`),
    enabled: !!id,
  });
}

export type LegalEntityFields = {
  name?: string;
  registration_number?: string | null;
  lei?: string | null;
  description?: string | null;
  parent_id?: string | null;
};

export function useCreateLegalEntity() {
  return useOrgMutation((body: LegalEntityFields & { name: string }) =>
    apiMutation<LegalEntity>("POST", `${BASE}/legal-entities`, body),
  );
}

export function useUpdateLegalEntity() {
  return useOrgMutation(({ id, body }: { id: string; body: LegalEntityFields }) =>
    apiMutation<LegalEntity>("PATCH", `${BASE}/legal-entities/${id}`, body),
  );
}

export function useDeleteLegalEntity() {
  return useOrgMutation((id: string) => apiMutation<void>("DELETE", `${BASE}/legal-entities/${id}`));
}

export function useLinkLegalEntityOrgUnit() {
  return useOrgMutation(({ id, orgUnitId }: { id: string; orgUnitId: string }) =>
    apiMutation<LegalEntityDetail>("POST", `${BASE}/legal-entities/${id}/org-units`, { org_unit_id: orgUnitId }),
  );
}

export function useUnlinkLegalEntityOrgUnit() {
  return useOrgMutation(({ id, orgUnitId }: { id: string; orgUnitId: string }) =>
    apiMutation<void>("DELETE", `${BASE}/legal-entities/${id}/org-units/${orgUnitId}`),
  );
}

export function useApplicationLegalEntities(appId: string | null) {
  return useQuery<LegalEntity[]>({
    queryKey: [...ORG_KEY, "application-legal-entities", appId],
    queryFn: () => apiGet(`/api/v1/applications/${appId}/legal-entities`),
    enabled: !!appId,
  });
}

export function useLinkApplicationLegalEntity() {
  return useOrgMutation(({ appId, legalEntityId }: { appId: string; legalEntityId: string }) =>
    apiMutation<LegalEntity[]>("POST", `/api/v1/applications/${appId}/legal-entities`, { legal_entity_id: legalEntityId }),
  );
}

export function useUnlinkApplicationLegalEntity() {
  return useOrgMutation(({ appId, legalEntityId }: { appId: string; legalEntityId: string }) =>
    apiMutation<void>("DELETE", `/api/v1/applications/${appId}/legal-entities/${legalEntityId}`),
  );
}

// ── 949 GEO-04: subdivisions on demand, place matrix, application footprint ────

export type SubdivisionCatalog = components["schemas"]["SubdivisionCatalog"];
export type PlaceMatrix = components["schemas"]["PlaceMatrix"];
export type PlaceRef = components["schemas"]["PlaceRef"];
export type GeoFootprint = components["schemas"]["GeoFootprint"];
export type FootprintPlace = components["schemas"]["FootprintPlace"];
export type FootprintLink = components["schemas"]["FootprintLink"];
export type HierarchyPlacement = components["schemas"]["HierarchyPlacement"];

export const PLACE_TYPE_LABEL: Record<PlaceType, string> = {
  country: "Country",
  subdivision: "Subdivision",
  authority: "Authority",
  residual: "Residual",
};

export function useSubdivisionCatalog(countryId: string | null) {
  return useQuery<SubdivisionCatalog>({
    queryKey: [...ORG_KEY, "subdivision-catalog", countryId],
    queryFn: () => apiGet(`${BASE}/geographies/${encodeURIComponent(countryId ?? "")}/subdivisions`),
    enabled: !!countryId,
  });
}

export function useAddSubdivision() {
  return useOrgMutation((code: string) => apiMutation<Geography>("POST", `${BASE}/geographies/subdivisions`, { code }));
}

export function usePlaceMatrix(asOf: string | null, hierarchyIds: string[] | null) {
  const params = new URLSearchParams();
  if (asOf) params.set("as_of", asOf);
  if (hierarchyIds && hierarchyIds.length > 0) params.set("hierarchy_ids", hierarchyIds.join(","));
  const q = params.toString() ? `?${params}` : "";
  return useQuery<PlaceMatrix>({
    queryKey: [...ORG_KEY, "place-matrix", asOf ?? "today", hierarchyIds?.join(",") ?? "all"],
    queryFn: () => apiGet(`${BASE}/geographies/matrix${q}`),
    placeholderData: (previous) => previous,
  });
}

export function useGeoFootprint(appId: string | null, asOf: string | null) {
  const q = asOf ? `?as_of=${encodeURIComponent(asOf)}` : "";
  return useQuery<GeoFootprint>({
    queryKey: [...ORG_KEY, "geo-footprint", appId, asOf ?? "today"],
    queryFn: () => apiGet(`/api/v1/applications/${encodeURIComponent(appId ?? "")}/geo-footprint${q}`),
    enabled: !!appId,
    placeholderData: (previous) => previous,
  });
}
