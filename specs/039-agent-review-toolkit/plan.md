# Implementation Plan: Agent Review Toolkit (with Business Capabilities Adapter)

**Branch**: `039-agent-review-toolkit` | **Date**: 2026-07-19 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `/specs/039-agent-review-toolkit/spec.md`

## Summary

Generalize the shape every existing AI pipeline (intake, recommendation, validation) already shares — submit → `OperationStore`-tracked job → structured suggestions → human accepts/rejects individually → acceptance writes through existing store CRUD with an `origin="ai"` audit entry — into a small shared toolkit (`adp.agents`), then build exactly one concrete adapter on it: a "business architecture expert" review of a single Business Capability. The primary requirement is FR-002 (grounding/citation validation) and FR-014 (no parallel write path): every suggestion that cites an entity is independently re-verified against the database, and acceptance always calls the same functions the manual edit UI already calls. No new database tables; the toolkit reuses `OperationStore` and `llm_reasoning_log` as-is (both already have untyped `Text`/nullable id columns with no FK constraints — confirmed by inspection, not assumed). Two authz actions gate the flow: the existing shared `SUBMIT_AI_OPERATION` (reused, not duplicated) for triggering, and one new `CONFIRM_AGENT_SUGGESTION` for accept/reject — separate from `WRITE_BUSINESS_ARCH`, the action actually performing the write.

## Technical Context

