import { useMutation, useQuery, useQueryClient, useSuspenseQuery } from "@tanstack/react-query";

const API = "/api/v1";

export type TimeClassification = "Tolerate" | "Invest" | "Migrate" | "Eliminate";
export type RStrategy = "Rehost" | "Replatform" | "Repurchase" | "Refactor" | "Retire" | "Retain" | "Relocate";
export type PaceLayer = "Record" | "Differentiation" | "Innovation";
export type UsageType = "provides" | "consumes";
export type IntegrationDir = "inbound" | "outbound" | "bidirectional";
export type AppIntegrationType = "API" | "event" | "file" | "database" | "messaging" | "other";
export type LifecycleStatus = "planned" | "active" | "sunset" | "retired";

export interface Application {
  id: string;
  name: string;
  description: string | null;
  vendor: string | null;
  primary_owner: string | null;
  time_classification: TimeClassification | null;
  r_strategy: RStrategy | null;
  pace_layer: PaceLayer | null;
  health_score: number | null;
  business_value: number | null;
  business_criticality: number | null;
  owning_business_unit: string | null;
  business_owner: string | null;
  technical_owner: string | null;
  lifecycle_status: LifecycleStatus;
  created_at: string;
  updated_at: string;
}

export interface ApplicationCreate {
  name: string;
  description?: string | null;
  vendor?: string | null;
  primary_owner?: string | null;
  time_classification?: TimeClassification | null;
  r_strategy?: RStrategy | null;
  pace_layer?: PaceLayer | null;
  health_score?: number | null;
  business_value?: number | null;
  business_criticality?: number | null;
  owning_business_unit?: string | null;
  business_owner?: string | null;
  technical_owner?: string | null;
  lifecycle_status?: LifecycleStatus;
}

export interface ApplicationUpdate extends Partial<ApplicationCreate> {}

export interface ApplicationListResponse {
  items: Application[];
  total: number;
}

// ── Rationalization (APM US1) ─────────────────────────────────────────────────

export type Quadrant = "tolerate" | "invest" | "migrate" | "eliminate";

export interface RationalizationEntry {
  app_id: string;
  name: string;
  business_value: number | null;
  health_score: number | null;
  quadrant: Quadrant | null;
}

export interface RationalizationResponse {
  assessed: RationalizationEntry[];
  unassessed: RationalizationEntry[];
  total: number;
}

// ── Risk & compliance (APM US3, sensitive) ────────────────────────────────────

export type DataClassification = "public" | "internal" | "confidential" | "restricted";
export type SecurityPosture = "strong" | "adequate" | "weak" | "unknown";
export type VulnerabilityStatus = "none_known" | "open_low" | "open_high" | "critical";
export type DrBcStatus = "tested" | "documented" | "none";

export interface ApplicationRisk {
  security_posture: SecurityPosture | null;
  vulnerability_status: VulnerabilityStatus | null;
  data_classification: DataClassification | null;
  regulatory_tags: string[];
  dr_bc_status: DrBcStatus | null;
  end_of_life_date: string | null;
  end_of_support_date: string | null;
  updated_at: string | null;
}

export type ApplicationRiskUpdate = Omit<ApplicationRisk, "updated_at">;

export interface OutOfSupportEntry {
  app_id: string;
  name: string;
  end_of_support_date: string;
}

export interface OutOfSupportResponse {
  items: OutOfSupportEntry[];
  total: number;
}

// ── Total Cost of Ownership (APM US4, ADP-9x6, sensitive) ────────────────────
// Money is Decimal on the backend and serializes as a string — never parse it
// back into a JS number except for display formatting.

export interface CostBucket {
  one_time: string;
  annual: string;
}

export const TCO_BUCKET_KEYS = [
  "acquisition", "implementation", "training", "operational",
  "maintenance", "upgrades", "risk_downtime", "end_of_life",
] as const;
export type TcoBucketKey = (typeof TCO_BUCKET_KEYS)[number];

