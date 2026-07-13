<!--
SYNC IMPACT REPORT
==================
Version change: (unversioned template) → 1.0.0
Bump type: MINOR — initial ratification; all sixteen articles established for the first time.

Modified articles: none (initial constitution)

Added:
  - Preamble
  - Article I   — Spec-Driven Development is Mandatory
  - Article II  — The Model is the Single Source of Truth
  - Article III — Everything is Machine-Readable
  - Article IV  — Test-Driven Development
  - Article V   — Security by Design
  - Article VI  — Observability is Not Optional
  - Article VII — Grounded AI Only
  - Article VIII — Human-in-the-Loop for Consequence
  - Article IX  — Provenance and Auditability
  - Article X   — Deterministic Validation Gating
  - Article XI  — Traceability End to End
  - Article XII — Fixed Visual Language
  - Article XIII — Typed Contracts Everywhere
  - Article XIV — Reproducible, Drift-Free Builds
  - Article XV  — Schema Evolution is Governed
  - Article XVI — Documentation as Code
  - Quality Gate Register (QG-01 through QG-18)
  - Governance section
  - Glossary

Removed: none (initial ratification)

Templates reviewed and updated:
  ✅ .specify/templates/plan-template.md      — Constitution Check section present; gates
     populated at plan-creation time from this document. No structural edit required.
  ✅ .specify/templates/spec-template.md      — Added mandatory "Constitutional Articles
     Touched" section (ART-I) and "Threat Model" section (ART-V).
  ✅ .specify/templates/tasks-template.md     — Updated test task sections from OPTIONAL to
     MANDATORY (ART-IV); updated header note and preamble.
  ✅ .specify/templates/agent-file-template.md — Generic placeholder template; no ADP-specific
     principle references to add.
  ℹ  .specify/templates/commands/             — Directory not present in this installation.
  ℹ  README.md                                — Does not exist yet; no references to update.

Deferred TODOs: none.
-->

---
constitution_id: ADP-CONST-001
title: Constitution — AI-Assisted Architecture Design Platform (ADP)
version: 1.0.0
status: ratified
ratified: 2026-06-26
supersedes: null
methodology: spec-driven-development
normative_language: RFC-2119
precedence:
  - constitution
  - specification
  - plan
  - tasks
  - user-preference
articles:
  - { id: ART-I,    title: Spec-Driven Development is Mandatory,      level: MUST }
  - { id: ART-II,   title: The Model is the Single Source of Truth,   level: MUST }
  - { id: ART-III,  title: Everything is Machine-Readable,            level: MUST }
  - { id: ART-IV,   title: Test-Driven Development,                   level: MUST }
  - { id: ART-V,    title: Security by Design,                        level: MUST }
  - { id: ART-VI,   title: Observability is Not Optional,             level: MUST }
  - { id: ART-VII,  title: Grounded AI Only,                          level: MUST }
  - { id: ART-VIII, title: Human-in-the-Loop for Consequence,         level: MUST }
  - { id: ART-IX,   title: Provenance and Auditability,               level: MUST }
  - { id: ART-X,    title: Deterministic Validation Gating,           level: MUST }
  - { id: ART-XI,   title: Traceability End to End,                   level: MUST }
  - { id: ART-XII,  title: Fixed Visual Language,                     level: MUST }
  - { id: ART-XIII, title: Typed Contracts Everywhere,               level: MUST }
  - { id: ART-XIV,  title: Reproducible, Drift-Free Builds,           level: MUST }
  - { id: ART-XV,   title: Schema Evolution is Governed,              level: MUST }
  - { id: ART-XVI,  title: Documentation as Code,                     level: SHOULD }
---

## Preamble

This constitution governs the design and construction of the AI-Assisted Architecture Design Platform (ADP). It is the highest-precedence artifact in the project. Every specification, plan, task, and line of code is subordinate to it. Where any lower artifact, tool default, or personal preference conflicts with this constitution, this constitution wins, and the conflict MUST be resolved by changing the lower artifact or by formally amending the constitution — never by silent deviation.

