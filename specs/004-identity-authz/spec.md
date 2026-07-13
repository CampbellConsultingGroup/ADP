# Feature Specification: Identity, Authorization & Audit Trail

**Feature Branch**: `004-identity-authz`  
**Created**: 2026-06-29  
**Status**: Draft  
**Input**: User description: "ADP-SPEC-004 — Identity, Authorization & Audit Trail"

## Constitutional Articles Touched *(mandatory — ART-I)*

- **ART-I** — Spec-Driven Development: always applies; this spec governs identity before any code
- **ART-IV** — Test-Driven Development: always applies; every role boundary and audit write requires a test before implementation
- **ART-V** — Security by Design: this spec IS the primary implementation of ART-V; authentication, authorization, secret management, and audit trail all originate here
- **ART-VIII** — Human-in-the-Loop for Consequence: central concern; FR-004 implements per-action confirmation; no blanket authorization
- **ART-IX** — Provenance and Auditability: central concern; FR-005 implements the append-only audit trail with actor, origin, and justification
- **ART-XIII** — Typed Contracts Everywhere: role definitions and identity tokens are typed; no string-role comparisons at runtime
- **ART-VII** — Grounded AI Only: not in scope; this spec produces no AI outputs
- **ART-XI** — Traceability End to End: indirectly supports; the audit trail produced here enables the "who introduced this and why" question to be answered for any mutation

## Threat Model *(mandatory — ART-V)*

Identity and authorization are ADP's highest-risk surface area. A failure here affects all designs, all verdicts, and the integrity of the platform's governance guarantees.

**Assets at risk**: The integrity of authorization decisions (which actors may do which things); the authenticity of the audit trail (who did what and when); the secrecy of externalized credentials (OIDC client secrets, API keys).

**Trust boundaries crossed**: User device → OIDC identity provider → ADP (token validation); ADP → ADP-SPEC-002 store (audit write path); CI/CD pipeline → source code (secret scan).

**Abuse cases**:
- **Credential theft at ADP**: An attacker compromises ADP's storage to extract user passwords → Mitigation: FR-002 prohibits ADP from storing any primary credential; the attack surface does not exist
- **Token replay across actions**: An actor confirms one recommendation and their token is replayed to confirm a second without knowledge → Mitigation: FR-004 requires per-action confirmation tied to a specific operation ID; one confirmation MUST NOT generalize
- **Client-side authorization bypass**: A frontend client omits an authorization check, or a caller crafts a direct API call to bypass the UI → Mitigation: NFR-001 requires all authorization decisions to be server-side; the client MUST NOT be trusted to enforce permissions
- **Persona impersonation**: A Technical Architect sets their `adp_role` claim in a self-issued token to `enterprise_architect` → Mitigation: ADP MUST NOT trust caller-supplied roles; roles MUST be asserted by the identity provider in a validated, signed token
- **Secret leakage in logs**: An OIDC client secret or bearer token is written to a log or test fixture → Mitigation: FR-006 requires all secrets to be externalized; QG-08 blocks any commit containing credentials
- **Audit trail tampering**: An actor with database access deletes or modifies an audit entry → Mitigation: NFR-002 and ADP-SPEC-002's append-only enforcement (trigger + ORM gate)

