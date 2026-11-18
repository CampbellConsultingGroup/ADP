import { useQuery, type UseQueryResult } from "@tanstack/react-query";
import { apiGet } from "./client";
import { QK } from "./queryKeys";

// ── Types ─────────────────────────────────────────────────────────────────────

export interface PortfolioSummary {
  total_designs: number;
  by_status: Record<string, number>;
  overdue_review_count: number;
}

// 919-insights-dashboard
export interface ApplicationHeatmapEntry {
  id: string;
  name: string;
  health_score: number | null;
  business_criticality: number | null;
  time_classification: string | null;
  // Always null when cost_permitted is false, regardless of whether the application
  // actually has a cost record.
  cost: number | null;
}

export interface ApplicationHeatmapResponse {
  items: ApplicationHeatmapEntry[];
  cost_permitted: boolean;
}

// ADP-8xo: Application Portfolio pivot, business-capability grouping dimension.
export interface ApplicationCapabilityGroupLink {
  app_id: string;
  capability_id: string;
  capability_name: string;
  fit_score: number;
}

export interface ApplicationCapabilityGroupsResponse {
  items: ApplicationCapabilityGroupLink[];
}

// ── Query keys ────────────────────────────────────────────────────────────────

const SUMMARY_KEY = [QK.portfolio, "summary"] as const;
const APPLICATIONS_HEATMAP_KEY = [QK.portfolio, "applications-heatmap"] as const;
const CAPABILITY_GROUPS_KEY = [QK.portfolio, "application-capability-groups"] as const;

// ── Hooks ─────────────────────────────────────────────────────────────────────

/** How many of each thing exist: one small request for the Overview page (ADP-blp.39). */
export interface EstateCounts {
  capabilities: number;
  value_streams: number;
  domains: number;
  technical_capabilities: number;
  knowledge_items: number;
  integrations: number;
}

export function useEstateCounts(): UseQueryResult<EstateCounts> {
  return useQuery<EstateCounts>({
    queryKey: [QK.portfolio, "counts"],
    queryFn: () => apiGet<EstateCounts>("/api/v1/portfolio/counts"),
    staleTime: 60_000,
  });
}

export function usePortfolioSummary(): UseQueryResult<PortfolioSummary> {
  return useQuery<PortfolioSummary>({
    queryKey: SUMMARY_KEY,
    queryFn: () => apiGet<PortfolioSummary>("/api/v1/portfolio/summary"),
    staleTime: 60_000,
  });
}

// 919-insights-dashboard: all dimensions returned in one call so switching the
// heat map's coloring dimension is a client-side recolor, not a re-fetch (SC-002).
export function useApplicationsHeatmap(): UseQueryResult<ApplicationHeatmapResponse> {
  return useQuery<ApplicationHeatmapResponse>({
    queryKey: APPLICATIONS_HEATMAP_KEY,
    queryFn: () => apiGet<ApplicationHeatmapResponse>("/api/v1/portfolio/applications-heatmap"),
    staleTime: 60_000,
  });
}

// ADP-8xo: every app-capability link across the whole registry in one call, so
// switching the Application Portfolio's "Group by" dropdown to Business Capability
// is a client-side regroup, not a re-fetch -- same principle as the heat map above,
// applied to a second, higher-cardinality data source (see groupApplications.ts).
export function useApplicationCapabilityGroups(): UseQueryResult<ApplicationCapabilityGroupsResponse> {
  return useQuery<ApplicationCapabilityGroupsResponse>({
    queryKey: CAPABILITY_GROUPS_KEY,
    queryFn: () =>
      apiGet<ApplicationCapabilityGroupsResponse>(
        "/api/v1/portfolio/application-capability-groups",
      ),
    staleTime: 60_000,
  });
}