ADP is a platform that produces architecture as machine-readable data, recommends solutions grounded in organizational knowledge, and validates designs with an LLM-as-a-Judge layer. Because ADP is itself an instrument of architectural rigor, it MUST be built to the standard it asks of its users. This document encodes that standard.

## How to Read This Constitution

Normative keywords (MUST, MUST NOT, SHOULD, SHOULD NOT, MAY) follow RFC 2119. A **MUST** article is non-negotiable and blocks merge when violated. A **SHOULD** article is a strong default; deviation is permitted only with a recorded, spec-level justification (an Architecture Decision Record) approved in review. Each article states its principle, its rationale, the concrete rules it imposes, and the quality gates (QG-NN, defined in the register at the end) that enforce it in CI. The front matter is the machine-readable index of this document, consistent with Article III.

## Article I — Spec-Driven Development is Mandatory

**Principle.** No implementation MAY begin without an approved specification. The build order is fixed: constitution → specification → plan → tasks → implementation.

**Rationale.** Code written ahead of an agreed spec encodes undocumented decisions and cannot be governed. SDD makes intent reviewable before effort is spent.

**Rules.**
- Every feature MUST have a specification that states its requirements, acceptance criteria, and the constitutional articles it touches, before any plan or code.
- Every pull request MUST reference the spec and task IDs it implements; PRs with no traceable spec MUST be rejected.
- Specifications MUST be machine-readable (Article III) and version-controlled alongside code.
- A change to behavior MUST be reflected as a change to its specification in the same PR.

**Enforcement.** QG-01.

## Article II — The Model is the Single Source of Truth

**Principle.** The typed domain model is authoritative. Schemas, documents, diagrams, and configuration are derived from it and MUST NOT be hand-edited as primary records.

**Rationale.** A single source eliminates the drift between what is described and what is built. ADP's own value proposition depends on this discipline; the platform MUST embody it.

**Rules.**
- `models.py` (Pydantic v2) is the source of truth for the architecture description. `architecture-description.schema.json`, generated documents, and diagram styling MUST be generated from it.
- Generated artifacts MUST NOT be edited by hand. To change a generated artifact, change its source and regenerate.
- The generator (`generate.py`) MUST be the only writer of generated files.

**Enforcement.** QG-02, QG-18.

## Article III — Everything is Machine-Readable

**Principle.** Every artifact ADP produces or relies on MUST conform to a published, versioned schema and carry typed metadata. No artifact's primary form is unstructured prose.

**Rationale.** Machine-readability is the platform's defining constraint. It is what makes designs queryable, diffable, gate-able, and consumable by other systems.

**Rules.**
- Every persisted or exported artifact MUST validate against a published schema.
- Human-readable documents (including this constitution) MUST be projections of, or carry, typed metadata that mirrors their structured form.
- Free-text fields are permitted inside typed records; free-text artifacts as systems of record are not.

**Enforcement.** QG-03.

## Article IV — Test-Driven Development

**Principle.** Tests are written before the implementation they verify. Red, then green, then refactor.

**Rationale.** TDD turns acceptance criteria into executable contracts and prevents untested code paths from accruing. It is the operational complement to SDD.

**Rules.**
- New behavior MUST be introduced by first adding a failing test derived from the spec's acceptance criteria, then making it pass.
- Schema and API boundaries MUST have contract tests; the canonical example instance (`example-adp.json`) MUST be retained as a permanent regression fixture that validates against the live schema.
- Test coverage MUST meet the project threshold (initial: 85% line coverage on application code); coverage MUST NOT regress.
- A bug fix MUST add a test that fails before the fix and passes after.
- Tests MUST be deterministic; flaky tests MUST be quarantined and fixed, not retried into green.

**Enforcement.** QG-04, QG-05.

## Article V — Security by Design

**Principle.** Security is a design input, not a later review. Every feature MUST be threat-modeled and MUST default to the least privilege and most private option.

**Rationale.** ADP handles an organization's architecture, standards, and prior solutions — sensitive intellectual property — and integrates AI and external services. Retrofitted security fails.

