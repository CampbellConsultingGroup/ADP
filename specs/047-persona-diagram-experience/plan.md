# Implementation Plan: Persona-Differentiated Diagram Experience

**Branch**: `047-persona-diagram-experience` | **Date**: 2026-08-11 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `/specs/047-persona-diagram-experience/spec.md`

**Note**: This template is filled in by the `/speckit.plan` command. See `.specify/templates/plan-template.md` for the execution workflow.

## Summary

Pre-select and visually flag the diagram type that best fits the signed-in architect's role (Enterprise → `architecture`, Solution → `flowchart`, Technical → `sequence`) when starting a new diagram in `DiagramEditorPage.tsx`, without restricting any role's ability to choose any of the other 4 types. Pure frontend, additive change: one new small constant/lookup module (`web/src/diagrams/persona.ts`) plus a targeted edit to `DiagramEditorPage.tsx`'s existing type-selection logic. Reuses the role already exposed by the existing `useAuth()` hook (`web/src/auth/AuthProvider.tsx`) — confirmed via direct read that `AuthProvider` blocks all children behind a loading screen until `user`/`role` is resolved, so there is no race condition to design around. Zero backend changes, zero new dependencies, zero change to `WRITE_DIAGRAM`/`permissions.py`, zero change to the vendored `diagram-core` library.

## Technical Context

