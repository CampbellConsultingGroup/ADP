"""Read-only portfolio snapshot for pattern evaluation (936 FR-005–FR-007, research.md D3). Pure.

Elements are plain JSON-like maps (so CEL can address them), keyed by element type and id. The
snapshot is always portfolio-wide; a :class:`Scope` only restricts which elements are selector
candidates (pins may name elements outside the scope — a domain's backbone usually is).

Domain derivation (spec GT-1): domains attach only to L1 business capabilities, so an
application's ``domain_ids`` is the set of domains of the L1 ancestors of its linked capabilities.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from typing import Any

from adp.patterns.conformance_models import ScopeType
from adp.patterns.models import ElementType

# Application attributes behind a sensitive-read permission (FR-006). Absent from the element
# maps when the caller lacks the permission; expressions touching them yield field_unavailable.
RISK_FIELDS = frozenset(
    {
        "security_posture",
        "vulnerability_status",
        "data_classification",
        "dr_bc_status",
        "end_of_life_date",
        "end_of_support_date",
    }
)
COST_FIELDS = frozenset({"tco"})
GOVERNANCE_FIELDS = frozenset({"renewal_date", "sla"})
GATED_FIELDS = RISK_FIELDS | COST_FIELDS | GOVERNANCE_FIELDS

# CEL `scope` map keys, per element type.
SCOPE_KEYS: dict[ElementType, str] = {
    ElementType.APPLICATION: "applications",
    ElementType.INTEGRATION: "integrations",
    ElementType.BUSINESS_CAPABILITY: "business_capabilities",
    ElementType.VALUE_STREAM: "value_streams",
    ElementType.BUSINESS_DOMAIN: "business_domains",
    ElementType.TECHNICAL_CAPABILITY: "technical_capabilities",
    ElementType.AGENT: "agents",
}

Element = dict[str, Any]


@dataclass(frozen=True)
class Scope:
    scope_type: ScopeType
    scope_ref: str | None = None
    member_ids: frozenset[str] = frozenset()


def l1_domain(cap_id: str | None, caps: dict[str, Element]) -> str | None:
    """Domain of a capability's L1 ancestor (cycle-safe parent walk)."""
    seen: set[str] = set()
    current = caps.get(cap_id) if cap_id else None
    while current is not None and current["id"] not in seen:
        seen.add(current["id"])
        parent = current.get("parent_id")
        if not parent or parent not in caps:
            return current.get("domain_id")
        current = caps[parent]
    return None


def derive_application_domains(apps: dict[str, Element], caps: dict[str, Element]) -> None:
    """Set every capability's ``domain_id`` to its L1 ancestor's and every application's
    ``domain_ids`` from its linked capabilities (in place)."""
    resolved = {cid: l1_domain(cid, caps) for cid in caps}
    for cid, domain in resolved.items():
        caps[cid]["domain_id"] = domain
    for app in apps.values():
        domains = {resolved.get(c) for c in app.get("capability_ids", [])}
        app["domain_ids"] = sorted(d for d in domains if d)


