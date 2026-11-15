/** TypeScript types and TanStack Query hooks for the EA pattern registry (935-pattern-registry,
 * ADP-mmm.2; specs/935-pattern-registry/contracts/rest-api.md). */

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ApiError, apiGet, apiMutation, getAuthHeader } from "./client";

const API = "/api/v1/patterns";

// ── Types ─────────────────────────────────────────────────────────────────────

export type PatternKind = "reference-architecture" | "portfolio-rule" | "transition" | "anti-pattern";
export type PatternLifecycle = "draft" | "proposed" | "current" | "deprecated" | "decommissioned";
export type PatternViewKind = "structure" | "catalog" | "traceability";
export type IssueSeverity = "error" | "warning" | "info";

export const PATTERN_KINDS: PatternKind[] = ["reference-architecture", "portfolio-rule", "transition", "anti-pattern"];
export const PATTERN_LIFECYCLES: PatternLifecycle[] = ["draft", "proposed", "current", "deprecated", "decommissioned"];

export interface PatternIssue {
  path: string;
  code: string;
  message: string;
  severity: IssueSeverity;
  line?: number | null;
  column?: number | null;
}

export interface PatternVersionSummary {
  id: string;
  pattern_key: string;
  version: string;
  kind: PatternKind;
  lifecycle: PatternLifecycle;
  name: string;
  summary: string;
  tags: string[];
  digest: string;
  created_at: string;
  created_by: string;
  lifecycle_changed_at: string;
}

export interface PatternFamily {
  pattern_key: string;
  kind: PatternKind;
  owner_role: string;
  created_at: string;
  created_by: string;
  current_version: string | null;
  versions: PatternVersionSummary[];
}

export interface PatternRelationRow {
  source_version_id: string;
  source_pattern_key: string;
  target_pattern_key: string;
  relation_type: string;
  note: string | null;
  target_resolved: boolean;
}

export interface LifecycleEvent {
  id: string;
  from_state: PatternLifecycle;
  to_state: PatternLifecycle;
  reason: string;
  confirmation_id: string;
  actor: string;
  at: string;
  caused_by_event_id: string | null;
}

/** The typed 934 definition, as JSON. Only the fields the UI reads are typed. */
export interface PatternDefinition {
  pattern: string;
  version: string;
  kind: PatternKind;
  name: string;
  summary: string;
  owner_role: string;
  tags: string[];
  motivation: {
    context: string;
    problem: string;
    forces: string[];
    benefits: string[];
    liabilities: string[];
    principles: string[];
    controls: string[];
  };
  roles: Record<string, {
    element_type: string;
    cardinality: { min: number; max: number | null; per: string | null };
    selector: string | null;
    label: string | null;
    stereotype: string | null;
    description: string | null;
  }>;
  relationships: { id: string; source: string; target: string; type: string; via: string | null; label: string | null; required: boolean }[];
  constraints: { id: string; rule: string; for_each: string | null; expr: string; polarity: string; severity: string }[];
  transition: { from_pattern: string; strategy: string; plateaus: { id: string; name: string; exit_criteria: string[] }[] } | null;
  relations: { type: string; target: string; note: string | null }[];
  known_implementations: string[];
  views: string[];
}

export interface PatternVersionDetail extends PatternVersionSummary {
  definition: PatternDefinition;
  relations: PatternRelationRow[];
  issues: PatternIssue[];
  allowed_transitions: PatternLifecycle[];
  history: LifecycleEvent[];
  knowledge_item_id: string | null;
}

export interface PatternImportResult {
  status: "created" | "unchanged" | "rejected";
  version: PatternVersionSummary | null;
  issues: PatternIssue[];
}

export interface PatternUpdateResult {
  version: PatternVersionSummary;
  issues: PatternIssue[];
}

export interface PatternValidateResult {
  ok: boolean;
  digest: string | null;
  issues: PatternIssue[];
}

export interface PatternViewResponse {
  view: PatternViewKind | "conformance" | "transition";
  flowchart: string;
  digest: string;
  generated_at: string;
  truncated: string[];
}

