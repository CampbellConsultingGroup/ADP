# Agent Instructions

## Project Status

Latest work: **052-diagram-editor-redesign** (ADP-SPEC-052, implemented — all three user stories) — a presentation-only redesign of the diagram list and editor screens (`web/src/diagrams/`), closing the gap where this screen was the one place in ADP with zero custom styling — confirmed directly that **zero `.css` files existed anywhere under `web/src/diagrams/`** before this feature. Two tracks: the three ADP-authored chrome files (`DiagramListPage.tsx`, `DiagramsPage.tsx`, `DiagramEditorPage.tsx`) were rewritten onto ADP's `.ui-*` classes and shared `Button`/`StatusBadge` components (mirroring `web/src/designs/DesignsPage.tsx`), including switching `DiagramListPage.tsx` off an ad hoc fetch onto new `useDiagrams()`/`useDeleteDiagram()` TanStack Query hooks; the six vendored editor internals (`Canvas.tsx`, `shapes.tsx`, `DslPanel.tsx`, `useDslSync.ts`, `ConfirmDialog.tsx`, `UnsupportedElementNotice.tsx`) kept their JSX structurally unchanged — a new feature-scoped stylesheet (`diagrams.css`) supplies every class name they already referenced — except two documented, one-line **value-only** exceptions: `shapes.tsx`'s hardcoded selection-stroke hex swapped for `var(--accent)`, and `Canvas.tsx`'s old single-character Unicode shape glyphs swapped for real `Icon` components. The canvas surface now adapts to theme while default shape colors deliberately stay fixed regardless of theme, matching ADP's locked-C4-theme precedent (FR-010, resolved via clarification). The editor's palette/canvas/DSL panel are now simultaneously visible via a CSS Grid workspace layout — built on `Canvas.tsx`'s pre-existing (but previously unused) `toolbarContainer` portal prop rather than any new vendored-file change — collapsing the palette to an overlay drawer below 900px, reusing the shell's own existing breakpoint. One test-infra gap found and fixed: jsdom has no `<dialog>` `showModal()`/`close()` — added a minimal polyfill to `web/tests/setup.ts`, since `ConfirmDialog`/`Modal` had never been directly unit-tested before. 216 frontend tests (was 202, +14), `tsc` clean — plus a full live Playwright walkthrough (dark/light theme, narrow-viewport drawer, Connect active state) confirming the rendered screens match spec. Undo/redo remains out of scope, tracked separately as ADP-914.10. See `specs/052-diagram-editor-redesign/`.

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

This project is indexed by GitNexus as **ADP** (13783 symbols, 21900 relationships, 233 execution flows). Use the GitNexus MCP tools to understand code, assess impact, and navigate safely.

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
