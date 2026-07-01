---
spec_id: ADP-SPEC-004
title: Identity, Authorization & Audit Trail
status: draft
version: 0.1.0
depends_on: [ADP-SPEC-001, ADP-SPEC-002]
articles_engaged: [ART-V, ART-VIII, ART-IX]
quality_gates: [QG-08, QG-09, QG-13, QG-14]
owner: enterprise-architecture
---

# ADP-SPEC-004 — Identity, Authorization & Audit Trail

## Overview

This feature governs who may do what in ADP and records what was done. Authentication is delegated to the organization's identity provider; authorization is role-based and aligned to the architect and reviewer personas. The append-only audit trail (stored by ADP-SPEC-002) is populated here with origin, actor, and rationale for every consequential action.

## User Scenarios & Acceptance Criteria

- **Delegated sign-in.** Given a user, when they authenticate, then ADP MUST rely on the external identity provider and MUST NOT hold a primary credential.
- **Persona permissions.** Given a technical architect, when they attempt an enterprise-only action, then it MUST be denied and the denial MUST be observable.
- **Override accountability.** Given a reviewer overrides a verdict, when it commits, then the audit trail MUST record the actor, timestamp, and justification.
- **No secret leakage.** Given any log or generated artifact, when scanned, then no secret or token MUST be present.

## Functional Requirements

- **FR-001.** Authentication MUST be delegated to the organization's identity provider over OIDC.
- **FR-002.** ADP MUST NOT store or manage primary user credentials.
- **FR-003.** Authorization MUST be role-based, with roles mapped to the enterprise, solution, technical architect, and reviewer personas.
- **FR-004.** Consequential and irreversible actions MUST be permission-checked per action; one approval MUST NOT generalize to later actions.
- **FR-005.** Every consequential action MUST record an audit entry with origin, actor, target, summary, and timestamp.
- **FR-006.** Secrets MUST be externalized and MUST NOT appear in source, fixtures, logs, or generated artifacts.

## Non-Functional Requirements

- **NFR-001.** Authorization decisions MUST be enforced server-side and MUST NOT be bypassable by the client.
- **NFR-002.** Audit writes MUST be durable and append-only.

## Data & Contracts

Owns role definitions and the audit-entry write path; consumes the ADP-SPEC-002 store.

## Out of Scope

Identity provider configuration itself; data classification labeling rules (referenced, defined with the data owner).

## Dependencies

ADP-SPEC-001, ADP-SPEC-002. External: OIDC identity provider.

## Constitutional Compliance

Implements ART-V (security), ART-VIII (human-in-the-loop), ART-IX (provenance). Gates: QG-08, QG-09, QG-13, QG-14.

## Open Questions

- `[NEEDS CLARIFICATION]` Exact permission matrix per persona, especially who may amend principles/standards versus designs.
