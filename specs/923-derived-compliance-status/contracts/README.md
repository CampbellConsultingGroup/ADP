# Contracts: Derived Compliance Status

No HTTP (or other external) contract is added by this feature. This is a deliberate scope boundary,
not an oversight — see [research.md](../research.md) Decision D1 and [spec.md](../spec.md)'s
Assumptions ("No new API surface in this pass").

The two new functions this feature adds (`compute_compliance_status`,
`get_entity_compliance_status`) are internal, same-package Python calls within `adp.compliance` —
not a boundary crossed by an external caller. When a future spec (expected: COMPLY-04, the read-side
rollup) first surfaces a derived compliance status to an API consumer, that spec is the right place
to define the response contract and the sensitivity-gating rule this spec's Threat Model flags as
residual risk.
