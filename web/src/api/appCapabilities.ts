// 937-application-capabilities: hooks for /api/v1/application-capabilities.
// Uses the shared client so a 409/422 carries the server's rule message (ApiError.body.detail).

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { apiGet, apiMutation, errorDetail } from "./client";
import { QK } from "./queryKeys";

const BASE = "/api/v1/application-capabilities";

export type AppCapLevel = 1 | 2 | 3;
export type AppCapWarning = "missing_technical_capability";
export const MISSING_TECHNICAL_CAPABILITY: AppCapWarning = "missing_technical_capability";

export interface CapRef {
  id: string;
  name: string;
  level: number;
}

export interface LinkedCapRef extends CapRef {
  path: CapRef[];
}

/** 943-mapping-rationale: why an application realizes an application capability. null = unclassified. */
export type Rationale = "target" | "tactical" | "transitional" | "redundant";

export interface GeoRef {
  id: string;
  name: string;
  code: string | null;
}

/** An application realizing an application capability. On a realization list, `rationale`,
 * `geography` (null = everywhere) and the derived TIME `hint` describe that realization (943). */
export interface AppRef {
  id: string;
  name: string;
  rationale?: Rationale | null;
  geography?: GeoRef | null;
  hint?: string | null;
}

export interface RealizationAttrs {
  rationale?: Rationale | null;
  geography_id?: string | null;
}

export interface ApplicationCapability {
  id: string;
  name: string;
  description: string | null;
  parent_id: string | null;
  level: AppCapLevel;
  created_at: string;
  updated_at: string;
  business_capability_count: number;
  technical_capability_count: number;
  realization_count: number;
  warnings: AppCapWarning[];
}

export interface ApplicationCapabilityDetail extends ApplicationCapability {
  path: CapRef[];
  business_capabilities: LinkedCapRef[];
  technical_capabilities: LinkedCapRef[];
  realized_by: AppRef[];
}

export interface AppCapSummary {
  id: string;
  name: string;
  level: AppCapLevel;
  path: CapRef[];
  warnings: AppCapWarning[];
  realized_by: AppRef[];
}

export interface ApplicationCapabilityCreate {
  name: string;
  description?: string | null;
  parent_id?: string | null;
}

export interface ApplicationCapabilityUpdate {
  name?: string;
  description?: string | null;
}

export type LinkKind = "business" | "technical" | "application";

const LINK_PATH: Record<LinkKind, string> = {
  business: "business-capabilities",
  technical: "technical-capabilities",
  application: "applications",
};

const LINK_BODY_KEY: Record<LinkKind, string> = {
  business: "business_capability_id",
  technical: "tech_cap_id",
  application: "app_id",
};

export { errorDetail };

const KEY = [QK.appCapabilities] as const;

export function useAppCapabilities() {
  return useQuery<{ items: ApplicationCapability[]; total: number }>({
    queryKey: [...KEY, "list"],
    queryFn: () => apiGet(BASE),
  });
}

export function useAppCapability(id: string | null) {
  return useQuery<ApplicationCapabilityDetail>({
    queryKey: [...KEY, "detail", id],
    queryFn: () => apiGet(`${BASE}/${id}`),
    enabled: !!id,
  });
}

export function useAppCapsByBusinessCapability(capId: string | null) {
  return useQuery<AppCapSummary[]>({
    queryKey: [...KEY, "by-business", capId],
    queryFn: () => apiGet(`${BASE}/by-business-capability/${capId}`),
    enabled: !!capId,
  });
}

export function useAppCapsByTechnicalCapability(tcId: string | null) {
  return useQuery<AppCapSummary[]>({
    queryKey: [...KEY, "by-technical", tcId],
    queryFn: () => apiGet(`${BASE}/by-technical-capability/${tcId}`),
    enabled: !!tcId,
  });
}

export function useAppCapsByApplication(appId: string | null) {
  return useQuery<AppCapSummary[]>({
    queryKey: [...KEY, "by-application", appId],
    queryFn: () => apiGet(`${BASE}/by-application/${appId}`),
    enabled: !!appId,
  });
}

/** Every write invalidates the whole app-capabilities key, so the tree badge, the gaps list,
 * the detail and the reverse lookups on other screens update together. */
function useInvalidating<V, R>(fn: (v: V) => Promise<R>) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: fn,
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: KEY });
      // 938-capability-model-analysis: roll-ups, impact and findings derive from these links.
      void qc.invalidateQueries({ queryKey: [QK.capAnalysis] });
    },
  });
}

export function useCreateAppCapability() {
  return useInvalidating((body: ApplicationCapabilityCreate) =>
    apiMutation<ApplicationCapability>("POST", BASE, body),
  );
}

export function useUpdateAppCapability() {
  return useInvalidating(({ id, body }: { id: string; body: ApplicationCapabilityUpdate }) =>
    apiMutation<ApplicationCapability>("PATCH", `${BASE}/${id}`, body),
  );
}

export function useDeleteAppCapability() {
  return useInvalidating((id: string) => apiMutation<void>("DELETE", `${BASE}/${id}`));
}

export function useAddAppCapLink() {
  return useInvalidating(({ id, kind, targetId }: { id: string; kind: LinkKind; targetId: string }) =>
    apiMutation<ApplicationCapabilityDetail>("POST", `${BASE}/${id}/${LINK_PATH[kind]}`, {
      [LINK_BODY_KEY[kind]]: targetId,
    }),
  );
}

export function useRemoveAppCapLink() {
  return useInvalidating(({ id, kind, targetId }: { id: string; kind: LinkKind; targetId: string }) =>
    apiMutation<void>("DELETE", `${BASE}/${id}/${LINK_PATH[kind]}/${targetId}`),
  );
}

/** 943: add a realization with an optional rationale and geography. */
export function useAddRealization() {
  return useInvalidating(({ id, appId, attrs }: { id: string; appId: string; attrs?: RealizationAttrs }) =>
    apiMutation<ApplicationCapabilityDetail>("POST", `${BASE}/${id}/applications`, { app_id: appId, ...(attrs ?? {}) }),
  );
}

/** 943: set or clear a realization's rationale and/or geography. Send only the fields to change;
 * null clears. Saves at once (the selects save on choose). */
export function useUpdateRealization() {
  return useInvalidating(({ id, appId, attrs }: { id: string; appId: string; attrs: RealizationAttrs }) =>
    apiMutation<ApplicationCapabilityDetail>("PATCH", `${BASE}/${id}/applications/${appId}`, attrs),
  );
}
