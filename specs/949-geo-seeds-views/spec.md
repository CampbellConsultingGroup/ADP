# 949 Place and hierarchy seeds, read views (GEO-04, ADP-bo1.4)

Epic ADP-bo1 (GEO). Builds on 946 (places, typed hierarchies, dated memberships), 947 (typed
geography links) and 948 (derived framework applicability).

## Why

Without seed data the geography model is empty and hand-entered country lists drift. A regulation
scoped to the EU should answer correctly for any date (the UK before and after 2020-01-31) with
nothing entered by hand, and a link to a US state should count as inside the United States.

## Decisions (user, 2026-11-21)

- **Q1** Subdivisions are added on demand, never bulk-loaded (epic note, 2026-11-20). A subdivision
  lies inside its country structurally, so it counts as inside every node the country belongs to.
  Only codes in the pinned ISO 3166-2 snapshot are accepted; the name comes from the snapshot.
  Governed custom places are seeded: Lloyd's of London (authority, inside GB) and Rest of World
  (residual, inside nothing).
- **Q2** The seeded "Regulatory blocs" hierarchy holds the EU and the EEA, with dated
  memberships checked against official sources.
- **Q3** The external (CRM) hierarchy import is deferred: which CRM and which format are still
  open. Follow-on bead.
- **Q4** Read views: an application's geography footprint (on its Geography tab) and a place x
  hierarchy matrix (Business -> Organization -> Places), API and UI. The hierarchy tree as of a
  date already exists (946).

## Ground truth

- GT-1 946's model let a place contain only itself and memberships hang only under nodes, so a
  subdivision could not be inside its country. Fixed by a structural `parent_place_id`, not by
  memberships (it is a fact about the place, not a hierarchy choice, and it is undated).
- GT-2 `geographies.code` is `String(8)`; the longest ISO 3166-2 code is 6 characters.
- GT-3 iso-codes 4.20.1 lists 5,046 subdivisions. Vendored gzipped (55 KB) with the LGPL notice in
  `data/README.md`.
- GT-4 EEA dates differ from EU dates: the EEA began 1994-01-01 (Austria, Finland and Sweden were
  in it a year before joining the EU), Liechtenstein 1995-05-01, and the EEA enlargements for
  Bulgaria/Romania and Croatia applied from 2007-08-01 and 2014-04-12, months after their EU
  accessions. The UK left both on 2020-01-31; the transition period to 2020-12-31 is not a
  membership and is not recorded (it is noted in the hierarchy's description).
- GT-5 The seed wipe in `scripts/seed_retail.py` deleted every non-reference hierarchy; it now
  keeps the regulatory blocs too.

## Requirements

- FR-001 Migration 060: `geographies.parent_place_id` (FK, indexed), CHECK on `place_type`
  (country | subdivision | authority | residual; a subdivision needs a parent place, a country
  has none); seeds the two custom places and the blocs hierarchy (2 nodes, 59 memberships) from
  `data/regulatory_blocs.json`. The hierarchy is writable (regulatory: needs write_compliance).
- FR-002 `POST /api/v1/business/geographies/subdivisions {code}` (201; 409 when already added;
  422 for a code not in the snapshot; write_business_arch) and
  `GET /api/v1/business/geographies/{country_id}/subdivisions` (the snapshot's subdivisions of
  that country, each marked `added`). Places stay read-only (no rename, no delete).
- FR-003 `GeoGraph`: a place contains itself and its subdivisions; `places(country)` includes
  them; 948 applicability follows them up (path Bavaria > Germany > EU).
- FR-004 `GET /api/v1/applications/{id}/geo-footprint?as_of=`: every place reached by the
  application's active links and its legal entities' (via), a node link expanded to its places
  (a subdivision dropped when its country is reached too), each place with its links and the
  nodes of each hierarchy containing it. Links reaching no place are listed as unresolved.
- FR-005 `GET /api/v1/business/geographies/matrix?as_of=&hierarchy_ids=`: every place (a
  subdivision right after its country) x hierarchies (reference first), each cell the nodes
  containing it.
- FR-006 Derived on read, never stored.
- FR-007 UI per Q4, plus the add-subdivision form on the Places view.

## Out of scope

CRM/external hierarchy import (follow-on), deleting a subdivision, ISO 3166-2 sub-subdivision
parents (a subdivision's parent place is always its country), EU territories with their own ISO
codes (Åland, French outermost regions, Gibraltar until 2020: can be added as members).
