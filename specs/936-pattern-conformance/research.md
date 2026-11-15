# Research: EA Pattern Adoptions, Conformance & Discovery (936)

Decisions resolving the plan's unknowns. Each cites the code it was checked against, at migration head `044`.

## D1 — Module layout

**Decision**: new modules in `adp.patterns`.

| Module | Purity | Contents |
|---|---|---|
| `conformance_models.py` | pure | Enums (`ScopeType`, `ConformanceStatus`, `FindingKind`); `ElementRef`, `Finding`, `PlateauState`, `BindingResult`, `ConformanceReport`, `DiscoveryReport`, `EvalLimits`; adoption API models; store exceptions |
| `snapshot.py` | pure | `PortfolioSnapshot` (element maps per type, evidence indexes, `unavailable_fields`), `Scope`, `in_scope()` and `GATED_FIELDS` |
| `engine.py` | pure | `resolve_bindings`, `evaluate`, `compute_conformance_status`, `compute_transition_plateau`, `discover` |
| `snapshot_store.py` | DB | `build_snapshot(session, permissions)`: a fixed set of queries |
| `adoptions.py` | DB | Adoption tables, CRUD, pin validation, version resolution |
| `render.py` | pure | Gains `render_conformance` and `render_transition` |
| `router.py` | — | New routes |

**Cross-domain reads**:
- Narrow mirror tables, as in 935: `applications` and `controls`.
- New mirrors: the integration, link, capability, domain, value-stream, technical-capability, agent and gated application tables.
- **One exception**: `tco` comes from `adp.application.store.list_all_costs()` (`src/adp/application/store.py:1042`). That avoids duplicating the eight-bucket TCO formula. The precedent is `adp.portfolio`'s heat map (919), which imports the same function for the same reason.

## D2 — Schema (migration 045)

| Table | Columns / constraints |
|---|---|
| `ea_pattern_adoption` | `id` String(36) PK; `pattern_key` → `ea_pattern` **CASCADE**; `pinned_version_id` → `ea_pattern_version` **RESTRICT**, nullable; `scope_type` CHECK in (business_domain, application_set, portfolio); `scope_ref` → `business_domains.id` **CASCADE**, nullable; `name`; `created_at/by`; `updated_at` |
| `ea_pattern_adoption_member` | PK(`adoption_id`, `application_id`); both legs CASCADE |
| `ea_pattern_adoption_pin` | PK(`adoption_id`, `role_key`, `element_type`, `element_id`); `adoption_id` CASCADE; `element_type` CHECK (the seven `ElementType` values); `element_id` TEXT with **no FK** (polymorphic, Clarification) |

Constraints:
- `ck_ea_pattern_adoption_scope_ref`: `scope_ref` is non-null iff `scope_type = 'business_domain'`.
- **Uniqueness** uses partial unique indexes instead of PATTERN-03's COALESCE sentinel:
  - `uq_ea_pattern_adoption_domain` (`pattern_key`, `scope_ref`) WHERE domain;
  - `uq_ea_pattern_adoption_portfolio` (`pattern_key`) WHERE portfolio;
  - `uq_ea_pattern_adoption_name` (`pattern_key`, `name`), which also keeps several application-set adoptions of one pattern distinct.

  The same partial indexes are declared on the store tables with `sqlite_where` (935 D2 precedent).

**RESTRICT on the pinned version** never fires in practice, because only drafts are deletable and adoptions refuse draft pins (store check). It is kept as a safety net.

**No status column anywhere**: a guard test introspects every `ea_pattern*` table.

## D3 — Snapshot construction

There is one query per source and the result is independent of estate size (FR-007):

1. Applications.
2. Integrations.
3. App ↔ capability links (`list_all_capability_links`-equivalent mirror select).
4. App ↔ technical-capability links.
5. Business capabilities.
6. Business domains.
7. Value streams and their stages: one join.
8. Technical capabilities.
9. Agents.
10. Solution memberships.
11. Gated, each only if permitted:
    - risk rows;
    - `list_all_costs`;
    - contract rows.

Derived in Python:
- `capability.domain_id` = the domain of its L1 ancestor (walk `parent_id`, cycle-safe);
- `application.domain_ids` = the sorted union over its linked capabilities;
- `integration.cross_domain` = `null` if either side has no domain, otherwise "the two endpoints share no domain".

**Values**:
- Dates become ISO strings and Decimal `tco` becomes a float. Enum values are passed through exactly as stored, e.g. `"Invest"` and `"API"`.
- Element maps contain only JSON-like values, so CEL receives plain maps and lists.

**`GATED_FIELDS`**:

```
{"security_posture", "vulnerability_status", "data_classification", "dr_bc_status",
 "end_of_life_date", "end_of_support_date", "tco", "renewal_date", "sla"}
```

`snapshot.unavailable_fields` = the gated names the caller cannot read. Those keys are **absent** from every application map, not set to null.

## D4 — Engine semantics

