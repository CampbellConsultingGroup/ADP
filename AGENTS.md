# Agent Instructions

## Project Status

Latest work: **917-objective-design-traceability** (ADP-d8u.2, implemented — both user stories) — closes the top-priority open-frontier traceability gap: objectives previously linked only to capabilities/value streams; adds forward links to designs (`objective_design_links`) and applications (`objective_application_links`), both directions surfaced. Six ground-truth corrections against the source doc found before writing the spec: every id in this schema is a plain string, not UUID; the reverse design-lookup endpoint belongs in the already-existing `designs.py` router, not a nonexistent `adp.store` router; the applications router prefix is plural; no new package/submodule needed (extends `adp.strategy`'s existing three files directly — "more of the same" shape, not a new concept); design/application existence checks reuse `adp.business.store`'s own lightweight-mirror-table pattern, and since those mirrors sit in the same physical database, no second cross-package session was even needed — a self-caught simplification over the original plan. `web/src/designs/` has no single-design detail screen at all — resolved via a real clarification to place the reverse "Objectives realizing this design" panel inside `C4DesignView.tsx` (the only design-scoped screen that exists) as an explicit placeholder. 1355 backend tests (+28), 279 frontend tests (+14), `ruff`/`mypy`/`tsc`/`adp-generate --check` clean, plus a full live Playwright walkthrough (linking a design and application from the objective side, confirming both reverse panels, and a direct DB check confirming zero orphaned links after deleting the objective). See `specs/917-objective-design-traceability/`.

Prior work: **916-strategy-initiatives-dependencies** (ADP-d8u.6, implemented — both user stories) — adds a strategy *execution* layer on `adp.strategy`: `StrategyInitiative` records (a program of work, free-enum status) linked many-to-many to objectives (both directions queryable), plus a self-referential `strategic_objective_dependencies` table (`depends_on`/`blocks`, both directions surfaced, cycles rejected). New submodule `src/adp/strategy/initiatives.py` — placement resolved by direct `wc -l` measurement (1,434 lines, well under the ~2,847-line split threshold) rather than guessing, sharing `store.py`'s existing `_metadata` object (a self-caught fix before any test ran). Cycle prevention is a pure, no-I/O `_reaches()` BFS over a plain dict plus a thin async wrapper — a self-caught design improvement mirroring `915`'s `compute_status()` precedent, split before any implementation code existed against the original single-function plan. A third self-caught fix, found only during the live walkthrough: the dependency panel initially read the generic `err.message` instead of unwrapping `ApiError.body.detail` for the real cycle-rejection text — fixed, verified live that the actual server message now renders. 1327 backend tests (+45), 265 frontend tests (+9), `ruff`/`mypy`/`tsc`/`adp-generate --check` clean, plus a full live Playwright walkthrough (initiative CRUD, linking from both sides, recording a dependency, and triggering + correctly rendering a direct-cycle rejection). See `specs/916-strategy-initiatives-dependencies/`.

Prior work: **915-objective-progress-tracking** (ADP-d8u.5, implemented — all three user stories) — extends `adp.strategy` (ADP-d8u.1) with a dated, editable progress history per objective (`strategic_objective_progress`, new table), a status field computed on every read from that history against the objective's target/direction (`proposed`/`active`/`at_risk`/`achieved`, plus a manually-set terminal `abandoned` with a required reason — ART-II: never persisted for its three derived values), and completes the *already-existing* `strategic_themes` entity's lifecycle (description/owner/priority, single-item `GET`/`PATCH`/`DELETE`). **A significant ground-truth correction made before writing the spec**: the source bead/doc described themes as "a free-text tag column" needing promotion to a first-class table — a direct code read confirmed this was already done; the actual net-new theme work was extension, not creation. **Two further corrections surfaced during planning**: no `users` table exists anywhere (`owner`/`recorded_by` are plain `TEXT`, matching `AuditEntry.actor`), and there's no audit mechanism this domain can write a real `AuditEntry` row to (`audit_entries` is tightly coupled to `design_id`) — ART-IX here is satisfied by structured `logger.info(...)` lines instead, `adp.strategy`'s first. One clarification resolved mid-spec: the source doc left same-day correction UX open (stated default was reject-only); added `PATCH .../progress/{as_of_date}` editing in place — verified live that the form auto-detects an existing entry and switches to "Save Correction". 1282 backend tests (+51), 256 frontend tests (+7), `ruff`/`mypy`/`tsc`/`adp-generate --check` clean, plus a full live Playwright walkthrough (theme edit, all four derived status states via real progress entries, the native `prompt()`-driven abandon flow). See `specs/915-objective-progress-tracking/`.

Prior work: **ADP-914.16** (repair stale locators in `tests/e2e/flows.spec.ts`, implemented) — test-only fix. Three distinct drifts fixed, each confirmed live: `exact: true` on substring-ambiguous "Portfolio" locators, stale `"+ New Design"`/`"+ Add Item"` button text, and a genuinely deeper issue — confirmed live that Governance (not Portfolio) is the nav item that highlights when reached via Portfolio's own button, since Governance was promoted to its own top-level nav item at some point. 14/14 `fullstack` tests passing (was 8/13), `tsc` clean.

Prior work: **ADP-914.15** (dead-code cleanup, implemented) — re-verifying the bead's own claim at pickup time turned up more than expected: the **entire `web/src/theme/` directory**, not just `getElementStyle`/`C4ElementStyle`, had zero real consumers. Deleted it plus its test; kept the unrelated, still-alive `C4Theme` type (used by `api/theme.ts`'s `useC4Theme()`). 244 frontend tests (−5), `tsc` clean.

