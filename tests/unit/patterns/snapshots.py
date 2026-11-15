"""In-memory portfolio snapshot builder for the pure engine tests (936 tasks T001).

    snap = (SnapshotBuilder()
            .domain("d1", "Claims").capability("c1", "Claims Handling", domain="d1")
            .app("a1", "Claims Core", caps=["c1"], time_classification="Invest")
            .integration("i1", "a1", "a2", integration_type="event")
            .build())

Domains of applications and integration endpoints are derived exactly as the real snapshot store
does (via the capabilities' domains), so engine tests exercise realistic element maps.
"""

from __future__ import annotations

from typing import Any

from adp.patterns.models import ElementType as T
from adp.patterns.snapshot import PortfolioSnapshot, derive_application_domains


class SnapshotBuilder:
    def __init__(self) -> None:
        self._apps: dict[str, dict[str, Any]] = {}
        self._integrations: dict[str, dict[str, Any]] = {}
        self._caps: dict[str, dict[str, Any]] = {}
        self._domains: dict[str, dict[str, Any]] = {}
        self._tcaps: dict[str, dict[str, Any]] = {}
        self._agents: dict[str, dict[str, Any]] = {}
        self._streams: dict[str, dict[str, Any]] = {}
        self._realizes: set[tuple[str, str]] = set()
        self._unavailable: set[str] = set()

    def domain(self, did: str, name: str, **extra: Any) -> SnapshotBuilder:
        self._domains[did] = {
            "id": did,
            "name": name,
            "classification": "differentiating",
            "risk_flags": [],
            **extra,
        }
        return self

    def capability(
        self,
        cid: str,
        name: str,
        *,
        domain: str | None = None,
        parent: str | None = None,
        level: int = 1,
        **extra: Any,
    ) -> SnapshotBuilder:
        self._caps[cid] = {
            "id": cid,
            "name": name,
            "level": level,
            "parent_id": parent,
            "domain_id": domain,
            "strategic_relevance": None,
            "maturity_level": None,
            **extra,
        }
        return self

    def app(
        self,
        aid: str,
        name: str,
        *,
        caps: list[str] | None = None,
        tcaps_provided: list[str] | None = None,
        **extra: Any,
    ) -> SnapshotBuilder:
        base: dict[str, Any] = {
            "id": aid,
            "name": name,
            "lifecycle_status": "active",
            "application_type": "custom",
            "time_classification": "Invest",
            "r_strategy": None,
            "pace_layer": None,
            "hosting_model": None,
            "architecture_pattern": None,
            "business_criticality": None,
            "health_score": None,
            "tech_debt_flags": [],
            "capability_ids": list(caps or []),
            "technical_capability_ids": list(tcaps_provided or []),
        }
        base.update(extra)
        self._apps[aid] = base
        for tc in tcaps_provided or []:
            self._realizes.add((aid, tc))
        return self

    def integration(
        self, iid: str, source: str, target: str, *, integration_type: str = "API", **extra: Any
    ) -> SnapshotBuilder:
        self._integrations[iid] = {
            "id": iid,
            "integration_type": integration_type,
            "description": None,
            "source_id": source,
            "target_id": target,
            **extra,
        }
        return self

    def tcap(self, tid: str, name: str) -> SnapshotBuilder:
        self._tcaps[tid] = {"id": tid, "name": name, "level": 1, "parent_id": None}
        return self

    def agent(self, gid: str, name: str, **extra: Any) -> SnapshotBuilder:
        self._agents[gid] = {
            "id": gid,
            "name": name,
            "lifecycle_status": "active",
            "autonomy_level": 1,
            "human_approval": "always",
            "data_classification_max": None,
            "solution_ids": [],
            **extra,
        }
        return self

    def unavailable(self, *fields: str) -> SnapshotBuilder:
        self._unavailable.update(fields)
        return self

    def build(self) -> PortfolioSnapshot:
        caps = {k: dict(v) for k, v in self._caps.items()}
        apps = {k: dict(v) for k, v in self._apps.items()}
        derive_application_domains(apps, caps)
        for app in apps.values():
            for field in self._unavailable:
                app.pop(field, None)
        return PortfolioSnapshot.from_parts(
            applications=apps,
            raw_integrations=self._integrations,
            business_capabilities=caps,
            business_domains=self._domains,
            technical_capabilities=self._tcaps,
            value_streams=self._streams,
            agents=self._agents,
            realizes_pairs=self._realizes,
            unavailable_fields=frozenset(self._unavailable),
        )


__all__ = ["SnapshotBuilder", "T"]


def make_pattern(
    roles: dict[str, dict[str, Any]],
    *,
    relationships: list[dict[str, Any]] | None = None,
    constraints: list[dict[str, Any]] | None = None,
    kind: str = "reference-architecture",
    transition: dict[str, Any] | None = None,
    key: str = "ea.test.pattern",
):  # type: ignore[no-untyped-def]
    """A validated PatternDefinition from compact parts (defaults fill the boilerplate)."""
    from adp.patterns.models import PatternDefinition

    data: dict[str, Any] = {
        "pattern": key,
        "version": "1.0.0",
        "kind": kind,
        "name": "Test pattern",
        "summary": "For engine tests.",
        "owner_role": "enterprise",
        "motivation": {"context": "c", "problem": "p"},
        "roles": roles,
        "relationships": relationships or [],
        "constraints": constraints or [],
    }
    if transition is not None:
        data["transition"] = transition
    return PatternDefinition.model_validate(data)
