# Research: Application Capabilities (937)

All decisions below were checked against the code at migration head `045`.

## D1 — Where the code lives

- **Decision**: a new sibling module, `adp.application.app_capabilities`, with its own router (`/api/v1/application-capabilities`). The tables are defined on `adp.application.store._metadata`.
- **Rationale**:
  - `adp.application.store` (2,181 lines) and `router.py` (1,141 lines) are already large. The `adp.business.value_chains` / `adp.strategy.initiatives` split precedent applies.
  - Defining the tables on the store's `_metadata` makes the foreign keys to `applications`, `technical_capabilities` and the `business_capabilities` mirror resolve, and every existing fixture's `create_all()` picks them up.
  - Technical capabilities already live in `adp.application`, and application capabilities sit beside them.
- **Alternatives**:
  - A new top-level package `adp.capabilities`. Rejected: it would need its own mirrors of three foreign tables, and it splits the application architecture domain.
  - Putting the code in `adp.business`. Rejected: permission and screen ownership are application-side (spec clarification).

## D2 — Hierarchy rules

- **Decision**: mirror technical capabilities exactly.
  - `level` is derived from the parent (no parent → 1, otherwise parent + 1). A parent at level 3 is refused with a depth error.
  - Parent and level are immutable (the update model has no `parent_id`).
  - Delete is refused while children exist.
- **Addition**: sibling names are unique, case-insensitive (FR-004). This is checked in the store, with an index on `(COALESCE(parent_id, ''), lower(name))` as the safety net. Postgres unique constraints treat NULL parents as distinct, so L1 roots need the COALESCE.
- **Rationale**: technical capabilities set the precedent (`store.py:1517-1526`, `1586`), and immutable levels keep every link valid for its lifetime (spec Edge Cases).

## D3 — Link tables

- **Decision**: three link tables, each with a composite primary key, `created_at`, and `ON DELETE CASCADE` on both legs:
  - `business_capability_app_capability_links (business_capability_id, app_capability_id)`;
  - `app_capability_tech_cap_links (app_capability_id, tech_cap_id)`;
  - `app_capability_realizations (app_capability_id, app_id)`.

  They have no other columns (spec Assumptions).
- **Level rules** are enforced in the store, inside the create function. An L1/L2 application capability, a business capability at L1/L2, or a technical capability at L1 raises `CapabilityLevelError` with a rule message. The router maps it to 422. Duplicates raise `DuplicateLinkError` → 409. Missing ends → 404.
- **Rationale**: the level of the far end must be read anyway to validate it, and the database can't express "the referenced row's level is 3".
- **Mirror change**: `adp.application.store._biz_caps` is a narrow mirror (`id`, `name`). It gains nullable `level` and `parent_id` columns so the store can validate and build L1/L2 paths. They are nullable in the mirror so fixtures that create only the application metadata still work. The real `business_capabilities` table has them `NOT NULL`.

## D4 — Deletes originating in other packages

- **Decision**:
  - Deleting an application capability removes its three kinds of link rows explicitly (the value-chain precedent: deletes behave the same on SQLite and Postgres).
  - `delete_application` and `delete_technical_capability` (same package) also delete their new link rows explicitly.
  - `adp.business.store.delete_capability` is **not** changed. Postgres `ON DELETE CASCADE` removes the business-side link rows, and every read in this module **inner-joins** the far-end table, so a dangling row (SQLite only) is never returned.
- **Rationale**: changing the business store would mean adding a mirror of an application-owned table to `adp.business`, which inverts the dependency direction. The Docker-gated migration test checks the real cascade.

## D5 — The warning is derived

- **Decision**: every application capability read model carries `technical_capability_count`, `business_capability_count` and `realization_count`, plus `warnings: list[Literal["missing_technical_capability"]]`. The warning is present when `level == 3 and technical_capability_count == 0`.
- The list endpoint computes the counts with three grouped `COUNT` queries (a fixed number of queries regardless of size). The gaps list is a client-side filter over the list (`?warning=missing_technical_capability` is also accepted server-side for API consumers).
- **Rationale**: FR-017 (never stored). The list is small, so filtering on the client needs no extra request and updates the badge and list together when a link changes (react-query invalidation of one key).
- **Guard test**: no table in the new metadata has a column named `warnings` or `missing_*`.

