# Feature Specification: EA Pattern Metamodel & YAML Format (PATTERN-01)

**Feature Branch**: `934-pattern-metamodel`
**Created**: 2026-11-14
**Status**: Draft
**Input**: User description: "ADP-mmm.1. Spec 1 of 4 in the EA Patterns-as-Code epic (ADP-mmm). It implements `docs/PATTERN-01-metamodel-and-yaml.md` with the corrections recorded in the `docs/PATTERN-00-bundle-overview.md` addendum: a typed pattern definition, a YAML authoring format, structural and expression validation, and canonical serialization with a stable digest."

## Background and Resolved Decisions

ADP's knowledge base stores architecture patterns as searchable prose. That prose drifts away from the estate it describes, which is the same problem ADP exists to fix. The PATTERN bundle (`docs/PATTERN-00` to `05`) proposes Enterprise Architecture patterns as code. Each pattern consists of:
- **roles**: abstract slots that are later bound to real registry entities;
- **relationships** between roles;
- **constraints**: expressions evaluated over the bound elements;
- **motivation**;
- an optional **transition**: ordered plateaus.

This spec covers only the **definition format**: what a pattern is and how it is written, checked and serialized. Persistence (spec 935), evaluation against the estate (936) and CALM export (937) build on it.

The user confirmed these decisions on 2026-11-14 (epic ADP-mmm). They are inputs, not open questions:
1. The ADP database is the canonical store. YAML is an authoring and interchange format: imported through the API and exported through the existing export tree (935).
2. Each pattern family is also projected into the existing knowledge base as one item (935), so search, chat retrieval and control mappings keep working.
3. The work is split into four vertical specs (934–937), and each ships its own UI. This spec is a pure library with no UI, because nothing here is visible to a user until 935 adds the registry.

Ground-truth corrections to `docs/PATTERN-01`, checked against the code at migration head `043`:

| # | PATTERN-01 says | Reality | This spec |
|---|---|---|---|
| GT-1 | Element type `technology_standard` | ADP has no technology-standards entity, only free-text technology tags on design elements | Removed |
| GT-2 | No agent element type | The agent registry (933, `adp.agentic`) is a first-class entity | `agent` added |
| GT-3 | Relationship type `owns` | No registry link gives evidence of ownership | Removed. `serves` (application↔business capability links) and `realizes` (application↔technical capability "provides" links) are kept because evidence exists |
| GT-4 | `lifecycle` field in the authored YAML, "ignored with a warning" on import | Lifecycle is registry state (935) | Removed from the authored format. A file that contains it is rejected as an unknown field |
| GT-5 | Generated JSON Schema committed under `src/adp/patterns/schema/` and checked by its own test | ADP has an established schema-generation and drift gate (`adp-generate` / `adp-generate --check`) | The pattern schema is produced and drift-checked by that existing mechanism |
| GT-6 | Expression library choice left open (OQ-1) | No expression library is in the project today | Choosing it is a **gating step of this spec**, decided by a documented spike before the expression adapter is built |

## Clarifications

### Session 2026-11-14

