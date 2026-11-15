// 938-capability-model-analysis (ADP-6et.2): hooks for /api/v1/application-capabilities/analysis.
// Everything here is derived on the server on every request and never stored. Cost and risk are
// null when the caller may not read them; the *_available flags say which ("not available to you"
// is not the same as "no data", which is worst: null).

import { useQuery } from "@tanstack/react-query";
import type { AppRef, CapRef, LinkedCapRef } from "./appCapabilities";
import type { LifecycleStatus, TechCapLifecycle } from "./application";
import { apiGet } from "./client";

const BASE = "/api/v1/application-capabilities/analysis";
export const CAP_ANALYSIS_KEY = ["cap-analysis"] as const;

export type RiskBand = "high" | "medium" | "low" | "unknown";
export type LifecycleBand = "past_end_of_life" | "retiring" | "contained" | "current" | "emerging";

export const RISK_BANDS: Exclude<RiskBand, "unknown">[] = ["high", "medium", "low"];
export const LIFECYCLE_BANDS: LifecycleBand[] = ["past_end_of_life", "retiring", "contained", "current", "emerging"];

export const RISK_BAND_LABEL: Record<RiskBand, string> = {
  high: "High",
  medium: "Medium",
  low: "Low",
  unknown: "Unknown",
};

export const LIFECYCLE_BAND_LABEL: Record<LifecycleBand, string> = {
  past_end_of_life: "Past end of life",
  retiring: "Retiring",
  contained: "Contained",
  current: "Current",
  emerging: "Emerging",
};

export interface AppVia {
  id: string;
  name: string;
  via: CapRef[];
}

export interface Spread<W> {
  worst: W | null;
  spread: Record<string, number>;
}

export interface CostRollup {
  /** Decimal string; null when no contributing application has a cost record. */
  total_tco: string | null;
  apps_without_cost: number;
}

export interface CapabilityRollup {
  capability_id: string;
  name: string;
  level: number;
  contributing_apps: AppVia[];
  excluded_retired_apps: AppRef[];
  health: Spread<number>;
  risk: Spread<RiskBand> | null;
  cost: CostRollup | null;
  exposure: Spread<LifecycleBand>;
}

export interface CapabilityRollupResponse {
  as_of: string;
  risk_available: boolean;
  cost_available: boolean;
  items: CapabilityRollup[];
}

export interface ImpactResult {
  technical_capability: LinkedCapRef;
  covered_technical: CapRef[];
  application_capabilities: (LinkedCapRef & { via_technical: CapRef[] })[];
  applications: { id: string; name: string; lifecycle_status: LifecycleStatus; via: CapRef[] }[];
  business_capabilities: (LinkedCapRef & { routes: CapRef[] })[];
}

export interface TechnologyDependency {
  technical: LinkedCapRef;
  lifecycle_status: TechCapLifecycle;
  end_of_life_date: string | null;
  effective_band: LifecycleBand;
  via_app_capability: CapRef;
  via_business_capability: CapRef;
}

export interface CapabilityFindings {
  overlaps: { business: LinkedCapRef; applications: AppVia[] }[];
  gaps: {
    business_without_app_capability: LinkedCapRef[];
    app_capability_without_business: LinkedCapRef[];
    app_capability_without_application: LinkedCapRef[];
  };
  shared: { app_capability: LinkedCapRef; business: CapRef[]; count: number }[];
  shared_threshold: number;
}

/** One fetch for every roll-up metric, so switching heat-map metrics never refetches (FR-019). */
export function useCapabilityRollup(enabled = true) {
  return useQuery<CapabilityRollupResponse>({
    queryKey: [...CAP_ANALYSIS_KEY, "rollup"],
    queryFn: () => apiGet(`${BASE}/business-rollup`),
    enabled,
  });
}

export function useTechCapImpact(tcId: string | null) {
  return useQuery<ImpactResult>({
    queryKey: [...CAP_ANALYSIS_KEY, "impact", tcId],
    queryFn: () => apiGet(`${BASE}/technical-capabilities/${tcId}/impact`),
    enabled: !!tcId,
  });
}

export function useBusinessTechnology(capId: string | null) {
  return useQuery<{ as_of: string; items: TechnologyDependency[] }>({
    queryKey: [...CAP_ANALYSIS_KEY, "technology", capId],
    queryFn: () => apiGet(`${BASE}/business-capabilities/${capId}/technology`),
    enabled: !!capId,
  });
}

export function useCapabilityFindings() {
  return useQuery<CapabilityFindings>({
    queryKey: [...CAP_ANALYSIS_KEY, "findings"],
    queryFn: () => apiGet(`${BASE}/findings`),
  });
}
