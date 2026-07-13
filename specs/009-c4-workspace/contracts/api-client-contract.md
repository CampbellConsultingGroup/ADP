# Contract: Web API Client

**Module**: `web/src/api/`  
**Consumers**: All canvas components  
**Date**: 2026-07-01

Typed TypeScript wrappers around ADP-SPEC-003 API calls using TanStack Query hooks. All calls include the bearer token from the auth context.

---

## Design Hooks (`web/src/api/designs.ts`)

```typescript
// Fetch current design (includes elements, requirements, relationships)
useDesign(designId: string): UseQueryResult<ArchitectureDescription>

// Fetch layout positions for current level
useLayout(designId: string, level: C4Level): UseQueryResult<DiagramLayout>

// Save updated layout positions
useSaveLayout(): UseMutationResult<void, Error, SaveLayoutInput>

// Place a new element on the canvas
usePlaceElement(): UseMutationResult<Element, Error, PlaceElementInput>

// Update an existing element (name, description, satisfies)
useUpdateElement(): UseMutationResult<Element, Error, UpdateElementInput>

// Draw a relationship between two elements
useDrawRelationship(): UseMutationResult<Relationship, Error, DrawRelationshipInput>

// Delete an element (also removes its relationships)
useDeleteElement(): UseMutationResult<void, Error, string>
```

### Optimistic Update Pattern

All mutation hooks implement optimistic updates:
```typescript
onMutate: async (input) => {
  await queryClient.cancelQueries({ queryKey: ['design', designId] });
  const snapshot = queryClient.getQueryData(['design', designId]);
  queryClient.setQueryData(['design', designId], (old) => applyOptimistic(old, input));
  return { snapshot };
},
onError: (err, input, context) => {
  queryClient.setQueryData(['design', designId], context.snapshot);
  if (err.status === 409) notifyConflict();
},
onSettled: () => {
  queryClient.invalidateQueries({ queryKey: ['design', designId] });
}
```

---

## Theme Hook (`web/src/api/theme.ts`)

```typescript
// Fetch locked C4 theme (cached 1 hour)
useC4Theme(): UseQueryResult<C4Theme>
```

---

## Input Types

```typescript
interface PlaceElementInput {
  design_id: string;
  name: string;
  kind: ElementKind;       // "person" | "system" | "container" | "component"
  description?: string;
  satisfies?: string[];    // requirement ids
  position: { x: number; y: number };
}

interface DrawRelationshipInput {
  design_id: string;
  source: string;          // ElementId
  target: string;          // ElementId
  label?: string;
  technology?: string;
}

interface SaveLayoutInput {
  design_id: string;
  level: C4Level;
  positions: Record<string, { x: number; y: number }>;
}
```

---

## Error Handling

| HTTP Status | Meaning | Canvas Behavior |
|---|---|---|
| 200/201 | Success | Update confirmed; no visual change needed |
| 400/422 | Schema validation failed | Roll back optimistic update; show typed error near affected element |
| 401 | Unauthorized | Redirect to login |
| 403 | Forbidden | Show "permission denied" toast; no rollback needed (optimistic never applied) |
| 409 | Version conflict | Roll back; show conflict notification with "Reload latest version" button |
| 5xx | Server error | Roll back; show generic error; allow retry |
