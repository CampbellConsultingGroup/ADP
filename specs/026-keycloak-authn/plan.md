# Implementation Plan: Keycloak Authentication (ADP-SPEC-026)

## Tech Stack

**Backend (no new packages needed — all already present):**
- `python-jose[cryptography]` 3.5.0 — JWT decoding and RS256 validation
- `httpx` — JWKS endpoint fetch (already used for LLM client)
- `fastapi` — middleware + dependency injection
- New module: `src/adp/auth/` — token validation, user context, role mapping

**Frontend (one new package):**
- `keycloak-js` — Keycloak official JS adapter for PKCE auth code flow
- Vite env variable: `VITE_AUTH_ENABLED` (default `"true"`)
- `VITE_KEYCLOAK_URL` (default `"http://127.0.0.1:8080"`)
- `VITE_KEYCLOAK_REALM` (default `"ADPRealm"`)
- `VITE_KEYCLOAK_CLIENT_ID` (default `"adp-frontend"`)

## Architecture

### New module `src/adp/auth/`

```
src/adp/auth/
  __init__.py
  middleware.py   — FastAPI middleware: validates Bearer token, injects AuthenticatedUser
  tokens.py       — JWKS fetch/cache, JWT decode, claims extraction
  models.py       — AuthenticatedUser dataclass
  deps.py         — get_current_user(), require_role() FastAPI dependencies
```

### Group → Role Mapping

```python
GROUP_TO_ROLE = {
    "EnterpriseArchitect":  PersonaRole.ENTERPRISE_ARCHITECT,
    "ADPAdministrator":     PersonaRole.ENTERPRISE_ARCHITECT,
    "SolutionArchitect":    PersonaRole.SOLUTION_ARCHITECT,
    "TechnicalArchitect":   PersonaRole.TECHNICAL_ARCHITECT,
}
# Highest-privilege group wins; no group → technical_architect (read-only)
```

### Token Validation Flow

```
Request arrives → AuthMiddleware
  → ADP_AUTH_ENABLED=false? → skip, actor="architect"
  → Extract "Authorization: Bearer <token>" header
  → Decode header to get kid
  → Fetch JWKS (cached 5min) → find matching key
  → Verify RS256 signature + exp + iss + aud
  → Extract preferred_username, groups
  → Map groups → PersonaRole
  → Set request.state.user = AuthenticatedUser(...)
  → Request proceeds to route handler
```

### Frontend Auth Flow

```
App loads
  → VITE_AUTH_ENABLED=false? → skip init → render app normally
  → keycloak.init({ onLoad: "login-required", pkceMethod: "S256" })
  → Not authenticated → Keycloak redirects to login
  → Authenticated → token stored in keycloak object
  → App renders normally
  → Every fetch → include Authorization: Bearer <token>
  → Token expiry → keycloak.updateToken(30) called before fetch
```

### Keycloak Client Configuration (admin step before implementation)

The Keycloak admin must create client `adp-frontend` in `ADPRealm`:
1. Client type: OpenID Connect
2. Authentication flow: Standard flow (Authorization Code)
3. Client authentication: OFF (public client)
4. Valid redirect URIs: `http://localhost:5173/*`, `http://localhost:8001/*`
5. Web origins: `+` (all origins permitted via CORS)
6. Advanced > Proof Key for Code Exchange: `S256`
7. Client scopes: add **Group Membership** mapper on `adp-frontend` client scope
   - Token claim name: `groups`
   - Full group path: OFF (return group names, not paths)

## File Changes

| File | Action |
|---|---|
| `src/adp/auth/__init__.py` | CREATE |
| `src/adp/auth/models.py` | CREATE — AuthenticatedUser |
| `src/adp/auth/tokens.py` | CREATE — JWKS cache + JWT validation |
| `src/adp/auth/middleware.py` | CREATE — FastAPI middleware |
| `src/adp/auth/deps.py` | CREATE — get_current_user, require_role |
| `src/adp/api/app.py` | EDIT — add auth middleware |
| `src/adp/api/deps.py` | EDIT — re-export get_current_user |
| `.env.example` | EDIT — add auth env vars |
| `web/package.json` | EDIT — add keycloak-js dependency |
| `web/src/auth/keycloak.ts` | CREATE — keycloak instance + init |
| `web/src/auth/AuthProvider.tsx` | CREATE — React context for auth state |
| `web/src/main.tsx` | EDIT — wrap app in AuthProvider |
| `web/src/api/client.ts` | EDIT — inject Bearer token in all requests |
| `web/src/shell/NavBar.tsx` | EDIT — show username + role + sign out button |
| `tests/unit/test_token_validation.py` | CREATE — unit tests for JWT validation |
| `tests/contract/test_auth_middleware.py` | CREATE — contract tests for 401/403 |

## Constitution Compliance

- **ART-IV**: unit tests for token validation (valid token, expired, wrong issuer, no group); contract tests for 401 without token, 403 wrong role
- **ART-V**: tokens never logged; JWKS validation (no introspection = no server-side state)
- **ART-VIII**: authenticated username used as actor in all audit entries
- **ART-IX**: actor field in audit entries is now the Keycloak username, not "architect"