export interface PatternFilters {
  kind?: PatternKind;
  lifecycle?: PatternLifecycle;
  tag?: string;
  q?: string;
}

export interface TransitionRequest {
  to: PatternLifecycle;
  reason: string;
  confirmation_id: string;
}

interface ListResponse<T> {
  items: T[];
  total: number;
}

/** A failed request whose body carries pattern issues (422 rejected import, blocked promotion). */
export class PatternIssuesError extends Error {
  constructor(public readonly status: number, public readonly issues: PatternIssue[], message: string) {
    super(message);
    this.name = "PatternIssuesError";
  }
}

/** FastAPI puts a human-readable reason in `detail`; fall back to the generic message. */
export function errorDetail(err: unknown): string {
  if (err instanceof ApiError && err.body && typeof err.body === "object") {
    const detail = (err.body as { detail?: unknown }).detail;
    if (typeof detail === "string") return detail;
  }
  return err instanceof Error ? err.message : String(err);
}

/** Issues carried by an error, if any (rejected import, blocked promotion, invalid draft). */
export function errorIssues(err: unknown): PatternIssue[] {
  if (err instanceof PatternIssuesError) return err.issues;
  if (err instanceof ApiError && err.body && typeof err.body === "object") {
    const body = err.body as { issues?: unknown; detail?: unknown };
    if (Array.isArray(body.issues)) return body.issues as PatternIssue[];
    const detail = body.detail as { issues?: unknown } | undefined;
    if (detail && typeof detail === "object" && Array.isArray(detail.issues)) return detail.issues as PatternIssue[];
  }
  return [];
}

/** POST/PUT a raw YAML body. 2xx and (for import) 422 both carry a JSON result body. */
async function sendYaml<T>(method: "POST" | "PUT", path: string, yaml: string): Promise<{ status: number; body: T }> {
  const authHeader = await getAuthHeader();
  const res = await fetch(path, {
    method,
    headers: { ...authHeader, "Content-Type": "application/yaml" },
    body: yaml,
  });
  let body: unknown;
  try {
    body = await res.json();
  } catch {
    body = undefined;
  }
  if (!res.ok && res.status !== 422) {
    throw new ApiError(res.status, `${method} ${path} failed: ${res.status}`, body);
  }
  return { status: res.status, body: body as T };
}

export function versionPath(key: string, version: string): string {
  return `${API}/${encodeURIComponent(key)}/versions/${encodeURIComponent(version)}`;
}

export function yamlDownloadUrl(key: string, version: string): string {
  return `${versionPath(key, version)}/yaml`;
}

// ── Query keys ────────────────────────────────────────────────────────────────

const keys = {
  all: ["patterns"] as const,
  list: (filters: PatternFilters) => ["patterns", "list", filters] as const,
  family: (key: string) => ["patterns", "family", key] as const,
  version: (key: string, version: string) => ["patterns", "version", key, version] as const,
  view: (key: string, version: string, view: PatternViewKind, depth: number) =>
    ["patterns", "view", key, version, view, depth] as const,
};

function useInvalidatePatterns() {
  const qc = useQueryClient();
  return (alsoKnowledge = false) => {
    void qc.invalidateQueries({ queryKey: keys.all });
    if (alsoKnowledge) void qc.invalidateQueries({ queryKey: ["knowledge"] });
  };
}

// ── Reads ─────────────────────────────────────────────────────────────────────

export function usePatterns(filters: PatternFilters = {}) {
  const params = new URLSearchParams();
  for (const [k, v] of Object.entries(filters)) {
    if (v !== undefined && v !== "") params.set(k, String(v));
  }
  const qs = params.toString();
  return useQuery<ListResponse<PatternVersionSummary>>({
    queryKey: keys.list(filters),
    queryFn: () => apiGet(`${API}${qs ? `?${qs}` : ""}`),
  });
}

export function usePatternFamily(key: string | null) {
  return useQuery<PatternFamily>({
    queryKey: keys.family(key ?? ""),
    queryFn: () => apiGet(`${API}/${encodeURIComponent(key ?? "")}`),
    enabled: !!key,
  });
}

