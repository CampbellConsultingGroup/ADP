# Research: EA Pattern Registry (935)

Decisions resolving the plan's technical unknowns. Every decision cites the code it was checked against, at migration head `043`.

## D1 — Package layout: extend `adp.patterns`, keep the library pure

**Decision**: the registry lives in the existing `adp.patterns` package as new modules:
- `registry_models.py`: API models;
- `lifecycle.py`: pure transition table;
- `resolve.py`: reference resolution;
- `projection.py`: knowledge item builder;
- `render.py`: pure flowchart views;
- `store.py`;
- `router.py`.

The 934 modules (`models`, `parse`, `cel`, `cardinality`) are unchanged. `lifecycle.py`, `render.py` and the text builder in `projection.py` stay pure: no I/O and no other `adp.*` domain imports.

**Rationale**: one package per domain is the ADP convention (`adp.agentic`, `adp.compliance`). 934's contract says 935 builds on its public API rather than re-parsing.

**Cross-domain access**: the store reads `applications`, `controls` and `knowledge_items` through narrow same-database **mirror tables**. This mirrors `adp.compliance.store._knowledge_items_mirror` (`src/adp/compliance/store.py:190`) and `adp.agentic.store._applications_mirror` (`src/adp/agentic/store.py:73`). The one exception is the knowledge write in D6, which needs the embedding helper from `adp.knowledge.embedder`. That is infrastructure, not a domain package.

**Alternatives**: a new `adp.pattern_registry` package was rejected because it splits one domain in two.

## D2 — Schema (migration 044)

**Decision**: four tables. Two deliberate deviations from `docs/PATTERN-02` are noted below.

| Table | Purpose |
|---|---|
| `ea_pattern` | Family: `pattern_key` PK, `kind`, `owner_role`, `created_at/by` |
| `ea_pattern_version` | Version: UUID-string PK, FK → family (CASCADE), `version`, `lifecycle`, `name`, `summary`, `definition` JSONB, `digest`, created/changed actor+time; UNIQUE(key, version); **partial UNIQUE(key) WHERE lifecycle='current'** |
| `ea_pattern_relation` | Edge: PK(source_version_id, target_pattern_key, relation_type), FK source → version (CASCADE), `note` |
| `ea_pattern_lifecycle_event` | History: id, FK version (CASCADE), `from_state`, `to_state`, `reason`, `confirmation_id` NOT NULL, `actor`, `at`, `caused_by_event_id` (nullable self-reference) |

**Deviation 1: `target_pattern_key` has no FK.**
- FR-003 allows drafts to reference families that don't exist yet. They produce warnings and no stubs.
- A FK would force either stubs or dropping the relation row.
- The catalog query outer-joins to `ea_pattern`, and a missing target is "unresolved".
- Deleting a family (drafts only) leaves rows that point at it unresolved, which matches the spec's edge case.

**Deviation 2: no `ea_pattern_principle_link` / control-link tables.**
- Nothing in 935 needs a reverse lookup (out of scope).
- Resolution reads the ids straight from the stored definition.
- An FK + CASCADE link to `knowledge_items` would *silently remove* the link when a principle is deleted. Resolving against the definition instead keeps the reference and reports it unresolved, which is the behaviour promotion needs (US2-6).
- Control traceability that *is* assessed already lives in `control_pattern_mapping` (GT-4).

**CHECK constraints** (named, in the migration only, per convention):
- key format;
- kind;
- owner_role;
- semver;
- lifecycle;
- relation_type;
- event states.

**SQLite parity**: the store `Table` objects stay DML-only, except that the partial unique index is also declared on the store table, with both `postgresql_where` and `sqlite_where`. The SQLite contract fixture therefore enforces "one current" as well. Partial-index precedent: `031_ai_process_capture.py:316`.

## D3 — Reference resolution and issue codes

**Decision**: `resolve.py` turns a definition plus the store's lookups into issues. Lookups are batched: one query per reference type.

| Code | Reference | Resolves when |
|---|---|---|
| `R1.unresolved_principle` | `motivation.principles[i]` | An **active** knowledge item of kind `principle` has that id |
| `R2.unresolved_control` | `motivation.controls[i]` | A `controls` row has that id |
| `R3.unresolved_relation` | `relations[i].target` | An `ea_pattern` family has that key |
| `R4.unresolved_implementation` | `known_implementations[i]` | An `applications` row has that id |

