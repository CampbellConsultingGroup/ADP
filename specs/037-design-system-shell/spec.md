# Feature Specification: Design System, Application Shell & Overview Landing

**Feature Branch**: `037-design-system-shell`  
**Created**: 2026-07-12  
**Status**: Draft  
**Input**: Ratifies the UI migration delivered on branch `036-application-registry` (commits `af61f99`…`7e6cddb`): a shared web design system, a left-rail application shell, an Overview landing dashboard, and system-default theming.

> **Supersedes**: ADP-SPEC-025 **FR-005, FR-006, FR-007, FR-008** (top `NavBar` component; Designs as landing page). See [Superseded Requirements](#superseded-requirements). This spec is written to restore ART-I / QG-01 traceability for UI behavior that has already shipped and now diverges from ADP-SPEC-025.

## Constitutional Articles Touched *(mandatory — ART-I)*

- **ART-I** — Spec-Driven Development: always applies; this spec ratifies and governs the shipped design-system migration and records what it supersedes in ADP-SPEC-025.
- **ART-IV** — Test-Driven Development: always applies; component and E2E tests (`web/tests/component`, `web/tests/e2e`) cover the shell, primitives, and Overview page.
- **ART-II** — The Model is the Single Source of Truth: applies as a *constraint*. The design system re-skins application chrome only; it MUST NOT introduce hand-authored substitutes for model-derived content.
- **ART-XII** — Locked Visual Theme: applies as a *boundary*. The web design system governs application chrome (navigation, cards, buttons, KPI tiles, light/dark mode). It MUST NOT alter the locked C4 diagram theme (`/api/v1/theme/c4`, `c4-theme.json`), which remains the single authority for rendered diagram styling.

## Threat Model *(mandatory — ART-V)*

**Assets at risk**: None new. This feature is presentation-only. It introduces no new persisted data, no new API endpoints, and no new trust boundary. The one piece of client state is the user's theme preference (`light`/`dark`/`system`) in `localStorage`.

**Trust boundaries crossed**: Browser only. The Overview dashboard reads existing, already-authorized API endpoints (portfolio summary, capabilities, applications, integrations, knowledge) via the existing data layer; it adds no new server surface.

**Abuse cases**:
- **Stored-preference tampering**: A user edits the `localStorage` theme key to an invalid value → Mitigation: the reader validates the value and falls back to `"system"` (FR-016).
- **Content spoofing via chrome**: A restyled shell could imply data the model does not contain → Mitigation: ART-II constraint — all figures on Overview are fetched live from the API; the shell renders no fabricated portfolio numbers.

**Residual risk**: Negligible. A cosmetic layer over existing, already-governed data flows.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Unified Application Shell (Priority: P1)

Every screen renders inside one persistent left-rail application shell instead of a per-page top navigation bar. The rail groups destinations into a **Workspace** section (Overview, Designs), an **Architecture** section (Business, Applications, Portfolio, Governance, Knowledge), and a per-design **Design** section (Intake, Recommendations, Canvas) that is scoped to and labelled with the selected design. The current view is visually active, and the navigation item set is defined in exactly one place.

**Why this priority**: The prior model duplicated navigation JSX across pages and only covered five views; the platform now has ten. A single shell is the precondition for adding any further screen without drift, and it replaces the now-deleted `NavBar` mandated by ADP-SPEC-025.

**Independent Test**: Render any view; confirm the left rail shows the full grouped navigation, the active item is highlighted, and the navigation definitions (`NavDef[]` arrays) resolve to a single component.

**Acceptance Scenarios**:

1. **Given** the user is on any view, **When** they look at the shell, **Then** the left rail lists all Workspace destinations and highlights the current one.
2. **Given** no design is selected, **When** the shell renders, **Then** the per-design Architecture section (Intake, Recommendations, Canvas) is not presented as an active design context.
3. **Given** a design is selected, **When** the user navigates, **Then** the design-scoped section shows the design identifier and the Intake / Recommendations / Canvas destinations.
4. **Given** the navigation definitions, **When** `grep -rln "NavDef\[\]" web/src/` is run, **Then** the destination arrays are defined in one component (the app shell), not duplicated per page.

---

### User Story 2 - Overview Landing Dashboard (Priority: P1)

Opening ADP lands on an **Overview** dashboard that surfaces live portfolio KPIs (e.g. designs by lifecycle status, application/integration/capability counts, knowledge coverage) drawn from existing endpoints, and lets the user jump into any section. Overview — not Designs — is the default view.

**Why this priority**: The platform now spans business, application, portfolio, and governance concerns; a single design-list landing no longer represents the practice. A live summary is the most useful entry point and establishes the new default route.

**Independent Test**: Load the app with no view selected; confirm the Overview dashboard renders live figures and that each summary card/section navigates to its corresponding view.

**Acceptance Scenarios**:

1. **Given** the app is opened with no explicit view, **When** it loads, **Then** the Overview dashboard is shown (the default `view` is `"overview"`).
2. **Given** portfolio data exists, **When** Overview renders, **Then** KPI figures are fetched live from the API (not hard-coded).
3. **Given** an Overview section for a domain, **When** the user activates it, **Then** the app navigates to that domain's view via the shell's navigation callback.
4. **Given** one or more underlying queries fail, **When** Overview renders, **Then** it surfaces an error state rather than presenting stale or fabricated figures.

---

### User Story 3 - Shared Design System (Priority: P2)

All screens are built from one shared set of design tokens and UI primitives, so spacing, color, elevation, typography, and component styling are consistent and changeable in one place. Domain areas (Business, Enterprise/Applications, Solution, Technology) are distinguished by a consistent accent-hue system rather than ad-hoc per-page colors.

**Why this priority**: Consistency and single-point restyling are the point of the migration; without shared primitives each screen re-invents its look and drifts.

**Independent Test**: Confirm the shared token stylesheet and primitive components exist and are consumed by the migrated pages; change a token and observe it propagate across screens.

**Acceptance Scenarios**:

1. **Given** the design system, **When** a page needs a card, panel, button, status badge, page header, or KPI tile, **Then** it uses the shared primitive rather than a bespoke element.
2. **Given** the token stylesheet, **When** a spacing, radius, surface, ink, border, accent, semantic (good/warn/crit), or domain-hue value is changed, **Then** the change is reflected consistently across all screens that consume it.
3. **Given** a domain area (Business, Applications/Enterprise, Solution, Technology), **When** its screens and nav items render, **Then** they use the corresponding accent hue consistently.

---

### User Story 4 - Theme Mode with System Default (Priority: P3)

The user can view ADP in light or dark mode, or follow their operating-system preference. New sessions default to **system**. The choice persists across reloads.

**Why this priority**: A pleasant default and respect for OS preference are table stakes for a daily-use tool; persistence avoids re-choosing on every visit. Lower priority than structure and consistency.

**Independent Test**: With no stored preference, confirm the app follows `prefers-color-scheme`; set a preference, reload, and confirm it persists; clear it and confirm the fallback to system.

**Acceptance Scenarios**:

1. **Given** no stored theme preference, **When** the app loads, **Then** it follows the OS `prefers-color-scheme` (system default).
2. **Given** the user selects light or dark, **When** they reload, **Then** the selection persists.
3. **Given** the mode is `system`, **When** applied, **Then** no explicit theme attribute is forced and the OS preference wins; selecting light/dark stamps an explicit theme attribute on the document root.

---

### Edge Cases

- **Deep-linking to a design-scoped view without a selected design**: the shell does not present a design context until one is selected; design-scoped destinations are unavailable/inactive.
- **Overview with an empty portfolio**: KPI tiles render zero/empty states rather than blank or broken cards.
- **Partial query failure on Overview**: a single failing endpoint surfaces an error affordance without blanking the whole dashboard's successful sections.
- **Invalid stored theme value**: reader validates and falls back to `system`.
- **The locked C4 diagram**: switching light/dark app theme MUST NOT change the rendered C4 diagram styling, which is governed by the locked theme (ART-XII).

## Requirements *(mandatory)*

### Functional Requirements

**Application shell (supersedes ADP-SPEC-025 FR-005, FR-006)**

- **FR-001**: The web app MUST render all views inside a single persistent left-rail application shell that replaces the previous per-page top navigation bar.
- **FR-002**: The navigation destination set MUST be defined in exactly one location (the app shell component) as grouped `NavDef[]` arrays; no view may declare its own navigation item array.
- **FR-003**: The shell MUST present a Workspace group (Overview, Designs), an Architecture group (Business, Applications, Portfolio, Governance, Knowledge), and a per-design Design group (Intake, Recommendations, Canvas) that is scoped to the selected design and labelled with its identifier.
- **FR-004**: The shell MUST indicate the active view and reflect the current design context when a design is selected.
- **FR-005**: The standalone top `NavBar` component (ADP-SPEC-025 FR-005/006) MUST be removed; no page may import or render it.

**Overview landing (supersedes ADP-SPEC-025 FR-007, FR-008)**

- **FR-006**: The application's default view MUST be `Overview` when no design is selected (replacing Designs as the landing view).
- **FR-007**: The Overview dashboard MUST present live portfolio KPIs fetched from existing API endpoints (e.g. portfolio summary, applications, integrations, capabilities, value streams, domains, knowledge); it MUST NOT hard-code portfolio figures.
- **FR-008**: Overview MUST allow the user to navigate into each corresponding view via the shell's navigation callback.
- **FR-009**: Overview MUST render an explicit error affordance when an underlying query fails, and sensible empty states when data is absent, rather than fabricating or blanking figures.
- **FR-010**: The Designs view MUST remain reachable from the shell and continue to list designs and support design selection (its capabilities from ADP-SPEC-025 are retained; only its role as the default landing view is superseded).

**Design system**

- **FR-011**: A shared design-token stylesheet MUST define spacing, radius, elevation/shadow, surface, ink, border, accent, semantic (good/warn/crit), and per-domain hue (Business, Enterprise/Applications, Solution, Technology) values used across all screens.
- **FR-012**: A shared set of UI primitives (at minimum: Card, Panel, Button, Status Badge, Page Header, KPI Tile) MUST be provided and consumed by the migrated screens.
- **FR-013**: All primary screens (Designs, Intake, Recommendations, Knowledge, Governance, Portfolio, Applications, Business, Canvas chrome, Overview) MUST render through the shared design system rather than bespoke per-page styling.
- **FR-014**: Domain accent hues MUST be applied consistently between a domain's navigation item and its screens.

**Theme**

- **FR-015**: The app MUST support `light`, `dark`, and `system` theme modes, defaulting new sessions to `system`.
- **FR-016**: The theme preference MUST persist across reloads; an invalid or absent stored value MUST fall back to `system`.
- **FR-017**: `system` mode MUST defer to the OS `prefers-color-scheme` without forcing an explicit theme attribute; `light`/`dark` MUST stamp an explicit theme attribute on the document root.

**Boundary constraints**

- **FR-018**: The web design system MUST NOT modify the locked C4 diagram theme (ART-XII). The application light/dark theme MUST NOT change rendered C4 diagram styling.
- **FR-019**: This migration MUST NOT change any server-side API contract, persisted schema, or behavior of the endpoints Overview consumes.

### Key Entities *(include if feature involves data)*

- **Theme preference**: client-only state — one of `light` | `dark` | `system`, persisted in browser `localStorage`; not persisted server-side, not part of the canonical model.
- **Navigation destination**: a client-side view identifier (`AppView`) with a label, icon, optional domain hue, and grouping; no server representation.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: `grep -rln "NavDef\[\]" web/src/` resolves the navigation destination arrays to a single component (`web/src/ui/AppShell.tsx`), and no `NavBar` component file remains.
- **SC-002**: Opening the app with no selected design lands on Overview (default view is `overview`).
- **SC-003**: All ten primary screens render inside the left-rail shell and consume the shared design tokens/primitives (verifiable by component/E2E tests).
- **SC-004**: With no stored preference the app follows OS `prefers-color-scheme`; a chosen light/dark preference survives reload.
- **SC-005**: Overview KPI figures match the values returned by the underlying API endpoints (no hard-coded numbers) and degrade to error/empty states on failure/absence.
- **SC-006**: Switching app theme does not alter rendered C4 diagram styling (locked theme unaffected).

## Superseded Requirements

This spec supersedes the following ADP-SPEC-025 (Multi-Design UI and Production Readiness) requirements, which described a UI that is no longer shipped:

| ADP-SPEC-025 requirement | Original intent | Superseded by |
|---|---|---|
| FR-005 | Create a shared top `NavBar.tsx` component | FR-001–FR-005 (left-rail shell; `NavBar` removed) |
| FR-006 | All views consume `<NavBar>` and drop local `NAV_ITEMS` | FR-002 (single navigation source in the shell) |
| FR-007 | `DesignsPage` is the application landing page | FR-006 (Overview is the landing view) |
| FR-008 | Initial view is `designs` | FR-006 (initial view is `overview`); FR-010 retains Designs as a reachable view |

ADP-SPEC-025's multi-design management, design-list, and production-readiness requirements not listed above remain in force.

## Assumptions

- This spec is **ratifying**: it documents and governs UI behavior already implemented on branch `036-application-registry`. It is filed to restore ART-I / QG-01 traceability rather than to authorize net-new work.
- The migration is presentation-only; no new backend endpoints, schemas, or auth surfaces were introduced.
- The Overview dashboard reads only endpoints that already exist and are already authorized under the current auth model (ADP-SPEC-003 / ADP-SPEC-026).
- Web stack is unchanged: TypeScript 5.x + React 18 + Vite 5; no new runtime packages were required for the shell, primitives, or theming.
- The locked C4 theme (ADP-SPEC-010, ART-XII) is out of scope and unchanged.

## Dependencies

- **ADP-SPEC-025** — Multi-Design UI and Production Readiness (partially superseded; see above).
- **ADP-SPEC-010 / ART-XII** — Locked Visual Theme (boundary; unchanged).
- The screens migrated onto the design system, whose functional behavior is unchanged and continues to be governed by their own specs: ADP-SPEC-014/016/017 (Intake), 018/019/028 (Recommendations), 020 (Knowledge), 031 (Portfolio), 032 (Governance), 033/034/035 (Business), 036 (Applications), 009 (Canvas).

## Open Questions

- None. (No `[NEEDS CLARIFICATION]` items outstanding for the shipped behavior this spec ratifies.)