**Language/Version**: TypeScript 5.x + React 18.3 (frontend only — no backend touched at all, matching ADP's existing `web/` toolchain)
**Primary Dependencies**: None new. Reuses `useAuth()` (`web/src/auth/AuthProvider.tsx`, ADP-SPEC-026) and the existing `DiagramEditorPage.tsx`/`DiagramType` (ADP-SPEC-046, ADP-914.5).
**Storage**: N/A — no new persisted data; the persona→type mapping is a static, in-memory frontend constant (mirrors the existing `ROLE_LABELS`/`ROLE_COLORS` pattern in `AuthProvider.tsx`), not a database table or part of the `Diagram` model.
**Testing**: Vitest + React Testing Library, following the exact conventions already established in `DiagramEditorPage.test.tsx` (`vi.mock`, `render`/`screen`/`userEvent`) — no new test tooling.
**Target Platform**: Browser (existing `web/` SPA) — no new deployable, no backend process touched.
**Project Type**: Web application — this feature is a frontend-only addition to the existing FastAPI backend + React frontend split; the backend side is entirely unmodified.
**Performance Goals**: None specific — a synchronous object-lookup on component mount; negligible compared to the existing render cost of the diagram editor itself.
**Constraints**: Zero backend changes (spec Assumptions); zero change to `WRITE_DIAGRAM`, `PersonaRole`, or `permissions.py` (spec Assumptions — the epic's stale "Business Architect" wording is corrected, not implemented, by reusing the 3 existing architect roles); zero change to the 5 diagram types or the vendored `diagram-core` parsing/rendering library; zero change to an *existing* diagram's type selector (immutable post-creation, per ADP-SPEC-046 — this feature only touches the new-diagram creation path).
**Scale/Scope**: 1 new frontend file (`web/src/diagrams/persona.ts`, ~15 lines) + 1 new test file, 1 modified frontend file (`DiagramEditorPage.tsx`) + its existing test file extended, 0 backend files, 0 new DB objects, 0 new dependencies.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Article | Applies? | How this feature satisfies it |
|---|---|---|
| ART-I (SDD Mandatory) | Yes | spec.md (all 3 open questions resolved with documented defaults, zero `NEEDS CLARIFICATION` markers) → this plan → tasks.md (next command) → implementation, in order. |
| ART-II (Model is Source of Truth) | No | No canonical model touched — `Diagram`/`ArchitectureDescription` are both unmodified; the persona mapping is a UI presentation constant, not part of any source-of-truth model. |
| ART-III (Machine-Readable) | No | No new structured data is introduced. |
| ART-IV (TDD) | Yes | tasks.md will sequence a failing `persona.ts` unit test and failing `DiagramEditorPage.test.tsx` additions before each corresponding implementation task. |
| ART-V (Security by Design) | Yes (verified low-risk) | Re-confirmed in spec.md's Threat Model: no new data exposure, no new trust boundary, `WRITE_DIAGRAM` unchanged — a manipulated client-side role value at worst mis-steers that same user's own default, never grants a capability. |
| ART-VI (Observability) | No | No new mutation type, no new AI orchestration span — this is a pure client-side presentation choice with no server round-trip of its own. |
| ART-VII, ART-VIII, ART-IX, ART-X, ART-XI | No | No AI-generated content, no AI proposal to confirm, nothing added to the audit trail, no validation gating, no traceability thread — consistent with ADP-SPEC-046, which this feature only extends at the UI layer. |
| ART-XII (Fixed Visual Language) | No | Governs the locked C4 theme specifically; this feature touches only the non-C4 diagram-type selector's option labels, not any rendered diagram's visual styling. |
| ART-XIII (Typed Contracts) | Yes (incidental) | The persona→type mapping is a plain `Record<string, DiagramType>` reusing the already-typed `DiagramType` union from `web/src/diagrams/api.ts` — no new API boundary, no new Pydantic model, no backend change at all. |
| ART-XIV, ART-XV (Reproducible builds / Schema evolution) | No | No migration, no schema change, no build-reproducibility concern — a same-repo, dependency-free frontend addition. |
| ART-XVI (Documentation as Code) | Yes (SHOULD) | A short note added to `web/src/diagrams/README.md` documenting the persona-mapping convention and where to change it. |

**Initial gate result**: PASS. No article is violated; most don't apply at all given the feature's narrow, presentation-only scope. **No Complexity Tracking entry is needed** — this is the smallest-footprint kind of change this codebase makes (a single new constant module + a targeted edit to one existing component), not an exception to any gate.

**Post-Phase-1 re-check**: PASS (unchanged) — data-model.md below confirms no persisted entity is introduced; the design stays exactly as narrow as the Summary describes.

## Project Structure

### Documentation (this feature)

```text
specs/047-persona-diagram-experience/
├── plan.md              # This file (/speckit.plan command output)
├── research.md          # Phase 0 output (/speckit.plan command)
├── data-model.md         # Phase 1 output (/speckit.plan command)
├── quickstart.md         # Phase 1 output (/speckit.plan command)
├── checklists/
│   └── requirements.md
└── tasks.md               # Phase 2 output (/speckit.tasks command - NOT created by /speckit.plan)
```

No `contracts/` directory — this feature adds no new API endpoint and changes no existing one; there is no interface contract to document beyond the UI behavior already fully specified in spec.md's Functional Requirements.

### Source Code (repository root)

```text
web/src/
├── auth/
│   └── AuthProvider.tsx           # UNCHANGED — read-only dependency (useAuth().user.role)
├── diagrams/
│   ├── persona.ts                 # NEW: PERSONA_DEFAULT_TYPE constant +
│   │                               #   getRecommendedDiagramType(role) lookup
│   ├── persona.test.ts            # NEW: unit tests for the mapping + fallback behavior
│   ├── DiagramEditorPage.tsx      # MODIFIED: new-diagram default now persona-aware
│   │                               #   (falls back to "flowchart" when role is unrecognized,
│   │                               #   unchanged from today); type <select> options gain a
│   │                               #   "(Recommended for your role)" suffix on the matching type
│   ├── DiagramEditorPage.test.tsx # MODIFIED: new test cases for persona-aware default +
│   │                               #   recommendation label, per role
│   ├── DiagramsPage.tsx           # UNCHANGED — already passes no `newDiagramType`, so
│   │                               #   DiagramEditorPage's own (now persona-aware) internal
│   │                               #   fallback applies with no call-site change needed
│   └── README.md                  # MODIFIED: short note on the persona-mapping convention
└── (no other files touched — no backend, no other frontend module)
```

**Structure Decision**: The smallest change that satisfies both user stories: one new pure-lookup module (`persona.ts`, easy to unit-test in isolation and easy to change later without touching component logic) plus a targeted edit to the single existing component that already owns the new-diagram type selector (`DiagramEditorPage.tsx`). `DiagramsPage.tsx` needs no change at all, because it already calls `<DiagramEditorPage diagramId={...} onSaved={...} />` without an explicit `newDiagramType` — the persona-aware fallback lives entirely inside `DiagramEditorPage`'s own existing `newDiagramType ?? "flowchart"` initializer, which becomes `newDiagramType ?? recommended ?? "flowchart"`. This keeps the change surface to exactly the two files the spec's Key Entities section already anticipated ("a small, static, in-memory constant on the frontend"), consistent with FR-007 (no change to the existing-diagram editing path, where the type selector is already hidden).

## Complexity Tracking

> **Fill ONLY if Constitution Check has violations that must be justified**

No violations — table intentionally omitted.
