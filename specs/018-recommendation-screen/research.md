# Research: Architecture Recommendation Screen

**Branch**: `018-recommendation-screen` | **Date**: 2026-07-02

---

## Decision 1: KnowledgeRetrieval Stub When pgvector Unavailable

**Decision**: Create a `_make_stub_knowledge_retrieval()` function that returns a no-op `KnowledgeRetrieval` instance when pgvector is not configured. The stub's `hybrid_search()` returns `[]`, causing all generated options to be marked `advisory=True`. This mirrors the `_StubLLMClient` pattern from intake (ADP-SPEC-015).

**Rationale**: pgvector is installed but the knowledge base has not been indexed (`adp-reindex` has not been run). Without a stub the orchestrator would throw on `hybrid_search()`. The advisory path is a valid and complete workflow — the user sees options with advisory warnings, which is the correct behaviour for an empty knowledge base.

**Alternatives considered**: Require pgvector/indexing before the feature can be used — rejected because it blocks demo/dev usage unnecessarily.

---

## Decision 2: ART-VIII Confirmation Pattern

**Decision**: `AcceptOptionRequest(confirmation_id: str)` with a Pydantic `@field_validator` that rejects blank strings. Same pattern as `ExportRequest` (ADP-SPEC-011). Any non-empty string is accepted as a valid confirmation in v1.

**Rationale**: Consistent with existing ART-VIII gates. The string value is logged as an audit attribute for attributability.

---

## Decision 3: Audit Entry ID in materialize_option()

**Decision**: `materialize_option()` in `adp.recommendation.orchestrator` currently uses `f"AUD-{len(design.audit_log)+1:03d}"` — the same `len+1` bug fixed in ADP-SPEC-017 for intake. **Must import and use `_next_audit_id()` from `adp.intake.orchestrator`** in this feature.

**Rationale**: Without this fix, accepting a recommendation on a design that already has audit entries will hit the `audit_entries` primary key unique constraint (same bug as rejecting intake proposals).

---

## Decision 4: Navigation — Three-View App State

**Decision**: Extend `App.tsx`'s view state from `"canvas" | "intake"` to `"canvas" | "intake" | "recommend"`. The header in each view shows the three-item nav: "Intake → Recommendations → Canvas". The active view is highlighted.

**Rationale**: Keeps the navigation in one place (App.tsx view state) rather than adding URL routing. Consistent with the existing ADP-SPEC-016 pattern.

---

## Decision 5: Recommendation Store

**Decision**: Module-level `_recommend_store: dict[str, Any] = {}` in `src/adp/api/routers/recommend.py`. Same pattern as `_intake_store` in intake. Operations are transient (TTL 24h, not enforced in v1).

---

## Decision 6: SolutionOptionResponse — Pydantic Serialisation of Dataclass

**Decision**: `SolutionOption` is a Python dataclass (not Pydantic). The API router converts it to `SolutionOptionResponse` (Pydantic model) using explicit field mapping. `TradeOffEntry` and `ProposedElement` are similarly mapped to Pydantic response models.

**Rationale**: The dataclass is the internal representation; the Pydantic model is the API contract. Same approach as `ProposalResponse` for intake proposals.

---

## Decision 7: Frontend — TanStack Query Polling

**Decision**: `useRecommendStatus(designId, operationId)` uses the same `refetchInterval: (data) => data?.status === "completed" || data?.status === "failed" ? false : 2000` pattern as `useIntakeStatus`. Polling stops automatically when the pipeline completes or fails.

---

## New Files Summary

| File | Purpose |
|---|---|
| `src/adp/api/routers/recommend.py` | 3 HTTP routes + operation store |
| `web/src/api/recommend.ts` | TanStack Query hooks + TypeScript interfaces |
| `web/src/recommend/RecommendationPage.tsx` | Top-level page |
| `web/src/recommend/RequirementSelector.tsx` | Checkbox list (P2 — defaults all selected) |
| `web/src/recommend/OptionCard.tsx` | Single option: rank, title, rationale, trade-offs, elements |
| `web/src/recommend/AcceptDialog.tsx` | Confirmation dialog (ART-VIII) with advisory checkbox |

**Modified files**: `src/adp/recommendation/orchestrator.py` (fix audit ID), `src/adp/api/app.py` (register router), `web/src/App.tsx` (add recommend view), `web/src/intake/IntakePage.tsx` (Recommendations nav button), `web/src/canvas/Workspace.tsx` (Recommendations nav button).