export type CostBuckets = { [K in TcoBucketKey]: CostBucket };

export interface ApplicationCostUpdate extends CostBuckets {
  currency: string;
  horizon_years: number;
}

export interface ApplicationCost extends ApplicationCostUpdate {
  updated_at: string | null;
  tco: string;
  run_total: string;
  change_total: string;
}

export interface BusinessUnitCostRollup {
  business_unit: string | null;
  app_count: number;
  tco: string;
}

export interface CostRollupResponse {
  items: BusinessUnitCostRollup[];
  total_tco: string;
}

export interface TechnicalCapability {
  id: string;
  name: string;
  description: string | null;
  parent_id: string | null;
  level: number;
  created_at: string;
}

export interface TechnicalCapabilityCreate {
  name: string;
  description?: string | null;
  parent_id?: string | null;
}

export interface TechCapListResponse {
  items: TechnicalCapability[];
  total: number;
}

export interface ApplicationCapabilityLink {
  app_id: string;
  capability_id: string;
  capability_name: string;
  fit_score: number;
}

export interface ApplicationTechCapLink {
  app_id: string;
  tech_cap_id: string;
  tech_cap_name: string;
  usage_type: UsageType;
}

export interface ApplicationStageLink {
  app_id: string;
  stage_id: string;
  stage_name: string;
}

export interface ApplicationDomainIntegration {
  id: string;
  app_id: string;
  domain_id: string | null;
  domain_name: string | null;
  integration_type: string;
  direction: IntegrationDir;
  created_at: string;
}

export interface ApplicationIntegration {
  id: string;
  source_app_id: string;
  source_app_name: string;
  target_app_id: string;
  target_app_name: string;
  integration_type: AppIntegrationType;
  description: string | null;
  created_at: string;
  updated_at: string;
}

export interface ApplicationIntegrationCreate {
  source_app_id: string;
  target_app_id: string;
  integration_type: AppIntegrationType;
  description?: string | null;
}

export interface ApplicationDesignLink {
  app_id: string;
  design_id: string;
}

async function apiFetch<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(path, { ...init, headers: { "Content-Type": "application/json", ...init?.headers } });
  if (!res.ok) throw new Error(`${res.status} ${res.statusText}`);
  if (res.status === 204) return undefined as T;
  return res.json();
}

// ── Application hooks ─────────────────────────────────────────────────────────

export function useApplications() {
  return useSuspenseQuery<ApplicationListResponse>({
    queryKey: ["applications"],
    queryFn: () => apiFetch(`${API}/applications`),
  });
}

export function useApplication(id: string) {
  return useQuery<Application>({
    queryKey: ["applications", id],
    queryFn: () => apiFetch(`${API}/applications/${id}`),
    enabled: !!id,
  });
}

export function useRationalization() {
  return useQuery<RationalizationResponse>({
    queryKey: ["rationalization"],
    queryFn: () => apiFetch(`${API}/applications/rationalization`),
  });
}

export function useApplicationRisk(appId: string) {
  return useQuery<ApplicationRisk>({
    queryKey: ["applications", appId, "risk"],
    queryFn: () => apiFetch(`${API}/applications/${appId}/risk`),
    enabled: !!appId,
    // Sensitive data: don't cache/refetch aggressively for a reader who lacks access.
    retry: false,
  });
}

export function useUpdateApplicationRisk(appId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (body: ApplicationRiskUpdate) =>
      apiFetch<ApplicationRisk>(`${API}/applications/${appId}/risk`, {
        method: "PUT",
        body: JSON.stringify(body),
      }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["applications", appId, "risk"] }),
  });
}

export function useOutOfSupport() {
  return useQuery<OutOfSupportResponse>({
    queryKey: ["applications", "risk", "out-of-support"],
    queryFn: () => apiFetch(`${API}/applications/risk/out-of-support`),
    retry: false,
  });
}

