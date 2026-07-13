# Implementation Plan: Design System, Application Shell & Overview Landing

**Branch**: `037-design-system-shell` (delivered on `036-application-registry`) | **Date**: 2026-07-12 | **Spec**: [spec.md](spec.md)

## Summary

This is a **retrospective / ratifying plan**. The design-system migration it governs already shipped (commits `af61f99`…`7e6cddb`); its purpose is to record the FR → implementation → test traceability required by ART-I / QG-01 and to make explicit which ADP-SPEC-025 requirements it supersedes. No net-new implementation phases are proposed — the tables below map the shipped artifacts to the spec instead.

The migration introduced a shared web **design system** (`web/src/ui`: tokens, primitives, icons), replaced the per-page top `NavBar` with a persistent left-rail **application shell** (`web/src/ui/AppShell.tsx`), added an **Overview** landing dashboard (`web/src/overview/OverviewPage.tsx`) that reads live portfolio data, and moved theming to a `light`/`dark`/`system` model defaulting to `system` (`web/src/ui/theme.ts`). It is presentation-only: no backend endpoint, schema, migration, or auth surface changed.

## Technical Context

**Language/Version**: TypeScript 5.x (frontend only)
**Primary Dependencies**: React 18 + Vite 5 + TanStack Query v5 — all existing stack; **zero new runtime packages**
**Storage**: None server-side. Client-only theme preference in browser `localStorage`.
**Testing**: Vitest (component + unit), Playwright (E2E flows/workspace)
**Target Platform**: Browser
**Project Type**: web-application (frontend); no web-service change
**Performance Goals**: No regression to existing screens; Overview first paint gated only by the existing portfolio/summary queries it already consumes
**Constraints**: Presentation-only (FR-019); MUST NOT touch the locked C4 diagram theme (FR-018 / ART-XII); single navigation source (FR-002)
**Scale/Scope**: 10 primary views migrated onto one shell + design system

## Constitution Check

