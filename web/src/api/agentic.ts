/** TypeScript types and TanStack Query hooks for the agent registry (933-agent-registry,
 * ADP-hii): agents, and their membership in agentic solutions (applications whose
 * application_type is "agentic"). */

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ApiError, apiGet, apiMutation } from "./client";

const API = "/api/v1/agentic";

// ── Types ─────────────────────────────────────────────────────────────────────

export type HumanApproval = "none" | "on_write" | "on_irreversible" | "always";
export type AgentLifecycle = "planned" | "active" | "sunset" | "retired";
export type DataClassification = "public" | "internal" | "confidential" | "restricted";
export type SolutionRole = "orchestrator" | "worker" | "reviewer" | "router";

export interface Agent {
  id: string;
  name: string;
  description: string | null;
  owner: string | null;
  lifecycle_status: AgentLifecycle;
  model_provider: string | null;
  model_id: string | null;
  model_version: string | null;
  framework: string | null;
  prompt_ref: string | null;
  autonomy_level: number;
  human_approval: HumanApproval;
  data_classification_max: DataClassification | null;
  a2a_card_url: string | null;
  /** Decimal serialized as a string; null when not estimated OR not visible (see cost_visible). */
  est_cost_per_run: string | null;
  runs_per_month: number | null;
  /** False when the caller lacks the application-cost read permission (Clarification Q2). */
  cost_visible: boolean;
  external_registry_ref: string | null;
  solution_count: number;
  created_at: string;
  updated_at: string;
}

export interface AgentSolution {
  app_id: string;
  app_name: string;
  role: SolutionRole;
  position: number;
}

export interface AgentDetail extends Agent {
  solutions: AgentSolution[];
}

export interface AgentWrite {
  name?: string;
  description?: string | null;
  owner?: string | null;
  lifecycle_status?: AgentLifecycle;
  model_provider?: string | null;
  model_id?: string | null;
  model_version?: string | null;
  framework?: string | null;
  prompt_ref?: string | null;
  autonomy_level?: number;
  human_approval?: HumanApproval;
  data_classification_max?: DataClassification | null;
  a2a_card_url?: string | null;
  est_cost_per_run?: string | null;
  runs_per_month?: number | null;
  external_registry_ref?: string | null;
}

export interface SolutionAgent {
  agent: Agent;
  role: SolutionRole;
  position: number;
}

export interface AgentFilters {
  autonomy_min?: number;
  model_provider?: string;
  owner?: string;
  lifecycle_status?: AgentLifecycle;
}

interface ListResponse<T> {
  items: T[];
  total: number;
}

/** FastAPI puts a human-readable reason in `detail`; fall back to the generic message. */
export function errorDetail(err: unknown): string {
  if (err instanceof ApiError && err.body && typeof err.body === "object") {
    const detail = (err.body as { detail?: unknown }).detail;
    if (typeof detail === "string") return detail;
  }
  return err instanceof Error ? err.message : String(err);
}

// ── Query keys ────────────────────────────────────────────────────────────────

const keys = {
  agents: ["agentic-agents"] as const,
  agent: (id: string) => ["agentic-agent", id] as const,
  solution: (appId: string) => ["agentic-solution", appId] as const,
};

function useInvalidateAll() {
  const qc = useQueryClient();
  return () => {
    void qc.invalidateQueries({ queryKey: keys.agents });
    void qc.invalidateQueries({ queryKey: ["agentic-agent"] });
    void qc.invalidateQueries({ queryKey: ["agentic-solution"] });
  };
}

// ── Agents ────────────────────────────────────────────────────────────────────

export function useAgents(filters: AgentFilters = {}) {
  const params = new URLSearchParams();
  for (const [k, v] of Object.entries(filters)) {
    if (v !== undefined && v !== "") params.set(k, String(v));
  }
  const qs = params.toString();
  return useQuery<ListResponse<Agent>>({
    queryKey: [...keys.agents, filters],
    queryFn: () => apiGet(`${API}/agents${qs ? `?${qs}` : ""}`),
  });
}

export function useAgent(agentId: string | null) {
  return useQuery<AgentDetail>({
    queryKey: keys.agent(agentId ?? ""),
    queryFn: () => apiGet(`${API}/agents/${agentId}`),
    enabled: !!agentId,
  });
}

export function useCreateAgent() {
  const invalidate = useInvalidateAll();
  return useMutation<Agent, Error, AgentWrite>({
    mutationFn: (body) => apiMutation<Agent, AgentWrite>("POST", `${API}/agents`, body),
    onSuccess: invalidate,
  });
}

export function useUpdateAgent(agentId: string) {
  const invalidate = useInvalidateAll();
  return useMutation<Agent, Error, AgentWrite>({
    mutationFn: (body) => apiMutation<Agent, AgentWrite>("PATCH", `${API}/agents/${agentId}`, body),
    onSuccess: invalidate,
  });
}

export function useDeleteAgent() {
  const invalidate = useInvalidateAll();
  return useMutation<void, Error, string>({
    mutationFn: (agentId) => apiMutation<void>("DELETE", `${API}/agents/${agentId}`),
    onSuccess: invalidate,
  });
}

// ── Solution membership ───────────────────────────────────────────────────────

export function useSolutionAgents(appId: string) {
  return useQuery<ListResponse<SolutionAgent>>({
    queryKey: keys.solution(appId),
    queryFn: () => apiGet(`${API}/solutions/${appId}/agents`),
  });
}

export function useAddSolutionAgent(appId: string) {
  const invalidate = useInvalidateAll();
  return useMutation<ListResponse<SolutionAgent>, Error, { agent_id: string; role: SolutionRole }>({
    mutationFn: (body) => apiMutation("POST", `${API}/solutions/${appId}/agents`, body),
    onSuccess: invalidate,
  });
}

export function useUpdateSolutionAgentRole(appId: string) {
  const invalidate = useInvalidateAll();
  return useMutation<SolutionAgent, Error, { agentId: string; role: SolutionRole }>({
    mutationFn: ({ agentId, role }) =>
      apiMutation("PATCH", `${API}/solutions/${appId}/agents/${agentId}`, { role }),
    onSuccess: invalidate,
  });
}

export function useReorderSolutionAgents(appId: string) {
  const invalidate = useInvalidateAll();
  return useMutation<ListResponse<SolutionAgent>, Error, string[]>({
    mutationFn: (agentIds) =>
      apiMutation("PUT", `${API}/solutions/${appId}/agents/order`, { agent_ids: agentIds }),
    onSuccess: invalidate,
  });
}

export function useRemoveSolutionAgent(appId: string) {
  const invalidate = useInvalidateAll();
  return useMutation<void, Error, string>({
    mutationFn: (agentId) => apiMutation<void>("DELETE", `${API}/solutions/${appId}/agents/${agentId}`),
    onSuccess: invalidate,
  });
}
