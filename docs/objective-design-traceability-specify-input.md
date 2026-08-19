Add a fifth many-to-many traceability link — objective↔design — closing the
reverse-traceability gap called out in both research docs: today an objective
links to capabilities and value streams, but nothing links a Solution Design
back to the strategic objective(s) it realizes.

## Why

The solution architecture doc already anticipates this exact link, describing
it as "about to be used a fifth (objective↔design, filed as a follow-on)" in
the data-model-shape section. The business requirements doc separately lists
it as the first item under Open frontier: "No reverse traceability yet from a
Solution Design back to the strategic objectives it realizes." This spec is
that follow-on.

Without it, the chain "objective → capability → design" is only walkable
forward (an architect can see what an objective is meant to affect) but not
backward (an architect looking at a design can't see what strategic
objective, if any, it's actually in service of). That breaks the platform's
core thesis — a traceability report should be a rendered view of the graph,
not something requiring a manual cross-reference between two screens.

## What to build

A new join table, `objective_design`, following the exact shape already used
by the other four traceability links (capability↔design, value-stream↔design,
objective↔capability, objective↔value-stream):

- Composite primary key (objective_id, design_id).
- `ON DELETE CASCADE` on both foreign-key legs — deleting either the
  objective or the design removes the link, never leaves an orphan.
- One index on the "other side" (design_id, mirroring the pattern used by
  the existing objective↔capability and objective↔value-stream tables).
- A plain `created_at` column.
- FK/PK constraints live only in the Alembic migration, per the existing
  convention — the Python `Table()` definition is for statement-building
  only, not constraint declaration.

### Surface changes

1. **Design detail / canvas view**: show linked objective(s), if any, with
   their owner and statement — mirroring how the design view likely already
   surfaces linked capabilities.
2. **Objective detail view** (Strategy → Objectives): show linked design(s),
   giving the reverse view for free once the table exists.
3. **Link management**: a way to create/remove an objective↔design link.
   Where this control lives (objective screen, design screen, or both) is an
   open question below — resolve before implementation, don't default to
   "both" just to be safe, since that doubles the surface to maintain.

### Cross-package validation

When creating a link, follow the existing cross-package convention: the
`strategy` package router opens a second, domain-scoped database session and
calls `adp.store`'s already-public get-design function directly to confirm
the design exists, rather than duplicating the check or standing up an
internal HTTP call — the same pattern already used to validate an objective's
capability/value-stream links.

## Explicitly out of scope

- Any AI-assisted suggestion of objective↔design links (e.g. the
  recommendation engine proposing a link during design creation). This spec
  is the data layer and manual linking UI only; AI-assisted linking is a
  separate, later spec if wanted.
- Changing the four existing join tables or their surfaces.
- The portfolio-level strategy map / causal rollup (Layer 0 → Layer 3) —
  that consumes this link once it exists but is out of scope here.
- Any change to design or objective lifecycle states.

## Constraints to respect

- Match the existing join-table shape exactly — no deviation (e.g. no soft
  delete, no extra metadata columns) unless a genuine need surfaces during
  spec review.
- New link-management endpoints must register a route-prefix→action mapping
  so the existing permission-completeness test continues to pass rather than
  needing a carve-out.
- Reuse the existing audit-trail mechanism for confirmed writes — a new link
  is a write and should show up in governance reporting like any other.

## Open questions to resolve during specification

- Where does link creation happen: from the objective screen ("link an
  existing design"), the design screen ("link an existing objective"), or
  both? Pick one primary entry point rather than building both by default.
- Should an objective require at least one design link before it can be
  considered "realized," or is the link purely informational with no status
  implication? This affects whether the Strategy landing card's future
  metrics should incorporate design-linkage alongside capability/value-stream
  linkage.
- Does this link need its own confirm/reject step (matching the AI-proposes/
  human-confirms pattern), or is it a direct human action since it's not
  AI-originated in this spec's scope?
