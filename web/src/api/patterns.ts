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
  view: PatternViewKind;
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
