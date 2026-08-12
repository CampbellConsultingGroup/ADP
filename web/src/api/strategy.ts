/** TypeScript interfaces and TanStack Query hooks for the Strategic Objective
 * Capture API (ADP-d8u.1). Mirrors web/src/api/business.ts's established
 * apiGet/apiMutation + useQuery/useMutation convention exactly. */

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { apiGet, apiMutation } from "./client";

// ── Types ─────────────────────────────────────────────────────────────────────

export type ObjectiveDirection = "increase" | "decrease" | "reach";
export type ObjectivePeriod = "Q1" | "Q2" | "Q3" | "Q4" | "FY";

export interface StrategicTheme {
  id: string;
  name: string;
  created_at: string;
}

export interface StrategicThemeCreate {
  name: string;
}

export interface StrategicObjective {
  id: string;
  theme_id: string;
  owner: string;
  statement: string;
  metric_name: string | null;
  target_value: number | null;
  target_unit: string | null;
  direction: ObjectiveDirection | null;
  fiscal_year: number;
  period: ObjectivePeriod;
  capability_ids: string[];
  value_stream_ids: string[];
  created_at: string;
  updated_at: string;
}

export interface StrategicObjectiveSummary {
  id: string;
  theme_id: string;
  owner: string;
  statement: string;
  fiscal_year: number;
  period: ObjectivePeriod;
  updated_at: string;
}

export interface StrategicObjectiveCreate {
  theme_id: string;
  owner: string;
  statement: string;
  metric_name?: string | null;
  target_value?: number | null;
  target_unit?: string | null;
  direction?: ObjectiveDirection | null;
  fiscal_year: number;
  period: ObjectivePeriod;
}

export interface StrategicObjectiveUpdate {
  theme_id?: string;
  owner?: string;
  statement?: string;
  metric_name?: string | null;
  target_value?: number | null;
  target_unit?: string | null;
  direction?: ObjectiveDirection | null;
  fiscal_year?: number;
  period?: ObjectivePeriod;
}

// ── Theme hooks ───────────────────────────────────────────────────────────────

export function useThemes() {
  return useQuery<{ items: StrategicTheme[]; total: number }>({
    queryKey: ["strategy-themes"],
    queryFn: () => apiGet("/api/v1/strategy/themes"),
  });
}

export function useCreateTheme() {
  const qc = useQueryClient();
  return useMutation<StrategicTheme, Error & { status?: number }, StrategicThemeCreate>({
    mutationFn: (body) =>
      apiMutation<StrategicTheme, StrategicThemeCreate>("POST", "/api/v1/strategy/themes", body),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ["strategy-themes"] });
    },
  });
}

// ── Objective hooks ─────────────────────────────────────────────────────────────

export function useObjectives() {
  return useQuery<{ items: StrategicObjectiveSummary[]; total: number }>({
    queryKey: ["strategy-objectives"],
    queryFn: () => apiGet("/api/v1/strategy/objectives"),
  });
}

export function useObjective(id: string | null) {
  return useQuery<StrategicObjective>({
    queryKey: ["strategy-objective", id],
    queryFn: () => apiGet(`/api/v1/strategy/objectives/${id}`),
    enabled: !!id,
  });
}

export function useCreateObjective() {
  const qc = useQueryClient();
  return useMutation<StrategicObjective, Error & { status?: number }, StrategicObjectiveCreate>({
    mutationFn: (body) =>
      apiMutation<StrategicObjective, StrategicObjectiveCreate>(
        "POST",
        "/api/v1/strategy/objectives",
        body,
      ),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ["strategy-objectives"] });
    },
  });
}

export function useUpdateObjective(objectiveId: string) {
  const qc = useQueryClient();
  return useMutation<StrategicObjective, Error & { status?: number }, StrategicObjectiveUpdate>({
    mutationFn: (body) =>
      apiMutation<StrategicObjective, StrategicObjectiveUpdate>(
        "PUT",
        `/api/v1/strategy/objectives/${objectiveId}`,
        body,
      ),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ["strategy-objectives"] });
      void qc.invalidateQueries({ queryKey: ["strategy-objective", objectiveId] });
    },
  });
}

export function useDeleteObjective() {
  const qc = useQueryClient();
  return useMutation<void, Error & { status?: number }, string>({
    mutationFn: (objectiveId) =>
      apiMutation<void>("DELETE", `/api/v1/strategy/objectives/${objectiveId}`),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ["strategy-objectives"] });
    },
  });
}

// ── Objective–Capability link hooks ────────────────────────────────────────────

export function useLinkObjectiveCapability(objectiveId: string) {
  const qc = useQueryClient();
  return useMutation<string[], Error & { status?: number }, string>({
    mutationFn: (capabilityId) =>
      apiMutation<string[], { capability_id: string }>(
        "POST",
        `/api/v1/strategy/objectives/${objectiveId}/capabilities`,
        { capability_id: capabilityId },
      ),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ["strategy-objective", objectiveId] });
    },
  });
}

export function useUnlinkObjectiveCapability(objectiveId: string) {
  const qc = useQueryClient();
  return useMutation<void, Error, string>({
    mutationFn: (capabilityId) =>
      apiMutation<void>(
        "DELETE",
        `/api/v1/strategy/objectives/${objectiveId}/capabilities/${capabilityId}`,
      ),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ["strategy-objective", objectiveId] });
    },
  });
}

// ── Objective–Value Stream link hooks ──────────────────────────────────────────

export function useLinkObjectiveValueStream(objectiveId: string) {
  const qc = useQueryClient();
  return useMutation<string[], Error & { status?: number }, string>({
    mutationFn: (valueStreamId) =>
      apiMutation<string[], { value_stream_id: string }>(
        "POST",
        `/api/v1/strategy/objectives/${objectiveId}/value-streams`,
        { value_stream_id: valueStreamId },
      ),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ["strategy-objective", objectiveId] });
    },
  });
}

export function useUnlinkObjectiveValueStream(objectiveId: string) {
  const qc = useQueryClient();
  return useMutation<void, Error, string>({
    mutationFn: (valueStreamId) =>
      apiMutation<void>(
        "DELETE",
        `/api/v1/strategy/objectives/${objectiveId}/value-streams/${valueStreamId}`,
      ),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ["strategy-objective", objectiveId] });
    },
  });
}

// ── Overview dashboard summary (051-strategy-landing-card) ────────────────────

export interface StrategicSummary {
  total_objectives: number;
  total_themes: number;
  linked_count: number;
  unlinked_count: number;
  current_period_count: number;
  upcoming_count: number;
  past_due_count: number;
}

export function useStrategySummary() {
  return useQuery<StrategicSummary>({
    queryKey: ["strategy-summary"],
    queryFn: () => apiGet("/api/v1/strategy/summary"),
    staleTime: 60_000,
  });
}