Prior work: **ADP-914.14** (canvas-v2 browser E2E coverage, implemented) — new `web/tests/e2e/canvas-v2.spec.ts` + a `playwright.config.ts` "canvas-v2" project, covering level toggle/add-element/select-and-inspect against a real backend, closing the gap ADP-914.13 left. Found and fixed a genuine pre-existing bug in `flows.spec.ts` along the way; filed `ADP-914.16` for further, deliberately-not-chased staleness there. 249 frontend tests unchanged, `tsc` clean.

Prior work: **054-c4-design-view** (ADP-914.12, implemented — all four user stories) — Phase B of the roadmap: a new editing surface for the canonical `ArchitectureDescription`/`Element`/`Relationship` model built on the diagram tool's reused `Canvas.tsx`/`DslPanel.tsx`. New backend `src/adp/api/routers/elements.py`, 5 granular endpoints — the actual fix for ADP-914.1–.4. 1231 backend tests (+41), 257 frontend tests (+29). See `specs/054-c4-design-view/`.

Prior work: **053-c4-diagram-type** (ADP-914.11, implemented — all three user stories) — Phase A of the C4Canvas-retirement roadmap decided on ADP-914.9: exposes `"c4"` as a sixth selectable `DiagramType` in the standalone diagram tool (`web/src/diagrams/`). The Mermaid-C4 parser/serializer (`core/dsl/c4.ts`) and its `dslFamilies` registry entry were already fully vendored and correct — just unreachable, since no `DiagramType` value routed to them (the already-exposed `"architecture"` type is a false friend: Mermaid's unrelated `architecture-beta` cloud/service notation). Genuinely additive with zero coupling to ADP's canonical `Design`/`Element`/`Relationship` model (confirmed during ADP-914.9's research) — does not touch `web/src/canvas/` at all. One real implementation wrinkle: `c4` is the only multi-level family, so a brand-new diagram must seed `diagramTypeId: "c4-context"` (matching `c4.ts`'s own `LEVEL_TO_HEADER`), not the bare `"c4"` selector value. A genuine, previously-undiscovered test-coverage gap was closed in the same pass: `c4.ts` had zero test coverage anywhere in the repo despite `families.test.ts` covering all five other families — new `core/dsl/c4.test.ts` fills it. Six existing tests that asserted `"c4"` was *rejected* on purpose were updated to assert the opposite, not silently left alone. **A genuine, pre-existing bug (not introduced by this feature) was found and fixed while writing the reopen test**: `DiagramEditorPage.tsx`'s load effect applied a freshly-fetched diagram's DSL text through a *stale* `applyDsl` closure still bound to the component's initial-default type, not the diagram's actual saved type — silently mis-parsing any reopened diagram whose type differed from that default. Undetected until now because every prior test fixture happened to use `"flowchart"` as both the diagram's type and the default; fixed with a two-effect split and verified live in the browser for both a C4 diagram and an unrelated UML diagram. 1192 backend tests (was 1190, +2; 1190 passing — 2 pre-existing failures confirmed unrelated), 228 frontend tests (was 216, +12), `adp-generate --check` clean — plus a full live Playwright walkthrough (create → author → save → reopen with full fidelity → export SVG/PNG, inspecting the real exported SVG content) against a freshly-restarted backend. See `specs/053-c4-diagram-type/`.

Prior work: **052-diagram-editor-redesign** (ADP-SPEC-052, implemented — all three user stories) — a presentation-only redesign of the diagram list and editor screens (`web/src/diagrams/`), closing the gap where this screen was the one place in ADP with zero custom styling — confirmed directly that **zero `.css` files existed anywhere under `web/src/diagrams/`** before this feature. Two tracks: the three ADP-authored chrome files (`DiagramListPage.tsx`, `DiagramsPage.tsx`, `DiagramEditorPage.tsx`) were rewritten onto ADP's `.ui-*` classes and shared `Button`/`StatusBadge` components (mirroring `web/src/designs/DesignsPage.tsx`), including switching `DiagramListPage.tsx` off an ad hoc fetch onto new `useDiagrams()`/`useDeleteDiagram()` TanStack Query hooks; the six vendored editor internals (`Canvas.tsx`, `shapes.tsx`, `DslPanel.tsx`, `useDslSync.ts`, `ConfirmDialog.tsx`, `UnsupportedElementNotice.tsx`) kept their JSX structurally unchanged — a new feature-scoped stylesheet (`diagrams.css`) supplies every class name they already referenced — except two documented, one-line **value-only** exceptions: `shapes.tsx`'s hardcoded selection-stroke hex swapped for `var(--accent)`, and `Canvas.tsx`'s old single-character Unicode shape glyphs swapped for real `Icon` components. The canvas surface now adapts to theme while default shape colors deliberately stay fixed regardless of theme, matching ADP's locked-C4-theme precedent (FR-010, resolved via clarification). The editor's palette/canvas/DSL panel are now simultaneously visible via a CSS Grid workspace layout — built on `Canvas.tsx`'s pre-existing (but previously unused) `toolbarContainer` portal prop rather than any new vendored-file change — collapsing the palette to an overlay drawer below 900px, reusing the shell's own existing breakpoint. One test-infra gap found and fixed: jsdom has no `<dialog>` `showModal()`/`close()` — added a minimal polyfill to `web/tests/setup.ts`, since `ConfirmDialog`/`Modal` had never been directly unit-tested before. 216 frontend tests (was 202, +14), `tsc` clean — plus a full live Playwright walkthrough (dark/light theme, narrow-viewport drawer, Connect active state) confirming the rendered screens match spec. Undo/redo remains out of scope, tracked separately as ADP-914.10. See `specs/052-diagram-editor-redesign/`.

Prior work: **051-strategy-landing-card** (ADP-d8u.3, implemented — all three user stories) — a fifth "Strategy" domain card on `OverviewPage.tsx`, closing the open-frontier gap where Strategy (ADP-d8u.1) had zero landing-dashboard presence while Business/Enterprise/Solution/Technical already did. Adds `GET /api/v1/strategy/summary`, a new aggregate endpoint mirroring `adp.portfolio`'s own already-established `GET /api/v1/portfolio/summary` pattern (raw `sa.text()` SQL, same response-model/hook shape) rather than inventing a new one — needed because the linkage-health split and fiscal-period breakdown require per-objective link facts the existing objectives list doesn't carry, and the fiscal comparison must be anchored to the server's clock, not the browser's. No migration. One atomic query computes all seven fields, including a `FY`-period-aware past-due rule (never past due partway through its own fiscal year) — verified correct by seeding objectives across every bucket against real Postgres, since the SQL's `NOW()`/`EXTRACT()`/`FILTER` can't run under the SQLite-backed unit tests (mocked instead, mirroring `adp.portfolio`'s own test pattern for this class of endpoint). Two real corrections found during implementation: the SQLite-incompatibility only became apparent once building the actual query; and a pre-existing test file outside `web/src/overview/` broke on the new query and needed its route-mock map updated. 1190 backend tests (+5), 202 frontend tests (+10), `ruff`/`mypy`/`tsc` clean — plus a full live Playwright walkthrough across every governance-signal state, confirming the rendered card matches the live API exactly. See `specs/051-strategy-landing-card/`.

Prior work: **050-strategic-objective-capture** (ADP-d8u.1, implemented — all three user stories) — a new sibling package `src/adp/strategy/` captures `StrategicTheme`/`StrategicObjective` as structured entities (owner, statement, an all-or-nothing metric/target/unit/direction group, a structured fiscal_year+period horizon) rather than a text blob, with many-to-many links to real `business_capabilities`/`value_streams` (never free text). New migration 025 mirrors migration 008's `capability_design_links` join-table shape exactly (composite PK, `ON DELETE CASCADE` both legs, one index, `created_at`); the cascade was verified live against real Postgres, zero orphaned join rows after deleting an objective. Frontend: `web/src/strategy/` — list/form/detail screens mirroring `DomainList`/`ValueStreamList`'s convention, plus two link editors that are near-verbatim mirrors of `DesignLinkEditor.tsx`, wired into a new "Strategy" nav entry placed first under Architecture. 1185 backend tests (+38), 192 frontend tests (+23). See `specs/050-strategic-objective-capture/`.

Prior work: **048-generate-diagrams-from-data** (ADP-914.7, implemented — both user stories) — "Generate Diagram" buttons on `ValueStreamDetail.tsx` and `CapabilityNode.tsx` produce a new, unsaved flowchart pre-filled from ADP's own business data: a value stream's ordered stages, or a capability's full subtree. New `web/src/diagrams/generators.ts` — two pure functions building a typed `DiagramModel` via the vendored `diagram-core`'s `addNode`/`addEdge`, never hand-written DSL text. One-way only by design (FR-008). Cross-page hand-off (Business page → Diagrams page) deliberately reuses `App.tsx`'s existing `currentDesignId`/`onSelectDesign` lifted-state pattern. Zero backend change. 151 frontend tests. See `specs/048-generate-diagrams-from-data/`.

Prior work: **047-persona-diagram-experience** (ADP-914.6, implemented — both user stories) — new diagrams get a persona-aware default type (Enterprise Architect → `architecture`, Solution Architect → `flowchart`, Technical Architect → `sequence`) and a "(Recommended for your role)" label on the matching option in `DiagramEditorPage.tsx`'s type selector — steering only, `WRITE_DIAGRAM` untouched. Also corrects a stale wording gap found while scoping this feature: ADP-914's epic said "EA/BA/TA" but ADP has no `business_architect` `PersonaRole` at all — spec.md fixes the wording rather than inventing a fourth role. Bundled in the same branch: **ADP-914.5**, the nav-wiring fix for 046's diagram editor, which had been fully built and tested but was never reachable from the running app at all — new `DiagramsPage.tsx` now wired into `App.tsx`/`AppShell.tsx` as a "Diagrams" nav item. 141 frontend tests (was 124, +17 across both fixes). See `specs/047-persona-diagram-experience/`.

Prior work: **046-diagram-type-support** (ADP-SPEC-046, implemented — all 3 user stories) — five new standalone diagram types (flowchart, sequence, ER, UML, cloud-architecture) additive alongside ADP's existing C4 workspace; zero changes to `ArchitectureDescription`, `web/src/canvas/`, or `adp.renderer`. Reuses a sibling project's mature TypeScript diagramming library (`/home/jmuir/projects/canvas/packages/diagram-core`, located and read directly during planning), **vendored** into `web/src/diagrams/core/` rather than a live cross-repo dependency, so the build stays reproducible from a clean ADP checkout alone (ART-XIV). Parsing/validation/SVG-rendering run entirely client-side; the new `adp.diagrams` backend package is just CRUD storage of an opaque `dsl_source` string plus one PNG-export endpoint reusing ADP's existing `cairosvg` dependency (the sibling project's own PNG path uses a Node-only binding). One new standalone table (`diagrams`, migration 024, no FK to `designs` — a deliberate stepping stone toward a future optional-Design-attachment model, per an explicit clarification answer optimizing for that migration path). New `ActionType.WRITE_DIAGRAM` (`PERMISSIONS_VERSION` 1.7.0 → 1.8.0). 1136 backend tests (+50), 124 frontend tests (+16), `ruff`/`mypy`/`tsc` clean, `adp-generate --check` clean. See `specs/046-diagram-type-support/`.

Prior work: **045-application-export** (ADP-SPEC-045, ADP-81p.2, implemented — both user stories) — extends ADP-SPEC-044's continuous-export pattern to the Application registry (ADP-81p's second and largest remaining domain): applications, technical capabilities, transformation initiatives (with member/disposition links), and application-to-application integrations, all reconciled to one JSON file per entity under `$ADP_BUSINESS_ARCH_EXPORT_ROOT/applications/`, sharing 044's exact env vars/background-task lifecycle — no new configuration surface. New shared `adp.export.common` module (research.md Decision 5) extracted from `business_arch.py`'s domain-agnostic mechanics (path safety, atomic writes, content-diff writes, orphan cleanup, background-loop lifecycle); a behavior-preserving refactor validated by 044's own existing test suite passing unchanged with zero test-file edits. Per an explicit, recorded Clarification (Q1) — not a default — the export includes an application's risk/cost/governance records **unredacted**, even though the live API gates them behind `READ_APPLICATION_{RISK,COST,GOVERNANCE}`: a background process has no per-viewer permission context to apply that gate selectively, so the honestly-documented choice was full inclusion with an explicit residual-risk callout (Threat Model, RUNBOOK.md) over silent partial redaction. No new database table, no new API endpoint — the exported file tree is this feature's external interface too. See `specs/045-application-export/`.

