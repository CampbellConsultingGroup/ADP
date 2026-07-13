# Research: Element Technology Tagging (ADP-SPEC-029)

## Key Findings

### Decision 1: Storage Architecture for FR-009 (Cross-Portfolio Queries)

**Decision**: Dual storage — extend the canonical `Element` Pydantic model AND maintain a dedicated `element_technology_tags` PostgreSQL table.

**Rationale**:
- The canonical model (stored as JSONB in `design_versions`) must include technology metadata so it travels with the design in exports (FR-006). The existing JSONB structure already carries `tags: list[str]` on each element.
- FR-009 requires cross-portfolio queries without full content scans. PostgreSQL supports JSON path queries on JSONB, but they require a full table scan across `design_versions`. A dedicated table with B-tree indexes on `technology`, `vendor`, `platform` satisfies the 2-second SC-004 requirement at 100 designs.
- The dedicated table is populated (upserted) every time tags are saved — it is a derived index, not the source of truth. The JSONB in `design_versions` remains the source of truth (ART-II).

**Alternatives considered**:
- JSONB-only with PostgreSQL JSON path indexes (`CREATE INDEX ... ON design_versions USING GIN (content)`): possible but fragile — requires extracting element arrays from the nested JSONB which is complex and version-dependent.
- Table-only without canonical model extension: would mean tags are lost on CALM/document export unless the exporter fetches the tags table separately — adds coupling and fragility.

### Decision 2: Relationship to Existing `tags: list[str]` on Element

**Decision**: Repurpose the existing `tags` field on `Element` as the free-form tags from US2. The structured fields (technology, vendor, platform, version, owner_team) are added as a new nested `technology_metadata` object on `Element`.

**Rationale**:
- `Element.tags` already exists and is already included in CALM export. Adding a new field alongside is additive and backward-compatible (ART-XV — governed schema evolution).
- Keeping `tags` as free-form strings and adding `technology_metadata` as a structured object maintains a clear separation of concerns.
- The existing `Element` model in `src/adp/models.py` uses Pydantic v2 with `extra="forbid"` — the new nested model must be properly typed.

**Alternatives considered**:
- Flatten all fields onto `Element` directly (technology, vendor, etc. as top-level fields): cleaner but pollutes the canonical element model with EA-specific metadata; the nested approach keeps EA metadata namespaced.

### Decision 3: API Surface

**Decision**: Single `PUT /api/v1/designs/{design_id}/elements/{element_id}/tags` endpoint for write; technology metadata included in the existing `GET /api/v1/designs/{design_id}` response on each element.

**Rationale**:
- Separate write endpoint keeps the concern isolated and makes audit entry generation clean — one endpoint → one audit entry.
- Including metadata in the design GET response avoids a second round-trip in the frontend when loading the InspectionPanel; the frontend already fetches the full design.
- No separate GET-by-element endpoint needed in v1 since the full design response includes everything.

### Decision 4: InspectionPanel Write Mode

**Decision**: The existing `InspectionPanel.tsx` (read-only view of element details) gains a Technology section that is read-only by default, with an "Edit" button that expands an inline edit form. The form submits via the new tags endpoint.

**Rationale**:
- The InspectionPanel is currently read-only (it doesn't save element fields like name or description either). Keeping the tagging edit in-panel avoids a new modal and is consistent with the "click to inspect" interaction model.
- Inline edit within the panel is preferred over a full modal for a small set of short-form fields.

### Decision 5: Audit Entry Content

**Decision**: The audit entry records a JSON diff of which technology metadata fields changed (old value → new value), not just "tags updated".

**Rationale**:
- SC-003 requires every change to be traceable. Knowing "technology changed from 'RabbitMQ' to 'Kafka'" is significantly more useful than "tags were updated" for governance purposes.
- Diffs are computed at the application layer by comparing the previous stored metadata with the new values before writing.

### Decision 6: No New Python Packages

**Decision**: Zero new dependencies. Uses existing SQLAlchemy 2, asyncpg, FastAPI, Pydantic v2 stack.

**Rationale**: All required capabilities (JSONB, indexed tables, REST endpoints, Pydantic models) are fully covered by the existing stack.