**Residual risk**: Compromised OIDC identity provider (external dependency; mitigated by token expiry and short-lived claims); privileged insider with direct database access bypassing the trigger (accepted; mitigated by access controls at the infrastructure layer, outside this spec's scope).

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Sign In via the Identity Provider (Priority: P1)

A user opens ADP for the first time. They click "Sign in" and are redirected to the organization's identity provider. After authenticating there, they are returned to ADP with a validated identity. ADP never sees their password.

**Why this priority**: Authentication is the entry gate to every other capability. Without delegated authentication, no other user story can be implemented or tested safely.

**Independent Test**: Attempt to use ADP without authenticating — assert rejection. Authenticate via a mock OIDC flow — assert the identity is accepted and a principal is established. Attempt to use an expired or tampered token — assert rejection. All three assertions are independent of authorization or audit.

**Acceptance Scenarios**:

1. **Given** a user has not authenticated, **When** they attempt any protected action, **Then** ADP redirects or challenges them with 401; no protected resource is accessed
2. **Given** a user authenticates successfully with the identity provider, **When** ADP receives their validated identity token, **Then** ADP extracts their principal ID and persona role without storing a credential
3. **Given** a validated token has expired, **When** the user attempts an action, **Then** ADP rejects the request and requires re-authentication; no stale session is honoured

---

### User Story 2 - Persona-Based Permission Enforcement (Priority: P1)

A Technical Architect attempts to amend a platform-level architecture principle — a capability reserved for Enterprise Architects. The system denies the attempt and the denial is observable in the audit trail.

**Why this priority**: Authorization without authentication is meaningless; these two stories are both P1. A role boundary failure would allow any authenticated user to perform any action, undermining the governance model.

**Independent Test**: Sign in as each of the four personas and attempt both permitted and forbidden actions — assert permitted actions succeed, forbidden actions receive a 403, and forbidden denials are logged. Tests are independent of audit trail write tests.

**Acceptance Scenarios**:

1. **Given** an authenticated Technical Architect, **When** they attempt an Enterprise-only action (e.g., amending a platform standard), **Then** the action is denied with a clear role-mismatch error; the attempted action is observable in logs
2. **Given** an authenticated Reviewer, **When** they attempt a write mutation on a design, **Then** the action is denied; the design is unchanged
3. **Given** an authenticated Enterprise Architect, **When** they perform any action in their permitted scope, **Then** the action is permitted without additional challenge
4. **Given** a role claim in a token that does not match a recognized persona, **When** any action is attempted, **Then** ADP denies the action; unrecognized roles receive no default permissions

---

### User Story 3 - Per-Action Confirmation Before Consequential Operations (Priority: P2)

An architect accepts an AI recommendation. This is a consequential, difficult-to-reverse action. Before committing, the system requires them to explicitly confirm the specific operation — they cannot reuse an earlier confirmation.

**Why this priority**: Per-action confirmation is the ART-VIII implementation. Builds on US1 (auth) and US2 (roles); without those, confirmation is meaningless. The confirmation gate itself is independently testable.

**Independent Test**: Attempt a consequential action without a confirmation payload — assert rejection. Submit a confirmation payload for operation A, then replay the same confirmation for operation B — assert the second is rejected. Both assertions are independent of specific design content.

**Acceptance Scenarios**:

1. **Given** an architect attempts a consequential action without a confirmation payload, **When** the request is submitted, **Then** it is rejected with a clear error; no change is made
2. **Given** an architect submits a confirmation tied to operation ID X, **When** the same confirmation payload is submitted again (replay), **Then** the second submission is rejected; the operation remains in its prior state
3. **Given** an architect submits a fresh confirmation payload for a distinct operation, **When** it is submitted, **Then** it is accepted independently of any prior confirmations

---

### User Story 4 - Audit Trail for Every Consequential Action (Priority: P2)

A reviewer overrides a validation verdict with a justification. The audit trail records their identity, the timestamp, the action taken, and the justification — permanently and without the ability to delete or amend the record.

**Why this priority**: The audit trail is the evidentiary record of all governance decisions. Builds on US2 (roles) and US3 (confirmation). Independently testable by verifying the audit entry after any confirmed action.

**Independent Test**: Perform any confirmed consequential action; query the audit trail; assert the entry is present with the correct actor, timestamp, action, and justification; attempt to delete the entry and assert failure.

**Acceptance Scenarios**:

1. **Given** a consequential action is confirmed and committed, **When** the audit trail is queried, **Then** an entry is present recording the actor, action, target entity, summary, and timestamp
2. **Given** a committed audit entry, **When** any path attempts to update or delete it, **Then** the attempt is rejected; the entry is unchanged
3. **Given** a consequential action fails before commit, **When** the audit trail is queried, **Then** no entry for the failed action appears — partial audit writes do not persist

---

### Edge Cases

- What happens when the identity provider is unreachable at authentication time?
- What happens when a role claim is absent from an otherwise valid token?
- How is the audit trail handled when a confirmed action fails mid-transaction (e.g., store write error)?
- What happens if the same persona role is granted via two different OIDC claims or groups?
- How does role enforcement behave for service accounts or automated pipelines that submit actions on behalf of a human?

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: Authentication MUST be delegated to the organization's identity provider over a standard federated identity protocol; ADP MUST NOT issue, manage, or validate primary user credentials
- **FR-002**: ADP MUST NOT store any primary user credential, password, or long-lived secret at any point in the authentication flow
- **FR-003**: Authorization MUST be role-based; every protected action MUST be mapped to one or more persona roles; the role mapping MUST be centrally defined and versioned
- **FR-004**: Consequential and irreversible actions MUST require a distinct, per-action confirmation tied to a specific operation identifier; a single authorization MUST NOT carry forward to a subsequent action
- **FR-005**: Every consequential action that commits successfully MUST write an audit entry recording: origin (human or AI), actor principal ID, target entity ID, action name, human-readable summary, and UTC timestamp — all within the same transaction as the mutation
- **FR-006**: All secrets, OIDC client credentials, and signing keys MUST be externalized to the deployment environment; they MUST NOT appear in source code, test fixtures, log output, or generated artifacts

### Non-Functional Requirements

- **NFR-001**: All authorization decisions MUST be evaluated and enforced on the server side; client-provided role assertions MUST NOT be trusted
- **NFR-002**: Audit entries MUST be written to a durable, append-only store; no application path may update or delete an existing audit entry

### Key Entities

- **PersonaRole**: A typed enumeration of recognized organizational roles — `enterprise_architect`, `solution_architect`, `technical_architect`, `reviewer`; unrecognized roles receive no permissions
- **PermissionGrant**: A mapping from `PersonaRole` to one or more permitted action types; the centrally-defined authorization table; versioned alongside the spec
- **IdentityToken**: The validated, transient representation of an authenticated principal; carries `principal_id` (from identity provider's `sub` claim) and `persona_role` (from identity provider's `adp_role` claim); never persisted by ADP
- **AuditRecord**: The typed record of a consequential action; maps to `AuditEntry` in ADP-SPEC-001; fields: `origin`, `actor`, `affected_entity`, `action`, `summary`, `timestamp`; append-only, never updatable

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: 100% of authentication flows route through the external identity provider; zero ADP-stored passwords or long-lived credentials exist at any point; verified by secret scan and code audit
- **SC-002**: 100% of authorization decisions are enforced server-side; every forbidden action attempt returns an error without executing; verified by role-boundary tests covering each persona and each action type
- **SC-003**: Every consequential action requires a distinct per-action confirmation; zero instances of a single confirmation authorizing more than one operation; verified by replay-prevention tests
- **SC-004**: 100% of committed consequential actions have a corresponding audit entry with all required fields; zero committed mutations with missing or partial audit records; verified by audit integrity tests
- **SC-005**: Zero secrets, tokens, or credentials appear in any log output, test fixture, generated artifact, or source file; verified by automated secret scanning in CI on every commit

## Assumptions

- **Permission matrix (resolved from open question)**: The four recognized personas and their default permissions for v1 are:

  | Action | Enterprise Architect | Solution Architect | Technical Architect | Reviewer |
  |---|---|---|---|---|
  | Read designs | ✅ | ✅ | ✅ | ✅ |
  | Create / modify designs | ✅ | ✅ | ✅ | ❌ |
  | Submit AI operations | ✅ | ✅ | ✅ | ❌ |
  | Confirm recommendations | ✅ | ✅ | ✅ | ❌ |
  | Override verdicts | ✅ | ✅ | ❌ | ✅ |
  | Add findings | ✅ | ✅ | ✅ | ✅ |
  | Amend platform standards / principles | ✅ | ❌ | ❌ | ❌ |
  | Manage role assignments | ✅ | ❌ | ❌ | ❌ |

  This matrix is the v1 baseline; it MUST be stored as a versioned, typed artifact alongside this spec and updated through the governance process when roles change.

- Persona roles are asserted by the identity provider as a custom claim (`adp_role`) in the validated token; ADP does not maintain its own role assignment database for v1.
- Service accounts and automated pipelines (e.g., CI/CD) are treated as `technical_architect` by default unless the identity provider asserts a different role in their token.
- The identity provider is a pre-existing organizational service; its configuration (client registration, claim mapping) is out of scope for this spec but is a deployment prerequisite.
- "Consequential actions" for the purpose of FR-004 and FR-005 are defined as: accepting an AI recommendation, overriding a validation verdict, amending a platform standard, and managing role assignments. This maps exactly to `ActionType` values `{confirm_recommendation, override_verdict, amend_standard, manage_roles}` in `adp.authz`. Export triggering is deferred and will be added as a governed amendment when ADP-SPEC-011 is ratified.
- US1 acceptance scenarios for redirect behavior and token extraction are implemented in ADP-SPEC-003's `auth/jwt.py`; this spec's contribution to US1 is the closed `PersonaRole` enum (raises `ValueError` on unrecognized strings) and the role mapping that ADP-SPEC-003's JWT validator uses to extract the `ApiPrincipal.role`.
- Audit entries are written by the ADP-SPEC-003 API layer into the ADP-SPEC-002 store; this spec defines the required fields and the append-only governance rule but does not own the write mechanism.

## Out of Scope

- Identity provider configuration, client registration, and claim mapping setup
- Multi-factor authentication policy (delegated to the identity provider)
- Data classification labeling rules (referenced by ART-V; defined separately with the data owner)
- User-facing sign-in UI flow (delegated to ADP-SPEC-009 web workspace)
- Audit trail querying and reporting UI (deferred)
- Fine-grained resource-level permissions (e.g., per-design read access control) — v1 is persona-based only; all users of a given role may act on all designs
