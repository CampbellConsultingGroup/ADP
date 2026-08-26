# Research: Admin UI for Editing Scoring Rubric Weights

## D1: Structural mirror of ADP-SPEC-042, not a fresh design

**Decision**: Every mechanism — registry pattern, override/history table pair, single-transaction
write, optimistic-concurrency `version`/409, confirmation-gate on both edit and restore,
`PersonaRole.PLATFORM_ADMIN`-only permission carve-out from the Enterprise Architect wildcard — is
copied from ADP-SPEC-042's already-shipped, already-reviewed shape, confirmed by direct reads of
`adp.admin.{prompt_registry,models,service}` and `src/adp/api/routers/admin_prompts_router.py`
before writing a single line of this spec.

**Rationale**: The bead itself names this precedent explicitly ("mirroring the existing Agent
Prompt Management admin surface, ADP-SPEC-042") — this isn't an inference, it's a literal
instruction. Deviating from an explicitly-named, already-approved pattern without a concrete reason
would be inventing complexity the bead didn't ask for.

## D2: New `adp.admin.rubric_registry`/`rubric_models`/`rubric_service`, not extending the prompt ones

**Decision**: Three new sibling files, not new branches inside `prompt_registry.py`/`models.py`/
`service.py`.

**Rationale**: `AgentRegistration.fallback_provider` returns a `str`; a rubric's fallback returns a
`dict[str, float]` plus needs a per-rubric *validator* the agent-prompt registry has no equivalent
of at all (a prompt has no "is this well-formed" check beyond non-empty). Trying to make one
generic registration type serve both shapes (`str | dict[str, float]` unions everywhere) would
make both simpler cases harder to read for a savings that doesn't materialize — these are two
distinct kinds of "admin-tunable data," not two instances of one kind.

## D3: `compute_business_value_score()` gains an optional parameter, stays pure/no-I/O

**Decision**: `compute_business_value_score(scores, weights: dict[BusinessValueDimension, float] |
None = None)` — when `weights` is omitted, behavior is byte-for-byte identical to today (uses the
module constant `BUSINESS_VALUE_WEIGHTS`). The two existing call sites
(`get_business_value_assessment`, `upsert_business_value_assessment`, both in
`adp.application.store`, both already holding an `AsyncSession`) call a new
`get_effective_weights("business_value")` first (self-contained, no session param -- mirrors
`get_effective_prompt(agent_id)`'s own signature) and pass the result through.

**Rationale**: The function's own docstring already declares this purity as a deliberate
architectural choice shared with `adp.strategy.store.compute_status()` — this feature must extend
it, not compromise it. Mirrors `get_effective_prompt()`'s exact role: the one place that touches
the DB, with every pure-function/call-site boundary elsewhere left untouched. A default parameter
value means every existing unit test in `test_business_value_score.py` continues to pass completely
unmodified (confirmed: none of them pass a `weights` argument today), and any other latent internal
caller (none found by grep) keeps working with zero change.

## D4: Weight storage — JSONB, not a fixed-column-per-dimension table

**Decision**: `rubric_weight_overrides.weights` and `rubric_weight_history.{prior,new}_weights` are
all `JSONB` (`dict[str, float]`), not one column per `BusinessValueDimension`.

**Rationale**: A fixed-column schema would need a migration every time a rubric's dimension set
changes, or a second physical table shape for the next registered rubric (whose dimension count/
names are unknown today) — directly contradicting SC-004 ("adding a second rubric requires zero
schema change"). JSONB is validated at the application layer (the rubric's own validator, not a DB
constraint) — the identical trust model migration 011's `searchable_items.embedding` already uses
for a different reason (pgvector), and the same "validate in Python, not SQL" precedent
`BusinessCapability`'s cycle-detection already established for a rule too complex for a `CHECK`
constraint.

## D5: Validator shape — a per-rubric callback, not a hardcoded business-value-specific check

**Decision**: `RubricRegistration.validate(weights: dict[str, float]) -> None` (raises `ValueError`
with a human-readable message on failure) — called by the service layer before ever writing
anything, for every rubric generically, with the actual rule (exactly 6 keys, sum to `1.0 ±
1e-6`) living inside the `business_value` registration's own validator function, not in
`rubric_service.py` itself.

**Rationale**: Directly required by spec.md's Edge Cases ("must not hardcode 'exactly one rubric
exists'") and SC-004 — a future rubric with a genuinely different validity rule (e.g. weights that
must each be ≥ some floor, or a different dimension count) plugs in without touching
`rubric_service.py` at all, mirroring `AgentRegistration.fallback_provider`'s own
callback-per-registration shape exactly.

## D6: Frontend — a new numeric-per-dimension editor, no existing component test to mirror

**Decision**: `RubricEditor.tsx` is a new component (not a variant of `PromptEditor.tsx`, whose
entire UI is one `<textarea>`) — a numeric input per dimension, a live running-sum indicator, and a
Save button disabled whenever the sum isn't within tolerance of 100. Confirmed by direct `find`
that neither `PromptEditor.tsx` nor `AdminPage.tsx` has any existing `.test.tsx` file today — this
feature's own new component tests (`ScoringRubricsPage.test.tsx`, `RubricEditor.test.tsx`) are the
first frontend test coverage either admin screen has, not a gap this feature is leaving behind.

**Rationale**: The underlying confirmation/history/version-conflict *mechanics* are identical to
`PromptEditor.tsx` (confirmed reusable via the same `useMutation`/409-handling shape in the new
`adminRubrics.ts` client, mirroring `adminPrompts.ts` almost verbatim) — only the actual input
widget differs, since a free-text prompt and a validated numeric weight set need fundamentally
different controls.

## D7: `BUSINESS_VALUE_EVIDENCE_CAP` is explicitly out of scope

**Decision**: Only `BUSINESS_VALUE_WEIGHTS` becomes admin-editable in this pass.

**Rationale**: The bead's own text names "weights" specifically; `BUSINESS_VALUE_EVIDENCE_CAP` is a
different data shape (`dict[int, int | None]`, a score→cap lookup) that would need its own
registration/validator design, not a natural fit for "weights summing to 100%." Bundling it in
would expand scope beyond what was asked without a concrete need driving it now.