- Q: Which expression engine should constraints and selectors use (`cel-python`, `common-expression-language`, or Google's `cel-expr-python`)? → A: **Decided by a time-boxed spike** that is part of this spec's planning (research.md). The spike must show:
  - support for the custom functions `role()` and `bound()`;
  - error positions at compile time;
  - a per-expression cost or time limit;
  - a detectable missing-key failure on map lookups (the next spec turns this into "field unavailable");
  - compatibility with Python 3.11.

  The adapter boundary keeps the choice reversible.
- Q: Should patterns be able to bind roles to Strategy objectives and Compliance controls directly (PATTERN-01 OQ-2)? → A: **No, not in this spec.** Controls and principles are referenced only through motivation. Direct binding can be added later by extending the element-type set.
- Q: Is 25 roles per pattern the right cap (PATTERN-01 OQ-3)? → A: **Yes.** Larger reference architectures are composed through `specializes` / `requires` relations.

## Constitutional Articles Touched *(mandatory — ART-I)*

- **ART-I** — Spec-Driven Development: (always applies)
- **ART-IV** — Test-Driven Development: (always applies). Fixture patterns, valid and one invalid fixture per rule, are written before the validators.
- **ART-II** — The Model is the Single Source of Truth: the pattern definition is the single, typed in-memory form that every later spec consumes, so none of them can reinterpret it.
- **ART-III** — Everything is Machine-Readable: patterns are authored as YAML, serialized to canonical JSON, and described by a published JSON Schema for editor autocomplete.
- **ART-V** — Security by Design: in scope. The format parses user-supplied YAML and compiles user-supplied expressions (see Threat Model).
- **ART-VII** — Grounded AI Only: not in scope. No AI is invoked.
- **ART-X** — Deterministic Validation Gating: validation is pure and deterministic. The same document always yields the same issues and the same digest.
- **ART-XIII** — Typed Contracts Everywhere: pattern kind, element type, relationship type, severity, polarity, transition strategy and view kind are closed value sets.
- **ART-XIV** — Reproducible, Drift-Free Builds: the published pattern schema is regenerated and drift-checked like every other ADP schema.
- **ART-XV** — Schema Evolution is Governed: no database change in this spec.

## Threat Model *(mandatory — ART-V)*

**Assets at risk**: API process availability (CPU and memory) when parsing or compiling untrusted pattern documents, and the integrity of the pattern digest that later specs use for idempotent import.

**Trust boundaries crossed**: none at runtime in this spec, which is a library. The next spec exposes it at browser → API, so its input is treated as untrusted from the start.

**Abuse cases**:
- **YAML alias bomb (billion laughs).** A document uses anchors and aliases to expand exponentially → aliases and anchors are rejected outright, and documents over 256 KB are rejected before parsing.
- **Arbitrary object construction through YAML tags** → only safe loading is used, so no custom tags are constructed.
- **Expensive or hostile expressions.** An attacker submits enormous or deeply nested expressions → expressions are capped at 2,000 characters. The engine is non-Turing-complete, and compilation happens under the chosen library's limits (proven in the spike).
- **Digest collision or spoofing.** Two different patterns produce the same digest, or an equal pattern produces a different digest → a SHA-256 digest over a canonical serialization, with the round-trip stability law tested on every fixture.

**Residual risk**: a worst-case expression could still be slow to *evaluate* against a large estate. Evaluation limits belong to spec 936.

## User Scenarios & Testing *(mandatory)*

The "users" of this spec are Enterprise Architects authoring pattern files, and the later ADP features (935–937) that consume the definition.

### User Story 1 - Author a pattern as YAML and get precise feedback (Priority: P1)

An Enterprise Architect writes a pattern file (for example, "Domain Event Backbone") with roles, relationships, constraints and motivation. They run it through validation and get either a valid definition or a list of issues. Each issue names the exact location (for example, `constraints[1].expr`), a stable code and a readable message.

**Why this priority**: every later feature depends on a trustworthy, typed definition. Without precise feedback, authors cannot write patterns at all.

**Independent Test**:
- Validate the reference fixture and confirm zero errors.
- Validate one invalid fixture per rule and confirm exactly the expected issue code and path.

**Acceptance Scenarios**:

1. **Given** the reference "Domain Event Backbone" fixture, **When** it is validated, **Then** it parses into a typed definition with no error-severity issues.
2. **Given** a pattern whose relationship references an undeclared role, **When** it is validated, **Then** one issue is returned with the reference-integrity code and the path of the offending field, and no exception escapes.
3. **Given** a constraint whose expression has a syntax error, **When** it is validated, **Then** the issue carries the path `constraints[N].expr` and the engine's error position.
4. **Given** a file containing a YAML alias, or larger than 256 KB, **When** it is validated, **Then** it is rejected with a single parse issue and nothing is expanded.
5. **Given** a pattern whose syntax and structure are both invalid, **When** it is validated, **Then** all issues are returned together in one list.

---

### User Story 2 - Patterns have a stable identity (canonical form and digest) (Priority: P2)

The registry (935) needs to tell whether an imported pattern is unchanged. Validating the same pattern written with different key order, cardinality longhand vs shorthand, or different whitespace must produce the same canonical YAML and the same digest. Changing any meaningful content must change the digest.

**Why this priority**: idempotent import and immutable versions in 935 depend on it, but authoring (P1) has value first.

**Independent Test**: for every valid fixture, parse → canonical YAML → parse again yields an equal definition and an identical digest. Reordering mapping keys leaves the digest unchanged; reordering roles or plateaus changes it.

**Acceptance Scenarios**:

1. **Given** a valid pattern, **When** it is exported to canonical YAML and re-parsed, **Then** the result equals the original and the digest is identical.
2. **Given** two files that differ only in mapping-key order and cardinality notation (`"2..*"` vs `{min: 2}`), **When** both are digested, **Then** the digests are equal.
3. **Given** two files that differ only in the declared order of roles, **When** both are digested, **Then** the digests differ (declared order is meaningful for rendering and plateaus).

---

### User Story 3 - Editor autocomplete from a published schema (Priority: P3)

An architect authoring in an editor gets field completion and inline type checking from a published JSON Schema for the pattern format. The schema always matches the definition the platform enforces.

**Why this priority**: it improves authoring, but validation (P1) is the real gate.

**Independent Test**: the schema-generation drift check passes after generation and fails if the definition changes without regenerating.

**Acceptance Scenarios**:

1. **Given** the published pattern schema, **When** the reference fixture is checked against it, **Then** it validates.
2. **Given** a change to the pattern definition without regeneration, **When** the drift gate runs, **Then** it fails.

---

### Edge Cases

- **Reserved role names:** a role named `it`, `scope` or `bindings` is rejected.
- **Self-loops:** a relationship whose source equals its target (for example application→application) is allowed.
- **Cardinality shorthand:** `"1"`, `"0..1"`, `"2..*"` and `"1 per <role>"` are accepted. `"*..1"`, `"1 per"` and `"0"` are rejected as invalid cardinality.
- **`per` without a link:** a `per` cardinality whose role has no declared relationship with the `per` role is rejected.
- **Anti-patterns:** every constraint must be `detect`, and the pattern may have no transition and no `replaces` relation. Every other kind must use `require` only.
- **Transitions:**
  - a transition is required if and only if the kind is `transition`;
  - plateau exit criteria must reference existing constraints;
  - each plateau's criteria must include all of the previous plateau's criteria (cumulative);
  - 1–10 plateaus.
- **Relations:** a relation that targets the pattern's own key is rejected, and so is a duplicate (type, target) pair.
- **Owner role:** anything other than `enterprise` is rejected in this release.
- **Unknown fields** anywhere, including a stray `lifecycle` (GT-4), are rejected.
- **Multi-document YAML** (`---` separating several documents) is rejected; one pattern per file.
- **Filename convention:** `<key>@<version>.yaml` is not enforced by parsing.

## Requirements *(mandatory)*

### Functional Requirements

**Definition**
- **FR-001**: The system MUST define a typed pattern definition with these fields:
  - key (dotted lowercase, 2–5 segments, e.g. `ea.integration.domain-event-backbone`);
  - semantic version (`MAJOR.MINOR.PATCH`);
  - kind: `reference-architecture`, `portfolio-rule`, `transition` or `anti-pattern`;
  - name (≤ 120 characters) and summary (≤ 500 characters);
  - owner role;
  - tags (≤ 20);
  - motivation;
  - 1–25 roles in declared order;
  - relationships, constraints and relations;
  - optional transition;
  - known implementations;
  - default views.
- **FR-002**: Each role MUST declare:
  - an element type, from `business_capability`, `value_stream`, `business_domain`, `application`, `integration`, `technical_capability` or `agent` (GT-1, GT-2);
  - a cardinality (min, optional max, optional `per` role);
  - an optional selector expression;
  - a label (≤ 60 characters), an optional stereotype (≤ 30 characters) and an optional description.
- **FR-003**: Each relationship MUST declare:
  - an id (`R` + 1–3 digits);
  - source and target roles;
  - a type, from `publishes`, `consumes`, `delivers`, `serves`, `realizes`, `depends_on` or `integrates_with` (GT-3);
  - an optional mediating (`via`) role, an optional label, and a `required` flag (default true).
- **FR-004**: Each constraint MUST declare:
  - an id (`C` + 1–3 digits);
  - a human-readable rule (≤ 280 characters);
  - an optional `for_each` role;
  - a boolean expression;
  - polarity (`require`, the default, or `detect`);
  - severity (`error`, the default, `warning` or `info`);
  - an optional render hint (prohibited edge, required edge or note, with optional source/target roles and a label).
- **FR-005**: Motivation MUST capture:
  - context and problem;
  - forces, benefits and liabilities;
  - principle identifiers and control identifiers. These are free identifiers here; 935 resolves them.
- **FR-006**: A transition MUST capture:
  - the pattern it migrates from;
  - a strategy: `strangler`, `phased-coexistence`, `parallel-run` or `big-bang`;
  - 1–10 ordered plateaus, each with an id (`PL` + 1–2 digits), a name, an optional description and a non-empty list of exit-criteria constraint ids.
- **FR-007**: Relations to other patterns MUST use the types `realizes`, `specializes`, `replaces`, `conflicts_with`, `requires` or `alternative_to`, with an optional note.

**Parsing and validation**
- **FR-008**: The system MUST parse a YAML document into the definition and accept the cardinality shorthand forms (`"1"`, `"0..1"`, `"2..*"`, `"N per <role>"`) as well as the longhand mapping.
- **FR-009**: Parsing MUST reject:
  - documents over 256 KB;
  - documents containing aliases or anchors;
  - multi-document streams;
  - non-mapping roots;
  - unknown fields at any level.
- **FR-010**: The system MUST enforce validation rules V1–V9 from `docs/PATTERN-01`, as amended by GT-1 to GT-4:
  - reserved role names;
  - reference integrity;
  - unique ids;
  - transition presence and cumulative plateaus;
  - `per` linkage;
  - anti-pattern polarity;
  - expressions compile;
  - no self or duplicate relations;
  - owner role `enterprise` only.
- **FR-011**: Every selector and constraint expression MUST be compile-checked against the declared variables:
  - `it`, `bindings` and `scope`;
  - the custom functions `role(string)`, which returns a list of ids, and `bound(element, string)`, which returns a bool.

  Compile errors MUST report the field path and the engine's position.
- **FR-012**: Validation MUST return a single list of issues, each with path, code, message and severity, and MUST NOT raise an exception for any input document.

**Canonical forms**
- **FR-013**: The system MUST produce:
  - a canonical JSON form, with mapping keys sorted but roles and all lists kept in declared order;
  - a SHA-256 digest of that form;
  - a canonical YAML form, with fixed key order, cardinality as shorthand, block style and no aliases.
- **FR-014**: Round-trip law. For every valid document, parsing the canonical YAML MUST yield an equal definition with an identical digest.

**Expression engine**
- **FR-015**: Expression compilation and evaluation MUST sit behind a replaceable engine boundary. The concrete library MUST be chosen by a documented spike against the criteria in Clarifications, before the boundary is implemented.

**Schema**
- **FR-016**: A JSON Schema for the pattern format MUST be generated from the definition and drift-checked by ADP's existing schema-generation gate (GT-5).

**Fixtures**
- **FR-017**: The feature MUST ship these fixture patterns:
  - **valid**: the reference "Domain Event Backbone" (reference architecture); a "Point-to-Point Mesh" anti-pattern; a transition pattern from the mesh to the backbone with at least two plateaus; one portfolio rule;
  - **invalid**: one per validation rule.

  The reference fixture's selectors MUST use only element attributes that exist in ADP (no application tags or technology-standard status).

### Key Entities

- **Pattern Definition**: the typed, immutable description of one version of an EA pattern. Its identity is key + version; its content identity is the digest.
- **Role**: an abstract slot (for example "backbone" or "domain application") with an element type, a cardinality and an optional selector.
- **Relationship**: a typed, optionally mediated edge between two roles.
- **Constraint**: a named rule with an expression, polarity and severity.
- **Transition / Plateau**: an ordered migration path whose plateaus are reached when their cumulative exit-criteria constraints pass.
- **Pattern Issue**: a validation finding with path, code, message and severity.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: 100% of valid fixtures validate with zero errors, and each invalid fixture yields exactly its expected issue code at the expected path.
- **SC-002**: The round-trip law holds for 100% of valid fixtures. Digests are identical across key reordering and cardinality notation, and different when the order of roles or plateaus changes.
- **SC-003**: No input document (malformed, oversized, aliased, multi-document, binary) causes an unhandled exception. Each produces at least one issue.
- **SC-004**: Validating the reference fixture completes in under 100 ms on a developer machine, including expression compilation.
- **SC-005**: The expression-engine decision is recorded with evidence for each spike criterion, and the schema drift gate passes in CI.

## Assumptions

- The definition and validators are internal library code. The first user-facing surface (import, editor, views) arrives in spec 935.
- Principle and control identifiers in motivation, relation targets and known implementations are not checked for existence here; 935 resolves them at import and promotion.
- Pattern content is not sensitive, so no permission gating applies to definitions.
- The single new runtime dependency is the expression library chosen by the spike. YAML parsing and JSON Schema support already exist in the project.
- Python 3.11 compatibility is required (the project targets 3.11+ and runs 3.12).