| Article | Status | Notes |
|---|---|---|
| ART-I Spec-Driven | ✓ PASS (retrospective) | This spec + plan restore traceability for shipped UI; supersession of ADP-SPEC-025 FR-005–008 recorded in both specs and `docs/000-index.md` |
| ART-II Model is Source of Truth | ✓ PASS | Chrome-only re-skin; Overview renders no fabricated figures — all KPIs fetched live (FR-007) |
| ART-IV TDD | ⚠ PARTIAL (retrospective) | Component/E2E coverage exists for the shell, migrated screens, and locked-theme isolation, but was not authored strictly test-first for this ratifying spec; see [Test Coverage](#test-coverage-fr--tests) and the follow-up in Open Risks |
| ART-V Security | ✓ PASS | No new endpoint, data, or trust boundary; only new client state is a validated `localStorage` theme key |
| ART-XII Locked Visual Theme | ✓ PASS | App design system governs chrome only; C4 diagram theme (`/api/v1/theme/c4`, `c4-theme.json`) unchanged — asserted by `web/tests/unit/c4-theme.test.ts` (FR-018) |
| ART-XIII Typed Contracts | ✓ PASS | `AppView` union + typed nav/theme models; no `any` in the shell/primitives |
| ART-XV Schema Evolution | N/A | No migration; no persisted schema touched |
| ART-VII AI Grounding / ART-VIII Human-in-Loop | N/A | No AI output or consequential action |

## Project Structure

### Documentation (this feature)

```text
specs/037-design-system-shell/
├── spec.md              ← ratifying spec (supersedes 025 FR-005–008)
└── plan.md              ← this file
```

(No `research.md` / `data-model.md` / `contracts/` — there is no new data model or API contract. `tasks.md` is not generated for a retrospective spec.)

### Source artifacts governed (already shipped)

```text
web/src/ui/                         ← DESIGN SYSTEM
├── tokens.css      ← design tokens: space/radius/shadow, surface/ink/border,
│                     accent, semantic (good/warn/crit), domain hues (biz/ent/sol/tec)
├── ui.css          ← component + shell styles
├── primitives.tsx  ← Card, Panel, Button, StatusBadge, PageHeader, KpiTile
├── Icon.tsx        ← shared icon set
├── AppShell.tsx    ← left-rail shell; single nav source (PRIMARY/ARCHITECTURE/DESIGN_SCOPED NavDef[]); grouped Workspace/Architecture/Design nav
├── theme.ts        ← light/dark/system mode; localStorage persist; data-theme stamping
└── index.ts

web/src/shell/index.ts              ← AppView union (10 views)
web/src/overview/OverviewPage.tsx   ← Overview landing dashboard (live KPIs)
web/src/App.tsx                     ← default view = "overview"; renders inside AppShell

web/src/{designs,intake,recommend,knowledge,governance,portfolio,application,business}/*
                                    ← migrated onto design system

web/src/shell/NavBar.tsx            ← REMOVED (was ADP-SPEC-025 FR-005/006)
```

## Requirements Traceability (FR → implementation)

| FR | Requirement (short) | Primary artifact |
|---|---|---|
| FR-001 | Persistent left-rail shell replaces top nav | `web/src/ui/AppShell.tsx`; `App.tsx` renders all views inside it |
| FR-002 | Single navigation source | grouped `NavDef[]` arrays (`PRIMARY`, `ARCHITECTURE`, `DESIGN_SCOPED`) defined only in `AppShell.tsx` |
| FR-003 | Workspace / Architecture / per-design groups | `AppShell.tsx` `shell-navlabel` sections: Workspace (Overview, Designs), Architecture (Business, Applications, Portfolio, Governance, Knowledge), Design · {id} (Intake, Recommendations, Canvas) |
| FR-004 | Active view + design context indicated | `AppShell.tsx` active-item class; design id shown when selected |
| FR-005 | `NavBar` removed | `web/src/shell/NavBar.tsx` deleted; no importers |
| FR-006 | Default view = Overview | `App.tsx` `useState<AppView>("overview")` |
| FR-007 | Live KPIs, no hard-coded figures | `OverviewPage.tsx` via `usePortfolioSummary`, `useApplications`, `useIntegrations`, `useCapabilities`, `useValueStreams`, `useDomains`, `useKnowledgeItems` |
| FR-008 | Navigate into each view from Overview | `OverviewPage.tsx` `onNavigate` callback |
| FR-009 | Error + empty states on Overview | `OverviewPage.tsx` `anyError` handling; zero/empty KPI states |
| FR-010 | Designs view retained + reachable | `web/src/designs/DesignsPage.tsx`; `designs` nav item in shell |
| FR-011 | Shared token stylesheet | `web/src/ui/tokens.css` (space/radius/shadow/surface/ink/border/accent/semantic/domain hues) |
| FR-012 | Shared primitives | `web/src/ui/primitives.tsx` (Card, Panel, Button, StatusBadge, PageHeader, KpiTile) |
| FR-013 | All primary screens use the design system | migrated `web/src/{designs,intake,recommend,knowledge,governance,portfolio,application,business,overview}` |
| FR-014 | Consistent domain accent hues | `HUE_VARS` in `AppShell.tsx` + `--biz/--ent/--sol/--tec` tokens |
| FR-015 | light/dark/system, default system | `web/src/ui/theme.ts` (`ThemeMode`, default `"system"`) |
| FR-016 | Persist preference; invalid → system | `theme.ts` reads/validates `localStorage`, falls back to `system` |
| FR-017 | system defers to OS; light/dark stamp attribute | `theme.ts` `applyTheme` (removes `data-theme` for system, sets it otherwise) |
| FR-018 | Locked C4 theme untouched | no change to `c4-theme.json` / `/api/v1/theme/c4`; boundary held by `web/src/theme/c4-theme.ts` staying separate from `web/src/ui` |
| FR-019 | No API/schema/behavior change | no diff under `src/adp/` for this feature |

## Test Coverage (FR → tests)

| Area | Tests |
|---|---|
| Shell navigation between views (Designs → design context → Knowledge/Canvas etc.) | `web/tests/e2e/flows.spec.ts`, `web/tests/e2e/workspace.spec.ts` |
| Migrated registry screens render via design system | `web/tests/component/business-registry.test.tsx`, `application-registry.test.tsx` |
| Canvas chrome / inspection panel | `web/tests/component/C4Canvas.test.tsx`, `InspectionPanel.test.tsx` |
| Locked C4 theme isolation (FR-018) | `web/tests/unit/c4-theme.test.ts`, `web/tests/unit/c4-filter.test.ts` |
| Business capability tree component | `web/src/business/CapabilityTree.test.tsx` |

## Verification (checkable Success Criteria)

Run from repo root; each maps to a Success Criterion in the spec:

```bash
# SC-001: single nav source + NavBar gone
grep -rln "NavDef\[\]" web/src/          # → resolves to web/src/ui/AppShell.tsx only
test ! -f web/src/shell/NavBar.tsx && echo "NavBar removed"

# SC-002: Overview is the default view
grep -n 'useState<AppView>("overview")' web/src/App.tsx

# SC-003/004/006: behavior + locked-theme isolation
cd web && npm run test:run              # Vitest (component + unit, incl. c4-theme)
cd web && npm run test:e2e              # Playwright flows/workspace (requires servers)

# SC-005: Overview reads live endpoints (no hard-coded portfolio numbers)
grep -n "usePortfolioSummary\|useApplications\|useIntegrations" web/src/overview/OverviewPage.tsx
```

## Superseded Requirements

Records the same supersession captured in [spec.md](spec.md) and cross-linked from `specs/025-multi-design-production/spec.md`:

- **ADP-SPEC-025 FR-005, FR-006** (top `NavBar` component + per-page consumption) → replaced by FR-001–FR-005 (left-rail shell, single nav source).
- **ADP-SPEC-025 FR-007, FR-008** (Designs as landing page / default view) → landing/default role replaced by FR-006 (Overview); the Designs screen itself retained by FR-010. ADP-SPEC-025 FR-009 (no hardcoded `DESIGN-001`) remains in force.

## Open Risks / Follow-ups

- **ART-IV (test-first) is retrospective here.** Coverage exists but was not authored test-first against this spec. Follow-up (optional): add explicit shell/Overview component tests asserting FR-002 (single nav source), FR-006 (default view), and FR-009 (Overview error/empty states) to convert PARTIAL → PASS.
- **`docs/solution-architecture.md`** should gain a short "web design system + application shell" note so the implemented-state doc matches the shipped UI.
