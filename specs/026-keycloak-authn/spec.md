# Feature Specification: Keycloak Authentication

**Feature Branch**: `026-keycloak-authn`
**Created**: 2026-07-04
**Status**: Draft
**Keycloak**: `http://127.0.0.1:8080`, realm `ADPRealm`

## Context

ADP currently has no authentication. Any user who can reach the server can read and modify any design. The authz module (`adp.authz`) already defines `PersonaRole` and the permission table but nothing enforces it at the HTTP boundary.

Keycloak is already running with `ADPRealm` and four groups:
- `EnterpriseArchitect` — full access
- `SolutionArchitect` — design read/write, AI operations, confirmation
- `TechnicalArchitect` — design read/write, AI operations
- `ADPAdministrator` — treated as EnterpriseArchitect (full access, platform management)

## Constitutional Articles Touched

- **ART-I** — Spec-Driven Development: always applies
- **ART-IV** — Test-Driven Development: always applies
- **ART-V** — Security & Threat Model: this is the core security spec; authentication and authorisation are the primary concern
- **ART-VIII** — Human in the Loop: the signed-in user's identity is the `actor` recorded in all audit entries
- **ART-IX** — Audit Trail: all audit entries must carry the authenticated user's Keycloak `sub` (subject) as the actor
- **ART-XV** — Governance: group membership controls which actions a user may perform

## Threat Model

**Assets at risk**: All design data, knowledge base items, AI operation results, and audit logs.

**Trust boundaries crossed**: Browser → Keycloak (login redirect), Keycloak → Browser (auth code), Browser → ADP API (Bearer token), ADP API → Keycloak JWKS (token validation).

**Abuse cases**:
- Unauthenticated access: mitigated by FastAPI middleware that returns 401 on all `/api/v1/` requests without a valid Bearer token.
- Token forgery: mitigated by RS256 signature validation against Keycloak's JWKS endpoint (public key rotation supported).
- Group escalation (user claiming a higher-privilege group): mitigated by reading group claims directly from the Keycloak-signed JWT, not from client-supplied headers.
- Token replay after expiry: mitigated by validating `exp` claim on every request.
- Token leakage in logs: ADP's existing log sanitization (`adp.telemetry`) must not log Authorization headers; `ADP_LLM_API_KEY` safety applies equally to Bearer tokens.

**Residual risk**: No fine-grained per-design access control in v1 — any authenticated user can access any design. Accepted for v1 single-tenant deployment. Multi-tenant isolation is a future spec.

## User Scenarios & Testing

### User Story 1 — Login Required to Access ADP (Priority: P1)

An unauthenticated user navigates to ADP. Instead of the Designs screen, they see a loading indicator while keycloak-js initialises, then they are redirected to the Keycloak login page. After entering valid credentials, they are redirected back to ADP with their session established.

**Why this priority**: The entire platform is inaccessible without this — it is the gate for everything else.

**Independent Test**: Open the ADP app in a browser without an active Keycloak session; the browser is redirected to `http://127.0.0.1:8080/realms/ADPRealm/protocol/openid-connect/auth`.

**Acceptance Scenarios**:

1. **Given** a user is not signed in, **When** they open ADP, **Then** they are redirected to the Keycloak login page automatically.
2. **Given** a user enters valid credentials, **When** Keycloak redirects back to ADP, **Then** the Designs screen is shown and the NavBar displays the user's name and role.
3. **Given** a user's token expires while using ADP, **Then** keycloak-js silently refreshes the token in the background without interrupting the user.
4. **Given** the FastAPI API receives a request without a Bearer token, **Then** it returns 401.
5. **Given** the FastAPI API receives a request with an expired or invalid token, **Then** it returns 401.

---

### User Story 2 — User Identity in NavBar and Audit (Priority: P2)

The signed-in user sees their display name and role badge in the NavBar. Every action they take (confirm requirement, accept recommendation, create design) records their Keycloak `preferred_username` as the actor in the audit log.

**Why this priority**: Without identity in the UI, users cannot tell who is logged in. Without it in the audit log, the audit trail is incomplete.

**Independent Test**: Sign in as a SolutionArchitect user; confirm a requirement; check the design's audit log — the actor field matches the Keycloak username.

**Acceptance Scenarios**:

1. **Given** a user signs in, **When** they look at the NavBar, **Then** they see their display name and a role badge (e.g. "Solution Architect").
2. **Given** a signed-in user performs an action, **Then** the audit entry actor is the user's Keycloak `preferred_username`.
3. **Given** a user signs out via the NavBar, **Then** they are redirected to the Keycloak logout endpoint and the local session is cleared.

---

### User Story 3 — Group-Based Role Enforcement (Priority: P3)

A TechnicalArchitect user cannot perform actions reserved for SolutionArchitect or EnterpriseArchitect (e.g. exporting a design bundle, overriding a verdict). Attempting such an action returns 403.

**Why this priority**: Role enforcement protects against privilege escalation. Lower priority than login because all users have at minimum read access.

**Independent Test**: Sign in as a TechnicalArchitect user; attempt to export a design; receive 403 Forbidden.

**Acceptance Scenarios**:

1. **Given** a TechnicalArchitect user, **When** they attempt an action requiring a higher role, **Then** the API returns 403 with a clear message.
2. **Given** an EnterpriseArchitect user, **When** they perform any action, **Then** it succeeds (no role-based blocks).
3. **Given** an ADPAdministrator user, **When** they perform any action, **Then** it succeeds (treated as EnterpriseArchitect).

---

### User Story 4 — Local Development Without Auth (Priority: P4)

