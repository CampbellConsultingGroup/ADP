import {
  useQuery,
  useMutation,
  useQueryClient,
  type UseQueryResult,
  type UseMutationResult,
} from "@tanstack/react-query";
import { apiGet, apiMutation, ApiError } from "./client";
import type {
  ArchitectureDescription,
  DiagramLayout,
  DrawRelationshipInput,
  Element,
  ElementKind,
  PlaceElementInput,
  Relationship,
  SaveLayoutInput,
} from "../types";
import { notifyConflict } from "../canvas/ConflictNotification";

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

export function usePlaceElement(): UseMutationResult<Element, Error, PlaceElementInput> {
  const qc = useQueryClient();
  return useMutation<Element, Error, PlaceElementInput>({
    mutationFn: async ({ design_id, name, kind, description, satisfies, position }) => {
      const design = qc.getQueryData<ArchitectureDescription>(designKey(design_id));
      if (!design) throw new Error("Design not loaded");

      const newId = `ELM-${String(Date.now()).slice(-6)}`;
      const newElement: Element = { id: newId, name, kind, description, satisfies, provenance: undefined };

      const updated: ArchitectureDescription = {
        ...design,
        elements: [...design.elements, newElement],
      };

      const saved = await apiMutation<ArchitectureDescription, ArchitectureDescription>(
        "PUT",
        `/api/v1/designs/${design_id}`,
        updated,
      );

      // Save layout position separately (ART-II: position is not in the canonical model)
      const activeLevel = kind === "person" || kind === "system"
        ? "context"
        : kind === "container"
        ? "container"
        : "component";

      await apiMutation("PUT", `/api/v1/designs/${design_id}/layout/${activeLevel}`, {
        positions: {
          ...((qc.getQueryData<DiagramLayout>(layoutKey(design_id, activeLevel))?.positions) ?? {}),
          [newId]: position,
        },
      });

      return saved.elements.find((e) => e.name === name && e.kind === kind) ?? newElement;
    },
    onMutate: async ({ design_id, name, kind, description, satisfies }) => {
      await qc.cancelQueries({ queryKey: designKey(design_id) });
      const snapshot = qc.getQueryData<ArchitectureDescription>(designKey(design_id));
      if (snapshot) {
        const optimistic: Element = {
          id: `__optimistic__${Date.now()}`,
          name,
          kind,
          description,
          satisfies,
        };
        qc.setQueryData<ArchitectureDescription>(designKey(design_id), {
          ...snapshot,
          elements: [...snapshot.elements, optimistic],
        });
      }
      return { snapshot };
    },
    onError: (_err, { design_id }, context) => {
      const ctx = context as { snapshot?: ArchitectureDescription } | undefined;
      if (ctx?.snapshot) {
        qc.setQueryData(designKey(design_id), ctx.snapshot);
      }
      if (_err instanceof ApiError && _err.status === 409) {
        notifyConflict(design_id);
      }
    },
    onSettled: (_data, _err, { design_id }) => {
      void qc.invalidateQueries({ queryKey: designKey(design_id) });
    },
  });
}

export function useDrawRelationship(): UseMutationResult<Relationship, Error, DrawRelationshipInput> {
  const qc = useQueryClient();
  return useMutation<Relationship, Error, DrawRelationshipInput>({
    mutationFn: async ({ design_id, source, target, label, technology }) => {
      const design = qc.getQueryData<ArchitectureDescription>(designKey(design_id));
      if (!design) throw new Error("Design not loaded");

      const newId = `REL-${String(Date.now()).slice(-6)}`;
      const newRel: Relationship = { id: newId, source, target, label, technology };

      const updated: ArchitectureDescription = {
        ...design,
        relationships: [...design.relationships, newRel],
      };

      const saved = await apiMutation<ArchitectureDescription, ArchitectureDescription>(
        "PUT",
        `/api/v1/designs/${design_id}`,
        updated,
      );

      return saved.relationships.find((r) => r.source === source && r.target === target) ?? newRel;
    },
    onMutate: async ({ design_id, source, target, label, technology }) => {
      await qc.cancelQueries({ queryKey: designKey(design_id) });
      const snapshot = qc.getQueryData<ArchitectureDescription>(designKey(design_id));
      if (snapshot) {
        const optimistic: Relationship = {
          id: `__optimistic__${Date.now()}`,
          source,
          target,
          label,
          technology,
        };
        qc.setQueryData<ArchitectureDescription>(designKey(design_id), {
          ...snapshot,
          relationships: [...snapshot.relationships, optimistic],
        });
      }
      return { snapshot };
    },
    onError: (_err, { design_id }, context) => {
      const ctx = context as { snapshot?: ArchitectureDescription } | undefined;
      if (ctx?.snapshot) {
        qc.setQueryData(designKey(design_id), ctx.snapshot);
      }
      if (_err instanceof ApiError && _err.status === 409) {
        notifyConflict(design_id);
      }
    },
    onSettled: (_data, _err, { design_id }) => {
      void qc.invalidateQueries({ queryKey: designKey(design_id) });
    },
  });
}

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
