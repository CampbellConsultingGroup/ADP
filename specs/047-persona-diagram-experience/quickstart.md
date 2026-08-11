# Quickstart: Persona-Differentiated Diagram Experience (ADP-914.6)

Assumes the web dev server is running (`cd web && npm run dev`) against an API with
`ADP_AUTH_ENABLED=true` and at least one Keycloak user per architect role (see
`src/adp/ops/keycloak_create_users.py` / RUNBOOK.md for seeding test users). With
`VITE_AUTH_ENABLED=false` (the project's default dev/test mode), `useAuth().user` is always `null`,
so Scenario 4 (the "unrecognized role" fallback) is what you'll actually observe locally unless
auth is explicitly enabled — that's expected, not a bug.

## Scenario 1: Enterprise Architect gets an `architecture`-defaulted new diagram (User Story 1)

1. Sign in as a user in the `EnterpriseArchitect` Keycloak group.
2. Navigate to **Diagrams** (left nav) → **+ New Diagram**.
3. Expect: the "Diagram type" selector is pre-set to `architecture`, and that option's label reads
   `architecture (Recommended for your role)`.
4. Without changing the type, author some content and save.
5. Expect: the saved diagram's `diagram_type` is `"architecture"`.

## Scenario 2: Solution Architect gets a `flowchart`-defaulted new diagram (User Story 1)

Repeat Scenario 1 signed in as a `SolutionArchitect` user. Expect the selector pre-set to
`flowchart`, labeled `flowchart (Recommended for your role)`.

## Scenario 3: Technical Architect gets a `sequence`-defaulted new diagram (User Story 1)

Repeat Scenario 1 signed in as a `TechnicalArchitect` user. Expect the selector pre-set to
`sequence`, labeled `sequence (Recommended for your role)`.

## Scenario 4: Unrecognized/absent role falls back to today's behavior (Edge Case)

With `VITE_AUTH_ENABLED=false`, or signed in as a role with no mapping entry (`platform_admin`):

1. Navigate to **Diagrams** → **+ New Diagram**.
2. Expect: the selector is pre-set to `flowchart` (the pre-feature default, unchanged), and **no**
   option shows a "(Recommended for your role)" suffix.

## Scenario 5: The default is steering only — every type remains selectable (User Story 1 + 2)

1. Sign in as any architect role, open **+ New Diagram**.
2. Manually change the selector away from the pre-set default to any of the other 4 types.
3. Author content and save.
4. Expect: the saved diagram's `diagram_type` matches the manually-chosen type, not the role's
   default — confirming FR-004 (the default never overrides an explicit choice).

## Scenario 6: Reopening an existing diagram is unaffected (Edge Case, FR-007)

1. Open any previously-saved diagram from the **Diagrams** list.
2. Expect: no "Diagram type" selector is shown at all (unchanged from ADP-SPEC-046 — the type is
   immutable post-creation), regardless of the signed-in user's role.

## Scenario 7: Automated regression check

```bash
cd web && npx vitest run src/diagrams/persona.test.ts src/diagrams/DiagramEditorPage.test.tsx
# Expect: all tests pass, including the new persona-aware default + recommendation-label cases.

npm run test:run
# Expect: full frontend suite green, no regressions (this feature touches only
# web/src/diagrams/persona.ts and web/src/diagrams/DiagramEditorPage.tsx).
```
