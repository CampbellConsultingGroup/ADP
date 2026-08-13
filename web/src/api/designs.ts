import {
  useQuery,
  useMutation,
  useQueryClient,
  type UseQueryResult,
  type UseMutationResult,
} from "@tanstack/react-query";
import { apiGet, apiMutation } from "./client";
import type {
  ArchitectureDescription,
  DiagramLayout,
  Element,
  ElementKind,
  Relationship,
  SaveLayoutInput,
} from "../types";

// ── Query keys ──────────────────────────────────────────────────────────────

const designKey = (id: string) => ["design", id] as const;
const layoutKey = (id: string, level: string) => ["layout", id, level] as const;

// ── Queries ──────────────────────────────────────────────────────────────────

export function useDesign(designId: string): UseQueryResult<ArchitectureDescription> {
  return useQuery<ArchitectureDescription>({
    queryKey: designKey(designId),
    queryFn: () => apiGet<ArchitectureDescription>(`/api/v1/designs/${designId}`),
    enabled: !!designId,
  });
}

export function useLayout(
  designId: string,
  level: string,
): UseQueryResult<DiagramLayout> {
  return useQuery<DiagramLayout>({
    queryKey: layoutKey(designId, level),
    queryFn: () => apiGet<DiagramLayout>(`/api/v1/designs/${designId}/layout/${level}`),
    enabled: !!designId,
  });
}

// ── Mutations ─────────────────────────────────────────────────────────────────

export function useSaveLayout(): UseMutationResult<void, Error, SaveLayoutInput> {
  const qc = useQueryClient();
  return useMutation<void, Error, SaveLayoutInput>({
    mutationFn: ({ design_id, level, positions }) =>
      apiMutation("PUT", `/api/v1/designs/${design_id}/layout/${level}`, { positions }),
    onSuccess: (_data, { design_id, level }) => {
      void qc.invalidateQueries({ queryKey: layoutKey(design_id, level) });
    },
  });
}

// ADP-914.13: usePlaceElement/useDrawRelationship removed here -- both called a
// whole-design PUT /api/v1/designs/{id} that was never a registered route (see
// ADP-SPEC-054's contracts/elements-api-contract.md); their only caller, C4Canvas.tsx,
// was deleted in the same change that removed these. useCreateElement/
// useCreateRelationship (ADP-SPEC-054, below) are the real, working replacement.

// ── ADP-SPEC-025: Design list + create ───────────────────────────────────────

export interface DesignSummary {
  id: string;
  title: string;
  description?: string | null;
  element_count: number;
  requirement_count: number;
  created_at: string;
  updated_at: string;
  // ADP-SPEC-030: lifecycle fields (T023)
  lifecycle_status: string;
  proposed_date: string | null;
  current_since: string | null;
  review_due: string | null;
  retirement_date: string | null;
  overdue_review: boolean;
}

export interface DesignListResponse {
  designs: DesignSummary[];
  total: number;
  page: number;
  page_size: number;
}

export interface CreateDesignRequest {
  title: string;
  description?: string;
}

// T024: status filter parameter
export function useDesignList(page: number = 1, status?: string) {
  return useQuery<DesignListResponse>({
    queryKey: ["designs", page, status],
    queryFn: () => {
      const statusParam = status ? `&status=${encodeURIComponent(status)}` : "";
      return apiGet<DesignListResponse>(`/api/v1/designs?page=${page}&page_size=50${statusParam}`);
    },
  });
}

export function useCreateDesign() {
  const qc = useQueryClient();
  return useMutation<ArchitectureDescription, Error, CreateDesignRequest>({
    mutationFn: (body) =>
      apiMutation<ArchitectureDescription, CreateDesignRequest>("POST", "/api/v1/designs", body),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ["designs"] });
    },
  });
}

// ── ADP-SPEC-029: Element Technology Tags ────────────────────────────────────

export interface TagsRequest {
  technology?: string | null;
  vendor?: string | null;
  platform?: string | null;
  version?: string | null;
  owner_team?: string | null;
  tags?: string[];
}