A developer running ADP locally can disable authentication entirely by setting `ADP_AUTH_ENABLED=false`. All existing tests continue to pass without a Keycloak instance. API requests succeed without a Bearer token.

**Why this priority**: Essential for keeping the existing test suite and development workflow intact.

**Independent Test**: `ADP_AUTH_ENABLED=false pytest tests/ --ignore=tests/integration -q` — all tests pass.

**Acceptance Scenarios**:

1. **Given** `ADP_AUTH_ENABLED=false`, **When** the API receives a request without a token, **Then** it succeeds (unauthenticated mode, actor defaults to "architect").
2. **Given** `ADP_AUTH_ENABLED=false`, **When** the React app loads, **Then** it skips Keycloak initialisation and proceeds directly to the Designs screen.

---

### Edge Cases

- Keycloak is unreachable on startup: API logs a warning but continues to start; all protected requests return 503 with "authentication service unavailable".
- User belongs to multiple groups: the highest-privilege role wins (EnterpriseArchitect > SolutionArchitect > TechnicalArchitect).
- User belongs to no recognised group: treated as read-only; 403 on any write action.
- Token with `iss` claim not matching configured realm: rejected with 401.

## Requirements

### Functional Requirements

**Keycloak Client Configuration (FR-001)**
- **FR-001**: A Keycloak public OIDC client named `adp-frontend` MUST be created in `ADPRealm` with: `Standard flow` enabled, `Direct Access Grants` disabled, `Valid Redirect URIs` covering both Vite dev server and production ports, `Web Origins` set to `+` (CORS), and PKCE enforced (`S256` challenge method).

**Frontend (FR-002 to FR-006)**
- **FR-002**: The React app MUST install and initialise `keycloak-js` with `ADPRealm` and `adp-frontend` client. Initialisation uses `checkLoginIframe: false` and `onLoad: "login-required"` — unauthenticated users are immediately redirected to Keycloak.
- **FR-003**: All API calls from the frontend MUST include the Keycloak access token as `Authorization: Bearer <token>`.
- **FR-004**: The `NavBar` component MUST display the authenticated user's `preferred_username` and their mapped ADP role when `ADP_AUTH_ENABLED=true`. No identity display when auth is disabled.
- **FR-005**: The NavBar MUST include a "Sign out" button that calls `keycloak.logout()` and redirects to the Keycloak logout endpoint.
- **FR-006**: When `ADP_AUTH_ENABLED=false` (read from Vite env variable `VITE_AUTH_ENABLED`), keycloak-js MUST NOT be initialised and the app MUST work as before.

**Backend (FR-007 to FR-012)**
- **FR-007**: A FastAPI middleware MUST be added that intercepts all `/api/v1/` requests. When `ADP_AUTH_ENABLED=true`, it MUST validate the `Authorization: Bearer` header using Keycloak's JWKS endpoint.
- **FR-008**: Token validation MUST verify: RS256 signature (via JWKS), `exp` claim (not expired), `iss` claim matches `ADP_KEYCLOAK_ISSUER`, `aud` claim contains `account` or the client ID.
- **FR-009**: The validated token's `preferred_username` MUST be made available as the request actor. All audit entries written during the request MUST use this value.
- **FR-010**: Keycloak group claims (`/groups` or `groups` in token) MUST be mapped to `PersonaRole` using the table: `EnterpriseArchitect` → `enterprise_architect`, `SolutionArchitect` → `solution_architect`, `TechnicalArchitect` → `technical_architect`, `ADPAdministrator` → `enterprise_architect`. Users with no matching group default to `technical_architect` (read access only).
- **FR-011**: A `require_role(minimum_role: PersonaRole)` FastAPI dependency MUST be available. Endpoints that mutate data MUST declare a minimum required role. Insufficient role returns 403.
- **FR-012**: When `ADP_AUTH_ENABLED=false`, the middleware MUST be skipped and actor defaults to `"architect"` (preserving existing behaviour).

### Key Entities

- **AuthenticatedUser**: `sub: str` (Keycloak user ID), `username: str` (preferred_username), `email: str`, `role: PersonaRole`, `groups: list[str]`
- **Keycloak Client**: `adp-frontend`, public, PKCE, ADPRealm

## Success Criteria

- **SC-001**: An unauthenticated browser navigating to ADP is redirected to Keycloak login within 2 seconds.
- **SC-002**: All API endpoints return 401 for requests without a valid Bearer token when `ADP_AUTH_ENABLED=true`.
- **SC-003**: The signed-in user's name is visible in the NavBar on every view.
- **SC-004**: All existing tests (`pytest tests/ --ignore=tests/integration -q`) pass with `ADP_AUTH_ENABLED=false`.
- **SC-005**: An ADPAdministrator user can perform all actions that an EnterpriseArchitect can.

## Assumptions

- Keycloak is configured to include group membership in the JWT token. This requires a **Group Membership** mapper to be configured on the `adp-frontend` client or at realm level.
- The `ADP_KEYCLOAK_ISSUER` env var defaults to `http://127.0.0.1:8080/realms/ADPRealm` for local development; can be overridden for production.
- The `ADP_KEYCLOAK_CLIENT_ID` env var defaults to `adp-frontend`.
- JWKS public keys are cached in-memory with a 5-minute TTL to avoid hitting Keycloak on every request.
- Token introspection is NOT used — local validation against JWKS only (faster, works offline).
- The Keycloak login page uses the default Keycloak theme; no custom branding in v1.
- `python-jose[cryptography]` is already listed in ADP-SPEC-003 dependencies.