export function usePatternVersion(key: string | null, version: string | null) {
  return useQuery<PatternVersionDetail>({
    queryKey: keys.version(key ?? "", version ?? ""),
    queryFn: () => apiGet(versionPath(key ?? "", version ?? "")),
    enabled: !!key && !!version,
  });
}

export function usePatternView(key: string, version: string, view: PatternViewKind, depth = 1) {
  return useQuery<PatternViewResponse>({
    queryKey: keys.view(key, version, view, depth),
    queryFn: () => apiGet(`${versionPath(key, version)}/views/${view}${view === "catalog" ? `?depth=${depth}` : ""}`),
  });
}

// ── Writes ────────────────────────────────────────────────────────────────────

/** Resolves for created/unchanged; rejects with PatternIssuesError for a rejected import. */
export function useImportPattern() {
  const invalidate = useInvalidatePatterns();
  return useMutation<PatternImportResult, Error, string>({
    mutationFn: async (yaml) => {
      const { status, body } = await sendYaml<PatternImportResult>("POST", `${API}/import`, yaml);
      if (status === 422) {
        throw new PatternIssuesError(422, body?.issues ?? [], "Import rejected");
      }
      return body;
    },
    onSuccess: () => invalidate(),
  });
}

/** Dry run: never stores anything. */
export function useValidatePattern() {
  return useMutation<PatternValidateResult, Error, string>({
    mutationFn: async (yaml) => (await sendYaml<PatternValidateResult>("POST", `${API}/validate`, yaml)).body,
  });
}

/** Dry run: structure view of unsaved YAML. Rejects with PatternIssuesError when the YAML is invalid. */
export function useRenderPattern() {
  return useMutation<PatternViewResponse, Error, string>({
    mutationFn: async (yaml) => {
      try {
        return await apiMutation<PatternViewResponse>("POST", `${API}/render`, { yaml, view: "structure" });
      } catch (err) {
        const issues = errorIssues(err);
        if (issues.length) throw new PatternIssuesError(422, issues, "Preview failed");
        throw err;
      }
    },
  });
}

export function useUpdateDraft(key: string, version: string) {
  const invalidate = useInvalidatePatterns();
  return useMutation<PatternUpdateResult, Error, string>({
    mutationFn: async (yaml) => {
      const { status, body } = await sendYaml<PatternUpdateResult & { detail?: { issues?: PatternIssue[] } }>(
        "PUT", versionPath(key, version), yaml,
      );
      if (status === 422) {
        throw new PatternIssuesError(422, body?.detail?.issues ?? [], "Draft update rejected");
      }
      return body;
    },
    onSuccess: () => invalidate(),
  });
}

export function useTransition(key: string, version: string) {
  const invalidate = useInvalidatePatterns();
  return useMutation<PatternVersionDetail, Error, TransitionRequest>({
    mutationFn: (req) => apiMutation<PatternVersionDetail>("POST", `${versionPath(key, version)}/lifecycle`, req),
    onSuccess: () => invalidate(true),
  });
}

export function useDeleteDraft(key: string, version: string) {
  const invalidate = useInvalidatePatterns();
  return useMutation<void, Error, void>({
    mutationFn: () => apiMutation<void>("DELETE", versionPath(key, version)),
    onSuccess: () => invalidate(),
  });
}

/** The canonical YAML of a version, as text (same bytes as the download and export). */
export function usePatternYaml(key: string | null, version: string | null) {
  return useQuery<string>({
    queryKey: ["patterns", "yaml", key ?? "", version ?? ""],
    queryFn: async () => {
      const authHeader = await getAuthHeader();
      const path = yamlDownloadUrl(key ?? "", version ?? "");
      const res = await fetch(path, { headers: authHeader });
      if (!res.ok) throw new ApiError(res.status, `GET ${path} failed: ${res.status}`);
      return res.text();
    },
    enabled: !!key && !!version,
  });
}

// ── 936: adoptions, conformance, discovery ──────────────────────────────────────────

