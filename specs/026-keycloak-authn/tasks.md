# Tasks: Keycloak Authentication (ADP-SPEC-026)

**Input**: Design documents from `/specs/026-keycloak-authn/`
**Prerequisites**: ADP-SPEC-025 complete ✅
**Admin required**: Before Phase 1, ask user to create `adp-frontend` Keycloak client per plan.md instructions.

---

## Phase 0: Keycloak Client Setup (Admin Action — BLOCKING)

- [X] T000 [ADMIN] Ask user to create `adp-frontend` Keycloak client in ADPRealm per plan.md:
  (1) Client type: OpenID Connect, Standard flow, public client
  (2) Valid redirect URIs: `http://localhost:5173/*` and `http://localhost:8001/*`
  (3) Web origins: `+`
  (4) PKCE: S256
  (5) Add Group Membership mapper: token claim name `groups`, full path OFF
  Then verify: `curl http://127.0.0.1:8080/realms/ADPRealm/protocol/openid-connect/auth?client_id=adp-frontend&response_type=code` returns a redirect

---

## Phase 1: Backend Auth Module

### Tests (MANDATORY — ART-IV)

- [X] T001 [P] Create `tests/unit/test_token_validation.py`: write `test_valid_token_decodes_correctly()` — create a test RSA key pair; sign a JWT with `iss=<realm>`, `exp=future`, `preferred_username="alice"`, `groups=["SolutionArchitect"]`; call `decode_token()`; assert username="alice" and role=SolutionArchitect
- [X] T002 [P] Write `test_expired_token_raises()`: same setup but `exp=past`; assert `TokenExpiredError` raised
- [X] T003 [P] Write `test_wrong_issuer_raises()`: `iss="https://evil.example.com"`; assert `TokenValidationError` raised
- [X] T004 [P] Write `test_no_group_defaults_to_technical_architect()`: token with no `groups` claim; assert role=TechnicalArchitect
- [X] T005 [P] Write `test_admin_group_maps_to_enterprise_architect()`: `groups=["ADPAdministrator"]`; assert role=EnterpriseArchitect
- [X] T006 [P] Write `test_highest_privilege_wins()`: `groups=["TechnicalArchitect", "SolutionArchitect"]`; assert role=SolutionArchitect

### Implementation

- [X] T007 Create `src/adp/auth/models.py`: define `AuthenticatedUser` dataclass with `sub: str`, `username: str`, `email: str`, `role: PersonaRole`, `groups: list[str]`; define `TokenValidationError(Exception)` and `TokenExpiredError(TokenValidationError)`
- [X] T008 Create `src/adp/auth/tokens.py`: implement `JwksCache` class that fetches JWKS from `ADP_KEYCLOAK_ISSUER/protocol/openid-connect/certs` with 5-minute TTL using `httpx.AsyncClient`; implement `decode_token(token: str, jwks_cache: JwksCache) -> AuthenticatedUser` using `python-jose` `jwt.decode()` with RS256 algorithm and issuer/audience validation; implement `_map_groups_to_role(groups: list[str]) -> PersonaRole` applying the group precedence table
- [X] T009 Create `src/adp/auth/middleware.py`: implement `AuthMiddleware(BaseHTTPMiddleware)` that: (1) skips if `ADP_AUTH_ENABLED=false`; (2) passes through non-`/api/v1/` paths; (3) extracts Bearer token from `Authorization` header; (4) returns 401 JSON on missing or invalid token; (5) sets `request.state.user = AuthenticatedUser(...)` on success; (6) returns 503 if Keycloak JWKS is unreachable
- [X] T010 Create `src/adp/auth/deps.py`: implement `get_current_user(request: Request) -> AuthenticatedUser` FastAPI dependency that reads `request.state.user` (or returns unauthenticated stub when auth disabled); implement `require_role(minimum_role: PersonaRole)` that returns a FastAPI `Depends` checking the current user's role
- [X] T011 Create `src/adp/auth/__init__.py`: export `AuthMiddleware`, `get_current_user`, `require_role`, `AuthenticatedUser`

**Checkpoint**: `pytest tests/unit/test_token_validation.py -q --no-cov` — 6+ tests pass

---

## Phase 2: Wire Auth into FastAPI

### Tests (MANDATORY — ART-IV)

- [X] T012 [P] Create `tests/contract/test_auth_middleware.py`: write `test_request_without_token_returns_401()` — create app with `ADP_AUTH_ENABLED=true`; GET `/api/v1/designs`; assert 401
- [X] T013 [P] Write `test_request_with_valid_token_returns_200()`: mock JWKS; include valid Bearer; GET `/api/v1/designs` (mock store); assert 200
- [X] T014 [P] Write `test_auth_disabled_no_token_succeeds()`: set `ADP_AUTH_ENABLED=false`; GET `/api/v1/designs` without token; assert 200
- [X] T015 [P] Write `test_expired_token_returns_401()`: valid structure but expired; assert 401

