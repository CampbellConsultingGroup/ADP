"""adp.strategy -- capture strategic objectives as structured entities (ADP-d8u.1).

A new sibling package, not an extension of adp.business (research.md
Decision 1: adp.business's existing models/store/router files are already
2,847 combined lines; this codebase's established response to a genuinely
distinct sub-domain -- as adp.diagrams and adp.chat both already show -- is
a fresh top-level package, not continued growth of an already-large one).

Two new entities: StrategicTheme (a small, reusable taxonomy table,
precedented directly by BusinessDomain) and StrategicObjective (theme
reference, owner, statement, optional typed metric/target, structured
horizon), plus two new many-to-many join tables to business_capabilities/
value_streams, mirroring capability_design_links/value_stream_design_links
(migration 008) exactly.

Cross-package validation: strategy.store calls adp.business.store's existing
get_capability/get_value_stream read functions directly to validate a link
target exists (research.md Decision 2) -- the same pattern
adp.business.agent_review already uses to call back into
adp.business.store.delete_capability. Never a duplicated or bypassed check.

Write endpoints reuse the existing ActionType.WRITE_BUSINESS_ARCH (research.md
Decision 3) -- no new ActionType, matching business_domains's own precedent
when it was added.
"""
