# Tasks: Recommendation Reasoning Display (ADP-SPEC-028)

**Input**: Design documents from `/specs/028-recommendation-reasoning-ui/`
**Prerequisites**: ADP-SPEC-027 complete ✅ (reasoning API endpoint exists)

---

## Phase 1: TypeScript API Hook

- [X] T001 [P] Add `ReasoningRecord` TypeScript interface to `web/src/api/recommend.ts`:
  ```typescript
  export interface ReasoningRecord {
    id: string;
    option_id: string | null;
    step_name: "generate" | "analyze_tradeoffs" | "extract" | string;
    model_id: string;
    reasoning_text: string;
    truncated: boolean;
    input_tokens: number;
    output_tokens: number;
    created_at: string;
  }
  export interface ReasoningResponse { records: ReasoningRecord[]; }
  ```
- [X] T002 [P] Add `useOptionReasoning(operationId: string, optionId: string, enabled: boolean)` TanStack Query hook to `web/src/api/recommend.ts`: GETs `/api/v1/reasoning?operation_id={operationId}&option_id={optionId}` when `enabled=true`; returns `{ records, isLoading, isError }`; `staleTime: Infinity` (reasoning records are immutable, never re-fetch)

---

## Phase 2: KnowledgeCitationChip Component

- [X] T003 Create `web/src/recommend/KnowledgeCitationChip.tsx`: accepts `itemId: string` prop; calls `useKnowledgeItem(itemId)` from `web/src/api/knowledge.ts`; renders a colour-coded badge matching the knowledge screen style showing `kind` + `title`; shows a grey skeleton while loading; shows `itemId` as fallback if fetch fails

---

## Phase 3: ReasoningPanel Component

- [X] T004 Create `web/src/recommend/ReasoningPanel.tsx`:
  - Props: `option: SolutionOption`, `operationId: string`, `designId: string`
  - State: `expanded: boolean = false`
  - When collapsed: single "Show reasoning" button (grey outline); if `records` not yet fetched, button is enabled; if fetch returned empty array, render disabled "No reasoning recorded" state
  - When expanded: button text changes to "Hide reasoning"; panel shows 3 sections:
    1. **Generation reasoning** — find record where `step_name === "generate"` → display `reasoning_text` as pre-wrap text; show `model_id` chip + `created_at` relative timestamp
    2. **Trade-off analysis** — find record where `step_name === "analyze_tradeoffs"` → display `reasoning_text` as pre-wrap text; if `truncated === true` show `"[Truncated at 100,000 characters]"` notice
    3. **Knowledge citations** — if `option.knowledge_source === "requirements_only"` show info notice; otherwise render `option.grounded_on.map(ref => <KnowledgeCitationChip key={ref.item_id} itemId={ref.item_id} />)`
  - While loading (first expand): grey skeleton rows matching the section heights
  - `useOptionReasoning` called with `enabled = expanded` (lazy — only fetch when opened)

---

## Phase 4: Wire into OptionCard and RecommendationPage

- [X] T005 Edit `web/src/recommend/OptionCard.tsx`:
  - Add `operationId: string` to `OptionCardProps`
  - Add `<ReasoningPanel option={option} operationId={operationId} designId={designId} />` between the trade-off table and the Accept/Reject action buttons
  - Import `ReasoningPanel` from `./ReasoningPanel`

- [X] T006 Edit `web/src/recommend/RecommendationPage.tsx`:
  - `operationId` is already available in the page component state; pass it to each `<OptionCard>` as `operationId={operationId ?? ""}`

---

## Phase 5: Polish

- [X] T007 [P] Run `cd web && npx tsc --noEmit` — zero TypeScript errors
- [X] T008 [P] Run `pytest tests/ --ignore=tests/integration -q --no-cov` — all tests pass (no backend changes in this spec)
- [X] T009 [P] Manual end-to-end: start server with DB; navigate to Recommendations; trigger a recommendation pipeline; after completion click "Show reasoning" on an option; verify 3 sections appear with non-empty text; verify knowledge citations resolve to readable titles
- [X] T010 [P] Test edge case: for an old recommendation operation that has no reasoning records, verify "No reasoning recorded" state renders correctly without errors

---

## Notes

- `staleTime: Infinity` on the reasoning query is correct because `llm_reasoning_log` is immutable — records will never change after being written
- The `enabled: boolean` param on `useOptionReasoning` implements lazy loading — reasoning is not fetched until the user actually clicks "Show reasoning", avoiding 10× extra API calls when the page loads
- `operationId` needs to be threaded from `RecommendationPage` → `OptionCard` → `ReasoningPanel`; this is a one-line prop addition at each level
- If `option.grounded_on` is empty AND `option.knowledge_source !== "requirements_only"`, the citations section shows "No knowledge citations for this option" (advisory case)
- The reasoning panel does NOT need to be tested with contract tests since it has no new backend changes — the backend is covered by ADP-SPEC-027's contract tests; the frontend can be verified manually
