# Tasks: Admin Screen for Managing AI Agent System Prompts

**Feature**: ADP-SPEC-042 (ADP-t32) | **Branch**: `042-admin-prompt-management`
**Spec**: [spec.md](./spec.md) · **Plan**: [plan.md](./plan.md) · **Research**: [research.md](./research.md) · **Data model**: [data-model.md](./data-model.md) · **Contracts**: [contracts/agent-prompts-api.md](./contracts/agent-prompts-api.md)

## Format: `[ID] [P?] [Story] Description`

- **[P]** = parallelizable (distinct file, no dependency on an incomplete task).
- **[US#]** = user-story phase task. Setup / Foundational / Polish carry no story label.
- Tests are **MANDATORY** (ART-IV): each story's contract/unit/integration tests precede its implementation, written to fail first.

## Path Conventions

New backend package `src/adp/admin/{models,service,prompt_registry}.py`; new router `src/adp/api/routers/admin_prompts_router.py`; authz `src/adp/authz/{roles,permissions,enforcement}.py`; auth `src/adp/auth/tokens.py`; migration `src/adp/store/migrations/versions/023_agent_prompt_management.py`; the five existing call sites `src/adp/chat/orchestrator.py`, `src/adp/recommendation/steps.py`, `src/adp/llm/client.py`, `src/adp/business/agent_review.py`; tests `tests/{contract,integration,authz,unit/admin,unit}/`; web `web/src/admin/`, `web/src/api/adminPrompts.ts`, `web/src/auth/AuthProvider.tsx`, `web/src/ui/AppShell.tsx`, `web/tests/{unit,component}/`.

> **Note (discovered during implementation)**: `prompt_registry.py` lives in `adp.admin`, not `adp.agents` as originally planned — `adp.agents` has a mechanically-enforced test (`tests/unit/agents/test_toolkit_boundary.py`, ADP-SPEC-039) forbidding imports from any single domain module, which `prompt_registry.py`'s fallback providers (importing `adp.chat`, `adp.recommendation`, `adp.llm`, `adp.business`) necessarily violate. See plan.md's Structure Decision and research.md Decision 5 for the corrected rationale.

> **File-contention note**: `src/adp/admin/{models,service}.py`, `src/adp/api/routers/admin_prompts_router.py`, `web/src/admin/AdminPage.tsx`, and `tests/contract/test_admin_prompts_contract.py` all grow across US1 → US2 → US3 (new fields/functions/endpoints/cases added, nothing removed) — treat them as sequential across phases even though phases themselves run in priority order anyway. Within a single phase, each story's own test files, web component, and the shared files above touch disjoint enough regions to run in parallel per the `[P]` markers below. The five existing prompt call sites (`orchestrator.py`, `steps.py`, `llm/client.py`, `agent_review.py`) are touched exactly once each, in US1, and never again.

---

## Phase 1: Setup (Shared Infrastructure)

- [x] T001 [P] Create the `adp.admin` package with `__init__.py` in src/adp/admin/__init__.py
- [x] T002 [P] Alembic migration `023` (`down_revision="022"`) adding `agent_prompt_overrides` (agent_id TEXT PK, prompt_text, updated_by, updated_at, version) and `agent_prompt_history` (BIGSERIAL id, agent_id, actor, changed_at, change_type CHECK IN ('edit','restore'), prior_text, new_text, confirmation_id; B-tree index on `(agent_id, changed_at DESC)`) per data-model.md §3–4, in src/adp/store/migrations/versions/023_agent_prompt_management.py — verified up/down against the real dev Postgres before writing the automated test (T004)

## Phase 2: Foundational (Blocking Prerequisites)

**⚠️ CRITICAL**: No user story work can begin until this phase is complete — even User Story 1's read-only view needs a working permission gate, a resolvable `PLATFORM_ADMIN` role, the schema in place, and a real effective-prompt lookup.

- [x] T003 Add `PersonaRole.PLATFORM_ADMIN` and `ActionType.MANAGE_AGENT_PROMPTS` in src/adp/authz/roles.py
- [x] T004 [P] Migration `023` up/down integration test (apply, verify both tables + the history index + the `change_type` CHECK constraint rejects an out-of-set value, downgrade cleanly) using its own dedicated testcontainer, mirroring migration `022`'s precedent (041's T009) rather than the shared session-scoped `db_engine` fixture, in tests/integration/test_migration_023.py — passes against a real containerized Postgres
- [x] T005 [P] Unit test: `PERMISSION_GRANTS[PersonaRole.ENTERPRISE_ARCHITECT]` no longer contains `MANAGE_AGENT_PROMPTS`; `PERMISSION_GRANTS[PersonaRole.PLATFORM_ADMIN]` contains every `ActionType` including it; `MANAGE_AGENT_PROMPTS in REQUIRES_CONFIRMATION`; `PERMISSIONS_VERSION == "1.7.0"` — in tests/authz/test_permissions.py (confirmed failing against pre-change grants, then passing)
- [x] T006 Bump `PERMISSIONS_VERSION` `"1.6.0"` → `"1.7.0"`; narrow `PERMISSION_GRANTS[PersonaRole.ENTERPRISE_ARCHITECT]` from the wildcard `frozenset(ActionType)` to `frozenset(ActionType) - {ActionType.MANAGE_AGENT_PROMPTS}`; add `PERMISSION_GRANTS[PersonaRole.PLATFORM_ADMIN] = frozenset(ActionType)`; add `ActionType.MANAGE_AGENT_PROMPTS` to `REQUIRES_CONFIRMATION` — in src/adp/authz/permissions.py
- [x] T007 [P] Update `test_admin_group_maps_to_enterprise_architect` → `test_admin_group_maps_to_platform_admin` (tests/unit/test_token_validation.py) to assert the `ADPAdministrator` group now resolves to `PersonaRole.PLATFORM_ADMIN`; also added `test_platform_admin_outranks_enterprise_architect` for the dual-group priority case — confirmed both failing first, then passing
- [x] T008 Remap `ADPAdministrator` from `PersonaRole.ENTERPRISE_ARCHITECT` to `PersonaRole.PLATFORM_ADMIN` in `_GROUP_ROLE_PRIORITY`; added `PLATFORM_ADMIN` at the top of `_ROLE_PRIORITY_ORDER` (it now outranks `ENTERPRISE_ARCHITECT`, not just added alongside it) — in src/adp/auth/tokens.py
- [x] T009 [P] Unit test: `groupsToRole(["ADPAdministrator"])` returns `"platform_admin"`, not `"enterprise_architect"` (plus dual-group and default cases) — in web/tests/unit/auth-groups-to-role.test.ts (confirmed failing — `groupsToRole` wasn't even exported yet — then passing)
- [x] T010 Exported `groupsToRole`; remapped `ADPAdministrator` to `"platform_admin"` and reordered `priority` so it's checked before `EnterpriseArchitect` (now a real priority distinction, not a no-op); added `platform_admin` to `ROLE_LABELS`/`ROLE_COLORS` — in web/src/auth/AuthProvider.tsx
- [x] T011 [P] Unit test: `get_effective_prompt(agent_id)` returns `(fallback_provider(), is_override=False, version=0)` when no override row exists, and the override row's `(prompt_text, True, version)` when one does, for all 6 registrations (including `agent_review_business_capability`, whose fallback provider is `_load_system_prompt` itself) — in tests/unit/admin/test_prompt_registry.py (relocated from tests/unit/agents/ alongside the module — see note above) — 10 tests pass against a throwaway SQLite DB (monkeypatched session factory, mirroring tests/unit/chat/test_store.py's convention)
- [x] T012 Implemented `AGENT_REGISTRATIONS` (6 entries — `agent_id`, `display_name`, a zero-arg `fallback_provider: Callable[[], str]` with each import deferred inside the function body to avoid a circular import with the 5 call-site modules; `_load_system_prompt` itself for `agent_review_business_capability`) and `get_effective_prompt(agent_id) -> EffectivePrompt` (self-contained — its own tiny session factory reading `ADP_DATABASE_URL`, no caller-supplied session, so every call site adopts it with a one-line change) — in src/adp/admin/prompt_registry.py (**not** src/adp/agents/ as originally planned — see note above; tests/unit/agents/test_toolkit_boundary.py confirmed this would have violated ADP-SPEC-039's zero-domain-import rule)

**Checkpoint**: Permission model, schema, and the read-path registry lookup are all in place — every user story below builds on them without modifying them.

---

## Phase 3: User Story 1 - See every agent's current system prompt in one place (Priority: P1) 🎯 MVP

**Goal**: An authorized administrator sees every registered agent's real, currently-effective system prompt in one place, with a clear default-vs-override indicator — read-only, zero write risk.
**Independent Test**: Log in as an authorized admin, open the admin screen, and confirm the text shown for each agent exactly matches what that agent actually sends to the LLM.

### Tests for User Story 1 (MANDATORY — ART-IV)

- [x] T013 [P] [US1] Contract test: `GET /api/v1/admin/agent-prompts` returns all 6 registrations with correct `is_override`/`active_text`/`version`; a caller without `MANAGE_AGENT_PROMPTS` gets 403 with no prompt content in the body, in tests/contract/test_admin_prompts_contract.py — confirmed failing (module didn't exist) then passing
- [x] T014 [P] [US1] Unit test: each of the 5 non-Agent-Review call sites (chat orchestrator, recommendation generation, recommendation generation-no-KB, recommendation trade-off, intake extraction) resolves its effective prompt via `prompt_registry.get_effective_prompt()` rather than referencing its module-level constant directly — this is what makes User Story 1's own Independent Test meaningful, in tests/unit/agents/test_call_site_wiring.py — note: written and confirmed passing *after* T020–T023's rewires (done earlier, while diagnosing the toolkit-boundary/circular-import issue), not strictly red-first for this one task

### Implementation for User Story 1

- [x] T015 [US1] `AgentPromptView` response model (`extra="forbid"`) in src/adp/admin/models.py (also added `AgentPromptListResponse`, and the US2/US3 models in the same pass: `PromptEditRequest`/`PromptChangeResult`/`VersionConflictError`/`PromptRestoreRequest`/`PromptHistoryEntry`/`PromptHistoryResponse` — cheap to define together, wired into endpoints per-story below)
- [x] T016 [US1] `list_agents()` — builds one `AgentPromptView` per `AGENT_REGISTRATIONS` entry via `get_effective_prompt()` — in src/adp/admin/service.py (also added this module's own `agent_prompt_overrides`/`agent_prompt_history` Core Table objects + session factory now, used by US2/US3's write functions added later)
- [x] T017 [US1] `GET /api/v1/admin/agent-prompts` endpoint; mounted the router in src/adp/api/app.py — in src/adp/api/routers/admin_prompts_router.py
- [x] T018 [US1] Added `("/api/v1/admin/agent-prompts", ActionType.MANAGE_AGENT_PROMPTS)` to `_PREFIX_ROUTE_ACTIONS` — in src/adp/authz/enforcement.py. **Correction during implementation**: this prefix rule alone does NOT gate GET requests — `enforce_route_permission` exempts all safe methods (GET/HEAD/OPTIONS) before ever calling `required_action_for`, by design (reads are open elsewhere in the app). FR-009 requires the admin screen's reads to be gated too, so `GET /agent-prompts` additionally attaches `dependencies=[Depends(require_action_dep(ActionType.MANAGE_AGENT_PROMPTS))]` directly on the route, mirroring the existing `READ_APPLICATION_{RISK,COST,GOVERNANCE}` precedent in `adp.application.router`. The prefix rule still does its job for the POST confirm/restore endpoints (US2/US3).
- [x] T019 [P] [US1] Extended the route-permission completeness gate — added `test_enterprise_architect_denied_admin_prompts_read`, `test_reviewer_denied_admin_prompts_read`, `test_admin_prompts_route_maps_to_manage_agent_prompts_action`, `test_admin_prompts_action_grant_matrix` (32 tests total, all passing) — in tests/authz/test_enforcement.py
- [x] T020 [US1] Rewired `adp.chat.orchestrator`'s one call site (orchestrator.py:156) to resolve `_SYSTEM_PROMPT` via `prompt_registry.get_effective_prompt("chat_assistant")` instead of the raw module constant — in src/adp/chat/orchestrator.py
- [x] T021 [US1] Rewired `adp.recommendation.steps`'s three call sites (steps.py:319 `GENERATION_SYSTEM_PROMPT`, :321 `GENERATION_SYSTEM_PROMPT_NO_KB`, :460/:513 `TRADEOFF_SYSTEM_PROMPT`) to resolve via `get_effective_prompt("recommendation_generation" | "recommendation_generation_no_kb" | "recommendation_tradeoff")` — the two generation prompts are still `.format(option_count=...)` templates, applied to the *resolved* text; the trade-off lookup is hoisted once above the per-option loop (steps.py:458) rather than repeated per option — in src/adp/recommendation/steps.py
- [x] T022 [US1] Rewired `adp.llm.client`'s two `_EXTRACTION_SYSTEM_PROMPT` usages (client.py:391, :439) to resolve via `get_effective_prompt("intake_extraction")` — in src/adp/llm/client.py
- [x] T023 [US1] Generalized `agent_review`'s two `_load_system_prompt()` call sites (agent_review.py:721, :801) to resolve via `get_effective_prompt("agent_review_business_capability")` (whose fallback provider *is* `_load_system_prompt`) instead of calling it directly — in src/adp/business/agent_review.py
- [x] T024 [P] [US1] Typed API client (`useAgentPrompts`, `useAgentPromptHistory`, `useConfirmPromptEdit`, `useRestorePromptVersion` — all 4 endpoints, TanStack Query hooks mirroring web/src/api/agentReview.ts's convention) in web/src/api/adminPrompts.ts
- [x] T025 [US1] `AdminPage.tsx` — lists all 6 agents with a "Default"/"Custom" badge per FR-002, click to view full text — in web/src/admin/AdminPage.tsx
- [x] T026 [US1] New nav section ("Administration", below "Architecture"), new `AppView = "admin"`, `TITLES` entry, gated on `user?.role === "platform_admin"` — in web/src/ui/AppShell.tsx, web/src/shell/index.ts (AppView union), web/src/App.tsx (route wiring)
- [x] T027 [P] [US1] Component tests: `AdminPage` renders 6 agents with correct Default/Custom labeling (1 custom, 5 default) and shows full text + badge on selection; `AppShell`'s Administration nav group is absent by default (no signed-in user, matching every other component test's convention) and present when `useAuth` is mocked to return a `platform_admin` user (`vi.doMock` + `vi.resetModules`) — in web/tests/component/admin-page.test.tsx — 4/4 pass; full web suite (102 tests) and `tsc --noEmit` both clean

**Checkpoint**: MVP — administrators can see every agent's real, currently-effective prompt in one place; zero write risk.

---

## Phase 4: User Story 2 - Edit an agent's system prompt, explicitly confirm it, and have it take effect without a redeploy (Priority: P2)

**Goal**: An administrator edits a prompt, explicitly confirms (a distinct step, not just "Save"), and the very next AI operation for that agent uses the new text — no code change or deployment.
**Independent Test**: Edit one agent's prompt, explicitly confirm, then trigger that agent's AI operation and confirm the new text was used, without restarting or redeploying.

### Tests for User Story 2 (MANDATORY — ART-IV)

- [x] T028 [P] [US2] Contract test: `POST .../confirm` — 422 empty/whitespace `new_text` (FR-004), 422 missing/blank `confirmation_id` (FR-010), 200 success with incremented `version` and attribution, 403 without `MANAGE_AGENT_PROMPTS`, 409 on `expected_version` mismatch with the response carrying the current `active_text`/`version` (FR-012, nested under FastAPI's standard `detail` key) — in tests/contract/test_admin_prompts_contract.py — confirmed failing (404, route didn't exist) then passing; also added the `GET .../history` endpoint one story early (T041) since the success test needed it to verify the history entry
- [x] T029 [P] [US2] Integration test: confirm an edit to `chat_assistant` via `admin_service.save_prompt` against a **real Postgres container**, then invoke the chat orchestrator's real `run_turn` code path and confirm the new text is used — no restart, no redeploy (FR-005, User Story 2 Scenario 4) — in tests/integration/test_admin_prompts_flow.py. Also includes User Story 3's two-actors-then-restore scenario (both `save_prompt`/`restore_prompt` were already implemented together in T031/T040, see below). **Pre-existing, unrelated finding**: running the full `tests/integration/` suite together surfaces ~9 failures in `test_store.py`/`test_search.py` that pass individually — confirmed reproducible with my new file entirely absent, i.e. pre-existing test-order pollution in this suite, not a regression from this feature. Not fixed (out of scope).

### Implementation for User Story 2

- [x] T030 [US2] `PromptEditRequest` (`new_text`, `expected_version`, `confirmation_id` with a `field_validator` mirroring `SuggestionAcceptRequest` in src/adp/business/models.py:548-567) and `PromptChangeResult` models — in src/adp/admin/models.py (done together with T015)
- [x] T031 [US2] `save_prompt(agent_id, new_text, expected_version, actor, confirmation_id, session)` — one DB transaction: reject empty/whitespace `new_text` (FR-004, ValueError), reject on `version` mismatch (FR-012, `PromptVersionConflict` carrying current text/version), else upsert `agent_prompt_overrides` (create at `version=1` or increment in place) AND insert one `agent_prompt_history` row (`change_type="edit"`) — both writes execute against the caller's not-yet-committed session, so they succeed or fail together (spec.md edge case); commit happens in the router — in src/adp/admin/service.py
- [x] T032 [US2] `POST /api/v1/admin/agent-prompts/{agent_id}/confirm` endpoint — actor via `_get_actor(request)` (mirrors `adp.business.router` exactly, reads `request.state.user`/`X-Actor` header, independent of the `get_current_user` permission dependency); `PromptVersionConflict` → 409 with `current_active_text`/`current_version` nested under FastAPI's standard `detail` key; `UnknownAgentError` → 404 — in src/adp/api/routers/admin_prompts_router.py
- [x] T033 [P] [US2] `PromptEditor.tsx` — edit textarea + confirm dialog, constructing `confirmation_id` as `` `CONFIRM-${agentId}-${isoTimestamp}` `` (mirrors web/src/recommend/AcceptDialog.tsx) — in web/src/admin/PromptEditor.tsx. Also extended `ApiError` (web/src/api/client.ts) with an optional `body?: unknown` field, populated from the response JSON on any non-2xx `apiMutation` call — additive/backward-compatible, needed so the 409 handler can read `current_active_text`/`current_version` without a bespoke fetch call bypassing the shared client.
- [x] T034 [US2] Wired `PromptEditor` into `AdminPage`; on a 409 response, surfaces the current text/version (via a "Load latest version" action) instead of silently discarding the admin's edit (FR-012) — in web/src/admin/AdminPage.tsx
- [x] T035 [US2] Unsaved-edit navigation guard (FR-011) — two layers: a `beforeunload` listener for browser tab close/refresh (in PromptEditor.tsx), and a `window.confirm` gate in `AdminPage.tsx` before switching the selected agent in-app while dirty
- [x] T036 [P] [US2] Component tests: Save is disabled until text is actually edited and re-disabled on whitespace-only text (FR-004); the mutation does NOT fire on clicking Save alone, only after confirming the dialog (FR-010); a 409 response shows the conflict banner with the admin's own edit still visible (not overwritten), and "Load latest version" then swaps in the newer text/version (FR-012) — in web/tests/component/prompt-editor.test.tsx — 4/4 pass; full web suite (106 tests) and `tsc --noEmit` both clean

**Checkpoint**: US1 + US2 — administrators can tune any of the 6 agents live, with no code deploy, safely.

---

## Phase 5: User Story 3 - Review who changed what and revert a bad edit (Priority: P3)

**Goal**: An administrator views an agent's full change history (who/when/before/after) and can restore a prior version, itself a new attributed history entry.
**Independent Test**: Make two successive edits as different admin accounts, confirm history shows both with correct attribution/timestamps, then restore and confirm the prior text becomes active again.

### Tests for User Story 3 (MANDATORY — ART-IV)

- [x] T037 [P] [US3] Contract tests: `GET .../history` returns entries newest-first with correct `change_type`; `POST .../restore/{history_id}` — 422 missing `confirmation_id` (restore is **not** a lower-friction path — Clarification Session 2026-07-24), 200 with a new `change_type="restore"` history row leaving the original edit entries untouched, 404 for an unknown/mismatched `history_id`, 403 without `MANAGE_AGENT_PROMPTS` — in tests/contract/test_admin_prompts_contract.py — confirmed failing (404, route didn't exist) then passing (12/12 total in the file)
- [x] T038 [P] [US3] Integration test: two successive edits by different actors, then restore the first — history shows both edits plus the restore, all three correctly attributed, and the restored text is now active — in tests/integration/test_admin_prompts_flow.py (written together with T029, both against the real Postgres container)

### Implementation for User Story 3

- [x] T039 [US3] `PromptHistoryEntry` response model and `PromptRestoreRequest` (same `expected_version`/`confirmation_id` shape as `PromptEditRequest`) — in src/adp/admin/models.py (done together with T015)
- [x] T040 [US3] `get_history(agent_id, session)` (ordered `changed_at DESC, id DESC`) and `restore_prompt(agent_id, history_id, expected_version, actor, confirmation_id, session)` — looks up the history row first (404 via `HistoryEntryNotFoundError` if missing/mismatched `agent_id`), then same transaction/version-check shape as `save_prompt`, but `new_text` is copied from the chosen history row and `change_type="restore"` — in src/adp/admin/service.py (done together with T031)
- [x] T041 [US3] `GET .../history` (added one story early alongside T028) and `POST .../restore/{history_id}` endpoints — in src/adp/api/routers/admin_prompts_router.py
- [x] T042 [P] [US3] `PromptHistory.tsx` — history list (newest-first) + a restore action per entry with its own confirm dialog (same "changes live AI behavior" copy as `PromptEditor`'s, not a shared component but the same gate shape) — in web/src/admin/PromptHistory.tsx
- [x] T043 [US3] Wired `PromptHistory` into `AdminPage` via an Edit/History tab toggle per selected agent (switching agents resets to the Edit tab) — in web/src/admin/AdminPage.tsx
- [x] T044 [P] [US3] Component tests: history renders newest-first with correct attribution; clicking "Restore this version" does NOT call the API directly, only after "Confirm & Restore" — in web/tests/component/prompt-history.test.tsx — 2/2 pass; full web suite (108 tests) and `tsc --noEmit` both clean

**Checkpoint**: All three user stories independently functional.

---

## Phase 6: Polish & Cross-Cutting Concerns

- [x] T045 [P] Confirmed no `adp-generate` schema drift — `adp-generate --check` exits 0; the new admin models are FastAPI request/response boundary models covered by `app.openapi()`, not the architecture-description schema (mirrors 039's precedent)
- [x] T046 Full backend regression: `pytest tests/ --ignore=tests/integration -q` → **1015 passed**; `pytest tests/integration/test_admin_prompts_flow.py tests/integration/test_migration_023.py -q` → **3 passed** (real Postgres container; the full `tests/integration/` directory has a pre-existing, unrelated test-order pollution issue noted at T029, not run as a whole here for that reason); `ruff check src/` → clean (one unused `dataclass` import in `admin/service.py` found and removed); `mypy src/` → clean. Full web regression: `tsc --noEmit` → clean; `npx vitest run` → **108 passed**; `npm run build` → succeeds (pre-existing >500kB chunk-size warning, unrelated)
- [x] T047 Ran quickstart.md's scenarios against a running dev stack (real local Postgres at head migration `023`, `uvicorn` started with `ADP_AUTH_ENABLED=false`). **Finding surfaced by this run**: unlike every other ADP feature, `ADP_AUTH_ENABLED=false`'s default caller (`UNAUTHENTICATED_USER`, hardcoded `PersonaRole.ENTERPRISE_ARCHITECT`) does NOT get admin access — confirmed via `curl` (Scenario 1's list call correctly 403'd, matching Scenario 6's expectation exactly, just via the default caller rather than an explicit non-admin token) — this is the intended, working FR-009 enforcement, not a bug, but it means Scenarios 1/3/4/5/7 (which need `PLATFORM_ADMIN`) can't be curled directly against the running dev server the way every prior feature's quickstart could. Verified those instead by calling `adp.admin.service`/`adp.admin.prompt_registry` directly against the SAME live dev Postgres the running server uses (exercising the identical code paths the HTTP layer calls, minus the auth middleware): Scenario 1 (6 agents, all `is_override=False`), Scenario 4 (empty text → `ValueError`), Scenario 3 (edit persists; a fresh `get_effective_prompt()` call — simulating "next AI operation" — immediately sees it, no restart), Scenario 5 (stale `expected_version` → `PromptVersionConflict` carrying the real current text/version), Scenario 7 (history shows both edits attributed correctly; restore creates a third, new `change_type="restore"` entry rather than rewriting history) — all passed exactly as specified. Scenario 2 (422 on missing `confirmation_id`) and Scenario 8 (transactional atomicity) are already covered exhaustively by the contract/integration suites (T028, T029) and weren't re-verified live. Scenario 9 (browser walkthrough) requires manual UI interaction and was not performed. Verification rows written to the dev DB during this run were cleaned up afterward; the temporary `uvicorn` instance was stopped.
- [x] T048 [P] Updated CLAUDE.md's Active Technologies (2 entries) and Recent Changes blurb from "plan only — not yet implemented" to "implemented"; updated AGENTS.md's "Project Status" — 042 promoted to "Latest work" (implemented), 041 demoted to "Prior work" (unchanged content, still not implemented)

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Ph1)** → **Foundational (Ph2)** → **User Stories (Ph3–5)** → **Polish (Ph6)**.
- Foundational (T003–T012) blocks **every** story — even US1's read-only view needs the permission gate (T003, T006), the schema (T002, T004), and the registry lookup (T012).
- **Migration chain**: `023` is the only pending migration (`down_revision="022"`, the current head) — no ordering conflict with concurrent work.

### Soft cross-story dependencies (functional, not blocking build)

- US2's `save_prompt()` (T031) and US3's `restore_prompt()` (T040) share the same version-check/transaction shape — US3 extends it, does not duplicate it.
- US3's history view is more useful once at least one US2 edit exists, but is independently testable on its own (an agent with zero history shows an empty list).

### Parallel opportunities

- Within Foundational: T004/T005/T007/T009/T011 are all `[P]` (distinct files); T003/T006/T008/T010/T012 have a strict enum-then-grant, test-then-remap, or test-then-implement ordering.
- Within a story: `[P]` test tasks and `[P]` web tasks run parallel to the sequential service/router work.
- Across stories: `src/adp/admin/{models,service}.py`, `admin_prompts_router.py`, `AdminPage.tsx`, and the shared contract-test file are serialized story-to-story (see File-contention note above); the five existing call sites are touched exactly once, in US1.
- Example (US1): T013 + T014 (tests) ∥ start; T024 (web API client) ∥ T015–T023 (backend); T026 (nav) ∥ T020–T023 (call-site rewires).

## Implementation Strategy

- **MVP = User Story 1** (Phase 3): every agent's real, currently-effective prompt visible in one place, zero write risk. Ship and demo before proceeding.
- **Then by priority, strictly increasing consequence**: US2 (the core value — live, confirmed edits) → US3 (the safety net that makes US2 trustworthy for ongoing use). Each phase is independently shippable; the platform can run on US1+US2 alone for a period if US3 lands slightly later, per spec.md's own prioritization rationale.
- **The permission fix is load-bearing, not incidental**: T006's narrowing of the `ENTERPRISE_ARCHITECT` wildcard grant is what makes Clarification Q1 actually true (see plan.md's Complexity Tracking) — it must land in Foundational, before any story, not be treated as a later hardening pass.

## Summary

- **Total tasks**: 48 across 6 phases.
- **Per story**: US1=15, US2=9, US3=8; Setup=2, Foundational=10, Polish=4.
- **MVP scope**: US1 (T001–T027) — every agent's real, currently-effective prompt visible in one place, end to end.
- **Tests**: mandatory per story (ART-IV) — contract + unit/integration before implementation; Foundational's own permission/registry/mapping tests (T004, T005, T007, T009, T011) also precede their implementations.
