# Feature Specification: C4 Design View

**Feature Branch**: `054-c4-design-view`
**Created**: 2026-08-12
**Status**: Draft
**Input**: User description: "ADP-914.12: Build the C4 Design View, replacing C4Canvas's editing surface" — Phase B of the C4Canvas-retirement roadmap decided on ADP-914.9, following Phase A (ADP-914.11, exposing the C4 diagram format). Replaces the legacy C4 architecture-editing screen with a new one built on the diagram tool's redesigned editor, reading and writing the same governed architecture-design records C4Canvas already does today — not the separate, ungoverned standalone-diagram concept from ADP-914.11.

## Constitutional Articles Touched *(mandatory — ART-I)*

- **ART-I** — Spec-Driven Development: (always applies)
- **ART-IV** — Test-Driven Development: (always applies)
- **ART-II, ART-III** — Model is Source of Truth / Machine-Readable: applies directly — this feature is a new *editing surface* for the existing canonical architecture-design model; it must read and write that model's real, typed records, never a shadow copy or a separate format.
- **ART-V** — Security by Design: applies — see Threat Model. Reuses the design's existing permission gate; introduces no new trust boundary, but does introduce new, more narrowly-scoped write endpoints than exist today.
- **ART-IX** — Provenance and Auditability: applies — every element/relationship this feature lets a user create, edit, or delete is a canonical-model mutation and must be recorded the same way the design's other mutation paths already are.
- **ART-XI** — Traceability End to End: applies — elements carry `satisfies` (requirement links) and must continue to; this feature must not silently break that thread even where it doesn't add new UI for it (see Assumptions).
- **ART-XII** — Fixed Visual Language: applies directly — this feature's export action must produce the same governed, locked visual output the platform already guarantees, not a different, ungoverned style.
- **ART-XIII** — Typed Contracts Everywhere: applies — any new read/write surface for elements and relationships must be typed and validated, matching the rest of the platform's boundaries.
- **ART-VI–VIII, X, XIV–XVI** — do not apply beyond the ordinary level: no new observability surface beyond what mutation endpoints already carry elsewhere, no AI step, no new deterministic-gating concern, no schema-breaking change, standard documentation expectations.

## Threat Model *(mandatory — ART-V)*

**Assets at risk**: an organization's architecture designs — the same governed records the platform already protects. This feature changes how they're edited, not what's exposed to whom; anyone who could already view or edit a design's elements/relationships through the existing screen can do so through this one.

**Trust boundaries crossed**: none new. All editing stays within the existing authenticated, permission-gated design-editing surface. The one structural change — replacing a single whole-design "save everything" action with several smaller, more specific ones (add one element, draw one relationship, etc.) — narrows what a single action can affect, which reduces risk rather than adding it.

**Abuse cases**:
- A user without edit rights to a design attempts to place an element or draw a relationship anyway → blocked by the same permission check every existing design-mutation path already enforces.
- Two people editing the same design's elements at the same time → addressed under Edge Cases below; the smaller, per-element nature of the new actions limits how much a conflicting edit can clobber compared to today's all-at-once save.

**Residual risk**: standard risk of any editing surface (a mistaken edit, an accidental deletion) — mitigated by this platform's existing audit trail, which must continue to record who changed what and when, unchanged in principle by this feature.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Build and edit a design's architecture visually (Priority: P1) 🎯 MVP

An architect opens one of their organization's architecture designs and, working directly on a visual canvas, adds people, systems, containers, and components, and connects them with relationships — removing anything that's no longer needed — with every change saved to the design's real, governed record.

**Why this priority**: This is the actual point of the feature and the fix for the platform's single most visible, longest-standing gap: today, adding an element or drawing a relationship on the architecture canvas does not work at all. Every other story in this feature builds on this one working correctly.

**Independent Test**: Open an existing design; add two new elements and a relationship between them entirely by direct manipulation on the canvas (not by hand-editing text); confirm both elements and the relationship are present when the design is reloaded.

**Acceptance Scenarios**:

