Extend the existing sensitivity-gated-read pattern — currently used only for
application risk/cost/governance data — to cover commercially sensitive
fields on strategic objectives.

## Why

The security model today treats reads as ungated by default, with a specific
carve-out: application risk, cost, and governance data sit behind their own
dedicated permission, independent of the general application-write
permission, because that data is more sensitive than "can see the app
registry exists." Strategic objectives carry an analogous category of
sensitivity — a metric target and fiscal horizon (e.g. "reduce claims cycle
time 40% by Q3") can reveal competitive positioning or internal performance
targets that not every role with general Strategy read access should
necessarily see — but no equivalent gate exists for the Strategy domain
today. This is a gap in an otherwise consistent access model, not a new
pattern.

## What to build

A new dedicated permission for sensitive objective fields, added to the
existing versioned role→action permission table (bumping from v1.8.0 to
v1.9.0), enforced the same way as the application risk/cost/governance gate:
route-prefix→action mapping, checked by the existing app-level middleware, no
per-endpoint hand-rolled check.

### Field split

- **Ungated (general Strategy read)**: objective statement, owner, theme,
  linked capabilities/value streams — the "what and why," comparable to how
  capability names and hierarchy are ungated today.
- **Gated (new sensitive-read permission)**: the metric group's target
  value, unit, and direction, plus the fiscal year+period horizon — the "how
  much and by when," comparable to application risk/cost/governance fields.

This split is a starting proposal, not a final answer — confirm the exact
field boundary during spec review; it's plausible the fiscal horizon alone
is sensitive enough to gate while the metric name isn't, or vice versa.

### Where enforcement applies

- Objective detail/list endpoints must omit or redact gated fields for
  callers without the new permission, rather than returning them and relying
  on the frontend to hide them.
- The Strategy landing-dashboard card (mini-stats, linkage health, fiscal
  breakdown) uses aggregate counts, not individual objective values — confirm
  whether aggregates need the same gate or are safe to leave ungated, the way
  the Overview dashboard's existing stat tiles are ungated today even though
  they roll up from domains with some gated detail fields.

## Explicitly out of scope

- Changing which roles exist or their broader grants (Enterprise Architect,
  Solution Architect, Technical Architect, Reviewer, Platform Admin stay as
  defined).
- Gating objective *writes* — this spec is read-side only; the existing
  write permission for Strategy is unchanged.
- Any change to the application risk/cost/governance gate itself — this
  spec follows that pattern, it doesn't modify it.
- Retroactive redaction of already-surfaced data in exports or the audit
  trail; this is a live-read-path gate only.

## Constraints to respect

- Use the same enforcement mechanism as the application gate: dedicated
  permission, route-prefix mapping, checked by app-level middleware — do not
  introduce a second enforcement mechanism for the sake of this one domain.
- The permission-completeness test that asserts every registered mutating
  route has a mapped action does not directly apply here since this is a
  read gate, but the new permission must still be registered in the
  versioned table so the gate is auditable and not implicit.
- No change to the underlying `strategy` package's data model — this is
  purely an access-control change layered on existing fields.

## Open questions to resolve during specification

- Exact field boundary: which of statement / owner / theme / metric target /
  metric unit / metric direction / fiscal horizon are gated versus general?
- Does the Reviewer persona get the new sensitive-read permission by
  default, given it already reviews AI-generated proposals in other gated
  workflows, or does it need to be granted separately per objective?
- Should the Strategy landing-dashboard aggregate counts (objective/theme
  totals, linkage health, fiscal-period breakdown) be gated as well, or do
  aggregates count as safe the way other domains' dashboard stat tiles are
  today?
