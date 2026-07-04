# Implementation Plan: Recommendation Learning and Knowledge Capture

**Branch**: `019-recommendation-learning` | **Date**: 2026-07-03 | **Spec**: [spec.md](spec.md)

## Summary

Three coordinated changes:

1. **Empty-KB generation fix**: Update `GENERATION_SYSTEM_PROMPT` and `generation_user_prompt` to support a "requirements-only" mode when no knowledge items are retrieved. Update `validate_citations_step` to not mark options advisory solely because KB is empty. Add `knowledge_source` field to `SolutionOption` and `SolutionOptionResponse`.

2. **Knowledge capture on accept/reject**: Add fire-and-forget KB writes in accept/reject handlers. Write `KnowledgeItem` records with zero-vector embeddings (re-indexed by `adp-reindex`). Add `acceptance_reason` (optional) to accept; add `POST .../reject` endpoint with required `rejection_reason`.

3. **UI changes**: Add Reject button + RejectDialog to each OptionCard. Update AcceptDialog to include optional reason field. Show accepted/rejected states visually.

## Technical Context

**Language/Version**: Python 3.12 (backend); TypeScript 5.x (frontend)
**New deps**: None. Uses existing `adp.knowledge.index.KnowledgeIndex` and `adp.knowledge.schema.KnowledgeItem`.
**Changed files**: `adp/recommendation/prompts.py`, `adp/recommendation/steps.py`, `adp/recommendation/models.py`, `adp/api/routers/recommend.py`, `web/src/recommend/OptionCard.tsx`, `web/src/recommend/AcceptDialog.tsx`, `web/src/recommend/RejectDialog.tsx` (new), `web/src/api/recommend.ts`

## Constitution Check

| Gate | Status |
|------|--------|
| QG-03 (ART-III): KnowledgeItem typed artifact | ✅ Written via KnowledgeIndex.upsert_item() with schema-valid KnowledgeItem |
| QG-04 (ART-IV): Tests before implementation | ✅ TDD planned |
| QG-13 (ART-IX): Provenance on decisions | ✅ KB item records actor + reason + option metadata |

## Key Design Decisions

1. **`knowledge_source` field**: `"requirements_only"` when KB was empty; `"knowledge_base"` when KB had entries. Determines UI label and advisory logic.
2. **Zero-vector embedding**: `[0.0] * 1536` placeholder when `sentence-transformers` not installed. `adp-reindex` generates real embeddings later.
3. **Fire-and-forget**: KB writes wrapped in `asyncio.create_task()` or `BackgroundTasks` — failure does not propagate to HTTP response.
4. **Reject endpoint**: Same URL pattern as accept — `POST .../options/{id}/reject` with `{"rejection_reason": "..."}`. No `confirmation_id` needed (rejection is less consequential than acceptance).
5. **advisory logic change**: `validate_citations_step` only marks advisory if `option.knowledge_source == "knowledge_base"` AND citations fail. Options with `knowledge_source == "requirements_only"` are never marked advisory.
