# 947 Legal entities and typed geography links (GEO-02, ADP-bo1.2)

Epic ADP-bo1 (GEO). Builds on 946 GEO-01 (places, typed hierarchies, dated memberships). Absorbs
the decision bead ADP-90r.5 (legal entities as a compliance dimension): yes, ADP has legal
entities, ADP-native (epic OQ-B3).

## Why

"Where is this application?" has several answers that are all true at once: where it runs, where
its data is stored, whose personal data it processes, whose customers it serves, and which
licensed company operates it. Regulators trigger on different ones (GDPR on data subjects,
insurance regulators on licensing, DORA on the regulated financial entity). One untyped region
field gives wrong answers. GEO-03 derives framework applicability from these links.

## Decisions (user, 2026-11-20)

- **Q1** Org units also get typed, dated links. Their existing operating geographies become
  undated `operates_in` links and the old table is dropped. The primary geography stays a plain
  field. The existing `/org-units/{id}/geographies` routes keep working as `operates_in`.
- **Q1b** 941's "performer outside the unit's operating geographies" note reads the unit's
  `operates_in` links active today.
- **Q2** A legal entity may have a parent legal entity (group ownership tree) and may be linked to
  any number of org units. Nothing is inferred from `applications.owning_org_unit_id`.
- **Q3** Relations (fixed in code, a matrix says which fits which subject):

  | Subject | Relations |
  |---|---|
  | application | deployed_in, stores_data_in, processes_personal_data_of, serves_customers_in |
  | legal entity | incorporated_in, licensed_in, has_establishment_in, tax_resident_in |
  | org unit | operates_in, serves_customers_in, has_staff_in |

  `incorporated_in` must point at a place (a country) and a legal entity has at most one at any
  instant. Every other relation may point at any place or node (946 Q1), Global included.
- **Q4** UI: a "Legal entities" sub-tab on Business > Organization, a "Geography" tab on each
  application, and the org unit panel's geographies become the typed-link editor. Search indexes
  legal entities; export writes them.

## Ground truth

- GT-1 `org_unit_geographies` (940, 16 rows locally) is read by the org unit list/detail, the
  geography `org_unit_count`, the reverse lookup `/geographies/{id}/org-units`, delete cleanup, 941's
  snapshot and the seed wipe list.
- GT-2 `WRITE_BUSINESS_ARCH` and `WRITE_APPLICATION` are granted to the same roles today. Links on
  an application are served under `/api/v1/applications/...` so they ride `WRITE_APPLICATION`.
- GT-3 `adp.application` must not import `adp.organization` at store level; the organization
  package reaches applications through its narrow `applications` mirror.

## User stories

- **US1 Legal entity registry.** Create, rename, describe, give a registration number and LEI,
  set or change the parent (no cycles), delete (refused while it has child entities). Link to org
  units and applications.
- **US2 Typed links.** On an application, legal entity or org unit: add a link (relation,
  geography, optional from/until), change its dates, remove it; list links active on a date or all
  of them.
- **US3 Org unit migration.** Existing operating geographies survive as `operates_in` and every
  screen and engine that used them gives the same answer.
- **US4 UI** as in Q4.

## Requirements

- FR-001 `legal_entities`: name unique ignoring case; LEI, when given, is 20 characters `[A-Z0-9]`
  (ISO 17442, two check digits validated mod 97); optional parent; delete refused while it has
  children; deleting removes its org unit, application and geography links.
- FR-002 `legal_entity_org_units` and `application_legal_entities`: plain many-to-many links,
  duplicate 409, unknown id 404/422.
- FR-003 Three link tables of one shape (`application_geo_links`, `legal_entity_geo_links`,
  `org_unit_geo_links`): id, subject, relation, geography, valid_from (inclusive), valid_to
  (exclusive), NULL = open.
- FR-004 Rules checked on every write, refused with a message naming the rule: relation not
  allowed for the subject (422); `incorporated_in` target not a place (422); end not after start
  (422); the same subject, relation and geography already linked for part of the period (409); a
  second `incorporated_in` overlapping in time (409).
- FR-005 Relation and geography of a link are fixed; only its dates change (remove and add
  again to change the rest).
- FR-006 `GET /api/v1/business/geo-link-relations` serves the matrix with labels, so the UI has
  one source.
- FR-007 Deleting a geography (a node) removes its links; deleting an org unit or legal entity
  removes theirs (explicit deletes for SQLite parity, CASCADE as the safety net). Deleting an
  application relies on migration 058's CASCADE: `adp.application` may not import this package,
  and every read goes through an existing subject, so a dangling SQLite row never surfaces.
- FR-008 Migration 058 copies every `org_unit_geographies` row to an undated `operates_in` link
  and drops the table; downgrade recreates it from `operates_in` links (one row per unit and
  geography, dates dropped) and drops the new tables.
- FR-009 `OrgUnit.geography_ids`, `Geography.org_unit_count`, `/geographies/{id}/org-units` and
  941 all mean "`operates_in` active today".
- FR-010 Search indexes legal entities (`ENTITY_LEGAL_ENTITY`, text includes the parent path) with
  write hooks and backfill.
- FR-011 Export: `organization/legal-entities/<id>.json` (parent, org units, applications, geo
  links with dates); org unit files gain `geo_links`; the applications' links are in the legal
  entity files and in `organization/application-geo-links.json`.
- FR-012 Writes are logged with the actor. No new permission.

## Out of scope

Framework jurisdiction and applicability (GEO-03), seeds and import (GEO-04), subdivisions.