### Implementation

- [X] T016 Edit `src/adp/api/app.py`: add `app.add_middleware(AuthMiddleware)` — import from `adp.auth`; place AFTER prometheus middleware so metrics still work for 401 responses
- [X] T017 Edit `src/adp/api/deps.py`: re-export `get_current_user` from `adp.auth.deps`; update `_get_actor()` callers in all routers to use `get_current_user(request).username` instead of the hardcoded header

**Checkpoint**: `pytest tests/contract/test_auth_middleware.py -q --no-cov` — all pass; existing 450 tests still pass with `ADP_AUTH_ENABLED=false`

---

## Phase 3: Frontend — keycloak-js Integration

- [X] T018 Run `cd web && npm install keycloak-js` — adds keycloak-js to package.json
- [X] T019 [P] Create `web/src/auth/keycloak.ts`: instantiate `Keycloak({ url: import.meta.env.VITE_KEYCLOAK_URL, realm: import.meta.env.VITE_KEYCLOAK_REALM, clientId: import.meta.env.VITE_KEYCLOAK_CLIENT_ID })`; export `keycloak` instance and `initKeycloak()` async function that calls `keycloak.init({ onLoad: "login-required", pkceMethod: "S256", checkLoginIframe: false })`
- [X] T020 [P] Create `web/src/auth/AuthProvider.tsx`: React context providing `{ user: { username, role } | null, isLoading: boolean, logout: () => void }`; when `VITE_AUTH_ENABLED !== "true"`, skip Keycloak init and provide `user=null, isLoading=false`; when enabled, call `initKeycloak()` and extract `preferred_username` + groups from decoded token claims
- [X] T021 Edit `web/src/main.tsx`: wrap `<App />` in `<AuthProvider>` so auth state is available to all components
- [X] T022 Edit `web/src/api/client.ts`: update `apiGet` and `apiMutation` to include `Authorization: Bearer <token>` header when `VITE_AUTH_ENABLED=true` and Keycloak token is available; call `keycloak.updateToken(30)` before each request to refresh if needed
- [X] T023 Edit `web/src/vite.config.ts` (or create `web/.env`): add default values for `VITE_AUTH_ENABLED=true`, `VITE_KEYCLOAK_URL=http://127.0.0.1:8080`, `VITE_KEYCLOAK_REALM=ADPRealm`, `VITE_KEYCLOAK_CLIENT_ID=adp-frontend`

---

## Phase 4: NavBar Identity Display

- [X] T024 Edit `web/src/shell/NavBar.tsx`: import `useAuth` context hook; when `user` is set show `{user.username}` and a role badge (colour-coded pill: EnterpriseArchitect=purple, SolutionArchitect=blue, TechnicalArchitect=teal, ADPAdministrator=red); add "Sign out" button that calls `logout()`; when auth disabled show nothing (existing behaviour)

---

## Phase 5: Environment Config

- [X] T025 Edit `.env.example`: add auth-related env vars: `ADP_AUTH_ENABLED=true`, `ADP_KEYCLOAK_ISSUER=http://127.0.0.1:8080/realms/ADPRealm`, `ADP_KEYCLOAK_CLIENT_ID=adp-frontend`; add note that these must match what is configured in Keycloak
- [X] T026 Edit `docker-compose.yml`: add `ADP_AUTH_ENABLED`, `ADP_KEYCLOAK_ISSUER`, `ADP_KEYCLOAK_CLIENT_ID` to the `api` service environment

---

## Phase 6: Polish

- [X] T027 [P] Run `pytest tests/ --ignore=tests/integration -q --no-cov` — all 450+ tests pass (with `ADP_AUTH_ENABLED=false` in test environment)
- [X] T028 [P] Run `ruff check src/adp/auth/` — clean
- [X] T029 [P] Run `cd web && npx tsc --noEmit` — zero TypeScript errors
- [X] T030 [P] End-to-end verify: start server with `ADP_AUTH_ENABLED=true ADP_KEYCLOAK_ISSUER=http://127.0.0.1:8080/realms/ADPRealm ...`; open browser; confirm redirect to Keycloak login; log in; confirm NavBar shows username and role

---

## Notes

- T000 MUST be completed before T008+ (JWKS URL depends on realm being configured)
- All existing tests must use `ADP_AUTH_ENABLED=false` (env fixture in conftest.py or monkeypatch)
- The `_get_actor(request)` helper in multiple routers currently reads `X-Actor` header — after T017 it should use `get_current_user(request).username` when auth is enabled
- JWKS caching: use a module-level `asyncio.Lock` + timestamp to avoid thundering herd on cache expiry
- `python-jose` `jwt.decode()` handles RS256 automatically when given the JWK key set
- Keycloak tokens include `realm_access.roles` and optionally `groups` — we use `groups` (requires the Group Membership mapper to be configured, T000 step 5)
