# Research & Decisions: Agent Review Toolkit (ADP-SPEC-039)

Phase 0 output. Each decision records the choice, rationale, and rejected alternatives.

## D1 — Reuse `operations` and `llm_reasoning_log` as-is; no migration

**Decision**: An `AgentReviewOperation` is tracked as a normal row in the existing `operations` table, passing the capability's id as the `design_id` argument to `OperationStore.create()`. A suggestion's reasoning is written as a normal `llm_reasoning_log` row, passing the suggestion's id as the `option_id` argument.

**Rationale**: Read directly from source (`003_operations_table.py`, `004_llm_reasoning_log.py`): `operations.design_id` is `TEXT NOT NULL` with no foreign key to `designs`; `llm_reasoning_log.option_id` is `TEXT NULL` with no foreign key to any recommendation table. Both are, in practice, generic "owning entity id" slots that happen to be named after the first caller that used them. Reusing them exactly as they are means zero migrations, zero new tables, and the review operation is pollable through the identical `GET .../{operation_id}` shape every other AI operation already uses (SC-007).

**Rejected**: Renaming these columns to a generic `entity_id` — a real improvement in the abstract, but an unrelated, unjustified schema change to two heavily-used tables for a spec whose scope is additive. Adding a new `agent_review_operations` table — duplicates `OperationStore`'s TTL/CAS/status machinery for no benefit; the whole point of Option B is reusing what exists.

## D2 — Single-prompt reviewer, not a LangGraph pipeline

**Decision**: The Business Capabilities adapter makes one `LLMClient.chat()` call per review (context in the system/user prompt, a suggestion list back), then runs the shared grounding pass over the result. No LangGraph `StateGraph` is introduced for this feature.

**Rationale**: The recommendation engine's graph (`retrieve → reuse → generate → analyze_tradeoffs → rank → validate_citations`) exists because it produces multiple *ranked* solution options from a large, retrieved knowledge base — each node earns its place. A single-capability review's job is narrower: read a bounded, already-known context (this one capability's direct links) and propose a handful of suggestions. Introducing a graph here would be the abstraction the spec's own philosophy (Option B, not Option A's monolithic engine) warns against — machinery justified by an existing pattern rather than by this feature's actual shape. If a future adapter genuinely needs multi-step retrieval-then-rank behavior, it can adopt LangGraph itself without the shared toolkit forcing that shape on every adapter.

**Rejected**: Reusing the recommendation module's `StateGraph` directly — wrong shape (no ranking, no multi-candidate retrieval); would also pull a business-capability adapter through `adp.recommendation`, violating the "adapter lives beside its domain, not inside another domain's pipeline" structure decision. A fan-out multi-critic pattern (like LLM-as-Judge) — considered for splitting "duplicate detection" from "classification suggestions" into concurrent sub-checks, but rejected for v1 as unnecessary complexity; one prompt covering all five suggestion types, each independently gradeable/groundable after the fact, is simpler and still satisfies every acceptance scenario.

## D3 — Authz: reuse `SUBMIT_AI_OPERATION`, add one new `CONFIRM_AGENT_SUGGESTION`

**Decision**: Triggering a review requires the existing `ActionType.SUBMIT_AI_OPERATION` (already used by both `POST .../intake` and `POST .../recommend`) — not a new action. Accepting or rejecting a suggestion requires one new action, `ActionType.CONFIRM_AGENT_SUGGESTION`, distinct from `WRITE_BUSINESS_ARCH` (the action that actually gates the underlying store write when a suggestion is applied). Both require explicit entries in `enforcement.py`'s `_EXPLICIT_ROUTE_ACTIONS`, since the `/api/v1/business/` prefix rule would otherwise map every mutating route under it to `WRITE_BUSINESS_ARCH` by default (confirmed by reading `enforcement.py`'s `required_action_for()` — explicit entries are checked before prefix rules).

**Rationale**: `SUBMIT_AI_OPERATION` is already the codebase's generic "start any AI pipeline" gate, shared across two domains (design intake and design recommendation) rather than duplicated per domain. Minting a redundant `SUBMIT_AGENT_REVIEW` action would fragment that existing gate for no governance benefit — the spec's requirement (FR-013) is that trigger and confirm are *distinct from each other and from the write action*, which reusing `SUBMIT_AI_OPERATION` still satisfies. `CONFIRM_AGENT_SUGGESTION` is new because there is no existing generic "confirm an AI suggestion" action (`CONFIRM_RECOMMENDATION` is recommendation-specific, and intake's confirm/reject just piggybacks on `WRITE_DESIGN` — the less consistent, older precedent per the spec's own clarification).

**Rejected**: Two brand-new actions (`SUBMIT_AGENT_REVIEW` + `CONFIRM_AGENT_SUGGESTION`) — the literal reading of the spec's Clarifications wording, but a closer look at existing precedent shows one of the two already exists in exactly the needed shape; adding a duplicate would be pure permission-matrix bloat. Folding confirm into `WRITE_BUSINESS_ARCH` directly (intake's older pattern) — rejected because it can't distinguish "may review AI suggestions" from "may edit capabilities manually," which the spec explicitly requires as separate concerns (FR-013, FR-016 — accept must re-check the *manual* write permission too, so the two checks need to be genuinely separable).