These issues are `warning` on import and update, and `error` (blocking) on promotion to `current`.

Import and update outcome codes:
- `I1.version_exists_use_update`
- `I2.version_immutable`
- `I3.kind_mismatch`
- `U1.identity_changed`: the key or version differs on update.
- `U2.not_draft`

Each is a `PatternIssue` with path `""`.

**Rationale**: it uses 934's single issue shape, so the UI shows every problem in one list.

## D4 — Lifecycle mechanics

**Decision**:
- `lifecycle.allowed_transitions(state) -> frozenset[PatternLifecycle]` is pure, and the whole matrix is tested (parametrized over 5×5).
- `store.transition()` runs in one transaction:
  1. lock-free read of the version;
  2. check the transition is allowed (else 409);
  3. on `→ current`: re-parse the stored definition, run resolution at error level, demote the other current version (if any) and insert its event with `caused_by_event_id`;
  4. update the version;
  5. insert the event;
  6. refresh the projection (D6).
- A concurrent second promotion trips the partial unique index. `IntegrityError` → `ConcurrentPromotionError` → 409.

Precedent: the insert-then-catch handling of duplicates in `adp.agentic.store`.

## D5 — Confirmation (Clarification Q3)

**Decision**:
- `GOVERN_PATTERN` is added to `REQUIRES_CONFIRMATION` (`src/adp/authz/permissions.py:136`).
- `LifecycleTransitionRequest{to, reason (1–500), confirmation_id (non-empty)}` is validated by Pydantic, giving 422 before any I/O.
- This mirrors `adp.export.models` (`src/adp/export/models.py:32-40`) and the admin rubric and prompt requests.
- The confirmation id is persisted on the event row (`040_rubric_weight_management.py:54` precedent, `NOT NULL`) and written to the log line.
- The UI generates it with `crypto.randomUUID()` when the user ticks "I confirm" and submits, the same way the admin editors do.

**Note**: the audit writer's confirmation check (`src/adp/audit/writer.py:74`) applies only to `audit_entries` records, which this domain does not write (GT-3). Enforcement is therefore the request model plus the persisted column.

## D6 — Knowledge projection

**Decision**:
- **Id and source.** Item id = `source_ref` = `adp-pattern:<key>`. It is deterministic, so no link column is needed on `ea_pattern`.
- **Kind.** `reference-architecture` → `reference_architecture`; everything else → `pattern` (Clarification Q2).
- **Title.** The version name.
- **`full_text`**: the summary, then context, problem, forces, benefits, liabilities and tags, as labelled lines. It is built by the pure `projection.build_projection(defn) -> ProjectedItem`.
- **`metadata`**: `{"managed_by": "pattern-registry", "pattern_key", "pattern_version", "pattern_kind"}`. `version` = the pattern version.
- **Embedding.** It is computed **before** the transaction opens. `asyncio.to_thread` keeps the sentence-transformer call off the event loop. The shared helper is extracted from `adp.api.routers.knowledge._embed` (`src/adp/api/routers/knowledge.py:55-62`) into `adp.knowledge.embedder.embed_or_zero(title, text)`, keeping today's zero-vector fallback and adding a warning log. The knowledge router then calls the shared helper. The store takes an injectable `embed` callable, so tests never load the model.
- **Write.** An upsert keyed on id, inside the promotion transaction, through a full-column mirror of `knowledge_items` in `adp.patterns.store`. The embedding column type is `Vector(384)` with a `sa.JSON()` variant for SQLite.
- **Deactivation.** When a transition leaves a family with no current version, the store sets `active=false`. Rows are never deleted, so `control_pattern_mapping` (FK CASCADE on hard delete, `033_control_mappings.py:136`) survives.

**Alternatives**: calling `KnowledgeIndex.upsert_item` directly. It uses `postgresql.insert().on_conflict_do_update`, which can't compile on SQLite (the same problem 922 hit, CLAUDE.md), so select-then-update/insert is used instead.

## D7 — Indexer exemption (GT-6)

