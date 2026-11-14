# PATTERN-05 — CALM export

**Bundle:** PATTERN · **Package:** `adp.patterns.calm` · **Depends on:** PATTERN-01 · **Status:** draft

## What

A pure function that exports a `reference-architecture` pattern as a **FINOS CALM pattern** (JSON Schema), together with an explicit **loss report** listing everything CALM can't represent. Solution architects can then run `calm generate` from an EA-governed starting point.

## Why

This is the "realizes" handoff from EA to Solution Architecture. CALM is a good format for the solution-level scaffold and a poor format for EA rules. Exporting keeps the EA pattern canonical and stops CALM documents from drifting into being the source of truth.

## Scope of export

| `kind` | Exportable? |
|---|---|
| `reference-architecture` | ✔ |
| `portfolio-rule`, `transition`, `anti-pattern` | ✘ → `422 not_exportable` (no topology to scaffold) |

## Pinned target

- CALM release **1.3** (current docs). Meta-schema `https://calm.finos.org/release/1.3/meta/calm.json`; node and relationship `$ref`s to `…/release/1.3/meta/core.json#/defs/node` and `#/defs/relationship`.
- Setting `ADP_CALM_RELEASE`, default `1.3`. The meta-schemas are **vendored** into `src/adp/patterns/calm/vendor/1.3/` (the reproducibility NFR: no live fetch at build or test time).

## Mapping

| PATTERN element | CALM output | Notes |
|---|---|---|
| Pattern `$id` | `https://<ADP_BASE_URL>/patterns/<key>/<version>/calm.json` | |
| `name`, `summary` | `title`, `description` | |
| Role | One `nodes.prefixItems` entry: `unique-id: {const: <role_key>}`, `node-type: {const: <mapped>}`, `name: {const: <label>}`, `description: {type: string}` (required → `[[ DESCRIPTION ]]` placeholder on generate) | One node per role, regardless of cardinality (see loss L1) |
| Role ordering | `prefixItems` order = declared role order | CALM is positional. Order is stable because PATTERN-01 preserves declaration order |
| `ElementType` → `node-type` | `application` → `service`; `integration` → *(not a node; becomes a relationship, see below)*; `business_capability`, `value_stream`, `business_domain`, `technical_capability`, `technology_standard` → **omitted** (loss L2) | `service` is the CALM node-type nearest to an ADP application. **Verify the full enumeration in the vendored 1.3 `core.json`** before finalizing; a `system` mapping for platform stereotypes is a candidate (OQ-2) |
| Required `RoleRelationship` between two exported roles | `relationships.prefixItems` entry: `unique-id: {const: "<rel_id>-<source>-<target>"}`, `relationship-type: {const: {connects: {source: {node: <source>}, destination: {node: <target>}}}}`, `description` required | `publishes`/`consumes`/`delivers`/`integrates_with`/`depends_on` → `connects`. `via` becomes two `connects` relationships through the mediator node |
| Non-required relationship | `relationships.items` candidate (`anyOf`) | Per CALM, a `calm generate` without options produces none of these, so the export **also** emits an `options` relationship listing them (`anyOf`), so they can be selected at generate time |
| `minItems` | Count of required `prefixItems`, **excluding the last entry** if it is optional | Follows CALM's documented pitfall: only the last `prefixItems` entry may be omitted |
| `realizes`, `serves`, `owns` relationships | Omitted | Loss L3: no CALM relationship type fits cleanly; candidates are `composed-of` / `interacts` (OQ-3) |
| Constraints, selectors, cardinality, motivation, transition, relations | Not representable | Recorded in the loss report; motivation is also copied into a top-level `metadata` block for human readers |

## Loss report

`CalmExportResult{pattern: dict, losses: list[CalmLoss], calm_release: str}`

| Code | Meaning |
|---|---|
| L1 `cardinality_collapsed` | A role with `min > 1` or unbounded `max` was exported as one node |
| L2 `element_type_unmapped` | A role was omitted because its element type has no CALM node equivalent |
| L3 `relationship_unmapped` | A relationship was omitted |
| L4 `constraints_dropped` | The count of constraints and selectors not carried over (always present if > 0) |
| L5 `dangling_relationship` | A relationship was omitted because one of its endpoints was omitted |

The export **succeeds with losses**. It fails (`422 empty_topology`) only if fewer than one node would be emitted.

## Files

| File | Contents |
|---|---|
| `src/adp/patterns/calm/export.py` | `export_calm_pattern(defn, release="1.3") -> CalmExportResult` (pure) |
| `src/adp/patterns/calm/mapping.py` | Mapping tables as module constants (one place to change when CALM moves) |
| `src/adp/patterns/calm/vendor/1.3/*.json` | Vendored meta-schemas, with a `SOURCE.md` recording URL and retrieval date |

## Router

`GET /api/v1/patterns/{key}/versions/{version}/export/calm` → `CalmExportResult` (read). `?download=true` returns only `pattern` with `Content-Disposition: attachment; filename=<key>@<version>.calm.json`.

## Tests

| Test | Asserts |
|---|---|
| `test_reference_fixture_export_golden` | The PATTERN-01 fixture exports to the committed golden JSON |
| `test_export_validates_against_vendored_meta_schema` | `jsonschema` validation of the output against the vendored CALM 1.3 meta-schema |
| `test_min_items_excludes_trailing_optional` | The CALM positional pitfall is handled |
| `test_options_relationship_emitted` | Optional relationships produce an `options` entry with `relationship-type.type == "object"` (CALM silently drops the decision otherwise) |
| `test_losses_reported` | Each of L1–L5 has a fixture that triggers exactly that code |
| `test_non_reference_kinds_rejected` | `portfolio-rule`, `transition` and `anti-pattern` return `422` |
| `test_calm_cli_generate` (CI job `calm-interop`, optional) | `calm generate -p <export> -o out.json` then `calm validate -p <export> -a out.json` succeed. Pinned `@finos/calm-cli` |

## Out of scope

CALM import, CALM architectures (instance documents), CALM controls/flows/metadata mapping beyond the motivation copy, multiple CALM releases at the same time.

## Open questions

| # | Question |
|---|---|
| OQ-1 | Should the export be available for `draft` versions (useful while authoring), or only for `proposed`/`current` (so solution architects never scaffold from unapproved patterns)? |
| OQ-2 | Should roles with stereotype `platform` map to CALM `system` rather than `service`? |
| OQ-3 | Should `realizes`/`serves` map to CALM `composed-of`/`interacts` when the target is exportable, or stay omitted? |
| OQ-4 | Should EA constraints be exported as CALM **controls**, so solution architectures carry the requirement reference even though CALM can't evaluate it? |