## D4 — Grounding mechanics mirror `validate_citations_step` exactly

**Decision**: `adp.agents.grounding` exposes a single function that takes a suggestion's declared citations (entity type + id pairs) and a per-entity-type "does this id currently exist" lookup, and returns which citations resolved and which didn't. A suggestion with any unresolved citation is marked `advisory=True`. Acceptance of an advisory suggestion requires an explicit acknowledgment flag in the accept request body, mirroring `materialize_option`'s `advisory_acknowledged` gate.

**Rationale**: This is a direct, deliberate copy of a mechanism already proven in production (the recommendation engine's anti-hallucination pattern) rather than a new design. Keeping the toolkit's grounding check generic over "entity type + id + lookup function" (rather than hardcoded to capability/domain ids) is what makes it usable by a hypothetical second adapter without modification (SC-005).

**Rejected**: Rejecting/discarding ungrounded suggestions silently — loses information the human reviewer might still find useful (e.g., a duplicate-flag citing a slightly-wrong id might still be pointing at something real worth a look), and removes the audit trail of what the model actually said. Blocking ungrounded suggestions permanently with no override — inconsistent with the existing `advisory_acknowledged` precedent and unnecessarily rigid for a human-in-the-loop feature whose entire safety property is that a human reviews it either way.

## D5 — Context assembly is single-capability-scoped, not tree-recursive

**Decision**: Context assembly for a review reads exactly: the capability's own row, its domain (if any), its direct parent and direct children (one level up/down, not the whole subtree), its linked value-stream stages, its linked applications' non-sensitive APM fields, its linked technical capabilities, and its linked designs. `flag_duplicate` additionally reads the sibling set at the same hierarchy level (needed to compare against). No recursive descent into grandchildren or the full tree.

**Rationale**: Satisfies the spec's "large/deep linked context" edge case directly — a bounded query set keeps the prompt size and cost predictable regardless of how large the overall capability tree grows. Consistent with the "single-capability review" scope decision (spec Clarifications).

**Rejected**: Full-subtree traversal — unbounded cost/prompt size as the tree grows, and out of scope per the spec's explicit v1 boundary (whole-tree review is a stated future extension, not this feature).

## D6 — Sensitive application data excluded by construction, not by permission check

**Decision**: The context-assembly function for linked applications only selects `time_classification`, `r_strategy`, `pace_layer`, `health_score` — it does not query `application_risk`, `application_cost`, or `application_contracts` at all, regardless of what permissions the reviewing user holds.

**Rationale**: Per the spec's clarification, sensitive application data is out of scope for v1's context. Excluding it at the query level (the function simply never selects those columns/tables) is stronger and simpler than including it and then filtering by permission — there's no risk of a future refactor accidentally leaking a sensitive field through the agent's context, because the code path to fetch it doesn't exist in this feature at all.

**Rejected**: Fetching all APM data and filtering by the reviewing user's sensitive-category permissions — technically possible (the permission checks already exist per ADP-SPEC-038) but adds a second, redundant place those checks would need to stay correct, and contradicts the spec's explicit "excluded regardless of permissions" resolution.

## D7 — LLM-call failure surfaces as `failed`, never a silent empty result (clarification 2026-07-19)

**Decision**: `agent_review.py` wraps its `LLMClient.chat()` call in a try/except. On any exception (network error, provider error, malformed/unparseable response), the operation transitions to `failed` via `OperationStore.update(status="failed", payload_patch={"error_description": ...})` — the exact same mechanism intake/recommendation already use for their own failure paths. No automatic retry. The error description is a short, sanitized message (exception type/summary), never raw prompt or response content (ART-VI's no-secrets-in-logs/spans rule extends naturally to this field).

**Rationale**: FR-021 requires this to be distinguishable from the legitimate "no LLM configured" case (which completes with an empty suggestion set, per the stub client). Collapsing the two into the same "empty result" outcome would silently hide real failures — a direct violation of ART-VI ("silent catch-and-continue is prohibited"). Reusing the existing `failed` status contract means no new client-side handling is needed beyond what `useAgentReviewStatus` already does for any operation.

**Rejected**: Automatic retry — no existing AI pipeline in this codebase retries automatically; adding it here would be new, unrequested complexity and could multiply LLM cost on a flaky provider. Silent fallback to an empty suggestion set — indistinguishable from "no LLM configured," which is exactly the ambiguity the clarification closed.

## D8 — Field-scoped stale-check via a generation-time value snapshot (clarification 2026-07-19)

**Decision**: FR-015's accept-time re-verification is implemented by snapshotting the *current value of the field a suggestion would overwrite* at generation time, storing it on the suggestion itself, and comparing it against the field's *current* value immediately before the accept-time write. A mismatch → 409, without writing. The snapshot-and-compare *mechanism* is toolkit-level in concept — reusable by any future adapter with a "suggest a new value for an existing field" suggestion type — but, consistent with adapters composing rather than inheriting a fixed suggestion shape, each adapter realizes it as its own strongly-typed field(s) for whatever it overwrites, not one untyped shared field. For this adapter: `previous_strategic_relevance` / `previous_maturity_level` on `CapabilitySuggestion` (data-model.md). This applies only to suggestion types that overwrite an existing field (`reclassify_strategic_relevance`, `set_maturity_level`); it does not apply to `flag_duplicate` (no write at all) or `propose_new_capability` (creates a new record — there is no pre-existing field to snapshot, so its grounding/staleness concern is about whether the *cited supporting entity* still exists, already covered by the standard grounding re-check). `assign_domain` is scoped to unassigned (`domain_id IS NULL`) capabilities by construction (FR-012), so its snapshot is trivially `None` and the check degenerates to "is `domain_id` still `None`" — no dedicated field needed.

**Rationale**: A field-scoped check needs *something* to compare the current value against — "unchanged since generation" is meaningless without knowing what it was at generation time. Storing the snapshot on the transient suggestion payload (inside `OperationStore`'s JSONB, per D1) avoids any new column or whole-record versioning scheme.

**Rejected**: A whole-record `updated_at` or hash comparison — would flag legitimate unrelated field changes as stale (rejected already, per the spec's field-scoped resolution), and `business_capabilities.updated_at` changes on *any* write including ones this feature makes itself, so it can't cleanly distinguish "someone else changed something" from "my own earlier accept already touched this row." Re-deriving staleness by diffing the audit log — far more complex than a snapshot-and-compare, with no precedent elsewhere in the codebase.

## Open items for `/speckit.tasks`

- Confirm the exact system-prompt wording for the "business architecture expert" persona during task breakdown — a prompt-engineering detail, not a schema/contract decision, and iterable without a spec change.
- No feeder beads to reparent (unlike ADP-SPEC-038) — this is a self-contained feature with one adapter.
