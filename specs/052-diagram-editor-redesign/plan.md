# Implementation Plan: Diagram Editor Visual & Workspace Redesign

**Branch**: `052-diagram-editor-redesign` | **Date**: 2026-08-12 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `/specs/052-diagram-editor-redesign/spec.md`

**Note**: This template is filled in by the `/speckit.plan` command. See `.specify/templates/plan-template.md` for the execution workflow.

## Summary

A presentation-only redesign of the diagram list and editor screens (`web/src/diagrams/`), closing
the gap where this screen is the one place in ADP with zero custom styling — confirmed directly
that **zero `.css` files exist anywhere under `web/src/diagrams/`**, so every vendored control
renders with nothing but browser defaults. Two distinct tracks, matched to what each file already
is: the three ADP-authored chrome files (`DiagramListPage.tsx`, `DiagramsPage.tsx`,
`DiagramEditorPage.tsx`) are rewritten directly to use ADP's existing `.ui-*` classes and shared
`Button`/`Card`/`Icon` components, following `web/src/designs/DesignsPage.tsx` as the closest
precedent; the six vendored editor internals (`Canvas.tsx`, `shapes.tsx`, `DslPanel.tsx`,
`useDslSync.ts`, `ConfirmDialog.tsx`, `UnsupportedElementNotice.tsx`) keep every line of JSX
unchanged, and instead get a new, feature-scoped stylesheet (`diagrams.css`) that defines the CSS
classes they already reference — the literal missing layer, not a rewrite. A workspace-layout
restructure (palette rail / canvas / DSL panel simultaneously visible, collapsing responsively at
ADP's existing shell breakpoint) and a canvas surface with a theme-aware background/grid (reusing
existing tokens, no new custom properties) complete the redesign. Default shape colors stay fixed
regardless of theme, per the resolved FR-010 decision, matching ADP's own locked-C4-theme
precedent. Undo/redo is explicitly out of scope, tracked separately as ADP-914.10.

## Technical Context

