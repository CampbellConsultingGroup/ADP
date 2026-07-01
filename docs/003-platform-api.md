---
spec_id: ADP-SPEC-003
title: Platform API
status: draft
version: 0.1.0
depends_on: [ADP-SPEC-001, ADP-SPEC-002, ADP-SPEC-004]
articles_engaged: [ART-III, ART-V, ART-VI, ART-VIII, ART-XIII]
quality_gates: [QG-03, QG-09, QG-10, QG-14]
owner: enterprise-architecture
---

# ADP-SPEC-003 — Platform API

## Overview

The Platform API is the single entrypoint to ADP. It exposes typed endpoints for model CRUD, requirements intake, recommendation and validation requests, and view generation. It enforces authentication and authorization, validates every payload against the published schema, and exposes long-running AI work as asynchronous operations with status polling.

## User Scenarios & Acceptance Criteria

- **Typed contract.** Given a request, when it does not match the published schema, then the API MUST reject it with a typed validation error and MUST NOT partially apply it.
- **Authorized access.** Given an authenticated user, when they act, then the API MUST enforce their persona's permissions before mutating anything.
- **Async AI work.** Given a recommendation or validation request, when accepted, then the API MUST return an operation handle and MUST NOT block; the caller MUST be able to poll status.
- **Consequential confirmation.** Given a consequential action (accept recommendation, override verdict, export), when requested, then the API MUST require an explicit confirmation step recorded to the audit trail.
- **Generated contract.** Given the API surface, when documentation is produced, then the OpenAPI specification MUST be generated from the typed handlers, not hand-maintained.

## Functional Requirements

- **FR-001.** The API MUST expose CRUD for the canonical model with schema-validated request and response payloads.
- **FR-002.** The API MUST expose intake, recommendation, validation, and view-generation operations.
- **FR-003.** Recommendation and validation operations MUST be asynchronous with a pollable status and result handle.
- **FR-004.** The API MUST authenticate every request and authorize it against persona roles (ADP-SPEC-004).
- **FR-005.** Consequential actions MUST require explicit human confirmation and MUST write an audit entry.
- **FR-006.** The API MUST publish a generated OpenAPI contract.
- **FR-007.** The API MUST emit structured, correlated telemetry per ADP-SPEC-012.

## Non-Functional Requirements

- **NFR-001.** Interactive (non-AI) endpoints MUST respond within sub-second budgets under normal load.
- **NFR-002.** The API MUST never place personal or sensitive data in URLs or query strings.

## Data & Contracts

Consumes ADP-SPEC-001 model and ADP-SPEC-002 store; owns the REST/OpenAPI contract.

## Out of Scope

The web workspace UI (ADP-SPEC-009); the AI logic itself (ADP-SPEC-006/007/008).

## Dependencies

ADP-SPEC-001, ADP-SPEC-002, ADP-SPEC-004. External: FastAPI, OIDC provider.

## Constitutional Compliance

Implements ART-III, ART-V (security), ART-VI (observability), ART-VIII (human-in-the-loop), ART-XIII. Gates: QG-03, QG-09, QG-10, QG-14.

## Open Questions

- `[NEEDS CLARIFICATION]` Async operation transport: polling only, or also server-sent events/webhooks for completion?