**Decision**:
- `KnowledgeIndex.get_all_active_ids` (`src/adp/knowledge/index.py:118-123`) gains an `exclude_source_prefixes` parameter.
- `Indexer.run` passes `("adp-pattern:",)`, so registry items are never deactivation candidates (`indexer.py:132`).

**Finding, out of scope**: the same sweep would also deactivate API-created and CALM-imported knowledge items, which are not in any connector's output either. Filed as a follow-on bead rather than widened here.

## D8 — Knowledge write guard (FR-015)

**Decision**: in `adp/api/routers/knowledge.py`:
- `PUT /{id}` and `DELETE /{id}` return **409** with `"managed by the Patterns registry — change it at /patterns/<key>"` when the item's `metadata.managed_by == "pattern-registry"` or the id starts with `adp-pattern:`.
- `POST` (create) rejects ids with that prefix, and any `metadata.managed_by = "pattern-registry"` on create or update (422), so nobody can pre-plant or fake a projection.
- *Implementation note*: `KnowledgeItemRow` also now renders `source_ref` as a link only when it is http(s) (`isHttpUrl`). A projection's `adp-pattern:` ref would otherwise be a dead link, and the existing code linked any scheme.

**UI**:
- `KnowledgeItemRow` shows a "Managed by Patterns" badge with a link and hides Edit/Delete for those items.
- The CALM import path (`calm.py`) generates its own ids, so it is unaffected.

## D9 — Compliance widening (FR-016)

**Decision**:
- `upsert_pattern_mapping` (`src/adp/compliance/store.py:794`) accepts `kind in {"pattern", "reference_architecture"}`.
- `InvalidPatternTargetError`'s message lists both kinds.
- There is no migration (the check is application-level) and no frontend change: `ControlMappingsEditor` takes a pattern target by id, and its label "Pattern" (`web/src/compliance/ControlMappingsEditor.tsx:28`) still fits.
- Existing COMPLY-02 tests that assert rejection of non-pattern kinds are updated to use kind `standard`.

## D10 — Views target the in-app flowchart dialect (GT-8)

**Decision**: `adp.patterns.render` emits text that `web/src/diagrams/core/dsl/flowchart-parser.ts` parses with zero errors. The dialect facts, checked line by line:

| Concern | Parser fact | Rule |
|---|---|---|
| Header | `%%` lines skipped anywhere (line 250); first other line must be `flowchart <dir>` (line 109) | Line 1 = provenance comment, line 2 = `flowchart LR` |
| Labels | Captured raw by `(.+)`; quotes are kept literally (lines 17-31) | **Unquoted** labels. `sanitize_label()` replaces `[]{}()<>"\|` and `#`/`;` with spaces, collapses whitespace, removes connector-like runs (`--`, `==`, `-.`, `.-`, `~~`), truncates at 60 characters with `…`, and falls back to `?` when empty |
| Line breaks | No `<br/>` support | Parts joined with ` · ` (for example `«platform» Backbone · 1`) |
| Shapes | `[ ]`, `([ ])`, `{{ }}`, `[/ /]` supported | Role `id[...]`; mediator/platform role `id([...])`; anti-pattern `id{{...}}`; plateau (936) `id[/.../]` |
| Edges | `-- label -->`, `-. label .->`, `== label ==>`, `-.-`, `-->` supported; no `x`/`o` arrowheads | Relationship `A -- type: label --> B`; `via` = `A -- type --> V` + `V --> B`; prohibited hint `A -. ✕ label .-> B`; required hint `A == label ==> B`; symmetric relations (`conflicts_with`, `alternative_to`) as a labelled dotted arrow `A -. conflicts with .-> B` (*implementation note*: chosen over the planned unlabelled `-.-`, which lost the relation type) |
| Subgraphs | Only `subgraph id [Title]`; `direction` only inside | Traceability columns: `subgraph col_motivation [Motivation]` + `direction TB` |
| Styles | `classDef` props limited to fill, stroke, stroke-width, stroke-dasharray (lines 131-141); text colour ignored | Light fills only, so the renderer's default dark text stays legible |
| Ids | `[A-Za-z0-9_]+` | Generated: roles `r_<key with - → _>`; patterns `pt_<sha1(key)[:8]>`; principles `pr_<n>`; controls `ct_<n>`; implementations `ap_<n>` (n = declared position). Role keys are `[a-z][a-z0-9_]*` (934), so roles cannot collide |

