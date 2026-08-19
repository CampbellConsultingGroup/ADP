---
document_type: business-requirements
title: ADP — Business Requirements
status: living
audience: External research partners, product strategy
last_updated: 2026-08-12
companion_docs:
  - research-solution-architecture.md
  - research-screen-reference.md
---

# ADP — Business Requirements

A single connected model spanning strategy, business, application, solution, and
technical architecture — with AI assisting at every seam, and a human as the
accept/reject gate on every AI action.

> **Note on scope**: this is a research-handoff brief, distinct from
> [`solution-architecture.md`](solution-architecture.md), ADP's own detailed,
> tool-maintained canonical architecture doc. This trio (business requirements,
> solution architecture summary, screen reference) exists to give an external
> research partner fast, accurate context without needing repo access — keep it
> current as the product evolves, but don't merge it into the canonical doc.

## Contents

1. [Problem statement](#1-problem-statement)
2. [Product thesis](#2-product-thesis)
3. [The five domains](#3-the-five-domains)
4. [Personas & access model](#4-personas--access-model)
5. [AI posture](#5-ai-posture)
6. [Functional requirements by domain](#6-functional-requirements-by-domain)
7. [Non-functional requirements](#7-non-functional-requirements)
8. [Deployment posture](#8-deployment-posture)
9. [Open frontier](#9-open-frontier)
10. [Questions for external research](#10-questions-for-external-research)

---

## 1. Problem statement

Enterprise architecture practice is fragmented across tools that don't talk to each
other: a strategy deck, a capability spreadsheet, an application-portfolio tool, a
diagramming tool for C4 designs, a wiki for standards. Traceability between layers
is manual, and it rots the moment anyone stops maintaining it by hand.

The result, in most organizations: nobody can answer "which applications realize
this strategic objective?" or "which designs touch this capability?" without a
multi-day audit. Governance findings live in a spreadsheet nobody re-checks. A
capability heat map is a slide someone builds once a year, already stale by the
time it ships.

## 2. Product thesis

Model all layers as one connected graph in one system, and let AI assist at the
seams — while a human stays the explicit accept/reject gate on every AI action.

The recurring design principle across every domain in ADP is turning what's
normally a hand-maintained document into **typed, linked, queryable entities**. A
strategic objective isn't a bullet in a deck — it's a record with an owner, a typed
metric/target, a fiscal horizon, and real foreign keys to the capabilities and
value streams it operationalizes. Once that's true, a capability heat map or a
traceability report becomes a *rendered output of the model*, not a separately
hand-maintained artifact that drifts out of sync the day after it's published.

**Concrete example**: the strategy-capture layer (shipped 2026-08) lets an
architect record "Reduce claims cycle time to improve retention" as a structured
objective — owner, metric (claims cycle time, target 40%, direction: decrease),
fiscal quarter — then link it to the exact `Claims Processing` capability and
`Claim to Payout` value stream it operationalizes. That link is queryable, not
prose.

## 3. The five domains

Product structure mirrors the architecture practice itself. Strategy sits above
the classic four; the four map directly onto how enterprise architects already
think about their estate.

| Layer | Domain | What it covers |
|---|---|---|
| 0 | **Strategy** | Strategic themes and objectives — owner, statement, typed metric/target, fiscal horizon — linked to real capabilities and value streams. The newest, thinnest layer; sits above Business Architecture and gives every layer below it a reason. |
| 1 | **Business** | Capabilities (hierarchical, three levels), value streams (staged), business domains (taxonomy + risk classification), strategic relevance and maturity scoring per capability. |
| 2 | **Enterprise** | Application registry, technical capabilities, integrations, transformation initiatives, TIME disposition (Tolerate / Invest / Migrate / Eliminate) plus 7R rationalization, cost/risk/governance tracking behind sensitivity-gated reads. |
| 3 | **Solution** | The platform's original core: C4 model designs (Context / Container / Component), AI-assisted requirements intake, AI-generated design-option recommendations, LLM-as-judge design review, full lifecycle tracking from draft to decommissioned. |
| 4 | **Technical** | Technical capability map, technology tags and standards, a governed knowledge base of patterns and principles with hybrid keyword+vector search, a locked C4 rendering theme for consistent export. |
| — | **Cross-cutting** | A general-purpose diagramming subsystem (flowchart / sequence / ER / UML / cloud architecture) independent of C4; an AI chat assistant grounded in the platform's own data via read-only tools; audit trail and governance reporting; platform admin for AI prompt configuration. |

## 4. Personas & access model

Five roles, drawn directly from the platform's own role-based access model — not
an idealized persona set, the actual enforced one.

| Persona | Owns |
|---|---|
| **Enterprise Architect** | Broadest grant in the system. Cross-domain traceability and governance; the role most other permission checks default to. |
| **Solution Architect** | The C4 design lifecycle end to end: requirements intake, AI recommendations, LLM-as-judge review, the design canvas itself. |
| **Technical Architect** | Technical capabilities, technology standards/tags, and the knowledge base. |
| **Reviewer** | Read-heavy across domains; can confirm or reject AI-generated proposals in specific gated workflows without full write access. |
| **Platform Admin** | AI prompt configuration for every AI-assisted feature. Deliberately holds no architecture-domain grants of its own — a narrow, distinct role, not folded into Enterprise Architect. |

## 5. AI posture

Every AI-touching flow — requirements intake, design recommendations,
LLM-as-judge review, agent-suggested capability/domain changes, the chat
assistant — follows the same shape:

1. AI proposes a change or answer, typed and inspectable — never a raw text blob.
2. A human explicitly confirms or rejects it.
3. Only on confirmation does anything write to the canonical model.

Nothing in the platform acts autonomously on the model. Raw source text fed to an
LLM during intake is never persisted — only the extracted, structured,
human-confirmed result is. This isn't a per-feature convention the team happens to
follow; it's written into the platform's own constitution as a standing rule that
every new AI feature must satisfy before it ships.

> **Why this matters for research framing**: any external research on "AI agents
> that modify enterprise data" should treat ADP's human-in-the-loop confirmation
> gate as a fixed constraint, not a variable to optimize away — it's a governance
> requirement, not a UX preference that could be relaxed for speed.

## 6. Functional requirements by domain

A representative, not exhaustive, cut of what each domain must support today.

**Strategy**
- Capture a strategic theme (taxonomy tag) and reuse it across objectives.
- Capture a strategic objective with owner, statement, an all-or-nothing typed
  metric group (name, target value, unit, direction), and a fiscal year + period
  horizon.
- Link an objective to one or more real business capabilities and value streams —
  never free text; a link target must exist in the registry.
- Browse, edit, and delete objectives; deleting one cascades its links, never
  orphans them.

**Business Architecture**
- Maintain a three-level capability hierarchy with strategic relevance and
  maturity scoring.
- Maintain staged value streams and business domains with risk classification.
- Trace a capability or value stream to the designs and strategic objectives that
  reference it.

**Application / Enterprise Architecture**
- Maintain the full application registry: identity, ownership, risk, cost,
  technical fit, roadmap, integrations.
- Score applications on TIME disposition and 7R rationalization for portfolio
  decisions.
- Gate sensitive reads (risk, cost, governance) behind dedicated permissions,
  independent of the general application-write permission.

**Solution Architecture**
- Author C4 designs (Context / Container / Component) with full requirement
  traceability.
- Turn a free-text business problem into typed, confirmable requirements via
  AI-assisted intake — source text never stored.
- Generate AI design-option recommendations a human accepts or rejects into the
  canonical model.
- Run an LLM-as-judge review against a design before promoting its lifecycle
  status.
- Track lifecycle: draft → proposed → current → deprecated → decommissioned.

**Technical Architecture**
- Maintain a technical capability map and a governed set of technology
  tags/standards.
- Maintain a knowledge base of patterns and principles, searchable by keyword and
  semantic (vector) similarity.
- Render and export designs against one locked, WCAG-compliant C4 theme.

## 7. Non-functional requirements

| Category | Requirement |
|---|---|
| Access control | Every write is gated by a role→action permission model with an explicit, versioned permission table (currently v1.8.0). No implicit trust from an architect-sounding role name. |
| Auditability | Governance reporting and an audit trail cover AI reasoning logs, operations, and design version history — not just final state. |
| Data integrity | Cross-entity links are foreign-key-enforced with cascade rules at the database level, not just application-layer checks. |
| Observability | Structured telemetry with trace-id propagation across every AI-assisted step; a documented no-leak gate prevents sensitive data reaching logs/metrics. |
| Reproducibility | The system must build clean from a fresh checkout with no undocumented external dependency — vendored code is copied in and tracked, not fetched live from a sibling repo. |

## 8. Deployment posture

This is a real deployed system, not a prototype.

Runs on Azure Container Apps (API service + Keycloak identity, both behind a
VNet), a VNet-injected PostgreSQL Flexible Server with no public network path, an
Azure Container Registry, and GitHub Actions CI/CD using OIDC federated
credentials (no long-lived cloud secrets in the pipeline). CI already runs SAST
(bandit), dependency-CVE scanning (pip-audit), and DAST (OWASP ZAP against the
live OpenAPI schema) on every change.

## 9. Open frontier

What's deliberately not built yet — useful context for where research effort
would compound.

- No reverse traceability yet from a Solution Design back to the strategic
  objectives it realizes (only objective→capability/value-stream links exist
  today).
- The landing dashboard has no strategy-layer visibility yet — an architect can't
  see objective counts or strategic health at a glance.
- No portfolio-level "strategy map" or causal view connecting objectives to
  outcomes across the whole estate — deliberately scoped out when the strategy
  layer was designed, to ship the well-specified core first.
- Single-tenant per deployment; no multi-tenant SaaS delivery model yet.

## 10. Questions for external research

Framed for a research partner without access to the codebase.

- How do comparable EA/APM tools (LeanIX, Ardoq, Avolution ABACUS, BiZZdesign)
  handle strategy-to-capability traceability today, and where does ADP's "typed
  entity, not a slide" bet look differentiated versus table-stakes?
- What's the right shape for a portfolio-level strategy map / causal view (Layer 0
  → Layer 3 rollup) once the underlying data model already exists — is there a
  known best-practice pattern worth adapting rather than designing fresh?
- For a human-in-the-loop AI governance model like this one, what emerging
  standards or audit expectations (e.g. EU AI Act-adjacent guidance, NIST AI RMF)
  should shape how the confirm/reject gate and reasoning-log retention evolve?
- Where do multi-tenant SaaS EA tools draw the line on tenant isolation for a
  graph this interconnected — per-schema, per-database, or row-level, and what
  does that imply for a system built single-tenant-first?

---

*Companion documents: [`research-solution-architecture.md`](research-solution-architecture.md), [`research-screen-reference.md`](research-screen-reference.md).*
