"""Guard (944-agent-traceability, ADP-12x, research.md R6): initiative <-> control-mapping
linkage (925) stays at five target types. MappingTargetType.AGENT exists for compliance mappings,
but no initiative link table, mirror or route accepts it.
"""

from __future__ import annotations

from adp.compliance.models import MappingTargetType
from adp.strategy import initiatives as sinit


def test_agent_absent_from_initiative_dispatch():
    assert MappingTargetType.AGENT not in sinit._LINK_TABLE_BY_TARGET_TYPE
    assert MappingTargetType.AGENT not in sinit._MIRROR_BY_TARGET_TYPE
    # The other five are all still present.
    assert set(sinit._LINK_TABLE_BY_TARGET_TYPE) == set(MappingTargetType) - {
        MappingTargetType.AGENT
    }


def test_no_strategy_route_takes_an_agent_target():
    from adp.api.app import create_app

    paths = [getattr(r, "path", "") for r in create_app().routes]
    assert not [p for p in paths if p.startswith("/api/v1/strategy") and "agents" in p]