- **Scope.** `in_scope(snapshot, scope, element_type)` returns candidate ids following the spec's Edge Cases. The snapshot is always portfolio-wide.
- **Bindings** (FR-008):
  - A role with pins binds exactly its pins. `B2` (warning) is raised when the selector is false or errors for a pin; `B3` (error) when the element is not in the snapshot.
  - A role without pins binds the selector-true candidates. Selector errors count as false, and one `evaluation_error` finding per role summarises them.
  - Order is (name, id).
- **Missing-key classification.** CEL `missing_key` + the expression text references a name in `unavailable_fields` → `field_unavailable`. Otherwise it is an `evaluation_error`.
  - The 934 adapter already classifies missing keys (`src/adp/patterns/cel.py:114-121`).
  - The expression-name check is a conservative token match.
- **Evidence** (FR-012) is indexed from the snapshot:
  - `integrations[(src_app, tgt_app)]` → integration ids;
  - `serves[(app, bcap)]`;
  - `realizes[(app, tcap)]` (provides only).

  Direction:

  | Relationship | Edge needed |
  |---|---|
  | `publishes`, `delivers` | source → target |
  | `consumes` | target → source |
  | `integrates_with`, `depends_on` | either direction |

  Any type pair outside application↔application (integrations), application→business_capability (`serves`) or application→technical_capability (`realizes`) has no evidence source → `unverifiable`.
- **`via`.** For a relationship with `via`, evidence for a source element means an edge from it to some bound `via` element (the first hop, which is what the backbone pattern means by "publishes to the backbone"). The second hop is the relationship's own concern, since the reference fixture models `delivers` separately.
- **`E:<rel>`** only for `required: true` relationships. Offenders are the source-role elements without evidence, and the severity is error.
- **`K:<role>/<per>`** counts, for each `per` element, the role elements linked to it through the evidence of the relationship declared between the two roles (either direction).
- **Declared constraints** follow the polarity matrix (FR-010). A `for_each` role with zero bindings → nothing is evaluated (no finding).
- **Limits.** Every `evaluate()` call (selectors included) counts against `EvalLimits.max_element_evaluations` (default 50,000). The CEL library's own per-evaluation budget arrives as a `budget_exceeded` error (`cel.py`), and both map to `L1` for the current constraint.
- **Findings:**
  - one per constraint, aggregating offenders, with `element_refs` capped at 100 plus `truncated`;
  - binding findings are one per pin;
  - order: binding (`B*`), implicit (`K*`, `E*`), declared in declared order, limit.

## D5 — Status and plateau

Pure functions exactly as FR-013 and FR-014 (first match wins, consecutive plateaus). A transition pattern's report includes `plateau` and every other kind has `plateau: null`.

## D6 — Version resolution

`adoption.pinned_version_id`, otherwise the family's current version. With neither, the report is `not_applicable` with a `B1 no_current_version` finding (info), the bindings are empty, and no evaluation runs.

## D7 — API (prefix `/api/v1/patterns`)

