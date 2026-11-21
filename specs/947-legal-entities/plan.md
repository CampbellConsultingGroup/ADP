# 947 Plan

## Research decisions

- **R1 Three link tables, one code path.** One table per subject keeps real foreign keys (the
  compliance mapping precedent). `adp.organization.geo_links._SUBJECTS` describes each (table,
  subject column, subject table, label); every function takes a subject type.
- **R2 Relation matrix in code.** `RELATIONS: dict[subject, dict[relation, RelationRule]]` with
  `label`, `place_only`, `single_active`. Pure `check_link(candidate, existing, rule, is_place)`
  is unit-tested without a database.
- **R3 Dates.** Same convention as 946 memberships: `valid_from` inclusive, `valid_to` exclusive,
  NULL open. Two periods overlap when each starts before the other ends.
- **R4 Org unit compatibility.** The 940 routes `POST/DELETE /org-units/{id}/geographies[/geo]`
  stay: POST adds an undated `operates_in` link (409 if any `operates_in` link for that pair
  exists), DELETE removes every `operates_in` link for the pair.
- **R5 Routers.** `adp.organization.links_router` holds two routers registered in `adp.api.app`
  (never nested): `/api/v1/business` (legal entities, their org unit links, legal entity and org
  unit geo links, relations) and `/api/v1/applications` (an application's legal entities and geo
  links, so writes ride `WRITE_APPLICATION`). Registered before the application router; the paths
  don't collide with `/applications/{app_id}`.
- **R6 Legal entity LEI** validated with the ISO 7064 mod 97-10 check (the last two characters).
- **R7 Migration 058** (`down_revision = "057"`).

## Files

- `src/adp/store/migrations/versions/058_legal_entities_geo_links.py`
- `src/adp/organization/store.py` (tables; org unit geography functions on `operates_in`)
- `src/adp/organization/geo_links.py`, `legal_entities.py`, `links_router.py`
- `src/adp/organization/models.py`, `cap_mappings.py`, `src/adp/search`, `src/adp/export/organization.py`
- `src/adp/api/app.py`, `scripts/seed_retail.py`
- Web: `api/organization.ts`, `business/LegalEntities.tsx`, `business/GeoLinksEditor.tsx`,
  `business/OrganizationTab.tsx`, `application/ApplicationDetail.tsx` (+ `ApplicationGeography.tsx`)
