# 948 Framework jurisdiction and derived applicability (GEO-03, ADP-bo1.3)

Epic ADP-bo1 (GEO). Builds on 946 (places, typed hierarchies, dated memberships) and 947 (legal
entities, typed geography links). Supersedes ADP-90r.1 (framework applicability by geography).

## Why

Which regulations apply to an application or a legal entity is today implied by which controls
someone mapped. It should be a derived, auditable fact: a framework has a jurisdiction (places
and nodes, e.g. the EU) and trigger relations (GDPR: processes personal data of people in, has an
establishment in, serves customers in). When the regulatory map changes (a country joins a bloc,
a state adopts a law) every answer updates on read, with no backfill.

## Decisions (user, 2026-11-20)

- **Q1** An application is evaluated on its own links plus those of the legal entities linked to
  it; evidence says "via <entity>". A legal entity is evaluated on its own links only.
- **Q2** The framework's lifecycle counts: repealed, or entry into force (else effective date)
  after the date asked about, means it does not apply, with that reason. `not_yet_applicable` with
  no date also does not apply.
- **Q3** Shown on the framework (jurisdiction editor + what it applies to), on the application's
  Regulatory Mappings tab and on the legal entity, plus the API.
- **Q4** Control-mapping screens are unchanged; using applicability there is a follow-on bead.

## Ground truth

- GT-1 `RegulatoryFramework.jurisdiction` is free text (e.g. "European Union"); it stays as the
  display label (926 precedent). The structured jurisdiction is new and optional.
- GT-2 `adp.compliance` imports no other domain today; `adp.organization` never imports
  compliance. Reading organization's pure resolver and link reads from compliance makes no cycle.
- GT-3 There is no compliance export yet, so none is added here.

## Rules (FR-004)

For a framework F, a subject S and a date D:

1. F has no jurisdiction places/nodes or no trigger relations -> **unknown** ("No jurisdiction
   recorded for this framework").
2. F is repealed, or not in force on D -> **does not apply** (reason names the status or date).
3. S's links active on D whose (subject type, relation) is a trigger of F, including, for an
   application, the links of its legal entities -> if none: **unknown** ("No <relation> links
   recorded").
4. Any such link whose geography overlaps a jurisdiction geography as of D (946 resolver: same
   place, inside, or sharing countries) -> **applies**, with every matching link as evidence
   (relation, geography, jurisdiction geography, how they meet, the hierarchy path, via entity).
5. Otherwise -> **does not apply** ("None of its <relations> links are in the jurisdiction").

## Requirements

- FR-001 Migration 059: `framework_jurisdiction_geographies` (framework, geography) and
  `framework_jurisdiction_triggers` (framework, subject type, relation), composite PKs, CASCADE
  from the framework and the geography.
- FR-002 `GET/PUT /api/v1/compliance/frameworks/{id}/jurisdiction` (PUT replaces both lists;
  unknown geography 422; a relation not in 947's matrix for that subject 422; writes need
  write_compliance via the /compliance/ prefix rule).
- FR-003 Pure `compute_framework_applicability(framework, links, graph, as_of)` (no I/O).
- FR-004 The rules above.
- FR-005 `GET /api/v1/compliance/frameworks/{id}/applicability?as_of=` -> every application and
  legal entity with its result; `GET /api/v1/compliance/{applications|legal-entities}/{id}/applicability?as_of=`
  -> every framework's result for that subject.
- FR-006 Derived on read, never stored (guard test).
- FR-007 Writes logged with the actor.
- FR-008 UI per Q3.

## Out of scope

Control-mapping suggestions and status exclusion (follow-on), regulatory bloc seed data
(GEO-04), sub-national places.
