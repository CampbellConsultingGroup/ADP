import { useQuery, type UseQueryResult } from "@tanstack/react-query";
import { apiGet } from "./client";

// ── Types ─────────────────────────────────────────────────────────────────────

export interface TechnologyCount {
  technology: string;
  design_count: number;
}

export interface TechnologiesResponse {
  technologies: TechnologyCount[];
  total_unique: number;
}

export interface PortfolioDesignSummary {
  id: string;
  title: string;
  lifecycle_status: string;
  overdue_review: boolean;
  element_count: number;
  primary_technology: string | null;
}

export interface PortfolioDesignsResponse {
  designs: PortfolioDesignSummary[];
  total: number;
  page: number;
  page_size: number;
}

export interface PortfolioSearchResult {
  id: string;
  title: string;
  lifecycle_status: string;
  overdue_review: boolean;
  element_count: number;
  primary_technology: string | null;
  matched_elements: string[];
}

export interface PortfolioSearchResponse {
  designs: PortfolioSearchResult[];
  total: number;
  truncated: boolean;
}

export interface PortfolioSummary {
  total_designs: number;
  by_status: Record<string, number>;
  overdue_review_count: number;
}

// ── Query keys ────────────────────────────────────────────────────────────────

const TECH_KEY = ["portfolio", "technologies"] as const;
const designsKey = (technology?: string, status?: string, page?: number) =>
  ["portfolio", "designs", technology ?? null, status ?? null, page ?? 1] as const;
const searchKey = (q: string) => ["portfolio", "search", q] as const;
const SUMMARY_KEY = ["portfolio", "summary"] as const;

// ── Hooks ─────────────────────────────────────────────────────────────────────

export function usePortfolioTechnologies(): UseQueryResult<TechnologiesResponse> {
  return useQuery<TechnologiesResponse>({
    queryKey: TECH_KEY,
    queryFn: () => apiGet<TechnologiesResponse>("/api/v1/portfolio/technologies"),
    staleTime: 60_000,
  });
}

export function usePortfolioDesigns(
  technology?: string,
  status?: string,
  page = 1,
): UseQueryResult<PortfolioDesignsResponse> {
  const params = new URLSearchParams();
  if (technology) params.set("technology", technology);
  if (status) params.set("status", status);
  params.set("page", String(page));

  return useQuery<PortfolioDesignsResponse>({
    queryKey: designsKey(technology, status, page),
    queryFn: () =>
      apiGet<PortfolioDesignsResponse>(`/api/v1/portfolio/designs?${params.toString()}`),
    staleTime: 30_000,
  });
}

export function usePortfolioSearch(
  q: string,
  enabled: boolean,
): UseQueryResult<PortfolioSearchResponse> {
  return useQuery<PortfolioSearchResponse>({
    queryKey: searchKey(q),
    queryFn: () =>
      apiGet<PortfolioSearchResponse>(`/api/v1/portfolio/search?q=${encodeURIComponent(q)}`),
    enabled: enabled && q.length >= 2,
    staleTime: 30_000,
  });
}

export function usePortfolioSummary(): UseQueryResult<PortfolioSummary> {
  return useQuery<PortfolioSummary>({
    queryKey: SUMMARY_KEY,
    queryFn: () => apiGet<PortfolioSummary>("/api/v1/portfolio/summary"),
    staleTime: 60_000,
  });
}
