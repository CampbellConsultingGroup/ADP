# Phase 1 Data Model: Persona-Differentiated Diagram Experience

No persisted entity, no database table, no Pydantic model, no change to the existing `Diagram`
model (ADP-SPEC-046). The only "data" this feature introduces is a static, in-memory frontend
constant — documented here per spec.md's Key Entities section, in lieu of a real entity.

## `PERSONA_DEFAULT_TYPE` (frontend constant, `web/src/diagrams/persona.ts`)

A fixed lookup from a `PersonaRole` string (as already produced by `useAuth().user.role` /
`groupsToRole()`, `web/src/auth/AuthProvider.tsx`) to one of the 5 existing `DiagramType` values
(`web/src/diagrams/api.ts`). Shape:

```ts
type PersonaDiagramDefault = Record<string, DiagramType>;
```

| Role key (matches `useAuth().user.role`) | Default `DiagramType` |
|---|---|
| `enterprise_architect` | `architecture` |
| `solution_architect` | `flowchart` |
| `technical_architect` | `sequence` |

Roles not present in the table (`reviewer`, `platform_admin`, `undefined`/unrecognized) have no
entry — the lookup function returns `undefined` for those, and callers fall back to the existing
pre-feature default (`flowchart`), per FR-006. `reviewer` is deliberately absent rather than mapped
to a value: Reviewers cannot reach the new-diagram flow at all (no `WRITE_DIAGRAM`), so a mapping
for that role would be dead code. `platform_admin` is also absent — that role is an operational/admin
persona, not one of the three architect personas this feature targets (spec.md scope).

**Validation rules**: None beyond TypeScript's own type checking (`DiagramType` is a closed union of
5 literals, so a typo in a mapping value is a compile error, not a runtime bug).

**State transitions**: None — this is a pure, stateless lookup evaluated fresh each time a new
diagram is started (research.md Decision 1's "no caching" note); there is no lifecycle to model.

**Relationships**: None to any persisted entity. Conceptually parallel to (not a foreign key against)
the existing `PersonaRole` enum (`src/adp/authz/roles.py`) — this frontend constant's keys are
expected to stay in sync with that enum's architect-role values by convention and by the unit tests
in `persona.test.ts`, not by any shared code or generated artifact (no `ADP_agents` script covers
this small a mapping; a code-review-time check is sufficient at this scope).