| Method & path | Action |
|---|---|
| `GET /adoptions` (`?pattern_key=&scope_type=&with_status=true`) | read |
| `POST /adoptions` | WRITE_PATTERN (prefix rule) |
| `GET /adoptions/{id}` | read |
| `PATCH /adoptions/{id}` (name, pinned version) | WRITE_PATTERN |
| `PUT /adoptions/{id}/members` · `PUT /adoptions/{id}/pins` | WRITE_PATTERN |
| `DELETE /adoptions/{id}` | WRITE_PATTERN |
| `GET /adoptions/{id}/conformance` | read |
| `GET /adoptions/{id}/views/{conformance\|transition}` | read |
| `GET /adoptions/{id}/candidates/{role_key}` | read (pin picker: elements of the role's type, portfolio-wide) |
| `GET /{key}/versions/{version}/discover` | read |
| `POST /evaluate` (`{yaml?, pattern_key?, version?, scope}`) | WRITE_PATTERN (explicit rule) |

**Route order**: the `/adoptions…` and `/evaluate` literals are declared **before** `GET /{key}`, otherwise `/adoptions` would be captured as a pattern key.

The router extracts the caller's permissions (`is_permitted(user.role, READ_APPLICATION_*)`) and passes them to `build_snapshot`.

## D8 — Views

`render_conformance(defn, digest, report, snapshot_names, opts)`:
- one `subgraph r_<role> [Label · n]` per role;
- element nodes `e_<role>_<i>`, classed `fail` / `warn` / `unknown` / `pass` by the worst finding naming them;
- worst-first ordering, cap 8 per role, then `e_<role>_more[+k more]`;
- evidence edges for declared relationships between shown elements;
- offending integrations drawn as edges labelled with the constraint id;
- a `⚠` title suffix when a `K:<role>` finding failed.

`render_transition(defn, digest, plateau_state)`:
- the anti-pattern hexagon (`from_pattern` key) → plateaus `p_<id>[/PLn name · criteria/]` → the target (the realized pattern, if any; otherwise the pattern itself);
- `reached` and `pending` classes;
- the edge into `next` labelled `blocked: C2`.

**Palette additions** (only `c4-theme.json` colours plus the existing UI status tokens' hexes):

| Class | Style |
|---|---|
| `pass` | fill `#FFFFFF`, stroke `#1168BD` |
| `warn` | dashed stroke `#707070` |
| `fail` | stroke-width 3px, stroke `#08427B`, dasharray `1 0` |
| `unknown` | as 935 |

Plus the `reached` and `pending` plateau classes. Meaning is also carried by **label suffixes** (` · FAIL`, ` · warn`), never by colour alone (WCAG). Goldens are parsed by the existing vitest.

## D9 — UI

- `PatternsPage` gains a mode toggle: **Patterns | Adoptions**.
- **Adoptions** list, with a status badge computed by `with_status=true`.
- `AdoptionForm`: pattern, name, scope type → domain picker (business domains) or application multi-select, optional version pin.
- `AdoptionPage`:
  - status banner, plateau strip and bindings per role;
  - findings table: code, kind, severity, rule, elements;
  - conformance/transition views (via 935's `FlowchartView`);
  - a pins editor per role, using the `candidates` endpoint;
  - Save as diagram.
- `PatternVersion` gets a **Discovery** tab for anti-patterns.
- `YamlEditor` gets an **Evaluate against…** control with a scope picker.

## D10 — Save as diagram

The client parses the view's flowchart text with diagram-core's `parseFlowchart` and runs `autoLayout`, producing a `DiagramModel`. It then calls the existing `onGenerateDiagram({title, diagramType: "flowchart", model})` path from `App.tsx` (lines 90-93, 120-125). That opens the Diagrams editor unsaved, and the user saves with the existing button.

There are no backend changes and no new permission: saving requires `WRITE_DIAGRAM` as today. `PatternsPage` receives `onGenerateDiagram` as a prop.

## D11 — Seed data (Clarification Q1)

**`seed_retail.py`**:
- Drop `health_score` from `ApplicationCreate` and set it through `upsert_health_assessment` with all six dimensions equal to the seeded score, so `health_score` equals the seeded value. This fixes GT-9.
- Add the app "Enterprise Event Hub": `application_type="cots"`, `architecture_pattern="event-backbone"`, `time_classification="Invest"`. It is linked to the IT-integration technical capability "Event Streaming" (provides).
- Add `event` integrations app → hub and hub → app for the applications of **E-commerce & Digital** and **Marketing & Loyalty**, keeping the existing direct integrations.

**Expected outcome**, confirmed by running the engine during implementation and adjusted if the estate says otherwise:
- **Marketing & Loyalty**, which has no direct cross-domain integration once its applications are hub-wired: `conformant` or `conformant_with_warnings`.
- **E-commerce & Digital**, whose `commerce→erp`, `commerce→snowflake` and `oms→wms` are direct cross-domain: `non_conformant` on `C1`.

**`seed_patterns.py`** creates, after promotion:
- **Backbone** on Marketing & Loyalty and on E-commerce & Digital, pinning the hub to `backbone`;
- **Mesh-to-backbone** on E-commerce & Digital, pinning the hub: PL1 reached, PL2 blocked by `C2`.

It is idempotent, matching adoptions by name. The order is `seed_retail.py` → `seed_knowledge.py` → `seed_patterns.py`.

## D12 — Test strategy

| Layer | Files | Covers |
|---|---|---|
| Pure engine | `tests/unit/patterns/test_engine_*.py` with an in-memory snapshot builder (`tests/unit/patterns/snapshots.py`) | Binding (pins authoritative, B2/B3), cardinality incl. `per`, evidence incl. direction/`via`/unverifiable, polarity matrix, status table and precedence, field_unavailable vs evaluation_error, plateau 0/1/all, limits, determinism, reference-fixture conformance, mesh discovery |
| Snapshot store | `test_snapshot_store.py` (SQLite, mirror tables) | Domain parent walk, multi-domain, `cross_domain` null/true/false, gated omission per permission, query count bounded |
| Adoptions store | `test_adoptions_store.py` | Uniqueness per scope, members, pin validation (role/type/existence), version resolution, cascade behaviour on SQLite (explicit deletes) |
| Contract | `tests/contract/test_pattern_adoptions_api.py` | Every route, 403s, 409/422s, route order (`/adoptions` is not a key), per-caller gating |
| Render | `test_render.py` + goldens | Conformance/transition goldens, collapse, `blocked:` label; vitest parses all goldens |
| Guard | `test_conformance_not_persisted` | No status column in `ea_pattern*` |
| Integration (Docker) | `test_migration_045.py` | Constraints, partial uniques, cascades (domain/app/family), RESTRICT |
| Seed | `test_seed_patterns.py` extended; `seed_retail` smoke via SQLite is impractical (Postgres-only types), so verified live | |
| Frontend | `web/src/patterns/adoptions.test.tsx` | List/status, form scope switching, pins editor, findings, discovery tab, Save as diagram calls `onGenerateDiagram` |