**Language/Version**: Python 3.12 (backend), TypeScript 5.x + React 18 (frontend)
**Primary Dependencies**: FastAPI ≥ 0.111, SQLAlchemy 2 async (Core), asyncpg, Pydantic v2, TanStack Query v5 — all existing stack; no LangGraph (a single-prompt reviewer, not a multi-node graph — see Research D2)
**Storage**: PostgreSQL 16 — no new tables or columns. Reuses `operations` (its `design_id TEXT` column, unconstrained by FK, holds the capability id instead) and `llm_reasoning_log` (its `option_id TEXT NULL` column holds the suggestion id) exactly as they exist today.
**Testing**: pytest (contract + unit, no DB via SQLite/mocks — mirrors `tests/contract/test_intake_api.py`'s mocked-`DesignStore` + real-SQLite-for-business-tables pattern), Vitest (web component tests mirroring `intake-form.test.tsx`/`capability-gap-panel.test.tsx`)
**Target Platform**: Linux server (API) + browser (web canvas)
**Project Type**: Web application (existing `src/adp` backend + `web/` frontend)
**Performance Goals**: context assembly for one capability is a handful of scoped queries (the capability's own row + direct joins), not a tree traversal — bounded prompt size, no N+1 across the estate
**Constraints**: zero hallucinated entity ids ever presented as fully actionable (FR-002); zero suggestions written without an explicit human accept (ART-VIII); zero new write path (ART-II); toolkit modules import nothing from `adp.business` (SC-005)
**Scale/Scope**: one toolkit package (`adp.agents`) + one adapter (business capability review); 4 user stories; 0 new tables; ~1 new authz action

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

- **ART-II (Model is source of truth)**: ✅ acceptance calls existing `business.store` functions (`update_capability`, capability-domain assignment, `create_capability`); no shadow write path (FR-014).
- **ART-III / ART-XIII (Machine-readable / Typed contracts)**: ✅ all new Pydantic v2 models (`extra="forbid"`); suggestion types are a tagged union; new models emit to JSON Schema via `adp-generate`.
- **ART-IV (TDD)**: ✅ contract tests for the toolkit's grounding validator and the capability adapter's endpoints precede handlers.
- **ART-V (Security by Design)**: ✅ threat model in spec; two-permission separation (trigger vs. confirm) distinct from the write action; sensitive application fields excluded from context by construction (FR-009), not by a permission check that could be bypassed.
- **ART-VI (Observability)**: ✅ the review operation emits a span with the same attribute categories (step name, entity id, operation id, tokens, cost, latency) as intake/recommendation steps.
- **ART-VII (Grounded AI Only)**: ✅ the toolkit's grounding validator re-verifies every cited entity id against the database before a suggestion is fully actionable (FR-002); unverifiable → advisory, requires explicit override to accept (mirrors `validate_citations_step`/`advisory_acknowledged`).
- **ART-VIII (Human-in-the-Loop)**: ✅ every suggestion is accepted/rejected individually; nothing auto-applies (FR-014, FR-017).
- **ART-IX (Provenance/Audit)**: ✅ acceptance writes an `AuditEntry` (`origin="ai"`) via a shared toolkit helper, plus a `llm_reasoning_log` row carrying the suggestion's rationale.
- **ART-XI (Traceability)**: ✅ the audit entry and reasoning-log row both carry the operation id (and suggestion id, via the reasoning log's `option_id` column) so an accepted change traces back to what produced it.

**Result**: PASS — no violations; Complexity Tracking not required.

## Project Structure

### Documentation (this feature)

```text
specs/039-agent-review-toolkit/
├── plan.md              # This file
├── research.md          # Phase 0 — decisions (OperationStore/reasoning-log reuse, authz, single-prompt vs LangGraph, taxonomy)
├── data-model.md        # Phase 1 — Pydantic models + authz additions (no DDL — no schema change)
├── checklists/
│   └── requirements.md  # Spec quality checklist (clarifications resolved)
└── tasks.md             # Phase 2 output (/speckit.tasks — not created here)
```

### Source Code Changes

```text
src/adp/agents/                        # NEW shared toolkit package
├── __init__.py
├── llm_stub.py       # NEW — single shared no-API-key stub client, replacing the
│                     #   ad hoc _StubLLMClient duplicated in intake.py/recommend.py
├── grounding.py       # NEW — verify_references(): given cited ids + an "id exists" lookup
│                     #   per entity type, returns which resolved/failed (ART-VII)
├── provenance.py      # NEW — write_suggestion_audit() (AuditEntry, origin="ai") +
│                     #   write_suggestion_reasoning() (llm_reasoning_log row), shared
│                     #   by every adapter's accept path
└── models.py          # NEW — AgentReviewOperation / AgentSuggestionBase shapes shared
                        #   across adapters (adapters extend/parameterize, not duplicate)

src/adp/business/
├── agent_review.py    # NEW — the Business Capabilities adapter: context assembly
│                       #   (capability + domain + parent/children + stages + app links
│                       #   [non-sensitive fields only] + tech-cap links + design links),
│                       #   the "business architecture expert" prompt, the 5-suggestion
│                       #   taxonomy, and accept-path dispatch to existing store functions
├── models.py           # + AgentSuggestion (tagged union of the 5 types), request/response
│                        #   models for trigger/poll/accept/reject
└── router.py            # + POST/GET/POST/POST under /capabilities/{cap_id}/agent-review

src/adp/authz/
├── roles.py           # + ActionType.CONFIRM_AGENT_SUGGESTION
└── permissions.py     # grant to solution/technical/enterprise architect; PERMISSIONS_VERSION bump

src/adp/authz/enforcement.py           # + explicit route entries: agent-review trigger →
                                        #   SUBMIT_AI_OPERATION (reused), accept/reject →
                                        #   CONFIRM_AGENT_SUGGESTION (both override the
                                        #   /api/v1/business/ prefix's WRITE_BUSINESS_ARCH default)

generated/                             # regenerated JSON Schema (adp-generate)

web/src/agent-review/                  # NEW reusable frontend package
├── AgentReviewButton.tsx  # generic trigger button, parameterized by base URL
├── SuggestionCard.tsx     # generic accept/reject card (mirrors ProposalCard/OptionCard)
└── (adapter wiring lives in web/src/business, not here)

web/src/api/agentReview.ts              # NEW — generic typed hooks (useSubmitAgentReview,
                                         #   useAgentReviewStatus poll, useAcceptSuggestion,
                                         #   useRejectSuggestion), parameterized by base path

web/src/business/CapabilityNode.tsx     # + per-node "Review with AI" affordance wiring
                                         #   AgentReviewButton/SuggestionCard against the
                                         #   capability's agent-review endpoints

tests/
├── unit/agents/          # grounding validator, llm_stub fallback behavior
├── unit/business/        # context-assembly shape, suggestion taxonomy validation
├── contract/             # per-endpoint contract tests (authz, grounding, accept/reject, audit)
└── (no integration/ changes — no schema, so no migration up/down test)
```

**Structure Decision**: New top-level `src/adp/agents/` package holds only the domain-agnostic toolkit (confirmed empty of `adp.business` imports per SC-005); the concrete adapter lives inside the existing `src/adp/business` package (`agent_review.py`, alongside its existing `models.py`/`store.py`/`router.py`), following the same models/store/router split every other domain module already uses. Frontend mirrors this split: `web/src/agent-review/` is generic, wired into `web/src/business` for this adapter.

## Phase 0 — Research & Decisions

Captured in [research.md](./research.md). Key decisions:

1. **No schema change needed.** `operations.design_id` and `llm_reasoning_log.option_id` are both plain, FK-unconstrained `Text`/nullable columns (verified by reading `003_operations_table.py` and `004_llm_reasoning_log.py`) — they can hold a capability id / suggestion id respectively with no migration.
2. **Single-prompt reviewer, not a LangGraph pipeline.** The recommendation engine's multi-node graph (retrieve → reuse → generate → analyze_tradeoffs → rank → validate_citations) fits a *ranked, multi-option* output; a single-capability review producing a handful of suggestions doesn't need graph orchestration — one `chat()` call plus the shared grounding pass is enough, keeping the toolkit's surface area small.
3. **Authz**: reuse the existing shared `SUBMIT_AI_OPERATION` (already used by both intake and recommend triggers) rather than minting a redundant per-domain submit action; add exactly one new action, `CONFIRM_AGENT_SUGGESTION`, for accept/reject — both require explicit entries in `enforcement.py`'s `_EXPLICIT_ROUTE_ACTIONS` to override the `/api/v1/business/` prefix's `WRITE_BUSINESS_ARCH` default.
4. **Grounding mechanics**: mirrors `adp.recommendation.steps.validate_citations_step` exactly — cited ids are looked up against the real store (capability/domain/application/etc. `get_*` functions already used elsewhere), not trusted from the LLM response.

## Implementation Phases

> Toolkit first (unblocks every story), then one phase per user story in priority order — each independently shippable and demonstrable.

### Phase 1 — Setup: shared toolkit
`adp.agents` package (`llm_stub.py`, `grounding.py`, `provenance.py`, `models.py`); `ActionType.CONFIRM_AGENT_SUGGESTION` + `PERMISSIONS_VERSION` bump; `web/src/agent-review/` generic components + `agentReview.ts` hooks. No adapter wired yet — covered by toolkit-level unit tests only.

### Phase 2 — US1 (P1): Flag possible duplicates
`agent_review.py` context assembly + prompt + `flag_duplicate` suggestion type; `POST/GET .../agent-review` endpoints; accept path is a no-op acknowledgment (no write); web wiring on `CapabilityNode`. **Ships the full pipeline end to end with zero write risk.**

### Phase 3 — US2 (P2): Strategic relevance / maturity suggestions
`reclassify_strategic_relevance` + `set_maturity_level` suggestion types; accept path calls existing `update_capability`; first exercise of the audit + reasoning-log write via `provenance.py`.

### Phase 4 — US3 (P3): Domain assignment suggestions
`assign_domain` suggestion type (L1-only, per FR-012); accept path calls the existing domain-assignment function; first cross-entity grounding check (domain id, not the capability's own id).

### Phase 5 — US4 (P4): Propose a new capability
`propose_new_capability` suggestion type, grounded on supporting context (an uncovered value-stream stage, or an ADP-zg3.4 gap-analysis finding) rather than an existing capability id; accept path calls existing `create_capability` with provenance back to the suggestion.

### Phase 6 — Polish
`adp-generate` regen + drift gate; SC-005 import-boundary check (toolkit has zero `adp.business` imports) as an automated test, not just a code-review convention; full contract/unit regression.

## Post-Design Constitution Re-Check

Re-evaluate after data-model.md: confirm (a) the toolkit package genuinely has no `adp.business` import (SC-005), (b) every suggestion type's citations are grounded before display, (c) every accept path calls a pre-existing store function (grep-verifiable — no new INSERT/UPDATE statements outside the toolkit/adapter's use of existing functions), (d) new models appear in `generated/` after `adp-generate`. No anticipated violations.