1. **Given** an architect is viewing a design, **When** they add a new element (choosing whether it's a person, system, container, or component), **Then** it appears on the canvas and is saved to the design's real record.
2. **Given** two elements are present, **When** an architect draws a relationship between them, **Then** the relationship appears on the canvas and is saved to the design's real record.
3. **Given** an element or relationship exists, **When** an architect deletes it, **Then** it is removed from the canvas and from the design's real record.
4. **Given** an architect makes several edits in sequence, **When** they reload the design, **Then** every edit is present exactly as made — none lost, none duplicated.

---

### User Story 2 - Work at the right level of detail (Priority: P2)

An architect moves between a design's Context, Container, and Component views while working on it, seeing only the elements appropriate to each level, with edits made at any level reflected consistently everywhere that element is visible.

**Why this priority**: Architecture is inherently multi-level (the whole premise of the C4 model this screen is named for); a single flat view would force architects back to a less useful tool. Depends on User Story 1's editing actions working, so correctly sequenced second.

**Independent Test**: Open a design containing people, systems, containers, and components; switch between Context, Container, and Component views; confirm each shows only the elements appropriate to that level (e.g. the Context view shows people and systems but not containers or components), and that an edit made at one level is visible the next time an element that also appears at another level is viewed there.

**Acceptance Scenarios**:

1. **Given** a design with elements of every kind, **When** an architect selects the Context level, **Then** only people and systems are shown.
2. **Given** the same design, **When** an architect selects the Container level, **Then** only systems and containers are shown.
3. **Given** the same design, **When** an architect selects the Component level, **Then** only containers and components are shown.
4. **Given** an element visible at more than one level, **When** an architect edits it (e.g. renames it) at one level, **Then** the change is visible the next time that element is viewed at another level.

---

### User Story 3 - Keep working technology tagging and export, uninterrupted (Priority: P2)

An architect continues to record technology details on elements (technology, vendor, platform, version, owning team) and to export a design — as a rendered diagram in the platform's official visual style, and as CALM data for external tooling — exactly as they can today, without regression.

**Why this priority**: These capabilities already work correctly today and are relied on by governance/portfolio reporting and external integrations; replacing the editing surface underneath them must not break them. Equal priority to User Story 2 — both are "don't regress" stories layered on top of User Story 1's new capability.

**Independent Test**: On a design with existing technology metadata, confirm it is still visible and editable; export the design and confirm the rendered image uses the platform's official, governed visual style (not a generic or different-looking one) and that the CALM export still succeeds.

**Acceptance Scenarios**:

1. **Given** an element with existing technology metadata, **When** an architect views it, **Then** the metadata is shown, exactly as today.
2. **Given** an element, **When** an architect edits its technology metadata, **Then** the change is saved, exactly as today.
3. **Given** a design, **When** an architect exports a rendered image of it, **Then** the image uses the platform's official, governed visual style — not a different, generic one.
4. **Given** a design, **When** an architect exports it in CALM format, **Then** the export succeeds and its content is unchanged in shape from today's export.

---

### User Story 4 - Previous work isn't lost in the transition (Priority: P3)

An architect opens a design they had already arranged visually before this feature shipped, and finds their elements positioned the way they left them, rather than reset to a generic default layout.

**Why this priority**: Real value (avoiding a jarring, work-losing first impression for existing designs), but the design's content and correctness are unaffected either way — this is about continuity of a visual arrangement, not data. Correctly lowest priority.

**Independent Test**: Open, in the new view, a design that already had a saved visual arrangement before this feature shipped; confirm elements appear in their previously-arranged positions rather than a freshly auto-generated layout.

**Acceptance Scenarios**:

1. **Given** a design with a previously-saved visual arrangement, **When** an architect opens it for the first time after this feature ships, **Then** elements appear in their previously-arranged positions.
2. **Given** a design with no previously-saved arrangement, **When** an architect opens it, **Then** elements appear in a reasonable automatic layout, exactly as new designs already do today.

---

### Edge Cases

- What happens when two architects edit the same design's elements at the same time? → Each add/edit/delete action applies to one element or relationship at a time (not a whole-design overwrite), so a conflict is limited to whichever single item both people happened to touch — a materially smaller blast radius than today's approach. Explicit real-time conflict notification (as today's screen has for whole-design saves) is out of scope for this feature; deferred as a follow-up if this narrower risk still proves to matter in practice.
- What happens to a design with no elements yet? → Opens to an empty, ready-to-author canvas, at the Context level by default.
- What happens when an architect deletes an element that has relationships attached? → Its relationships are removed along with it, so no relationship is ever left pointing at a deleted element.
- What happens to a design element's requirement links (`satisfies`) and origin tracking (whether a human or an AI step created it) through an edit made in this view? → Preserved exactly, even for edits made through this feature's own new actions — see Assumptions on why editing them directly isn't part of this feature.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: Users MUST be able to open a design's architecture model in this view, the same way they reach the design-editing screen today.
- **FR-002**: Users MUST be able to add a new element (person, system, container, or component) directly on the canvas, saved to the design's real record.
- **FR-003**: Users MUST be able to draw a relationship between two elements directly on the canvas, saved to the design's real record.
- **FR-004**: (Descoped — see Assumptions) Grouping elements into a labeled boundary is **not** part of this feature. Confirmed directly: the screen this feature replaces never had this capability either — it is genuinely new scope, not a re-plumbed existing one, and persisting it would require the platform's governed architecture-design record to gain a wholly new concept it doesn't have today. That deserves its own deliberate specification, not to be folded silently into this migration.
- **FR-005**: Users MUST be able to delete an existing element or relationship, saved to the design's real record.
- **FR-006**: Users MUST be able to switch between Context, Container, and Component levels while working on the same design, seeing only the elements appropriate to each level (Context: people and systems; Container: systems and containers; Component: containers and components — matching the platform's existing level rules).
- **FR-007**: An edit made to an element visible at more than one level MUST be reflected consistently the next time that element is viewed at any level where it appears.
- **FR-008**: Users MUST be able to view and edit an element's technology metadata (technology, vendor, platform, version, owning team, free-form tags), matching today's capability exactly.
- **FR-009**: Exporting a rendered image of a design MUST use the platform's existing official, governed visual style — never a different or generic one.
- **FR-010**: Exporting a design in CALM format MUST continue to work, unchanged in shape from today.
- **FR-011**: Every edit made through this feature MUST preserve each affected element's existing requirement links (`satisfies`), origin tracking (`provenance`), technology metadata, and tags exactly — this feature's actions must never silently drop information they don't directly present.
- **FR-012**: (Resolved) Editing an element's free-text description and its requirement links (`satisfies`) directly is explicitly **out of scope** for this feature — those remain read-only, exactly as today, until a dedicated follow-up feature addresses that pre-existing gap. This feature focuses purely on the visual/structural editing described in FR-002 through FR-005.
- **FR-013**: (Resolved) When an architect opens, for the first time in this new view, a design that already had a saved visual arrangement from the previous screen, that arrangement MUST be carried over automatically — elements MUST appear in their previously-arranged positions, not a freshly auto-generated layout. The previous screen's layout storage MAY be retired once this migration is confirmed complete.
- **FR-014**: This feature MUST NOT change how the platform's separate, standalone diagramming tool (flowcharts, sequence diagrams, and similar — introduced separately) works, looks, or stores its data — that tool and this feature's designs remain entirely distinct.
- **FR-015**: (Resolved) A design has exactly one shared set of elements, relationships, and visual arrangement — the Context/Container/Component level selector only changes which of those elements are currently shown (per FR-006), matching how the platform's existing design-editing screen already works. An edit made at one level MUST be immediately consistent when the same element is viewed at another level (FR-007); there is no independent per-level copy of an element's position or content.

### Key Entities *(include if feature involves data)*

- **Architecture Design** (existing entity, unchanged shape): the governed record this feature edits. No new fields.
- **Element** (existing entity, unchanged shape): a person, system, container, or component within a design. This feature is a new way to create, arrange, and remove these — not a change to what one is.
- **Relationship** (existing entity, unchanged shape): a connection between two elements. Same as above — new way to create and remove, not a new concept.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: An architect can add at least three elements and two relationships to a design entirely through direct canvas interaction (no hand-typed text required) and have them persist correctly on reload — directly closing today's broken add/connect gap.
- **SC-002**: An architect can move between all three C4 levels for the same design without losing any prior edit.
- **SC-003**: 100% of existing designs' technology metadata remains intact and editable after this feature ships.
- **SC-004**: Exported rendered images and CALM data, for the same underlying design content, are indistinguishable in style/shape from what the platform produced before this feature shipped.
- **SC-005**: Zero loss of requirement links, origin tracking, technology metadata, or tags on any element edited through this feature, across 100% of tested edit actions.
- **SC-006**: An architect attempting the currently-broken "add element" or "connect elements" actions succeeds on the first attempt, every time — the concrete fix for the platform's longest-standing known gap in this area.

## Assumptions

- **Multi-user conflict notification is out of scope.** The move to smaller, per-element actions (rather than one whole-design save) inherently shrinks the blast radius of a conflicting simultaneous edit; explicit notification UI for the narrower remaining risk is left as a possible follow-up, not built here.
- **The exact mechanics of adding/removing individual elements and relationships without replacing an entire design at once are a technical implementation detail**, not a user-facing choice — users only see "my action worked," not how it was carried out underneath.
- **This feature changes how a design's C4 model is edited; it does not change navigation for reaching this screen** in a way that removes anyone's access to the previous screen mid-transition — how and when the previous screen is fully retired is tracked separately, as the next step in the same roadmap this feature belongs to.
- **Standalone diagrams** (a separate, more general-purpose diagramming capability introduced earlier in this roadmap) are entirely unaffected — they have no relationship to architecture designs and this feature does not touch them.
- **Description/`satisfies` editing (FR-012) is a real, confirmed gap — not silently dropped.** It has no edit path anywhere in the platform today and is a natural fit for this newly-built screen, but is deliberately deferred to keep this already-substantial feature's scope bounded; expected to be filed as its own small, independently-valuable follow-up once this feature ships.
- **Boundary/container grouping (FR-004) is descoped, not silently dropped either.** The canvas being reused for this feature is shared with the platform's separate standalone diagramming tool, which does support drawing a visual grouping — so that control may still be visible in this screen's toolbar. Using it does not persist anything for this feature (any grouping made disappears on reload, with the elements themselves entirely unaffected); real, governed support for this concept is out of scope here and expected to be filed as its own follow-up once a deliberate decision is made on how the architecture-design record itself should represent it.
