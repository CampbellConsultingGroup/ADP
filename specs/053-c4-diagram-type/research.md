# Research: C4 Diagram Type in the Diagram Tool

## Decision 1: Seed a new C4 diagram's model with `diagramTypeId: "c4-context"`, not the bare app-level type `"c4"`

**Decision**: `DiagramEditorPage.tsx`'s create-a-new-diagram path currently calls
`createEmptyDiagramModel(next)` where `next` is exactly the selected `DiagramType` string — correct
for the other five families, whose `model.diagramTypeId` convention is identical to their
`DiagramType`/`dslFamily` value. For `c4` specifically, this feature adds a small mapping so a
newly created C4 diagram is seeded with `createEmptyDiagramModel("c4-context")` instead.

**Rationale**: Confirmed directly (`c4.ts:7-16`) that `c4.ts` is a *multi-level* family —
`model.diagramTypeId` must be one of `c4-context | c4-container | c4-component | c4-code |
c4-deployment` (matching `HEADER_TO_LEVEL`/`LEVEL_TO_HEADER`), never the bare string `"c4"`. The
app-level `DiagramType`/`dslFamily` value (`"c4"`) is a *separate* concept — it only selects which
entry in the `dslFamilies` registry (`registry.ts:23`) parses/serializes this diagram; it is never
itself written into the model. `createEmptyDiagramModel` (`diagram-model.ts:232-234`) performs zero
validation on its argument, so passing `"c4"` directly would silently produce a model whose
`diagramTypeId` doesn't match any `LEVEL_TO_HEADER` key. This wouldn't crash — `serializeC4`
(`c4.ts:378`) falls back to `'C4Context'` regardless — but it's the wrong reason for the right
default: the fallback exists for genuinely malformed/legacy DSL text, not as the intended path for
every brand-new diagram. Seeding the correct `"c4-context"` value directly (spec.md FR-004: new
diagrams start at Context level) makes the model's own state honest from creation, not merely
correct-by-accident-of-a-fallback.

**Alternatives considered**:
- *Leave `createEmptyDiagramModel(next)` unchanged and rely on the `'C4Context'` fallback* —
  rejected: works today only because the fallback and the desired default happen to coincide; a
  future change to that fallback (e.g. if it's ever tightened to error instead of defaulting) would
  silently break new-C4-diagram creation for a reason completely disconnected from this feature.
- *Change `c4.ts` itself to accept `"c4"` as an alias for `"c4-context"`* — rejected outright: `c4.ts`
  is vendored and explicitly not to be modified (Constraints); the fix belongs entirely on the
  ADP-authored caller side.

## Decision 2: Add genuine round-trip test coverage for the `c4` DSL family — it currently has none

**Decision**: This feature adds `web/src/diagrams/core/dsl/c4.test.ts`, mirroring the existing
per-family `describe` blocks already in `families.test.ts` (`flowchart`, `erd`, `architecture`,
`sequence`, `uml` — `families.test.ts:33,57,86,112,131`) — parse-then-serialize round-trip
assertions covering at minimum: a `System`/`Person`/`Container`/`Component` element mix, a `Db`/
`Queue` variant, a nested `System_Boundary`, and a `Rel`/`BiRel` relationship pair.

**Rationale**: Directly confirmed by grep: `families.test.ts` has **zero** mention of `c4`
anywhere, and no dedicated `c4.test.ts`/similar file exists anywhere in the repo. `c4.ts` is a
large, structurally complete parser/serializer (`c4.ts:1-423`) that was vendored in already-working
from its source project — "already fully built" is accurate for its *capability*, not for its
*test coverage inside this repository*. spec.md's SC-002 ("every standard C4 diagram construct...
parses without error") is not verifiable — for this codebase's own regression-safety purposes — by
an assertion that the code merely exists; it needs an assertion that it behaves correctly, checked
in CI. ART-IV (TDD) treats this the same as any other new-behavior path: a failing test first, not
an assumption of correctness carried over from the vendored source.

**Alternatives considered**:
- *Skip dedicated `c4.ts` tests, relying on `DiagramEditorPage.test.tsx`'s app-level exposure test
  (verifying `"c4"` merely appears as a choice)* — rejected: that test can pass while the parser
  itself is silently broken (e.g. by a future unrelated refactor of shared DSL helpers `c4.ts`
  imports, like `splitFrontMatter`/`joinFrontMatter`) — an app-level "it's selectable" test and a
  DSL-engine-level "it's correct" test verify different things and neither substitutes for the
  other.

## Decision 3: No dedicated C4 shape-picker UI in this pass (confirmed, not just assumed)

**Decision**: Confirmed directly — a `c4-notation` icon-shape-library manifest already exists
(`web/src/diagrams/core/libraries/c4-notation.ts`: Person/System/Container/Component/Database/
Boundary, each with `keywords` and an `assetRef`), reachable in principle via the already-built
`getLibraryIcons(libraryId, ...)` mechanism `Canvas.tsx` already calls (`Canvas.tsx:33,315`). This
feature does **not** wire up a UI entry point for picking from it — the toolbar's shape-grid stays
exactly as it is for every non-flowchart family (`shapes.tsx:212-236`, `getAddableShapes` returns
only `UNIVERSAL_SHAPES` for any `dslFamily !== 'flowchart'`).

**Rationale**: Confirms spec.md's own Assumption on independent grounds — ADP-SPEC-052's own
research.md (this session, prior feature) already established that **no icon-library palette entry
point exists anywhere in the app today** ("Icon-library palette entry point: out of scope. Placing
icon-type nodes (`shape: "icon"`) has no existing UI entry point today, and adding one is a new
capability, not a restyle of an existing control"). That finding is about the UI mechanism in
general, not C4 specifically — it would need building regardless of which family wanted to use it,
making it correctly out of scope for a feature whose own bead explicitly asked for "low risk, small
surface." A generic toolbar-added rectangle still round-trips correctly through `c4.ts` today: an
unset `node.role` falls through `elementKindFor` (`c4.ts:341-359`) to `'System'`, a safe, valid
default — so the DSL-text-authoring path (FR-002/FR-003, fully supported) is not blocked by this
deferral in any way.

**Alternatives considered**:
- *Add one-click "Add Person"/"Add System"/etc. buttons now, reusing the existing manifest* —
  rejected for this pass: building the first-ever icon-library UI entry point is a materially larger
  scope than "expose an already-built parser as a selectable type," and the bead this feature
  implements (ADP-914.11) explicitly scoped it out. Tracked as a natural, independently-valuable
  follow-on, not silently dropped.

## Decision 4: No backend schema/migration change

**Decision**: Confirmed by reading migration 024 directly — `diagrams.diagram_type` is a plain
`TEXT` column, not a Postgres `ENUM` or `CHECK` constraint. The value set is enforced only at the
Pydantic `Literal` layer (`src/adp/diagrams/models.py:10`).

**Rationale**: Adding `"c4"` to a Python `Literal` requires no `ALTER TABLE`, no new Alembic
revision, and no data backfill — the column already accepts any string; only the application-layer
validation gate changes, and it changes in the additive, backward-compatible direction ART-XV
explicitly permits without a schema version bump.

**Alternatives considered**: None — this is a direct consequence of the existing schema design,
not a choice this feature makes.
