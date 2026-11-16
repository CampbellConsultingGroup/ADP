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