**Palette** (FR-017; only colours from `src/adp/theme/c4-theme.json`):

| Class | Fill | Stroke | Extra |
|---|---|---|---|
| `role` | `#85BBE0` | `#78A8CC` | |
| `mediator` | `#FFFFFF` | `#1168BD` | stroke-width 2px |
| `focus` | `#85BBE0` | `#08427B` | stroke-width 3px |
| `pattern` | `#FFFFFF` | `#2874A6` | |
| `antipattern` | `#FFFFFF` | `#707070` | stroke-dasharray 4 2 (the hexagon shape carries the meaning, not the colour) |
| `motivation` | `#FFFFFF` | `#08427B` | |
| `unknown` | `#FFFFFF` | `#707070` | stroke-dasharray 2 2, label suffix ` · not in registry` (catalog) / ` · not found` (traceability) |

**Legend**: a `subgraph legend [Legend]` with one node per class used (optional, `include_legend`).

**Catalog**:
- breadth-first search over relations in both directions, depth 1–3;
- node cap 40, after which `truncated` notes are added;
- the representative version is current → latest proposed → latest draft, by semantic version (Python `tuple(int)` ordering, never text order);
- deprecated versions get a ` · deprecated` suffix (*implementation note*: parentheses are dialect metacharacters and are stripped by `sanitize_label`, so the planned `(deprecated)`/`(unknown)` suffixes could not survive);
- unresolved targets use the `unknown` class.

**Goldens**:
- `tests/unit/patterns/goldens/<view>__<fixture>.mmd`, compared byte-for-byte;
- `pytest --update-goldens` (a conftest option) regenerates them, and CI never passes it;
- a vitest (`web/src/patterns/goldens.test.ts`) reads every golden through Node `fs` and asserts that `parseFlowchart` returns a model with zero errors. This replaces the bundle's mermaid-cli job (G11).

**Determinism**:
- the order is: roles as declared, relationships as declared, then hints as declared;
- catalog nodes are sorted by (depth, key);
- a 50× shuffle test covers it.

## D11 — Read-only diagram display (GT-9)

**Decision**:
- A new `web/src/patterns/FlowchartView.tsx` runs `getDslFamily("flowchart").parse(text)`, then `autoLayout(model, direction)` (`web/src/diagrams/core/model/auto-layout.ts:52`), then `renderToSvg(model)` (`core/render/svg-renderer.ts:446`).
- The SVG string is mounted as an `<img>` data URL (*implementation note*: stronger than injecting markup, since nothing in an image can execute). The renderer also escapes text nodes, which a test checks.
- Below it sits a collapsible "Flowchart source" `<pre>` with a Copy button.
- There is no interactive canvas.

## D12 — API surface and authz (GT-2)

**Decision**:
- **Router.** Prefix `/api/v1/patterns`. Literal routes (`/import`, `/validate`, `/render`) are declared before `/{key}`. Keys contain dots but no slashes, so they fit in one path segment.
- **Prefix rule.** A new rule `("/api/v1/patterns/", WRITE_PATTERN)` is added to `_PREFIX_ROUTE_ACTIONS` (`src/adp/authz/enforcement.py:146`).
- **Explicit rules** in `_EXPLICIT_ROUTE_ACTIONS` (`enforcement.py:40`):
  - `POST /api/v1/patterns/{key}/versions/{version}/lifecycle` → `GOVERN_PATTERN`;
  - `POST /api/v1/patterns/validate` and `/render` → `WRITE_PATTERN`. They are already covered by the prefix, but listed explicitly so the intent is visible.
- **Permissions.** `PERMISSIONS_VERSION` 1.10.0 → 1.11.0, with a changelog line. EA gets both new actions through its wildcard (`permissions.py:78`), and so does Platform Admin. No architect role list changes.

## D13 — Export (GT-7)