Prior work: **044-business-arch-export** (ADP-SPEC-044, ADP-81p.1, implemented — both user stories) — continuous, opt-in export of business capabilities/value streams/stages/domains from Postgres to one versioned JSON file per entity (`web/src/admin/`-adjacent but backend-only, no UI), closing the "architecture as code" gap for this domain (parent epic ADP-81p, which itself left three architecturally divergent options open — this implements its own recommended starting point). New `adp.export.business_arch` module: a periodic full-reconciliation background task (deliberately NOT write-path hooks — `value_stream_stages` has no `updated_at` column at all, which would have silently broken a timestamp-based approach) wired into `adp.api.app`'s existing lifespan, inert unless `ADP_BUSINESS_ARCH_EXPORT_ROOT` is set. No new database table — change detection compares candidate file content against what's already on disk rather than a persisted sync-state table; a deleted value stream's whole directory (its stages included) is removed in one step. No new API endpoint — the exported file tree itself is this feature's external interface, documented as a contract (`specs/044-business-arch-export/contracts/`). Scope deliberately excludes applications and the two design-linking join tables from ADP-SPEC-034 (those connect to entities that are themselves out of scope or separately exported); the one in-scope cross-entity relationship — which capabilities a value stream stage links to — is included, since omitting it would leave the export nearly meaningless. See `specs/044-business-arch-export/`.

