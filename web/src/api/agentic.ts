/** TypeScript types and TanStack Query hooks for the agent registry (933-agent-registry,
 * ADP-hii): agents, and their membership in agentic solutions (applications whose
 * application_type is "agentic"). */

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { apiGet, apiMutation, errorDetail } from "./client";
import { QK } from "./queryKeys";

const API = "/api/v1/agentic";

// ── Types ─────────────────────────────────────────────────────────────────────

export type HumanApproval = "none" | "on_write" | "on_irreversible" | "always";
export type AgentLifecycle = "planned" | "active" | "sunset" | "retired";
export type DataClassification = "public" | "internal" | "confidential" | "restricted";
export type SolutionRole = "orchestrator" | "worker" | "reviewer" | "router";

// ── Agentic risk (944-agent-traceability): derived on read, never stored ──────

export type RiskBand = "high" | "medium" | "low";
export type RiskFactorCode = "autonomy" | "no_human_approval" | "sensitive_data";

export interface RiskFactor {
  code: RiskFactorCode;
  label: string;
}

export interface AgenticRisk {
  band: RiskBand;
  factors: RiskFactor[];
  missing: "data_classification"[];
  not_considered: "tool_side_effects"[];
}

export interface SolutionAgenticRisk {
  /** null = the solution has no non-retired agents ("No agents"). */
  band: RiskBand | null;
  agents: { id: string; name: string }[];
  not_considered: "tool_side_effects"[];
}

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
  agentic_risk: AgenticRisk;
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

export interface SolutionAgentList {
  items: SolutionAgent[];
  total: number;
  solution_risk: SolutionAgenticRisk;
}

// ── Automates links (944) ─────────────────────────────────────────────────────

export type AutomatesKind = "capability" | "stage" | "activity";

export interface AutomatesCapability {
  id: string;
  name: string;
  level: number;
  /** [L1 name, L2 name] */
  path: string[];
}

export interface AutomatesStage {
  id: string;
  name: string;
  value_stream_id: string;
  value_stream_name: string;
}

export interface AutomatesActivity {
  id: string;
  name: string;
  category: "primary" | "support";
  value_chain_id: string;
  value_chain_name: string;
}

export interface AgentAutomates {
  capabilities: AutomatesCapability[];
  stages: AutomatesStage[];
  activities: AutomatesActivity[];
}

export interface AgentSummary {
  id: string;
  name: string;
  lifecycle_status: AgentLifecycle;
  autonomy_level: number;
  agentic_risk: AgenticRisk;
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

export { errorDetail };

// ── Query keys ────────────────────────────────────────────────────────────────

const keys = {
  agents: [QK.agenticAgents] as const,
  agent: (id: string) => [QK.agenticAgent, id] as const,
  solution: (appId: string) => [QK.agenticSolution, appId] as const,
  automates: (id: string) => [QK.agenticAutomates, id] as const,
  automatedBy: (kind: AutomatesKind, id: string) => [QK.agenticAutomatedBy, kind, id] as const,
};

function useInvalidateAll() {
  const qc = useQueryClient();
  return () => {
    void qc.invalidateQueries({ queryKey: keys.agents });
    void qc.invalidateQueries({ queryKey: [QK.agenticAgent] });
    void qc.invalidateQueries({ queryKey: [QK.agenticSolution] });
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
  return useQuery<SolutionAgentList>({
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

// ── Automates links (944-agent-traceability) ──────────────────────────────────

const KIND_PATH: Record<AutomatesKind, { segment: string; field: string; reverse: string }> = {
  capability: { segment: "capabilities", field: "capability_id", reverse: "capabilities" },
  stage: { segment: "stages", field: "stage_id", reverse: "value-stream-stages" },
  activity: { segment: "activities", field: "activity_id", reverse: "value-chain-activities" },
};

export function useAgentAutomates(agentId: string | null) {
  return useQuery<AgentAutomates>({
    queryKey: keys.automates(agentId ?? ""),
    queryFn: () => apiGet(`${API}/agents/${agentId}/automates`),
    enabled: !!agentId,
  });
}

function useInvalidateAutomates(agentId: string) {
  const qc = useQueryClient();
  return () => {
    void qc.invalidateQueries({ queryKey: keys.automates(agentId) });
    void qc.invalidateQueries({ queryKey: [QK.agenticAutomatedBy] });
  };
}

export function useAddAutomates(agentId: string) {
  const invalidate = useInvalidateAutomates(agentId);
  return useMutation<AgentAutomates, Error, { kind: AutomatesKind; targetId: string }>({
    mutationFn: ({ kind, targetId }) =>
      apiMutation("POST", `${API}/agents/${agentId}/automates/${KIND_PATH[kind].segment}`, {
        [KIND_PATH[kind].field]: targetId,
      }),
    onSuccess: invalidate,
  });
}

export function useRemoveAutomates(agentId: string) {
  const invalidate = useInvalidateAutomates(agentId);
  return useMutation<void, Error, { kind: AutomatesKind; targetId: string }>({
    mutationFn: ({ kind, targetId }) =>
      apiMutation<void>(
        "DELETE",
        `${API}/agents/${agentId}/automates/${KIND_PATH[kind].segment}/${targetId}`,
      ),
    onSuccess: invalidate,
  });
}

/** Reverse lookup: the agents that automate a capability, stage or activity. */
export function useAutomatedBy(kind: AutomatesKind, targetId: string | null, enabled = true) {
  return useQuery<ListResponse<AgentSummary>>({
    queryKey: keys.automatedBy(kind, targetId ?? ""),
    queryFn: () => apiGet(`${API}/${KIND_PATH[kind].reverse}/${targetId}/agents`),
    enabled: !!targetId && enabled,
  });
}