**Decision**:
- A new `src/adp/export/patterns.py` mirrors `adp.export.agentic` (newest precedent): `run_reconciliation_cycle(export_root, session)` writes `<root>/patterns/<key>@<version>.yaml` for each current version.
- **Content.** `to_canonical_yaml()` of the stored definition, the same function as the download, so the two are byte-identical by construction.
- **Writes.** Reuses `common._write_file_atomic` only after comparing existing bytes; there is no `exported_at` stamp, since YAML must stay byte-identical. That is why `_write_entity_file` is not reused.
- **Filenames.** Built by `_pattern_filename(key, version)`, which validates against the 934 key and semver regexes. Dots are allowed, and no `/` or `..` can appear.
- **Orphans.** The module's own cleanup deletes `*.yaml` files in `patterns/` that aren't in the live set.
- **Wiring.** A 5th lifespan task, `start_pattern_export`/`stop_pattern_export`, in `src/adp/api/app.py`, using the shared `ADP_BUSINESS_ARCH_EXPORT_ROOT`/`_INTERVAL_SECONDS` variables.

## D14 — UI structure (FR-021)

**Decision**:
- **Package.** A new `web/src/patterns/` with `PatternsPage` (catalog + filters), `PatternFamily` (versions), `PatternVersion` (tabs: Overview · YAML · Views · History), `ImportPanel` (paste/upload, with a prefill for "New version"), `LifecycleDialog` (allowed targets only, reason, confirm checkbox), `YamlEditor` (monospace textarea, Validate / Preview / Save), `FlowchartView` and `IssueList`.
- **API client.** `web/src/api/patterns.ts` (TanStack Query hooks, `apiGet`/`apiMutation`, as in `web/src/api/agentic.ts`).
- **Nav.** The `"patterns"` view is added to `AppView` (`web/src/shell/index.ts`), to `TITLES` and to the Oversight section (`web/src/ui/AppShell.tsx:50-57`, before Knowledge), with a case in `App.tsx`.
- **Gating.** `canManagePatterns(role) = role ∈ {enterprise_architect, platform_admin}`, from `useAuth()` (`AppShell.tsx:126`). It hides write and governance controls; the server stays authoritative.
- **Allowed transitions.** The UI gets them from the API (`allowed_transitions` in the version detail), so the client never re-encodes the state machine.
- **Editor.** No new dependency (GT-10).

## D15 — Seed (FR-023)

**Decision**:
- A new `scripts/seed_patterns.py`, with seed YAML in `scripts/seed_data/patterns/`.
- It is separate from `seed_retail.py` because it depends on `seed_knowledge.py`'s principles (`PRIN-*`).
- It imports four patterns and promotes each `draft → proposed → current` with reason "Seed" and confirmation id `seed-<key>`, calling the store directly with the real embedder.
- It is idempotent: re-running yields `unchanged` imports and skips the transitions.
- Principles cited: backbone `PRIN-003, PRIN-004`; mesh `PRIN-004`; one-SoR `PRIN-001`.

## D16 — Test strategy

| Layer | File(s) | Covers |
|---|---|---|
| Unit (pure) | `tests/unit/patterns/test_lifecycle.py`, `test_resolve.py`, `test_projection.py`, `test_render.py` (+ goldens), `test_sanitize.py` | Matrix, codes, projection text/kind, dialect rules, determinism, escaping |
| Unit (store, SQLite) | `tests/unit/patterns/test_store.py` | Import outcomes, atomic rejection, draft-only update/delete, last-version delete, promotion swap, partial index → `ConcurrentPromotionError`, deactivation, relation rows, history rows |
| Contract | `tests/contract/test_patterns_api.py` | Every route, status codes, 403s by role, 422 confirmation, YAML media type, size limit |
| Contract (touch) | `test_knowledge_api.py`, `test_compliance_mappings_api.py`, `tests/knowledge/test_indexer.py` | Guard (409), prefix create (422), widening, indexer exemption |
| Authz | `tests/authz/test_permissions.py`, `test_enforcement.py` | Version 1.11.0, new actions, completeness, Reviewer/SA/TA denied |
| Export | `tests/unit/export/test_patterns_export.py` | Byte-identical to download, unchanged = no rewrite, orphan removal, filename validation |
| Integration (Docker-gated, runs in CI) | `tests/integration/test_migration_044.py`, `test_pattern_registry.py` | Up/down, named CHECKs, partial index under real concurrency, vector projection |
| Frontend | `web/src/patterns/*.test.tsx`, `goldens.test.ts` | Catalog filters, lifecycle dialog shows only allowed transitions and requires reason + confirm, editor validate/save, gating hides controls, goldens parse |