## D6 — Reverse lookups

- **Decision**: three read-only routes on the new router:
  - `GET /api/v1/application-capabilities/by-business-capability/{cap_id}`
  - `GET /api/v1/application-capabilities/by-technical-capability/{tc_id}`
  - `GET /api/v1/application-capabilities/by-application/{app_id}`

  Each returns application capability summaries. The business one includes each capability's realizing applications (FR-018).
- These literal segments are registered before `/{ac_id}`.
- **Rationale**: keeping every route in one module avoids the cross-package session helpers used by 922/925. GETs need no permission rule.

## D7 — Authorization

- **Decision**: one prefix rule, `("/api/v1/application-capabilities", ActionType.WRITE_APPLICATION)`, added beside the technical-capabilities rule in `src/adp/authz/enforcement.py`. No new ActionType and no `PERMISSIONS_VERSION` bump. The enforcement completeness test covers the new POST/PATCH/DELETE routes.

## D8 — Search

- **Decision**: a new `ENTITY_APPLICATION_CAPABILITY = "application_capability"`. Indexed text is name + description + L1/L2 path. Write hooks run on create, update and delete. A delete unindexes only the row itself, because a delete is refused while children exist. Backfill is added to `reindex_all()`.
- Not added to chat retrieval defaults (Out of Scope).

## D9 — Export

- **Decision**: `adp.export.application_arch` writes `applications/application-capabilities/<id>.json` with `id, name, description, level, parent_id, business_capability_ids, technical_capability_ids, realized_by_application_ids`, plus orphan cleanup.
- Bulk-fetched with four queries (one table plus three link tables), keeping the module's no-N+1 rule.

## D10 — Seed

- **Decision**: `scripts/seed_retail.py` gains a phase that builds the user's POS example:
  - business: under an L1 "Sales & Customer Transactions" > L2 "In-Store Transaction Management", the five L3s;
  - application: "Transaction Processing" > Checkout / Pricing / Payments / Returns > the five L3s;
  - technical: "Integration & Data Services" > API Services / Data Storage / Security > the five L3s;
  - the five chains, with Store POS (`Oracle Retail Xstore POS`) realizing all five.

  Existing seeded capabilities with the same names are reused, not duplicated. One extra application capability L3 ("Loyalty Points Accrual") is seeded with no technical link, to demonstrate the warning (FR-024).
- Technical L2 assignments: "API Services" ⊃ API Gateway Services, Notification Messaging; "Data Storage" ⊃ Local Data Store with Offline Sync, Distributed Caching; "Security" ⊃ Payment Tokenization (P2PE).

## D11 — Frontend

- **Decision**:
  - A fourth **Capabilities** tab on `ApplicationPage.tsx`.
  - New components in `web/src/application/`:
    - `AppCapTree.tsx` (mirrors `TechCapTree.tsx`: alphabetical siblings, add-child, warning badge);
    - `AppCapForm.tsx`;
    - `AppCapDetail.tsx` (the three link editors, with pickers filtered to valid levels);
    - `AppCapGaps.tsx`;
    - a guidance note.
  - The hooks go in a new `web/src/api/appCapabilities.ts`.
  - Read-only sections are added to:
    - `CapabilityNode.tsx` (business L3 rows: application capabilities plus their realizing applications);
    - `TechCapTree.tsx` nodes ("used by");
    - `ApplicationDetail.tsx` ("Realizes").
- **Navigation**: clicking an application capability elsewhere opens Applications → Capabilities with that capability selected. This uses the existing view-navigation callback pattern (the 3fg `onNavigateTo…` precedent) and a `focusAppCapId` state in `ApplicationPage`.
- Pickers only offer valid targets, so the 422 path is a backstop rather than the normal error path.

## D12 — Migration

- **Decision**: `046_application_capabilities.py` (`down_revision="045"`) with four tables and the sibling-name index. Downgrade drops them in reverse order. A Docker-gated `tests/integration/test_migration_046.py` covers up/down/up and both cascade directions.
