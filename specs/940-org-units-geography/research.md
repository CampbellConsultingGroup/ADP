# Research: Org Units and Geography (940)

The spec has no open NEEDS CLARIFICATION items. These are the design decisions, checked against main at 8c8c65d (migration head `047`).

## R1 — A new package, `adp.organization`, with routes under `/api/v1/business/`

**Decision**:
- New sibling package `adp.organization`:
  - `store.py`: the tables and their logic;
  - `models.py`;
  - `router.py`: its own `APIRouter(prefix="/api/v1/business")`, registered in `src/adp/api/app.py` before the business router;
  - `data/geographies.json`.

**Rationale**:
- The business core files are already past the size threshold that led to `adp.strategy` and `adp.compliance` being split out. Org units are also reused by applications (FR-010) and, later, by 941–943.
- The `/api/v1/business/` prefix rule (`src/adp/authz/enforcement.py:161`) already gates writes with `WRITE_BUSINESS_ARCH`. No new ActionType and no `PERMISSIONS_VERSION` bump.

**Alternatives considered**:
- Folding into `adp.business.store`: rejected, the file is too large.
- A top-level `/api/v1/organization` route: needs a new prefix rule and clashes with compliance's "organization" scope (spec GT-3).

## R2 — How applications reach org units without circular imports

**Decision**:
- `applications.owning_org_unit_id` (String 36, nullable) is added to `adp.application.store._applications` as a **plain column**. The migration adds the real foreign key, with `ON DELETE SET NULL`.
- The application router checks that the org unit exists before create or update, by calling `adp.organization.store.org_unit_exists(id, session)` on the same session. The compliance and designs routers already import another domain's store this way.
- `adp.organization.store` holds a **narrow `_applications` mirror** (id, name, owning_business_unit, owning_org_unit_id). The review queue uses it to read and bulk-update.
- `delete_org_unit` clears the links explicitly, so SQLite tests behave like Postgres; the foreign key's SET NULL stays as the safety net.

**Rationale**:
- `adp.application` never imports `adp.organization` at store level.
- Mirrors are the established idiom (`adp.strategy.store`, `adp.application.store`'s `regulatory_frameworks` mirror).

**Alternatives considered**:
- A SQLAlchemy ForeignKey across metadatas: it doesn't resolve across separate `MetaData` objects.

**Known fixture gotcha**: a test fixture that creates both `astore._metadata` and `ostore._metadata` on one connection must create astore first, then ostore excluding its `applications` mirror (the 933/932 pattern).

## R3 — Hierarchy rules, reused from 937

**Decision**: one generic helper set in `adp.organization.store`, applied to both trees:
- level = parent level + 1, max 3;
- parent and level fixed after creation;
- delete refused while children exist;
- sibling names unique ignoring case, through a COALESCE(parent_id, '') expression index, as in 937 migration 046, so top-level siblings are covered too.

The errors map to HTTP the same way `app_capabilities_router._STATUS` does (404 / 409 / 422).

## R4 — The geography data file and seeding

**Decision**:
- `src/adp/organization/data/geographies.json` is generated **once** from the UN Statistics Division M49 "overview" table (public; columns: region, sub-region, country, ISO alpha-2, M49 code) and committed, with a header giving the source and retrieval date.
- Shape: `{"source", "retrieved", "regions": [{"name", "m49", "countries": [{"name", "iso2", "m49"}]}], "unassigned": [{"name","iso2"}]}`.
- Sub-regions are folded into their region (spec assumption).
- ISO 3166-1 codes missing from M49 (for example Taiwan, TW) are listed under `unassigned` and seeded directly under Global (spec edge case). Antarctica (AQ) has no M49 region and goes the same way.
- Migration `048` reads the file at upgrade time and bulk-inserts one Global row, the 5 regions and about 249 countries, with stable ids `geo-<code>` (`geo-001` for Global, `geo-m49-NNN` for regions, `geo-XX` for countries). Downgrade drops the tables.

**Rationale**:
- No new package (`pycountry` isn't installed) and nothing downloaded at runtime.
- Stable ids let 942/943 seed against known countries.
- A file is easier to review than a 250-line migration body.

**Alternatives considered**: hard-coding the list in the migration; adding `pycountry`. Both rejected.

**Verification**: a unit test loads the file and checks:
- every `iso2` is two uppercase letters and unique;
- the country count is between 240 and 260;
- there are exactly 5 regions;
- `TW` and `AQ` are in `unassigned`.

## R5 — The review queue

**Decision**:
- `list_unmatched(session)`: `SELECT owning_business_unit, count(*) FROM applications WHERE owning_org_unit_id IS NULL AND trim(owning_business_unit) <> '' GROUP BY owning_business_unit ORDER BY count DESC, value`.
- Values are compared exactly; nothing is merged automatically (spec edge case).
- `resolve_unmatched(value, org_unit_id | create{name,parent_id}, session)`, in one transaction:
  - optionally creates the org unit (same hierarchy rules);
  - then runs `UPDATE applications SET owning_org_unit_id=:id WHERE owning_business_unit=:value AND owning_org_unit_id IS NULL`;
  - returns `{org_unit, updated_count}`.
- The router logs `organization.unmatched.resolve value=… org_unit=… count=… actor=…` (FR-012).
- The free text is never written (SC-004, enforced by a test).

## R6 — Portfolio grouping

**Decision**:
- `groupByBusinessUnit(apps, orgUnitNames?)` in `web/src/portfolio/groupApplications.ts:152` gains an optional `Map<id, name>`.
- A linked application buckets under its org unit's name. An unlinked one with text buckets under `"<text> (unmatched)"`. An application with neither goes to Unclassified.
- `PortfolioPage` passes the map from `useOrgUnits()`.
- Existing callers without the map behave as before, apart from the "(unmatched)" suffix on free-text buckets. The tests asserting old bucket names are updated.

## R7 — Search, export and seed

- **Search**: `ENTITY_ORG_UNIT`, indexed on name + description + parent path, with write hooks and backfill. Geography is **not** indexed: about 250 static country names would crowd global search, and nothing in 940 needs geography search. Spec FR-015 is narrowed accordingly; see plan Complexity Tracking.
- **Export**: `adp.export.business_arch` adds `organization/org-units/<id>.json` (with `geography_ids`, `primary_geography_id`, `application_ids`) and one `organization/geographies.json` file. Orphan cleanup applies to org units.
- **Seed** (`scripts/seed_retail.py`), a new phase:
  - org tree: Retail Co → Stores, Digital, Supply Chain, Corporate → (Corporate) Finance, HR;
  - geography links: Stores → US, CA, DE; Digital → US, GB;
  - `owning_business_unit` set on about 8 applications, including "Store Systems" ×2 and the near-duplicate "Store systems" ×1, so the review queue has something to show.