@dataclass(frozen=True)
class PortfolioSnapshot:
    elements: dict[ElementType, dict[str, Element]]
    unavailable_fields: frozenset[str] = frozenset()
    realizes_pairs: frozenset[tuple[str, str]] = frozenset()
    _by_pair: dict[tuple[str, str], list[str]] = field(default_factory=dict, repr=False)

    @classmethod
    def from_parts(
        cls,
        *,
        applications: dict[str, Element],
        raw_integrations: dict[str, Element],
        business_capabilities: dict[str, Element],
        business_domains: dict[str, Element],
        technical_capabilities: dict[str, Element],
        value_streams: dict[str, Element],
        agents: dict[str, Element],
        realizes_pairs: set[tuple[str, str]] | frozenset[tuple[str, str]],
        unavailable_fields: frozenset[str] = frozenset(),
    ) -> PortfolioSnapshot:
        """Build the integration element maps (endpoints with names, domains, cross_domain).
        ``applications`` must already carry ``domain_ids``."""

        def endpoint(app_id: str) -> Element:
            app = applications.get(app_id, {})
            return {
                "id": app_id,
                "name": app.get("name", app_id),
                "domain_ids": list(app.get("domain_ids", [])),
            }

        integrations: dict[str, Element] = {}
        by_pair: dict[tuple[str, str], list[str]] = defaultdict(list)
        for iid, raw in raw_integrations.items():
            src, tgt = endpoint(raw["source_id"]), endpoint(raw["target_id"])
            if not src["domain_ids"] or not tgt["domain_ids"]:
                cross: bool | None = None
            else:
                cross = not set(src["domain_ids"]) & set(tgt["domain_ids"])
            integrations[iid] = {
                "id": iid,
                "name": f"{src['name']} → {tgt['name']}",
                "integration_type": raw.get("integration_type"),
                "description": raw.get("description"),
                "source": src,
                "target": tgt,
                "cross_domain": cross,
            }
            by_pair[(src["id"], tgt["id"])].append(iid)
        for ids in by_pair.values():
            ids.sort()
        return cls(
            elements={
                ElementType.APPLICATION: applications,
                ElementType.INTEGRATION: integrations,
                ElementType.BUSINESS_CAPABILITY: business_capabilities,
                ElementType.BUSINESS_DOMAIN: business_domains,
                ElementType.TECHNICAL_CAPABILITY: technical_capabilities,
                ElementType.VALUE_STREAM: value_streams,
                ElementType.AGENT: agents,
            },
            unavailable_fields=frozenset(unavailable_fields),
            realizes_pairs=frozenset(realizes_pairs),
            _by_pair=dict(by_pair),
        )

    # ── Lookups ─────────────────────────────────────────────────────────────────────────
    def of_type(self, element_type: ElementType) -> dict[str, Element]:
        return self.elements.get(element_type, {})

    def element(self, element_type: ElementType, element_id: str) -> Element | None:
        return self.of_type(element_type).get(element_id)

    def name(self, element_type: ElementType, element_id: str) -> str:
        el = self.element(element_type, element_id)
        return str(el.get("name", element_id)) if el else element_id

    # ── Evidence (FR-012) ───────────────────────────────────────────────────────────────
    def integrations_between(self, source_app: str, target_app: str) -> list[str]:
        return list(self._by_pair.get((source_app, target_app), []))

    def serves(self, app_id: str, capability_id: str) -> bool:
        app = self.element(ElementType.APPLICATION, app_id)
        return bool(app) and capability_id in app.get("capability_ids", [])  # type: ignore[union-attr]

    def realizes(self, app_id: str, technical_capability_id: str) -> bool:
        return (app_id, technical_capability_id) in self.realizes_pairs


def in_scope(snapshot: PortfolioSnapshot, scope: Scope, element_type: ElementType) -> list[str]:
    """Ids of the elements of ``element_type`` that are selector candidates in ``scope``
    (spec Edge Cases), sorted for determinism."""
    elements = snapshot.of_type(element_type)
    if scope.scope_type == ScopeType.PORTFOLIO:
        return sorted(elements)

    if scope.scope_type == ScopeType.BUSINESS_DOMAIN:
        domain = scope.scope_ref
        apps = {
            aid
            for aid, a in snapshot.of_type(ElementType.APPLICATION).items()
            if domain in a.get("domain_ids", [])
        }
        if element_type == ElementType.APPLICATION:
            return sorted(apps)
        if element_type == ElementType.BUSINESS_CAPABILITY:
            return sorted(cid for cid, c in elements.items() if c.get("domain_id") == domain)
        if element_type == ElementType.BUSINESS_DOMAIN:
            return [domain] if domain in elements else []
    else:  # APPLICATION_SET
        apps = set(scope.member_ids) & set(snapshot.of_type(ElementType.APPLICATION))
        if element_type == ElementType.APPLICATION:
            return sorted(apps)

    if element_type == ElementType.INTEGRATION:
        return sorted(
            iid
            for iid, i in elements.items()
            if i["source"]["id"] in apps or i["target"]["id"] in apps
        )
    return sorted(elements)