export type ScopeType = "business_domain" | "application_set" | "portfolio";
export type ConformanceStatus = "conformant" | "conformant_with_warnings" | "non_conformant" | "indeterminate" | "not_applicable";
export type FindingKind = "violation" | "match" | "binding" | "evaluation_error" | "field_unavailable" | "unverifiable" | "limit";
export type ElementType = "business_capability" | "value_stream" | "business_domain" | "application" | "integration" | "technical_capability" | "agent";

export interface ElementRef { type: ElementType; id: string; name: string }
export interface Finding {
  code: string;
  kind: FindingKind;
  severity: IssueSeverity;
  rule: string;
  element_refs: ElementRef[];
  element_count: number;
  truncated: boolean;
}
export interface RoleBinding { role_key: string; element_type: ElementType; label: string; elements: ElementRef[]; count: number }
export interface PlateauState { reached: string | null; next: string | null; blocking: string[] }
export interface AdoptionScope { scope_type: ScopeType; scope_ref: string | null; member_ids: string[] }
export interface ConformanceReport {
  adoption_id: string | null;
  pattern_key: string;
  version: string | null;
  digest: string | null;
  evaluated_at: string;
  scope: AdoptionScope;
  bindings: RoleBinding[];
  findings: Finding[];
  status: ConformanceStatus;
  plateau: PlateauState | null;
}
export interface DiscoveryReport { pattern_key: string; version: string; digest: string; evaluated_at: string; matches: Finding[]; match_count: number }
export interface Pin { role_key: string; element_type: ElementType; element_id: string }
export interface Adoption {
  id: string;
  pattern_key: string;
  pattern_name: string | null;
  kind: PatternKind;
  name: string;
  scope_type: ScopeType;
  scope_ref: string | null;
  scope_name: string | null;
  member_ids: string[];
  pinned_version: string | null;
  resolved_version: string | null;
  pins: Pin[];
  created_at: string;
  created_by: string;
  updated_at: string;
  status: ConformanceStatus | null;
}
export interface AdoptionCreate {
  pattern_key: string;
  name: string;
  scope_type: ScopeType;
  scope_ref?: string | null;
  member_ids?: string[];
  pinned_version?: string | null;
  pins?: Pin[];
}
export interface EvaluateRequest {
  yaml?: string;
  pattern_key?: string;
  version?: string;
  scope: AdoptionScope;
  pins?: Pin[];
}
export type AdoptionViewKind = "conformance" | "transition";

const adoptionKeys = {
  all: ["patterns", "adoptions"] as const,
  list: (withStatus: boolean) => ["patterns", "adoptions", "list", withStatus] as const,
  one: (id: string) => ["patterns", "adoptions", "one", id] as const,
  conformance: (id: string) => ["patterns", "adoptions", "conformance", id] as const,
  view: (id: string, view: AdoptionViewKind) => ["patterns", "adoptions", "view", id, view] as const,
  candidates: (id: string, role: string) => ["patterns", "adoptions", "candidates", id, role] as const,
};

function useInvalidateAdoptions() {
  const qc = useQueryClient();
  return () => void qc.invalidateQueries({ queryKey: adoptionKeys.all });
}

export function useAdoptions(withStatus = true) {
  return useQuery<ListResponse<Adoption>>({
    queryKey: adoptionKeys.list(withStatus),
    queryFn: () => apiGet(`${API}/adoptions${withStatus ? "?with_status=true" : ""}`),
  });
}

export function useAdoption(id: string | null) {
  return useQuery<Adoption>({
    queryKey: adoptionKeys.one(id ?? ""),
    queryFn: () => apiGet(`${API}/adoptions/${encodeURIComponent(id ?? "")}`),
    enabled: !!id,
  });
}

export function useConformance(id: string | null) {
  return useQuery<ConformanceReport>({
    queryKey: adoptionKeys.conformance(id ?? ""),
    queryFn: () => apiGet(`${API}/adoptions/${encodeURIComponent(id ?? "")}/conformance`),
    enabled: !!id,
  });
}

