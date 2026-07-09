# Implementation Plan: Recommendation Reasoning Display (ADP-SPEC-028)

## Tech Stack
- **No new packages**: TanStack Query v5 (existing), existing API client pattern
- **Backend**: Extends the `GET /api/v1/reasoning` endpoint from ADP-SPEC-027 (no new endpoints needed)
- **Frontend**: `web/src/recommend/ReasoningPanel.tsx` (new), updates to `OptionCard.tsx`

## Architecture

### API shape (from ADP-SPEC-027, no changes needed)

```
GET /api/v1/reasoning?operation_id={id}&option_id={id}
→ [
    { id, option_id, step_name, model_id, reasoning_text, input_tokens, output_tokens, created_at },
    ...
  ]
```

### New frontend hook `useOptionReasoning`

```typescript
// web/src/api/recommend.ts
export function useOptionReasoning(
  designId: string,
  operationId: string,
  optionId: string,
  enabled: boolean,
)
```

Calls `GET /api/v1/reasoning?operation_id=&option_id=` only when `enabled = true` (lazily — only when the panel is opened).

### New component `ReasoningPanel`

```
web/src/recommend/ReasoningPanel.tsx
  Props: { option: SolutionOption, operationId: string, designId: string }
  State: { expanded: boolean }

  When expanded:
    ├── useOptionReasoning(designId, operationId, option.option_id)
    ├── Section 1: "Generation reasoning" (step_name = "generate")
    │     reasoning_text, model_id chip, created_at
    ├── Section 2: "Trade-off analysis" (step_name = "analyze_tradeoffs")  
    │     reasoning_text (multiline prose)
    └── Section 3: "Knowledge citations"
          option.grounded_on.map(ref → KnowledgeCitationChip(ref.item_id))
```

### `KnowledgeCitationChip` component

Resolves a `item_id` to a title + kind using `useKnowledgeItem(item_id)`. Renders as a coloured badge matching the Knowledge screen style.

### Changes to `OptionCard`

Add `<ReasoningPanel>` below the existing trade-off table and above the Accept/Reject buttons. Pass through `operationId` which the card receives as a new prop from `RecommendationPage`.

## File Changes

| File | Action |
|---|---|
| `web/src/api/recommend.ts` | EDIT — add `useOptionReasoning()`, `ReasoningRecord` interface |
| `web/src/recommend/ReasoningPanel.tsx` | CREATE — collapsible reasoning display |
| `web/src/recommend/KnowledgeCitationChip.tsx` | CREATE — resolves item_id → title chip |
| `web/src/recommend/OptionCard.tsx` | EDIT — add `operationId` prop, render `<ReasoningPanel>` |
| `web/src/recommend/RecommendationPage.tsx` | EDIT — pass `operationId` to `OptionCard` |

## Constitution Compliance

- **ART-VII**: Knowledge citation chips make grounding visible in the UI
- **ART-VIII**: Reasoning is displayed before the Accept/Reject buttons — architects see the evidence before deciding