**Language/Version**: TypeScript 5.x + React 18 (frontend only — no backend touched at all, per spec.md FR-016).
**Primary Dependencies**: None new. Existing `web/src/ui` primitives (`Button`, `Card`, `Panel`, `StatusBadge`, `Icon`), existing token system (`web/src/ui/tokens.css`), existing vendored `web/src/diagrams/editor/*` and `web/src/diagrams/core/*` (untouched internals) — all already in the project.
**Storage**: N/A — no data persisted or read differently; this feature changes only presentation of already-fetched diagram data.
**Testing**: Vitest + React Testing Library, extending the existing `DiagramListPage.test.tsx`/`DiagramsPage.test.tsx`/`DiagramEditorPage.test.tsx` (all three already exist) plus new tests for the workspace-layout and theme-adaptive behaviors this feature adds; mirrors this session's established `vi.mock(hooks-module)` convention where a component under test has dependencies to isolate.
**Target Platform**: Browser (existing `web/` SPA) — no new deployable, no new route.
**Project Type**: Web application, frontend-only slice of the existing FastAPI + React split.
**Performance Goals**: None specific — this is a styling/layout change to an already-interactive canvas; no new rendering cost beyond ordinary CSS.
**Constraints**: `web/src/diagrams/core/` (vendored parser/serializer) and the six vendored `editor/` files' JSX/class names must not be modified (spec.md Constraints, research.md Decision 1). No new CSS custom properties added to `tokens.css` (research.md Decision 3) — canvas surface reuses `--surface-2`/`--border`. Default shape colors stay fixed regardless of theme (spec.md FR-010, resolved). No backend/API change of any kind (FR-016).
**Scale/Scope**: 1 new stylesheet (`web/src/diagrams/diagrams.css`, imported once from `DiagramsPage.tsx`, mirroring `overview.css`'s own scoping-and-import pattern). 3 modified ADP-authored chrome files. 1 modified icon file (`editor/ui/Icon.tsx`, +10 icon entries). 1 modified error-styling call site (`UnsupportedElementNotice.tsx`, inline style → `.ui-alert`). Zero changes to `web/src/diagrams/core/` or the six vendored `editor/` files' markup.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Article | Applies? | How this feature satisfies it |
|---|---|---|
| ART-I (SDD Mandatory) | Yes | spec.md (16/16 checklist, all `NEEDS CLARIFICATION` markers resolved via a clarification round) → this plan → tasks.md (next command) → implementation, in order. |
| ART-II, ART-III (Model is Source of Truth / Machine-Readable) | No | Purely presentational — no canonical data touched, read differently, or newly exposed. |
| ART-IV (TDD) | Yes | tasks.md will sequence failing frontend tests (extending the three existing page test files, plus new tests for workspace-layout/theme behavior) before their implementation tasks. |
| ART-V (Security by Design) | Yes | Threat model in spec.md: no new data, no new trust boundary, frontend-only. |
| ART-VI (Observability) | No, beyond ordinary | No new telemetry surface, no AI step. |
| ART-VII–XI (AI/traceability articles) | No | No AI-generated content, no new audit obligation, no traceability-thread change. |
| ART-XII (Fixed Visual Language) | No | Governs the locked C4 rendering theme specifically (ADP-SPEC-010), not this screen — though this feature's FR-010 deliberately follows that same precedent's *reasoning* (fixed colors for export consistency) without being governed by the article itself. |
| ART-XIII (Typed Contracts) | No | No new API, no new persisted or transmitted data shape; the one typed change (`IconName` extension) is an internal UI enum, not a boundary contract. |
| ART-XIV, ART-XV (Reproducible builds / Schema evolution) | No | No migration, no schema change. |
| ART-XVI (Documentation as Code) | Yes (SHOULD) | This plan + research.md + data-model.md + contracts/ are the documentation, each decision grounded in a direct read of the file it changes or the precedent it follows. |

**Initial gate result**: PASS. No article is violated. **No Complexity Tracking entry is needed** — every design decision (restyle-in-place for vendored files rather than editing them; reuse existing tokens rather than adding new ones; reuse the shell's existing responsive breakpoint) picks the option that adds the least new surface area, not the most.

**Post-Phase-1 re-check**: PASS (unchanged) — data-model.md and contracts/ below implement exactly the additive, low-diff design described above; no new gate is implicated by the detailed design.

## Project Structure

### Documentation (this feature)

```text
specs/052-diagram-editor-redesign/
├── plan.md              # This file (/speckit.plan command output)
├── research.md          # Phase 0 output (/speckit.plan command)
├── data-model.md         # Phase 1 output (/speckit.plan command)
├── quickstart.md         # Phase 1 output (/speckit.plan command)
├── contracts/
│   └── diagram-css-contract.md   # Phase 1 output (/speckit.plan command)
├── checklists/
│   └── requirements.md
└── tasks.md               # Phase 2 output (/speckit.tasks command - NOT created by /speckit.plan)
```

### Source Code (repository root)

```text
web/src/diagrams/diagrams.css              # NEW — defines every class name the six vendored
                                            #   editor/*.tsx files already emit (contracts/
                                            #   diagram-css-contract.md), plus .modal* for
                                            #   editor/ui/Modal.tsx, plus the new workspace-
                                            #   layout grid and canvas-surface/grid-dot styling.
                                            #   Imported once from DiagramsPage.tsx, mirroring
                                            #   overview.css's own import pattern.

web/src/diagrams/DiagramListPage.tsx        # MODIFIED — .ui-list/.ui-list-row/.ui-empty,
                                            #   Button/Icon, replacing the raw <table>.
web/src/diagrams/DiagramsPage.tsx           # MODIFIED — .ui-page/.ui-toolbar/.ui-h1, Button,
                                            #   replacing bare <div style={{...}}> chrome; adds
                                            #   the `import "./diagrams.css"` entry point.
web/src/diagrams/DiagramEditorPage.tsx      # MODIFIED — .ui-input/.ui-select/Button for title/
                                            #   type/Save; new persistent save-state indicator
                                            #   (FR-003); new palette-collapse state (FR-012)
                                            #   threaded into the new workspace layout wrapper.

web/src/diagrams/editor/ui/Icon.tsx         # MODIFIED — +10 IconName entries (shape glyphs),
                                            #   data-model.md's exact mapping.
web/src/diagrams/editor/UnsupportedElementNotice.tsx   # MODIFIED — inline style={{color:...}}
                                            #   → .ui-alert (ADP-authored, not vendored, so this
                                            #   is a safe direct edit despite living in editor/).

web/src/diagrams/editor/Canvas.tsx          # UNCHANGED (vendored) — styled entirely via
web/src/diagrams/editor/shapes.tsx          #   diagrams.css targeting classes already present;
web/src/diagrams/editor/DslPanel.tsx        #   zero JSX edits (research.md Decision 1). shapes.tsx
web/src/diagrams/editor/useDslSync.ts       #   specifically: FR-010 resolved as "no change" —
web/src/diagrams/editor/ConfirmDialog.tsx   #   its color defaults are untouched.
web/src/diagrams/editor/ui/Modal.tsx        # UNCHANGED markup (ADP-authored but no JSX change
                                            #   needed — only diagrams.css adds its styling).

web/src/diagrams/DiagramListPage.test.tsx   # MODIFIED — extended for the new list styling
web/src/diagrams/DiagramsPage.test.tsx      # MODIFIED — extended for the new chrome
web/src/diagrams/DiagramEditorPage.test.tsx # MODIFIED — extended for save-state indicator,
                                            #   workspace-layout, theme-adaptive canvas surface
```

**Structure Decision**: No new package, no new route, no new component library. One new
feature-scoped stylesheet (mirroring `overview.css`'s precedent) carries almost the entire visual
change; the only `.tsx` edits are to files ADP already owns outright (three chrome pages, the
already-ADP-authored icon/notice files) — the vendored editor internals are styled into shape by
CSS alone, keeping this a genuinely low-diff, low-regression-risk change relative to its visual
scope.

## Complexity Tracking

> **Fill ONLY if Constitution Check has violations that must be justified**

No violations — table intentionally omitted.
