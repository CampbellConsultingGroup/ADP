import { useQuery, type UseQueryResult } from "@tanstack/react-query";
import { apiGet } from "./client";

// ── Types ─────────────────────────────────────────────────────────────────────

export interface DesignGovernanceRecord {
  design_id: string;
  title: string;
  lifecycle_status: string;
  last_activity: string | null;
  audit_count: number;
  accepted_recommendations: number;
  reasoning_record_count: number;
}

export interface GovernanceStatusResponse {
  designs: DesignGovernanceRecord[];
  total: number;
}

export interface ComplianceException {
  design_id: string;
  title: string;
  finding_id: string;
  finding_summary: string;
  severity: "FAIL" | "ADVISORY";
  source: string | null;
  recorded_at: string;
}

export interface ComplianceExceptionsResponse {
  exceptions: ComplianceException[];
  total: number;
}

export interface AuditActivityEntry {
  id: string;
  design_id: string;
  design_title: string;
  actor: string;
  action: string;
  affected_entity: string;
  summary: string;
  timestamp: string;
  origin: string;
}

export interface ActivityFeedResponse {
  entries: AuditActivityEntry[];
  total: number;
  page: number;
  page_size: number;
  from_date: string;
  to_date: string;
}

// ── Query keys ────────────────────────────────────────────────────────────────

const STATUS_KEY = ["governance", "status"] as const;
const EXCEPTIONS_KEY = ["governance", "exceptions"] as const;
const activityKey = (
  fromDate: string,
  toDate: string,
  action?: string,
  actor?: string,
  page?: number,
) => ["governance", "activity", fromDate, toDate, action ?? null, actor ?? null, page ?? 1] as const;

// ── Hooks ─────────────────────────────────────────────────────────────────────

export function useGovernanceStatus(): UseQueryResult<GovernanceStatusResponse> {
  return useQuery<GovernanceStatusResponse>({
    queryKey: STATUS_KEY,
    queryFn: () => apiGet<GovernanceStatusResponse>("/api/v1/governance/status"),
    staleTime: 60_000,
  });
}

export function useComplianceExceptions(): UseQueryResult<ComplianceExceptionsResponse> {
  return useQuery<ComplianceExceptionsResponse>({
    queryKey: EXCEPTIONS_KEY,
    queryFn: () => apiGet<ComplianceExceptionsResponse>("/api/v1/governance/exceptions"),
    staleTime: 300_000,
  });
}

export function useActivityFeed(
  fromDate: string,
  toDate: string,
  action?: string,
  actor?: string,
  page = 1,
  enabled = true,
): UseQueryResult<ActivityFeedResponse> {
  const params = new URLSearchParams({ from_date: fromDate, to_date: toDate });
  if (action) params.set("action", action);
  if (actor) params.set("actor", actor);
  params.set("page", String(page));

  return useQuery<ActivityFeedResponse>({
    queryKey: activityKey(fromDate, toDate, action, actor, page),
    queryFn: () =>
      apiGet<ActivityFeedResponse>(`/api/v1/governance/activity?${params.toString()}`),
    enabled,
    staleTime: 30_000,
  });
}

export function downloadActivityCSV(
  fromDate: string,
  toDate: string,
  action?: string,
  actor?: string,
): void {
  const params = new URLSearchParams({ from_date: fromDate, to_date: toDate });
  if (action) params.set("action", action);
  if (actor) params.set("actor", actor);

  const url = `/api/v1/governance/activity/export?${params.toString()}`;
  const a = document.createElement("a");
  a.href = url;
  a.download = `adp-audit-${fromDate}-${toDate}.csv`;
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
}