export function useApplicationCost(appId: string) {
  return useQuery<ApplicationCost>({
    queryKey: ["applications", appId, "cost"],
    queryFn: () => apiFetch(`${API}/applications/${appId}/cost`),
    enabled: !!appId,
    retry: false, // sensitive data: don't hammer a reader who lacks access
  });
}

export function useUpdateApplicationCost(appId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (body: ApplicationCostUpdate) =>
      apiFetch<ApplicationCost>(`${API}/applications/${appId}/cost`, {
        method: "PUT",
        body: JSON.stringify(body),
      }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["applications", appId, "cost"] });
      qc.invalidateQueries({ queryKey: ["applications", "cost", "rollup"] });
    },
  });
}

export function useCostRollup() {
  return useQuery<CostRollupResponse>({
    queryKey: ["applications", "cost", "rollup"],
    queryFn: () => apiFetch(`${API}/applications/cost/rollup`),
    retry: false,
  });
}

export function useCreateApplication() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (body: ApplicationCreate) =>
      apiFetch<Application>(`${API}/applications`, { method: "POST", body: JSON.stringify(body) }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["applications"] });
      qc.invalidateQueries({ queryKey: ["rationalization"] });
    },
  });
}

export function useUpdateApplication(id: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (body: ApplicationUpdate) =>
      apiFetch<Application>(`${API}/applications/${id}`, { method: "PATCH", body: JSON.stringify(body) }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["applications"] });
      qc.invalidateQueries({ queryKey: ["applications", id] });
      qc.invalidateQueries({ queryKey: ["rationalization"] });
    },
  });
}

export function useDeleteApplication() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => apiFetch<void>(`${API}/applications/${id}`, { method: "DELETE" }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["applications"] }),
  });
}

// ── Technical Capability hooks ────────────────────────────────────────────────

export function useTechCaps() {
  return useQuery<TechCapListResponse>({
    queryKey: ["tech-caps"],
    queryFn: () => apiFetch(`${API}/technical-capabilities`),
  });
}

export function useCreateTechCap() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (body: TechnicalCapabilityCreate) =>
      apiFetch<TechnicalCapability>(`${API}/technical-capabilities`, { method: "POST", body: JSON.stringify(body) }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["tech-caps"] }),
  });
}

export function useDeleteTechCap() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: string) =>
      apiFetch<void>(`${API}/technical-capabilities/${id}`, { method: "DELETE" }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["tech-caps"] }),
  });
}

// ── Capability Link hooks ─────────────────────────────────────────────────────

export function useAppCapLinks(appId: string) {
  return useQuery<{ items: ApplicationCapabilityLink[] }>({
    queryKey: ["applications", appId, "capability-links"],
    queryFn: () => apiFetch(`${API}/applications/${appId}/capability-links`),
    enabled: !!appId,
  });
}

export function useCreateAppCapLink(appId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (body: { capability_id: string; fit_score: number }) =>
      apiFetch<ApplicationCapabilityLink>(
        `${API}/applications/${appId}/capability-links`,
        { method: "POST", body: JSON.stringify(body) },
      ),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["applications", appId, "capability-links"] }),
  });
}

export function useDeleteAppCapLink(appId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (capId: string) =>
      apiFetch<void>(`${API}/applications/${appId}/capability-links/${capId}`, { method: "DELETE" }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["applications", appId, "capability-links"] }),
  });
}

// ── Tech Cap Link hooks ───────────────────────────────────────────────────────

export function useAppTechCapLinks(appId: string) {
  return useQuery<{ items: ApplicationTechCapLink[] }>({
    queryKey: ["applications", appId, "tech-cap-links"],
    queryFn: () => apiFetch(`${API}/applications/${appId}/technical-capability-links`),
    enabled: !!appId,
  });
}

export function useCreateAppTechCapLink(appId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (body: { tech_cap_id: string; usage_type: UsageType }) =>
      apiFetch<ApplicationTechCapLink>(
        `${API}/applications/${appId}/technical-capability-links`,
        { method: "POST", body: JSON.stringify(body) },
      ),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["applications", appId, "tech-cap-links"] }),
  });
}