**Rules.**
- Each feature spec MUST include a brief threat model (assets, trust boundaries, abuse cases) proportional to its risk.
- Secrets MUST NOT appear in source, fixtures, logs, or generated artifacts; configuration secrets MUST be externalized.
- Authentication MUST be delegated to the organization's identity provider (OIDC); authorization MUST be role-based and aligned to the architect and reviewer personas.
- The platform MUST NOT perform the prohibited action classes (e.g. entering credentials, modifying access controls, irreversible deletes, fund transfers) on a user's behalf, and MUST require explicit per-action human permission for consequential actions (sending, publishing, submitting). This rule binds both the product's behavior and any agentic build tooling.
- Personal or sensitive data MUST NOT be placed in URLs, query strings, or logs.
- Dependencies MUST be scanned; known high/critical vulnerabilities MUST block release. Static analysis MUST run on every change.
- Data MUST carry and respect its classification label end to end.

**Enforcement.** QG-06, QG-07, QG-08, QG-09.

## Article VI — Observability is Not Optional

**Principle.** Every code path, and especially every AI step, MUST be observable in production through structured logs, distributed traces, and metrics.

**Rationale.** An AI system whose recommendations and judgments cannot be inspected after the fact cannot be governed, debugged, or trusted. Observability is the runtime counterpart to auditability.

**Rules.**
- Logs MUST be structured (JSON), carry a correlation/trace ID, and MUST NOT contain secrets or unclassified sensitive data.
- A correlation ID MUST be threaded through the full request, including across the intake, recommendation, and validation orchestration steps.
- Each AI orchestration step (every node in the recommendation and validation graphs) MUST emit a span recording inputs, outputs, retrieved-knowledge references, token usage, cost, and latency.
- Services MUST expose health and the standard service metrics (request rate, errors, duration; resource saturation).
- Failures MUST be surfaced explicitly; silent catch-and-continue is prohibited.

**Enforcement.** QG-10, QG-11.

## Article VII — Grounded AI Only

**Principle.** AI recommendations and validation verdicts MUST be grounded in retrieved organizational knowledge and MUST cite it. Ungrounded generation MUST NOT write to the model.

**Rationale.** The platform's purpose is to reuse existing patterns, standards, and principles — not to invent plausible-sounding architecture. Grounding is both a quality and a governance control.

**Rules.**
- Every recommendation MUST record the knowledge items (patterns, standards, principles, prior solutions) it was grounded on, with their versions.
- Every validation finding MUST cite the specific standard, principle, or pattern it judges against, with version.
- Retrieval inputs and results MUST be logged (Article VI) so a recommendation or verdict can be reconstructed.
- An AI output lacking grounding citations MUST be treated as advisory only and MUST NOT be committed to the canonical model.

**Enforcement.** QG-12.

## Article VIII — Human-in-the-Loop for Consequence

**Principle.** AI proposes; a human confirms anything consequential. AI MUST NOT autonomously commit consequential changes to the canonical model.

**Rationale.** Architects remain accountable for designs. Automation accelerates their judgment; it does not replace it.

**Rules.**
- Confirming an AI-extracted requirement, accepting a recommendation, and overriding a verdict MUST each be explicit, attributable human actions.
- Consequential or irreversible operations MUST require per-action human permission; one approval MUST NOT be generalized to later actions.
- The actor for each confirmation MUST be recorded (Article IX).

**Enforcement.** QG-13, QG-14.

## Article IX — Provenance and Auditability

**Principle.** Every mutation of the canonical model MUST be recorded in an append-only audit trail.

**Rationale.** Reviewers MUST be able to answer "who or what introduced this, from what input, and why" for any element of any design.

**Rules.**
- Each mutation MUST record origin (human or which AI step), actor, affected entity, a summary, and a timestamp.
- The audit trail MUST be append-only; entries MUST NOT be edited or deleted.
- AI-derived model elements MUST carry provenance linking them to the recommendation that produced them.

**Enforcement.** QG-13.

## Article X — Deterministic Validation Gating