export function useAdoptionView(id: string, view: AdoptionViewKind, enabled = true) {
  return useQuery<PatternViewResponse>({
    queryKey: adoptionKeys.view(id, view),
    queryFn: () => apiGet(`${API}/adoptions/${encodeURIComponent(id)}/views/${view}`),
    enabled,
  });
}

export function useCandidates(id: string, roleKey: string | null) {
  return useQuery<ElementRef[]>({
    queryKey: adoptionKeys.candidates(id, roleKey ?? ""),
    queryFn: () => apiGet(`${API}/adoptions/${encodeURIComponent(id)}/candidates/${encodeURIComponent(roleKey ?? "")}`),
    enabled: !!roleKey,
  });
}

export function useCreateAdoption() {
  const invalidate = useInvalidateAdoptions();
  return useMutation<Adoption, Error, AdoptionCreate>({
    mutationFn: (body) => apiMutation<Adoption>("POST", `${API}/adoptions`, body),
    onSuccess: () => invalidate(),
  });
}

export function useUpdateAdoption(id: string) {
  const invalidate = useInvalidateAdoptions();
  return useMutation<Adoption, Error, { name?: string; pinned_version?: string | null }>({
    mutationFn: (body) => apiMutation<Adoption>("PATCH", `${API}/adoptions/${encodeURIComponent(id)}`, body),
    onSuccess: () => invalidate(),
  });
}

export function useSetMembers(id: string) {
  const invalidate = useInvalidateAdoptions();
  return useMutation<Adoption, Error, string[]>({
    mutationFn: (memberIds) => apiMutation<Adoption>("PUT", `${API}/adoptions/${encodeURIComponent(id)}/members`, { member_ids: memberIds }),
    onSuccess: () => invalidate(),
  });
}

export function useSetPins(id: string) {
  const invalidate = useInvalidateAdoptions();
  return useMutation<Adoption, Error, Pin[]>({
    mutationFn: (pins) => apiMutation<Adoption>("PUT", `${API}/adoptions/${encodeURIComponent(id)}/pins`, { pins }),
    onSuccess: () => invalidate(),
  });
}

export function useDeleteAdoption(id: string) {
  const invalidate = useInvalidateAdoptions();
  return useMutation<void, Error, void>({
    mutationFn: () => apiMutation<void>("DELETE", `${API}/adoptions/${encodeURIComponent(id)}`),
    onSuccess: () => invalidate(),
  });
}

export function useDiscovery(key: string, version: string, enabled = true) {
  return useQuery<DiscoveryReport>({
    queryKey: ["patterns", "discovery", key, version],
    queryFn: () => apiGet(`${versionPath(key, version)}/discover`),
    enabled,
  });
}

export function useEvaluate() {
  return useMutation<ConformanceReport, Error, EvaluateRequest>({
    mutationFn: (body) => apiMutation<ConformanceReport>("POST", `${API}/evaluate`, body),
  });
}

/** Applications for the application-set member picker (plain query, no Suspense). */
export function useApplicationChoices() {
  return useQuery<ElementRef[]>({
    queryKey: ["patterns", "application-choices"],
    queryFn: async () => {
      const res = await apiGet<{ items: { id: string; name: string }[] }>("/api/v1/applications");
      return res.items
        .map((a) => ({ type: "application" as const, id: a.id, name: a.name }))
        .sort((a, b) => a.name.localeCompare(b.name));
    },
  });
}

/** Unique pattern families with a selectable version, for the adoption form. */
export function usePatternFamilies() {
  const list = usePatterns({});
  const families = new Map<string, { key: string; name: string; kind: PatternKind; versions: string[] }>();
  for (const v of list.data?.items ?? []) {
    const f = families.get(v.pattern_key) ?? { key: v.pattern_key, name: v.name, kind: v.kind, versions: [] };
    if (v.lifecycle !== "draft") f.versions.push(v.version);
    if (v.lifecycle === "current") f.name = v.name;
    families.set(v.pattern_key, f);
  }
  return { ...list, families: [...families.values()].sort((a, b) => a.name.localeCompare(b.name)) };
}
