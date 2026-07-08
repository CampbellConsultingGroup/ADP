/** TypeScript interfaces and TanStack Query hooks for the Knowledge Base API (ADP-SPEC-020). */

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { apiGet, apiMutation } from "./client";

export type KnowledgeKind =
  | "principle"
  | "pattern"
  | "standard"
  | "reference_architecture"
  | "prior_solution";

export const KNOWLEDGE_KINDS: { value: KnowledgeKind; label: string }[] = [
  { value: "principle", label: "Principle" },
  { value: "pattern", label: "Pattern" },
  { value: "standard", label: "Standard" },
  { value: "reference_architecture", label: "Reference Architecture" },
  { value: "prior_solution", label: "Prior Solution" },
];

export interface KnowledgeItemSummary {
  id: string;
  version: string;
  kind: KnowledgeKind;
  title: string;
  source_ref: string;
  metadata: Record<string, unknown>;
  indexed_at: string | null;
}

export interface KnowledgeItemDetail extends KnowledgeItemSummary {
  full_text: string;
}

export interface KnowledgeItemCreateRequest {
  id?: string;
  version?: string;
  kind: KnowledgeKind;
  title: string;
  full_text: string;
  source_ref: string;
  metadata?: Record<string, unknown>;
}

export interface KnowledgeItemUpdateRequest {
  kind?: KnowledgeKind;
  title?: string;
  full_text?: string;
  source_ref?: string;
  metadata?: Record<string, unknown>;
}

// ── Hooks ─────────────────────────────────────────────────────────────────────

export function useKnowledgeItems() {
  return useQuery<{ items: KnowledgeItemSummary[]; total: number }>({
    queryKey: ["knowledge-items"],
    queryFn: () => apiGet("/api/v1/knowledge"),
  });
}

export function useKnowledgeItem(id: string | null) {
  return useQuery<KnowledgeItemDetail>({
    queryKey: ["knowledge-item", id],
    queryFn: () => apiGet(`/api/v1/knowledge/${id}`),
    enabled: !!id,
  });
}

export function useCreateKnowledgeItem() {
  const qc = useQueryClient();
  return useMutation<KnowledgeItemSummary, Error, KnowledgeItemCreateRequest>({
    mutationFn: (body) =>
      apiMutation<KnowledgeItemSummary, KnowledgeItemCreateRequest>("POST", "/api/v1/knowledge", body),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ["knowledge-items"] });
    },
  });
}

export function useUpdateKnowledgeItem(itemId: string) {
  const qc = useQueryClient();
  return useMutation<KnowledgeItemSummary, Error, KnowledgeItemUpdateRequest>({
    mutationFn: (body) =>
      apiMutation<KnowledgeItemSummary, KnowledgeItemUpdateRequest>(
        "PUT",
        `/api/v1/knowledge/${itemId}`,
        body,
      ),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ["knowledge-items"] });
      void qc.invalidateQueries({ queryKey: ["knowledge-item", itemId] });
    },
  });
}

export function useDeleteKnowledgeItem() {
  const qc = useQueryClient();
  return useMutation<void, Error, string>({
    mutationFn: (itemId) => apiMutation<void>("DELETE", `/api/v1/knowledge/${itemId}`),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ["knowledge-items"] });
    },
  });
}

export interface CALMImportResult {
  items_created: number;
  items_updated: number;
  items_failed: number;
  errors: string[];
  items: KnowledgeItemSummary[];
}

export function useImportCalmPattern() {
  const qc = useQueryClient();
  return useMutation<CALMImportResult, Error, string>({
    mutationFn: (jsonText: string) => {
      let parsed: unknown;
      try {
        parsed = JSON.parse(jsonText);
      } catch {
        throw new Error("Invalid JSON — please paste a valid CALM pattern document");
      }
      return apiMutation<CALMImportResult, unknown>("POST", "/api/v1/knowledge/import/calm", parsed);
    },
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ["knowledge-items"] });
    },
  });
}
