Add a Strategy domain card to the ADP landing Overview dashboard, closing the
open-frontier gap where the Strategy layer has no visibility on the landing
screen while Business, Enterprise, Solution, and Technical already do.

## Why

The Overview dashboard today shows six stat tiles plus four "Architecture
domain" cards (Business / Enterprise / Solution / Technical). Strategy
(Layer 0) shipped 2026-08 with objectives, themes, and typed links to
capabilities and value streams, but has no presence on the landing screen. An
architect can't see objective counts or strategic health at a glance, which
is the one domain currently exempt from the platform's own thesis: "no
governance finding should live somewhere nobody re-checks."

## What to build

A fifth domain card, visually and structurally consistent with the existing
four, added to the Overview screen's domain-card grid.

The card must show only values the current data model can actually compute —
no fabricated progress-to-target metric. The Strategy metric group (name,
target, unit, direction) has no stored "current/actual value" field today, so
a completion-percentage or progress bar is explicitly out of scope for this
card; do not add one without also adding the underlying field.

### Card contents

1. **Mini-stats** (matches the existing domain-card pattern): total objective
   count, total theme count.

2. **Linkage health bar**: a two-segment bar showing objectives that have at
   least one confirmed link (to a capability and/or value stream) versus
   objectives with zero links. Zero-link objectives are a real governance
   signal — an unlinked objective can't be traced from and nothing rolls up
   to it — so this should read as a warning state, not a neutral stat.
   Resolve as an open question whether "linked" requires a capability link, a
   value-stream link, or either, before implementing the count logic.

3. **Fiscal period breakdown**: count of objectives whose fiscal year+period
   is the current period, upcoming, or past due, computed against today's
   date server-side. Past-due objectives should read as a warning state.

4. A deep-link control to the Strategy screen (`Strategy → Objectives`),
   consistent with the other domain cards' navigation pattern.

### Explicitly out of scope for this change

- Any progress/completion percentage tied to the metric target (requires a
  new "current value" field this spec doesn't add).
- The portfolio-level strategy map / causal view (Layer 0 → Layer 3 rollup)
  — that's a separate, larger piece of open-frontier work.
- Reverse traceability from Solution Designs back to objectives.
- Changes to objective/theme data capture or the metric-group shape itself.

## Constraints to respect

- Match the visual and interaction conventions of the four existing domain
  cards (mini-stats, deep-link action) so Strategy doesn't read as a
  bolted-on afterthought relative to the other layers.
- All counts must be computed from real stored fields (objective/theme
  tables, the objective↔capability and objective↔value-stream join tables,
  fiscal year+period) — no new persisted fields required for v1.
- Sensitivity: objectives can carry fiscal-timing and target information;
  confirm whether the existing sensitivity-gated-read pattern used for
  application risk/cost/governance data should extend to this card's
  aggregate counts, or whether aggregate counts are safe to leave ungated
  like other Business/Enterprise summary stats.
- Follow the existing route-prefix→action permission convention for any new
  read endpoint this card requires; the completeness test that asserts every
  mutating route has a mapped action does not apply here since this is a
  read-only surface, but the endpoint should still sit behind normal
  authentication.

## Open questions to resolve during specification

- Does "linked" for the linkage-health bar mean any link at all, or does it
  require both a capability and a value-stream link to count as healthy?
- Should the fiscal-period breakdown use fiscal year+quarter boundaries or a
  configurable org fiscal calendar (today's data model assumes a single
  fixed fiscal calendar — confirm that assumption still holds)?
- Does this card need its own aggregate-stats endpoint, or can it reuse
  existing `strategy` package store functions with a thin aggregation layer
  in the router, consistent with how other domain cards source their stats?