**Principle.** LLM-as-a-Judge produces scored, cited verdicts; the pass/fail decision derived from those scores MUST be deterministic and reproducible.

**Rationale.** "Approved" must mean the same thing every time. Non-deterministic gating cannot be a basis for governance.

**Rules.**
- Validation MUST run as independent critics (fan-out), each scoped to one dimension and each citing its source.
- Gating thresholds MUST be explicit configuration; given the same critic scores, the gate decision MUST be identical.
- A human MAY override a verdict, but the override MUST be explicit and recorded with justification (Article VIII, Article IX).

**Enforcement.** QG-15.

## Article XI — Traceability End to End

**Principle.** Every design element MUST trace to the requirement it serves and, where AI-derived, to its recommendation; every design version MUST trace to the verdicts that evaluated it.

**Rationale.** Traceability is what lets a reviewer ask "why does this exist?" and receive a machine-answerable response. It is the connective tissue of governance.

**Rules.**
- An element with no satisfied requirement is an orphan and MUST fail validation.
- References MUST be referentially intact: every relationship endpoint, `satisfies`, `provenance`, and finding target MUST resolve to an existing entity.
- The requirement → element → recommendation → verdict thread MUST be queryable.

**Enforcement.** QG-16.

## Article XII — Fixed Visual Language

**Principle.** Diagram styling is locked, derived from element type, and non-overridable per diagram.

**Rationale.** Visual consistency across every architect's work is a product guarantee. Per-diagram styling choices destroy it.

**Rules.**
- The locked theme (`c4-theme.json`) is the only styling the renderer applies; element styling MUST derive from the element's type, not from per-diagram input.
- The theme MUST validate against the theme schema and MUST be marked locked.
- A change to the visual language MUST be a deliberate, versioned, reviewed change to the theme artifact — never an ad-hoc override.

**Enforcement.** QG-17.

## Article XIII — Typed Contracts Everywhere

**Principle.** Every boundary — service, API, persistence, AI step — MUST exchange typed, validated data.

**Rationale.** Untyped dicts crossing boundaries defeat machine-readability and hide errors until runtime. The platform is Python-first and MUST exploit that with typed models.

**Rules.**
- Pydantic v2 models MUST define every boundary payload; models MUST set `extra="forbid"` so unknown fields are rejected.
- API requests and responses MUST validate against the published schema; the OpenAPI contract MUST be generated, not hand-maintained.
- Inter-service data MUST NOT be passed as untyped dictionaries.

**Enforcement.** QG-03, QG-05.

## Article XIV — Reproducible, Drift-Free Builds

**Principle.** Generated artifacts MUST be reproducible, and the repository MUST never contain a generated artifact that differs from what its source would produce.

**Rationale.** Reproducibility is what makes "the model is the source of truth" verifiable rather than aspirational.

**Rules.**
- CI MUST regenerate all generated artifacts and fail if any committed file would change (`generate.py --check` semantics).
- Dependencies MUST be pinned; builds MUST be reproducible from a clean checkout.

**Enforcement.** QG-02, QG-18.

## Article XV — Schema Evolution is Governed

**Principle.** Schemas evolve in a backward-compatible way by default; breaking changes are deliberate, versioned, and migrated.

**Rationale.** External consumers depend on exported artifacts. Uncontrolled schema change breaks them silently.

**Rules.**
- Additive, backward-compatible changes MAY ship with a minor schema version bump.
- A breaking change MUST bump the major schema version, MUST ship a migration for existing artifacts, and MUST be justified in an ADR.
- The schema version MUST be embedded in every conforming artifact.

**Enforcement.** QG-03, QG-18.

## Article XVI — Documentation as Code

**Principle.** Documentation SHOULD be generated from the model and the code, and significant decisions SHOULD be captured as Architecture Decision Records.

**Rationale.** Documentation maintained by hand and apart from the code drifts. ADRs preserve the reasoning behind decisions that the model alone cannot capture.