export function useDeleteAppTechCapLink(appId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ tcId, usageType }: { tcId: string; usageType: UsageType }) =>
      apiFetch<void>(
        `${API}/applications/${appId}/technical-capability-links/${tcId}/${usageType}`,
        { method: "DELETE" },
      ),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["applications", appId, "tech-cap-links"] }),
  });
}

// ── Stage Link hooks ──────────────────────────────────────────────────────────

export function useAppStageLinks(appId: string) {
  return useQuery<{ items: ApplicationStageLink[] }>({
    queryKey: ["applications", appId, "stage-links"],
    queryFn: () => apiFetch(`${API}/applications/${appId}/stage-links`),
    enabled: !!appId,
  });
}

export function useCreateAppStageLink(appId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (stageId: string) =>
      apiFetch<ApplicationStageLink>(
        `${API}/applications/${appId}/stage-links`,
        { method: "POST", body: JSON.stringify({ stage_id: stageId }) },
      ),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["applications", appId, "stage-links"] }),
  });
}

export function useDeleteAppStageLink(appId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (stageId: string) =>
      apiFetch<void>(`${API}/applications/${appId}/stage-links/${stageId}`, { method: "DELETE" }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["applications", appId, "stage-links"] }),
  });
}

// ── Domain Integration hooks ──────────────────────────────────────────────────

export function useAppDomainIntegrations(appId: string) {
  return useQuery<{ items: ApplicationDomainIntegration[] }>({
    queryKey: ["applications", appId, "domain-integrations"],
    queryFn: () => apiFetch(`${API}/applications/${appId}/domain-integrations`),
    enabled: !!appId,
  });
}

export function useCreateAppDomainIntegration(appId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (body: { domain_id?: string | null; integration_type: string; direction: IntegrationDir }) =>
      apiFetch<ApplicationDomainIntegration>(
        `${API}/applications/${appId}/domain-integrations`,
        { method: "POST", body: JSON.stringify(body) },
      ),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["applications", appId, "domain-integrations"] }),
  });
}

export function useDeleteAppDomainIntegration(appId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (linkId: string) =>
      apiFetch<void>(`${API}/applications/${appId}/domain-integrations/${linkId}`, { method: "DELETE" }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["applications", appId, "domain-integrations"] }),
  });
}

// ── Integration hooks ─────────────────────────────────────────────────────────

export function useIntegrations(appId?: string) {
  return useQuery<{ items: ApplicationIntegration[]; total: number }>({
    queryKey: ["integrations", appId ?? "all"],
    queryFn: () => apiFetch(`${API}/integrations${appId ? `?app_id=${appId}` : ""}`),
  });
}

export function useCreateIntegration() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (body: ApplicationIntegrationCreate) =>
      apiFetch<ApplicationIntegration>(`${API}/integrations`, {
        method: "POST",
        body: JSON.stringify(body),
      }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["integrations"] }),
  });
}

export function useDeleteIntegration() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => apiFetch<void>(`${API}/integrations/${id}`, { method: "DELETE" }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["integrations"] }),
  });
}

// ── Design Link hooks ─────────────────────────────────────────────────────────

export function useAppDesignLinks(appId: string) {
  return useQuery<{ items: ApplicationDesignLink[] }>({
    queryKey: ["applications", appId, "design-links"],
    queryFn: () => apiFetch(`${API}/applications/${appId}/design-links`),
    enabled: !!appId,
  });
}

export function useCreateAppDesignLink(appId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (designId: string) =>
      apiFetch<ApplicationDesignLink>(
        `${API}/applications/${appId}/design-links`,
        { method: "POST", body: JSON.stringify({ design_id: designId }) },
      ),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["applications", appId, "design-links"] }),
  });
}

export function useDeleteAppDesignLink(appId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (designId: string) =>
      apiFetch<void>(`${API}/applications/${appId}/design-links/${designId}`, { method: "DELETE" }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["applications", appId, "design-links"] }),
  });
}
