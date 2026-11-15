# Feature Specification: EA Pattern Adoptions, Conformance & Discovery (PATTERN-03 + PATTERN-04 part)

**Feature Branch**: `936-pattern-conformance`
**Created**: 2026-11-14
**Status**: Draft
**Input**: User description: "ADP-mmm.3. Spec 3 of 4 in the EA Patterns-as-Code epic (ADP-mmm): pattern adoptions against a scope, a read-only portfolio snapshot built from the real registries, a pure binding/conformance engine with derived (never stored) status and transition plateau, anti-pattern discovery, conformance and transition views, and the adoption/conformance UI."

## Background and Resolved Decisions

Spec 934 defined what a pattern is. Spec 935 (PR #135) made patterns governed artifacts: a registry, a lifecycle, a knowledge-base projection, views and the Patterns screen. Patterns still say nothing about the estate.

This spec makes them **evaluate against the real portfolio**:
- An Enterprise Architect **adopts** a pattern for a scope: a business domain, an explicit set of applications, or the whole portfolio. They may pin specific elements to roles.
- ADP reads the live registries into a **snapshot**, binds registry elements to the pattern's roles, evaluates its implicit and declared constraints, and reports a **conformance status** with the offending elements. A *transition* pattern also reports which **plateau** has been reached.
- **Anti-patterns** are discovered across the whole portfolio without an adoption.

Status and plateau are **derived on read and never stored**, mirroring `compute_compliance_status()` (`src/adp/compliance/store.py`) and `compute_status()` (`src/adp/strategy/store.py`).

It implements `docs/PATTERN-03-binding-and-conformance.md` and the conformance and transition views of `docs/PATTERN-04-mermaid-views.md`, as amended by the `docs/PATTERN-00-bundle-overview.md` addendum (G1–G6). CALM export is spec 937.

Epic decisions (2026-11-14) still apply: the DB is canonical, and each spec ships its own UI.

Ground-truth corrections, checked against the code at migration head `044`:

| # | PATTERN-03 says / assumes | Reality | This spec |
|---|---|---|---|
| GT-1 | `application.domain_id` | There is no such column (`src/adp/application/store.py:111-135`). Domains can be assigned **only to L1 capabilities** (`src/adp/business/store.py:1103`), while applications link mostly to L2/L3 capabilities (`application_capability_links`) | An application's `domain_ids` is the set of domains of the **L1 ancestors** of its linked capabilities (walk `parent_id`). It can be empty or hold several domains |
| GT-2 | `time_disposition`, `r7_disposition`, `tags`, `technology_standard_status`, `risk_rating`, `annual_cost` | The real fields are `time_classification` (Tolerate/Invest/Migrate/Eliminate, title case), `r_strategy`, `pace_layer`, `lifecycle_status`, `application_type`, `hosting_model`, `architecture_pattern`, `business_criticality`, `health_score`, `tech_debt_flags`. Risk, cost and governance live in separate gated tables (`application_risk`, `application_cost` with a computed `tco`, `application_contracts`) | The snapshot exposes the real field names. Gated attributes appear only for callers holding `READ_APPLICATION_RISK` / `_COST` / `_GOVERNANCE` |
| GT-3 | Integrations carry `protocol`, `style`, `mediator_id` and endpoint domains | `application_integrations` = `id, source_app_id, target_app_id, integration_type` (`API`, `event`, `file`, `database`, `messaging`, `other`), `description` | Integration elements expose `integration_type` and both endpoints (with their derived `domain_ids`). Mediation is evidenced by app → backbone → app integrations |
| GT-4 | Evidence for `serves`/`owns`/`realizes` "to verify" | `serves` ← `application_capability_links`; `realizes` ← `application_tech_cap_links` with `usage_type='provides'`; `owns` was removed in 934 | Every relationship type has an evidence source; none is "unverifiable" (see FR-012) |
| GT-5 | `business_domain.risk_classification`, `capability.maturity`, `technology_standard` element | `business_domains.classification` (strategic/differentiating/commodity) and `risk_flags[]`; `business_capabilities.maturity_level`; no standards entity, but `agent` exists (933, 934) | The snapshot uses the real names and covers `agent`, with no standards element |
| GT-6 | `PATTERN_GOVERN` for adoption writes; a "read-only allowlist" for `POST /evaluate` | No allowlist exists; every non-GET route maps to an action (`src/adp/authz/enforcement.py`) | Adoption writes and the dry-run evaluate use `WRITE_PATTERN` (Clarification Q2) |
| GT-7 | `scope_ref UUID`, member/binding ids as UUID | All ADP ids are `String(36)`/TEXT | TEXT throughout |
| GT-8 | Pins are *added* to the selector's candidates | The reference fixture's `backbone` selector (`application_type in ['custom','saas','cots']`) matches almost every application. Its own comment says the backbone "is normally pinned by an adoption" | **Pins are authoritative for their role.** A role with ≥ 1 pin is bound to exactly its pins, and the selector only produces a `B2` warning for a pin that fails it. A role without pins is bound by its selector |
| GT-9 | Seed data can demo a non-conformant domain | The retail seed has no event-backbone application, both of its `event` integrations are point-to-point, and **`scripts/seed_retail.py` currently fails**: it passes `health_score` to `ApplicationCreate`, which forbids that field (`scripts/seed_retail.py:621-623`; `src/adp/application/models.py:185`) | The seed is fixed (health is set through the health assessment) and extended with an event hub and hub-routed integrations (Clarification Q1) |

## Clarifications

### Session 2026-11-14

- Q: How should demo data that yields a real `non_conformant` result be provided, given the retail seed has no backbone and is currently broken? → A: **Fix and extend the retail seed.** Fix the `health_score` bug. Add an "Enterprise Event Hub" application and a set of integrations routed through it, keeping some direct cross-domain integrations. `seed_patterns.py` creates demo adoptions whose evaluations show at least one `non_conformant` and one better result, plus a transition adoption with a partially reached plateau.
- Q: Who manages adoptions, and do changes need a confirmation? → A: **`WRITE_PATTERN`, with no confirmation.** An adoption only declares a scope. Conformance is derived on read, and no governed content changes.
- Q: Should conformance be evaluated without an adoption (PATTERN-03 OQ-2)? → A (informed default): **No.** Conformance needs an explicit adoption. Only anti-pattern *discovery* runs portfolio-wide without one.
- Q: Typed pin tables per element type or polymorphic (OQ-1)? → A (informed default): **polymorphic** (`element_type`, `element_id`), with a store-level existence check when pinning and a `B3 dangling_pin` finding at evaluation time, because pinned elements can be deleted later. Seven typed tables for a handful of pins is not worth it, and evaluation surfaces dangling pins anyway.
- Q: Warn when a followed `current` version changes (OQ-3), roll up into Governance (OQ-6)? → A: **Out of scope.** Both need stored history or a new dashboard.

## Constitutional Articles Touched *(mandatory — ART-I)*

- **ART-I** — Spec-Driven Development: (always applies)
- **ART-IV** — Test-Driven Development: (always applies). The pure engine is driven by in-memory snapshot fixtures before any DB or API work (the COMPLY-03 precedent).
- **ART-II** — Single Source of Truth: the snapshot is a read projection of the registries. Status is derived, never stored, and a guard test asserts that no table stores it.
- **ART-V** — Security by Design: in scope. Snapshots include sensitive application data, and expressions run against it (see Threat Model).
- **ART-VII** — Grounded AI: not in scope. No AI is invoked.
- **ART-IX** — Auditability: actor-attributed log lines for adoption writes.
- **ART-X** — Deterministic Validation Gating: the same snapshot, definition and pins always give the same report.
- **ART-XI** — Traceability: findings name the exact registry elements involved.
- **ART-XII** — Fixed Visual Language: the conformance and transition views reuse the 935 palette.
- **ART-XIII** — Typed Contracts: status, finding kind, scope type and element type are closed sets.
- **ART-XV** — Schema Evolution: migration `045`, reversible.

## Threat Model *(mandatory — ART-V)*

**Assets at risk**: sensitive application data (risk posture, cost, contracts), the availability of the API process when evaluating expressions over the portfolio, and the integrity of governance signals.

**Trust boundaries crossed**: browser → API (adoption writes, conformance reads, the dry-run evaluate) and API → database (registry reads).

**Abuse cases**:
- **Reading gated data through a pattern.** A user without `READ_APPLICATION_COST` writes a constraint such as `it.tco > 1000000` to infer costs → gated attributes are *absent* from that caller's snapshot. Expressions touching them yield `field_unavailable`, and status becomes `indeterminate` rather than leaking a pass or fail. Reports are computed per caller, never cached across callers.
- **Expensive evaluation.** A pattern with nested comprehensions over a large scope → CEL's per-evaluation iteration budget plus an `EvalLimits` cap on element evaluations per report. Exceeding either gives a `limit` finding and stops only that constraint.
- **Dangling or forged pins.** A pin naming a non-existent or wrong-type element → pins are validated on write (exists, matching element type, role exists in the resolved version), and pins dangling later become `B3` findings.
- **Unauthorised adoption changes** → `WRITE_PATTERN` (Enterprise Architect / Platform Admin), with the authz completeness test covering every new route.
- **Markup injection in views** → the same sanitised, generated-id rendering as 935, displayed as an image.

**Residual risk**: findings list element names (application or integration names), which are not sensitive in ADP. Conformance is computed synchronously per request; at demo scale (tens of apps) this is fast. Scheduling and caching are out of scope.

## User Scenarios & Testing *(mandatory)*

Actors:
- **Enterprise Architect (EA):** manages adoptions and pins.
- **Any authenticated user:** reads conformance and discovery.

### User Story 1 - See whether a domain conforms to a pattern (Priority: P1)

An EA adopts "Domain Event Backbone" for the Marketing & Loyalty domain and pins the Enterprise Event Hub as the backbone. Opening the adoption shows:
- a status: `non_conformant`;
- each role with its bound elements and count;
- every finding: `C1` names the direct cross-domain integration that bypasses the hub, and `E:R1` names a domain application that publishes nothing to the hub.

Re-opening the adoption after the registry changes shows a freshly computed result. Nothing is stored.

**Why this priority**: it is the point of the epic, turning patterns into a governance signal on the real estate.

**Independent Test**: create an adoption through the API against the seeded estate. `GET .../conformance` returns `non_conformant` with the expected finding codes and element references. Fix the offending integration in the registry and the next read reflects it.

**Acceptance Scenarios**:

1. **Given** an adoption of the backbone pattern on a domain containing a direct cross-domain integration, **When** conformance is read, **Then** the status is `non_conformant` and a `C1` finding lists that integration.
2. **Given** the same adoption with every cross-domain integration routed through the pinned hub, **When** conformance is read, **Then** no `C1` finding exists.
3. **Given** a domain with no applications, **When** conformance is read, **Then** the status is `not_applicable`.
4. **Given** an adoption that follows `current` while the family has no current version, **When** conformance is read, **Then** the status is `not_applicable` with finding `B1 no_current_version`.
5. **Given** an adoption pinned to a specific version, **When** a newer version becomes current, **Then** the adoption still evaluates its pinned version.
6. **Given** a caller without `READ_APPLICATION_COST` and a constraint reading `tco`, **When** conformance is read, **Then** that constraint yields `field_unavailable` and the status is `indeterminate`, never `conformant` or `non_conformant` on the strength of that constraint.
7. **Given** any evaluation, **When** the database schema is inspected, **Then** no column stores a conformance status or plateau.

---

### User Story 2 - Manage adoptions, members and pins (Priority: P1)

An EA creates an adoption for a pattern with a scope (domain, application set or portfolio) and an optional pinned version. For an application set they choose the members. They pin elements to roles, choosing only from elements of each role's element type. Adoptions can be renamed, re-scoped (members/pins replaced) and deleted.

**Why this priority**: without adoptions there is nothing to evaluate. Equal priority with US1 because they ship together as the MVP.

**Independent Test**: create, list, replace members and pins, and delete through the API and the UI. Invalid pins (unknown role, wrong element type, missing element) are rejected with a reason. A second adoption of the same pattern on the same scope is rejected.

**Acceptance Scenarios**:

1. **Given** a pattern and a business domain, **When** an EA creates a domain adoption, **Then** it is listed with its scope and resolved version.
2. **Given** an existing adoption of the same pattern on the same scope, **When** another is created, **Then** it is rejected (409).
3. **Given** a pin naming a role the resolved version does not declare, an element type different from the role's, or an element that does not exist, **When** pins are saved, **Then** they are rejected (422) with the reason, and no pins change.
4. **Given** an application-set adoption, **When** its members are replaced, **Then** the next evaluation uses exactly the new members.
5. **Given** a user without `WRITE_PATTERN`, **When** they try any adoption write, **Then** it is refused (403). Reading adoptions and conformance stays open.
6. **Given** an adoption whose pinned application is later deleted, **When** conformance is read, **Then** a `B3 dangling_pin` error finding appears and the adoption is still readable and editable.

---

### User Story 3 - Track migration progress with a transition pattern (Priority: P2)

An EA adopts the "Mesh to Event Backbone" transition pattern for a domain. The report shows the plateau reached (e.g. `PL1 Backbone live`), the next plateau, and the constraint ids blocking it. The transition view draws the anti-pattern, the plateaus and the target pattern, with reached plateaus highlighted and a "blocked: C2" edge into the next one.

**Why this priority**: it makes transitions measurable, but it builds on US1's engine.

**Independent Test**: with the seeded estate, the transition adoption reports `reached = PL1`, `next = PL2` and `blocking = [C2]`. Routing the remaining direct integrations through the hub moves it to PL2.

**Acceptance Scenarios**:

1. **Given** no plateau's exit criteria pass, **When** the report is read, **Then** `reached` is empty and `next` is the first plateau.
2. **Given** PL1's criteria pass and PL2's do not, **When** the report is read, **Then** `reached = PL1`, `next = PL2`, and `blocking` lists PL2's failing constraint ids.
3. **Given** all plateaus pass, **When** the report is read, **Then** `reached` is the last plateau and `next` is empty.

---

### User Story 4 - Discover anti-patterns across the portfolio (Priority: P2)

On an anti-pattern version (e.g. "Point-to-Point Mesh"), a Discovery tab lists every match in the whole portfolio, such as each direct cross-domain integration, with the elements involved and a match count. No adoption is needed, and there is no verdict: the results are information to act on.

**Why this priority**: it shows where an anti-pattern exists before anyone adopts the remedy, but it is secondary to adoption-based conformance.

**Independent Test**: discovery on the mesh pattern over the seeded estate returns the expected number of direct cross-domain integration matches. Discovery on a non-anti-pattern version is rejected (422).

**Acceptance Scenarios**:

1. **Given** the mesh anti-pattern and an estate with N direct cross-domain integrations, **When** discovery runs, **Then** N matches are listed, each naming the integration.
2. **Given** a non-anti-pattern version, **When** discovery is requested, **Then** it is refused (422).

---

### User Story 5 - See conformance as a diagram and keep it (Priority: P3)

The adoption page shows a conformance view: one group per role with its bound elements, coloured by their worst finding (fail, warn, pass, unknown), collapsing large roles to the worst N plus "+k more", with evidence edges and offending integrations labelled by constraint id. "Save as diagram" opens it in the Diagrams editor as a new flowchart diagram, ready to save. Its provenance header records the pattern, version, view and digest.

**Why this priority**: it communicates results to non-EAs, but the findings table already carries the information.

**Independent Test**: conformance and transition views for the seeded adoptions match committed golden files, and every golden parses with zero errors in the in-app flowchart dialect. "Save as diagram" lands in the Diagrams editor prefilled with the view.

**Acceptance Scenarios**:

1. **Given** a role with more elements than the display cap, **When** the view renders, **Then** the worst elements are shown first, followed by a "+k more" node with the correct k.
2. **Given** the same report rendered repeatedly with shuffled input order, **When** the outputs are compared, **Then** they are identical.
3. **Given** a conformance view, **When** "Save as diagram" is used, **Then** the Diagrams editor opens a new, unsaved flowchart diagram containing it.

---

### User Story 6 - Try a draft against the estate before proposing it (Priority: P3)

While editing a draft, an EA evaluates the unsaved YAML against a chosen scope (dry run) and sees the would-be status and findings, without storing anything.

**Why this priority**: it improves authoring, but it is not needed to govern or report.

**Independent Test**: `POST /evaluate` with draft YAML and a domain scope returns a report and stores nothing. Invalid YAML returns its parse issues.

**Acceptance Scenarios**:

1. **Given** valid draft YAML and a scope, **When** it is evaluated, **Then** a report is returned and no adoption is created.
2. **Given** invalid YAML, **When** it is evaluated, **Then** the parse issues are returned (422).

---

### Edge Cases

- **Applications with no domain** (no capability links, or capabilities whose L1 ancestor has no domain) belong to no domain scope. Under the reference fixture's selector, an integration with such an endpoint counts as cross-domain, because `all()` over an empty list is true. The snapshot therefore also exposes a precomputed `cross_domain` (true, false, or null when either side has no domain) for authors who want the stricter meaning.
- **Applications in several domains** are in every one of those domain scopes. An integration is cross-domain only when the two endpoints share no domain.
- **Domain scope membership:** an application is in scope if the domain is in its `domain_ids`. An integration is in scope if either endpoint is. Other element types (capabilities, value streams, technical capabilities, agents, domains) are in scope as follows:
  - capabilities: those whose L1 ancestor has that domain;
  - the domain itself;
  - everything else: the whole portfolio.
- **Application-set scope:** applications are exactly the members; integrations are those with at least one member endpoint.
- **Pins outside the scope** are allowed: a domain's backbone usually lives outside the domain. The snapshot is always portfolio-wide; scope only restricts selector candidates.
- **Deleting a pattern family** cascades to its adoptions. A version pinned by an adoption cannot be deleted; only drafts can be deleted anyway, and adoptions may pin only non-draft versions.
- **Deleting a business domain** cascades to adoptions scoped to it. Deleting an application removes it from application sets, and pins on it become `B3`.
- **Limits:** a report exceeding the element-evaluation cap gets an `L1 limit_exceeded` finding for the constraint that hit it, and the other constraints are still evaluated.
- **Findings with many elements** list at most 100 element references, with a truncation flag.
- **Retail re-seed:** `seed_retail.py` truncates domains and applications, which cascades to adoptions. Re-run `seed_patterns.py` afterwards to recreate the demo adoptions.

## Requirements *(mandatory)*

### Functional Requirements

**Adoptions**
- **FR-001**: The system MUST persist adoptions with:
  - pattern family;
  - optional pinned version (`null` follows the family's current version; drafts cannot be pinned);
  - scope type (`business_domain`, `application_set` or `portfolio`) and scope reference (a domain id, only for domain scope);
  - name;
  - creator and creation time.

  There MUST be at most one adoption per pattern per scope.
- **FR-002**: Application-set adoptions MUST hold their member applications. Members are removed automatically when an application is deleted.
- **FR-003**: Adoptions MUST hold pins (role, element type, element id). On write, each pin's role MUST exist in the resolved version, its element type MUST equal the role's element type, and the element MUST exist. Otherwise the whole write is rejected.
- **FR-004**: Create, rename, replace members, replace pins and delete MUST require `WRITE_PATTERN` and emit actor-attributed log lines. Reads are open to authenticated users.

**Snapshot**
- **FR-005**: The system MUST build a read-only, portfolio-wide snapshot. Each element is a plain map addressable by expressions:
  - **application:** id, name, lifecycle status, application type, TIME classification, R-strategy, pace layer, hosting model, architecture pattern, business criticality, health score, tech-debt flags, derived domain ids, and linked capability / technical-capability ids;
  - **integration:** id, integration type, description, `source` and `target` (each id, name, domain ids), and `cross_domain`;
  - **business capability:** id, name, level, parent id, domain id (of its L1 ancestor), strategic relevance, maturity level;
  - **value stream:** id, name, stage ids;
  - **business domain:** id, name, classification, risk flags;
  - **technical capability:** id, name, level, parent id;
  - **agent:** id, name, lifecycle status, autonomy level, human approval, data classification, and solution application ids.
- **FR-006**: Gated application attributes MUST be included only for callers holding the matching permission, and otherwise be absent:
  - risk (security posture, vulnerability status, data classification, DR/BC status, end-of-life and end-of-support dates) — `READ_APPLICATION_RISK`;
  - cost (TCO) — `READ_APPLICATION_COST`;
  - governance (renewal date, SLA) — `READ_APPLICATION_GOVERNANCE`.
- **FR-007**: Building the snapshot MUST use a bounded number of queries, independent of the number of elements (no N+1).

**Engine (pure)**
- **FR-008**: Binding resolution MUST, per role in declared order:
  - bind exactly the pins when the role has any (GT-8), with a `B2` warning per pin that fails the role's selector and a `B3` error per pin whose element is missing;
  - otherwise bind the in-scope elements of the role's type that pass its selector, or all of them if it has none.

  Bindings MUST be ordered by name, then id.
- **FR-009**: The engine MUST generate implicit constraints, evaluated before the declared ones:
  - `K:<role>`: bound count within the role's cardinality;
  - `K:<role>/<per>`: per-element cardinality through the linking relationship's evidence;
  - `E:<relationship>`: every source element of a *required* relationship has evidence to a target element (through the `via` role when set).
- **FR-010**: Declared constraints MUST follow the polarity semantics:
  - `require` + `for_each`: each element evaluating false is an offender;
  - `require` without `for_each`: false → one violation;
  - `detect` + `for_each`: each element evaluating true is a match;
  - `detect` without `for_each`: true → one match.

  A non-boolean result is an evaluation error. A missing key on a gated attribute is `field_unavailable`; any other missing key is an evaluation error.
- **FR-011**: Expressions MUST see these variables and functions:
  - `it` (the current element);
  - `bindings` (role → elements);
  - `scope` (element lists in scope, per type);
  - `role(k)` (bound ids);
  - `bound(e, k)`.
- **FR-012**: Relationship evidence MUST come from the registries:
  - `publishes`, `delivers`, `consumes` (direction-aware) and `integrates_with`, `depends_on` (either direction): application integrations;
  - `serves`: application ↔ business-capability links;
  - `realizes`: application → technical-capability links with usage "provides".

  A relationship between element types with no evidence source yields an `unverifiable` info finding.
- **FR-013**: Status MUST be computed by a pure function, first match wins:
  1. no role bound → `not_applicable`;
  2. any error-severity violation, binding or limit finding → `non_conformant`;
  3. any evaluation error, or field-unavailable on an error-severity constraint → `indeterminate`;
  4. any warning-severity violation → `conformant_with_warnings`;
  5. otherwise `conformant`.

  Info and unverifiable findings never lower the status.
- **FR-014**: For transition patterns, a pure function MUST return the highest consecutively reached plateau, the next plateau, and the constraint ids blocking it. A plateau is reached when none of its exit criteria has a violation, evaluation error or field-unavailable finding.
- **FR-015**: Evaluation limits MUST cap element evaluations per report (default 50,000). Exceeding the cap or the expression engine's own budget yields an error-severity `L1` limit finding for that constraint, without aborting the others.
- **FR-016**: Findings MUST carry a code, kind, severity, rule text, and up to 100 element references (type, id, name) with a truncation flag.
- **FR-017**: Discovery MUST evaluate an anti-pattern version portfolio-wide by selectors only (no pins) and return the matches and a count. Requesting it for any other kind is refused.

**API**
- **FR-018**: The system MUST expose:
  - adoption CRUD, members and pins;
  - conformance per adoption (report: adoption, pattern, version, digest, evaluated-at, per-role bound counts and bindings, findings, status, plateau);
  - discovery per version;
  - the conformance and transition views per adoption;
  - a dry-run evaluate for YAML or a stored version against a scope.

  The dry run is mapped to `WRITE_PATTERN`.
- **FR-019**: Reports MUST be computed per request and per caller (gating differs by caller). No conformance status, plateau or finding is persisted.

**Views**
- **FR-020**: The conformance and transition views MUST follow 935's dialect rules (provenance header, sanitised labels, generated ids, fixed palette, zero parse errors) and add:
  - pass/warn/fail/unknown element classes;
  - worst-first collapse per role (default 8, then "+k more");
  - reached/pending plateau classes;
  - a "blocked: …" edge label into the next plateau.

**User interface**
- **FR-021**: The Patterns screen MUST gain:
  - **Adoptions:** a list across patterns with scope and current status, plus create, edit (name, version pin, members, pins) and delete;
  - an **adoption page:** status, plateau, per-role bindings, findings table, conformance view and, for transition patterns, the transition view, plus "Save as diagram";
  - a **Discovery** tab on anti-pattern versions;
  - an **"Evaluate against…"** action in the draft editor.

  Write controls are hidden for users without the permission.
- **FR-022**: "Save as diagram" MUST open the Diagrams editor with a new, unsaved flowchart diagram built from the view's text, titled after the adoption and view.

**Seed data**
- **FR-023**: `scripts/seed_retail.py` MUST run successfully again: health scores are set through the health assessment rather than at creation. It MUST also add:
  - an "Enterprise Event Hub" application (architecture pattern "event-backbone");
  - integrations routing several domains' applications through it;
  - while keeping some direct cross-domain integrations.
- **FR-024**: `scripts/seed_patterns.py` MUST create demo adoptions such that:
  - one backbone adoption is `non_conformant`;
  - another backbone adoption is `conformant` or `conformant_with_warnings`;
  - a mesh-to-backbone transition adoption has reached a plateau with a later one still blocked.

### Key Entities

- **Adoption**: a declaration that one pattern (current or a pinned version) applies to a scope, with optional members and pins.
- **Pin**: an explicit element bound to a role of the adopted pattern.
- **Portfolio Snapshot**: an ephemeral, per-caller read projection of the registries.
- **Binding Result**: the elements bound to each role, plus binding findings.
- **Finding**: one evaluated fact (violation, match, binding, error, field-unavailable, unverifiable, limit) with the elements involved.
- **Conformance Report**: the status, plateau, bindings and findings for one adoption at one moment. Never stored.
- **Discovery Report**: the anti-pattern matches across the portfolio. Never stored.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: On the seeded estate, an EA can create an adoption, pin the backbone and read a `non_conformant` report naming the offending integration in under 3 minutes from the Patterns screen.
- **SC-002**: 100% of the status aggregation table, polarity matrix, cardinality cases, evidence cases and plateau cases are covered by automated tests on in-memory snapshots, and behave as specified.
- **SC-003**: The same estate, pattern and pins always produce an identical report (apart from the evaluation timestamp), including under shuffled input order.
- **SC-004**: A caller lacking a sensitive-read permission never gets a pass or fail decided by an attribute they cannot read.
- **SC-005**: A conformance report for the seeded estate is returned in under 1 second.
- **SC-006**: 100% of the conformance and transition view goldens parse with zero errors in the in-app diagram dialect.
- **SC-007**: No database table or column stores a conformance status, plateau or finding (schema guard test).

## Assumptions

- Estate size is demo scale (tens of applications and integrations), so per-request evaluation is acceptable. Scheduling and caching are out of scope.
- An adoption's version is resolved at read time: the pin if set, otherwise the family's current version.
- Element names are not sensitive and may appear in findings for any authenticated reader.
- The reference fixture's selectors are kept as they are. GT-8's pin rule and the `cross_domain` attribute make them usable without changing the 934/935 fixtures.

## Out of Scope

- Scheduled or continuous evaluation, conformance history and trends, notifications.
- Rolling conformance up into the Governance dashboard (PATTERN-03 OQ-6), and warning on current-version change (OQ-3).
- Implicit portfolio-wide conformance of every current pattern (OQ-2).
- Auto-remediation suggestions and AI explanations.
- CALM export (spec 937).