**Rules.**
- Stakeholder-facing documents SHOULD be generated projections of the model (Article II, Article III).
- Each significant or hard-to-reverse decision SHOULD be recorded as a dated ADR referencing the articles it engages.
- This constitution MUST itself be versioned and amended through the governance process below.

**Enforcement.** QG-01 (spec/ADR linkage).

## Governance

**Precedence.** Constitution > specification > plan > tasks > tooling defaults and personal preference. A `userPreferences`-level preference (for example, a preferred language or style) applies only where it does not conflict with a higher artifact; here, the Python-first orientation is consistent with Article XIII and is adopted as the project default.

**Amendment.** An amendment MUST be proposed as a specification that states the article(s) affected, the rationale, and the migration impact. It MUST be reviewed and approved by the enterprise-architecture owner. On ratification, the constitution `version` MUST be bumped (semantic versioning: major for a removed or materially weakened MUST, minor for a new or strengthened article, patch for clarifications), the `ratified` date updated, and `supersedes` set to the prior version.

**Compliance.** Every pull request is checked against the quality-gate register. A failing MUST-level gate blocks merge. A failing SHOULD-level expectation requires an approved ADR-documented exception to proceed. Gates MUST run in CI and MUST NOT be bypassable by individual contributors.

**Review cadence.** The constitution SHOULD be reviewed at each major milestone and whenever a recurring exception suggests an article needs to change.

## Quality Gate Register

Each gate is a CI check. "Blocking" gates fail the pipeline and block merge.

| Gate | Enforces | Check (mechanism) | Blocking |
|---|---|---|---|
| QG-01 | ART-I, ART-XVI | PR references an approved spec/task ID; behavior changes carry a spec change | Yes |
| QG-02 | ART-II, ART-XIV | Schema regenerated from `models.py` equals committed schema (drift test) | Yes |
| QG-03 | ART-III, ART-XIII, ART-XV | All artifacts validate against their published, versioned schemas | Yes |
| QG-04 | ART-IV | Tests present for new behavior; coverage ≥ 85% and non-regressing | Yes |
| QG-05 | ART-IV, ART-XIII | Contract tests pass; `example-adp.json` validates against live schema | Yes |
| QG-06 | ART-V | Static analysis (SAST) clean | Yes |
| QG-07 | ART-V | Dependency vulnerability scan: no high/critical | Yes |
| QG-08 | ART-V | Secret scan clean across source, fixtures, generated files | Yes |
| QG-09 | ART-V, ART-VIII | No prohibited-action code paths; consequential actions gated by permission | Yes |
| QG-10 | ART-VI | New code paths emit structured, correlated logs; no secret leakage | Yes |
| QG-11 | ART-VI | AI orchestration steps emit spans with inputs/outputs/cost/latency | Yes |
| QG-12 | ART-VII | AI recommendations and verdicts carry grounding citations with versions | Yes |
| QG-13 | ART-VIII, ART-IX | Model mutations write append-only audit entries with origin and actor | Yes |
| QG-14 | ART-VIII | Consequential actions require explicit, attributable human confirmation | Yes |
| QG-15 | ART-X | Validation gating is deterministic given critic scores | Yes |
| QG-16 | ART-XI | Referential integrity holds; no orphan elements | Yes |
| QG-17 | ART-XII | Theme is locked and valid against `c4-theme.schema.json` | Yes |
| QG-18 | ART-II, ART-XIV, ART-XV | Clean checkout regenerates with no uncommitted diffs; deps pinned | Yes |

## Glossary

**Canonical model** — the typed `ArchitectureDescription` graph that is the single source of truth for a design. **Generated artifact** — any file produced from the model by the generator (schema, docs, diagram styling). **Grounding** — the retrieved organizational knowledge an AI step cites as the basis for its output. **Critic** — one independent, single-dimension evaluator in the fan-out validation step. **Verdict** — the aggregated, deterministically gated result of validation for a design version. **Provenance** — the recorded origin of a model element or change. **Quality gate (QG)** — a CI check that enforces one or more articles. **ADR** — Architecture Decision Record, the dated record of a significant decision and its rationale.