Prior work: **042-admin-prompt-management** (ADP-SPEC-042, ADP-t32, implemented — all 3 user stories) — an admin-only screen (`web/src/admin/`, gated on the new `PersonaRole.PLATFORM_ADMIN` role at the nav/route level) to view, edit-with-confirmation, and revert the system prompts behind ADP's six AI agent call sites (Chat Assistant, Recommendation generation, Recommendation generation no-KB, Recommendation trade-off, Intake extraction, Agent Review) without a code deploy. New `ActionType.MANAGE_AGENT_PROMPTS`, granted only to `PLATFORM_ADMIN`; `PERMISSIONS_VERSION` `1.6.0` → `1.7.0` deliberately narrows `ENTERPRISE_ARCHITECT`'s former all-actions wildcard grant to exclude it (no architect role gains admin access by virtue of that role alone). Two new additive tables (`agent_prompt_overrides`, `agent_prompt_history` via migration 023) sit in front of the existing hardcoded prompt constants as an override layer; a new `adp.admin.prompt_registry` module (relocated from the originally-planned `adp.agents.prompt_registry` once `adp.agents`' own zero-domain-import boundary test caught the conflict — see `specs/042-admin-prompt-management/research.md` Decision 5) is the shared effective-prompt lookup all five non-Agent-Review call sites and the admin screen itself read through, so what the screen shows is guaranteed to match what agents actually send. Restore uses the identical `confirmation_id` gate as a manual edit, not a lower-friction path. See `specs/042-admin-prompt-management/`.

Prior work: **041-ai-chat-assistant** (ADP-SPEC-041, spec + plan drafted, not yet implemented, on branch `041-ai-chat-assistant`) — a read-only, cross-domain conversational Q&A assistant (business capabilities, applications, portfolio, governance) complementing Agent Review rather than duplicating its write path. New top-level `adp.chat` package (deliberately outside `adp.agents`' zero-domain-import contract, since cross-domain reads are the whole point); grounding is two-legged (extended `adp.search` hybrid index for fuzzy questions + a fixed read-only tool-call registry for precise/aggregate ones); sensitive application data filtered per the asking user's own permissions inside the tool layer; real-time SSE streaming (the platform's first); persisted, actor-scoped conversation history via new migration 022. First entry point: a toggle on the Business Capabilities page. See `specs/041-ai-chat-assistant/spec.md` and `plan.md`.

Prior work: **040-portfolio-agent-review** (ADP-SPEC-040, implemented, merged) — a portfolio-scope sibling to the per-capability Agent Review: a "Review Portfolio" button reviews the whole capability tree at once, reusing `propose_new_capability` and adding a sixth suggestion type `flag_capability_for_removal` (accept reuses the existing `delete_capability`, which already guards against removing a capability with children). New routes have no `{cap_id}` path segment, so no collision with the 039 per-capability routes. Also fixed two bugs in the 039 UI: stale dropdowns after accepting a suggestion, and no way to close/dismiss the review panel.

Prior work: **039-agent-review-toolkit** (ADP-SPEC-039, implemented — all 4 user stories) — a reusable "agent review" pattern: a shared `adp.agents` toolkit (LLM stub, ART-VII grounding/citation validator, audit+reasoning helpers, no new tables — reuses `OperationStore`/`llm_reasoning_log` as-is; zero domain-module imports, mechanically enforced by tests/unit/agents/test_toolkit_boundary.py) plus a Business Capabilities adapter (4 suggestion-type stories, P1 read-only duplicate-flagging → P4 propose-new-capability). `PERMISSIONS_VERSION` progressed `1.4.0` → `1.5.0` adding `CONFIRM_AGENT_SUGGESTION` (trigger reuses the existing `SUBMIT_AI_OPERATION`). See `docs/solution-architecture.md`'s "Agent Review" section for full detail.

Prior completed epic: **038-application-portfolio-management** (Application Portfolio Management, 8 user stories US1–US8 built on the 036 application registry, plus 3 follow-on beads: strategic relevance, capability maturity, intake gap analysis). Alembic head is migration `021` (`down_revision` chain 010→021). See `CLAUDE.md`'s "Active Technologies" / "Recent Changes" and `docs/solution-architecture.md`'s "Application Portfolio Management" section for full detail.

This project uses **bd** (beads) for issue tracking. Run `bd prime` for full workflow context.

> **Architecture in one line:** Issues live in a local Dolt database
> (`.beads/dolt/`); cross-machine sync uses `bd dolt push/pull` (a
> git-compatible protocol), stored under `refs/dolt/data` on your git
> remote — separate from `refs/heads/*` where your code lives.
> `.beads/issues.jsonl` is a passive export, not the wire protocol.
>
> See [SYNC_CONCEPTS.md](https://github.com/gastownhall/beads/blob/main/docs/SYNC_CONCEPTS.md)
> for the one-screen overview and anti-patterns (don't treat JSONL as the
> source of truth; don't `bd import` during normal operation; don't
> reach for third-party Dolt hosting before trying the default).

## Quick Reference

```bash
bd ready              # Find available work
bd show <id>          # View issue details
bd update <id> --claim  # Claim work atomically
bd close <id>         # Complete work
bd dolt push          # Push beads data to remote
```

## Non-Interactive Shell Commands

**ALWAYS use non-interactive flags** with file operations to avoid hanging on confirmation prompts.

Shell commands like `cp`, `mv`, and `rm` may be aliased to include `-i` (interactive) mode on some systems, causing the agent to hang indefinitely waiting for y/n input.

**Use these forms instead:**
```bash
# Force overwrite without prompting
cp -f source dest           # NOT: cp source dest
mv -f source dest           # NOT: mv source dest
rm -f file                  # NOT: rm file

# For recursive operations
rm -rf directory            # NOT: rm -r directory
cp -rf source dest          # NOT: cp -r source dest
```

**Other commands that may prompt:**
- `scp` - use `-o BatchMode=yes` for non-interactive
- `ssh` - use `-o BatchMode=yes` to fail instead of prompting
- `apt-get` - use `-y` flag
- `brew` - use `HOMEBREW_NO_AUTO_UPDATE=1` env var

<!-- BEGIN BEADS INTEGRATION v:1 profile:minimal hash:970c3bf2 -->
## Beads Issue Tracker

This project uses **bd (beads)** for issue tracking. Run `bd prime` to see full workflow context and commands.

### Quick Reference

```bash
bd ready              # Find available work
bd show <id>          # View issue details
bd update <id> --claim  # Claim work
bd close <id>         # Complete work
```

### Rules

- Use `bd` for ALL task tracking — do NOT use TodoWrite, TaskCreate, or markdown TODO lists
- Run `bd prime` for detailed command reference and session close protocol
- Use `bd remember` for persistent knowledge — do NOT use MEMORY.md files

**Architecture in one line:** issues live in a local Dolt DB; sync uses `refs/dolt/data` on your git remote; `.beads/issues.jsonl` is a passive export. See https://github.com/gastownhall/beads/blob/main/docs/SYNC_CONCEPTS.md for details and anti-patterns.

## Agent Context Profiles

The managed Beads block is task-tracking guidance, not permission to override repository, user, or orchestrator instructions.

- **Conservative (default)**: Use `bd` for task tracking. Do not run git commits, git pushes, or Dolt remote sync unless explicitly asked. At handoff, report changed files, validation, and suggested next commands.
- **Minimal**: Keep tool instruction files as pointers to `bd prime`; use the same conservative git policy unless active instructions say otherwise.
- **Team-maintainer**: Only when the repository explicitly opts in, agents may close beads, run quality gates, commit, and push as part of session close. A current "do not commit" or "do not push" instruction still wins.

## Session Completion

This protocol applies when ending a Beads implementation workflow. It is subordinate to explicit user, repository, and orchestrator instructions.

1. **File issues for remaining work** - Create beads for anything that needs follow-up
2. **Run quality gates** (if code changed) - Tests, linters, builds
3. **Update issue status** - Close finished work, update in-progress items
4. **Handle git/sync by active profile**:
   ```bash
   # Conservative/minimal/default: report status and proposed commands; wait for approval.
   git status

   # Team-maintainer opt-in only, unless current instructions forbid it:
   git pull --rebase
   bd dolt push
   git push
   git status
   ```
5. **Hand off** - Summarize changes, validation, issue status, and any blocked sync/commit/push step

**Critical rules:**
- Explicit user or orchestrator instructions override this Beads block.
- Do not commit or push without clear authority from the active profile or the current user request.
- If a required sync or push is blocked, stop and report the exact command and error.
<!-- END BEADS INTEGRATION -->

<!-- BEGIN BEADS CODEX SETUP: generated by bd setup codex -->
## Beads Issue Tracker

Use Beads (`bd`) for durable task tracking in repositories that include it. Use the `beads` skill at `.agents/skills/beads/SKILL.md` (project install) or `~/.agents/skills/beads/SKILL.md` (global install) for Beads workflow guidance, then use the `bd` CLI for issue operations.

### Quick Reference

```bash
bd ready                # Find available work
bd show <id>            # View issue details
bd update <id> --claim  # Claim work
bd close <id>           # Complete work
bd prime                # Refresh Beads context
```

### Rules

- Use `bd` for all task tracking; do not create markdown TODO lists.
- Run `bd prime` when Beads context is missing or stale. Codex 0.129.0+ can load Beads context automatically through native hooks; use `/hooks` to inspect or toggle them.
- Keep persistent project memory in Beads via `bd remember`; do not create ad hoc memory files.

**Architecture in one line:** issues live in a local Dolt DB; sync uses `refs/dolt/data` on your git remote; `.beads/issues.jsonl` is a passive export. See https://github.com/gastownhall/beads/blob/main/docs/SYNC_CONCEPTS.md for details and anti-patterns.
<!-- END BEADS CODEX SETUP -->

<!-- gitnexus:start -->
# GitNexus — Code Intelligence

This project is indexed by GitNexus as **ADP** (14366 symbols, 22849 relationships, 232 execution flows). Use the GitNexus MCP tools to understand code, assess impact, and navigate safely.

> Index stale? Run `node .gitnexus/run.cjs analyze` from the project root — it auto-selects an available runner. No `.gitnexus/run.cjs` yet? `npx gitnexus analyze` (npm 11 crash → `npm i -g gitnexus`; #1939).

## Always Do

- **MUST run impact analysis before editing any symbol.** Before modifying a function, class, or method, run `impact({target: "symbolName", direction: "upstream"})` and report the blast radius (direct callers, affected processes, risk level) to the user.
- **MUST run `detect_changes()` before committing** to verify your changes only affect expected symbols and execution flows. For regression review, compare against the default branch: `detect_changes({scope: "compare", base_ref: "main"})`.
- **MUST warn the user** if impact analysis returns HIGH or CRITICAL risk before proceeding with edits.
- When exploring unfamiliar code, use `query({search_query: "concept"})` to find execution flows instead of grepping. It returns process-grouped results ranked by relevance.
- When you need full context on a specific symbol — callers, callees, which execution flows it participates in — use `context({name: "symbolName"})`.
- For security review, `explain({target: "fileOrSymbol"})` lists taint findings (source→sink flows; needs `analyze --pdg`).

## Never Do

- NEVER edit a function, class, or method without first running `impact` on it.
- NEVER ignore HIGH or CRITICAL risk warnings from impact analysis.
- NEVER rename symbols with find-and-replace — use `rename` which understands the call graph.
- NEVER commit changes without running `detect_changes()` to check affected scope.

## Resources

| Resource | Use for |
|----------|---------|
| `gitnexus://repo/ADP/context` | Codebase overview, check index freshness |
| `gitnexus://repo/ADP/clusters` | All functional areas |
| `gitnexus://repo/ADP/processes` | All execution flows |
| `gitnexus://repo/ADP/process/{name}` | Step-by-step execution trace |

## CLI

| Task | Read this skill file |
|------|---------------------|
| Understand architecture / "How does X work?" | `.claude/skills/gitnexus/gitnexus-exploring/SKILL.md` |
| Blast radius / "What breaks if I change X?" | `.claude/skills/gitnexus/gitnexus-impact-analysis/SKILL.md` |
| Trace bugs / "Why is X failing?" | `.claude/skills/gitnexus/gitnexus-debugging/SKILL.md` |
| Rename / extract / split / refactor | `.claude/skills/gitnexus/gitnexus-refactoring/SKILL.md` |
| Tools, resources, schema reference | `.claude/skills/gitnexus/gitnexus-guide/SKILL.md` |
| Index, status, clean, wiki CLI commands | `.claude/skills/gitnexus/gitnexus-cli/SKILL.md` |

<!-- gitnexus:end -->