export interface TagsResponse {
  element_id: string;
  design_id: string;
  technology?: string | null;
  vendor?: string | null;
  platform?: string | null;
  version?: string | null;
  owner_team?: string | null;
  tags: string[];
  updated_at: string;
}

export function useUpdateElementTags(designId: string, elementId: string) {
  const qc = useQueryClient();
  return useMutation<TagsResponse, Error, TagsRequest>({
    mutationFn: (body) =>
      apiMutation<TagsResponse, TagsRequest>(
        "PUT",
        `/api/v1/designs/${designId}/elements/${elementId}/tags`,
        body,
      ),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ["design", designId] });
    },
  });
}

// ── ADP-SPEC-030: Design Lifecycle ───────────────────────────────────────────

export interface LifecycleTransitionRequest {
  status: string;
  note?: string;
  proposed_date?: string | null;
  current_since?: string | null;
  review_due?: string | null;
  retirement_date?: string | null;
}

export interface LifecycleResponse {
  design_id: string;
  lifecycle_status: string;
  proposed_date?: string | null;
  current_since?: string | null;
  review_due?: string | null;
  retirement_date?: string | null;
}

// T025: useTransitionLifecycle mutation hook
export function useTransitionLifecycle(designId: string) {
  const qc = useQueryClient();
  return useMutation<LifecycleResponse, Error, LifecycleTransitionRequest>({
    mutationFn: (body) =>
      apiMutation<LifecycleResponse, LifecycleTransitionRequest>(
        "PATCH",
        `/api/v1/designs/${designId}/lifecycle`,
        body,
      ),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ["designs"] });
    },
  });
}

// ── ADP-SPEC-054: Element/Relationship CRUD ──────────────────────────────────
// Granular, per-entity mutations replacing the broken whole-design PUT
// usePlaceElement/useDrawRelationship call (that PUT route has never existed --
// see contracts/elements-api-contract.md). Added alongside, NOT replacing,
// usePlaceElement/useDrawRelationship/useSaveLayout above, which stay exactly as
// they are -- still used by the untouched C4Canvas.tsx.

export interface ElementCreateBody {
  kind: ElementKind;
  name: string;
}

export interface ElementUpdateBody {
  name: string;
}

export interface RelationshipCreateBody {
  source: string;
  target: string;
  label?: string;
}

export function useCreateElement(designId: string): UseMutationResult<Element, Error, ElementCreateBody> {
  const qc = useQueryClient();
  return useMutation<Element, Error, ElementCreateBody>({
    mutationFn: (body) =>
      apiMutation<Element, ElementCreateBody>("POST", `/api/v1/designs/${designId}/elements`, body),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: designKey(designId) });
    },
  });
}

export function useUpdateElement(designId: string): UseMutationResult<Element, Error, { elementId: string; body: ElementUpdateBody }> {
  const qc = useQueryClient();
  return useMutation<Element, Error, { elementId: string; body: ElementUpdateBody }>({
    mutationFn: ({ elementId, body }) =>
      apiMutation<Element, ElementUpdateBody>("PATCH", `/api/v1/designs/${designId}/elements/${elementId}`, body),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: designKey(designId) });
    },
  });
}

export function useDeleteElement(designId: string): UseMutationResult<void, Error, string> {
  const qc = useQueryClient();
  return useMutation<void, Error, string>({
    mutationFn: (elementId) =>
      apiMutation<void>("DELETE", `/api/v1/designs/${designId}/elements/${elementId}`),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: designKey(designId) });
    },
  });
}

export function useCreateRelationship(designId: string): UseMutationResult<Relationship, Error, RelationshipCreateBody> {
  const qc = useQueryClient();
  return useMutation<Relationship, Error, RelationshipCreateBody>({
    mutationFn: (body) =>
      apiMutation<Relationship, RelationshipCreateBody>("POST", `/api/v1/designs/${designId}/relationships`, body),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: designKey(designId) });
    },
  });
}

export function useDeleteRelationship(designId: string): UseMutationResult<void, Error, string> {
  const qc = useQueryClient();
  return useMutation<void, Error, string>({
    mutationFn: (relationshipId) =>
      apiMutation<void>("DELETE", `/api/v1/designs/${designId}/relationships/${relationshipId}`),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: designKey(designId) });
    },
  });
}
