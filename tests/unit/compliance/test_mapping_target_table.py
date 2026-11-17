"""One table describes every entity-targeted mapping type (ADP-blp.27).

A new target should be one entry in the store's table and one in the router's; these
fail if the two disagree or if a per-target wrapper is left out.
"""

from __future__ import annotations

import pytest

from adp.compliance import router as crouter
from adp.compliance import store as cstore
from adp.compliance.models import MappingTargetType


def test_every_entity_target_has_routes_and_only_those() -> None:
    routed = [spec.target_type for spec in crouter._ENTITY_MAPPING_ROUTES]

    assert routed == list(cstore._ENTITY_TARGETS)
    assert MappingTargetType.ORGANIZATION not in cstore._ENTITY_TARGETS
    assert set(MappingTargetType) - set(routed) == {MappingTargetType.ORGANIZATION}


def test_each_target_keeps_its_named_routes_and_path_parameter() -> None:
    by_name = {route.name: route.path for route in crouter.router.routes}

    for spec in crouter._ENTITY_MAPPING_ROUTES:
        noun = spec.target_type.value
        base = (
            "/api/v1/compliance/controls/{control_id}/mappings/"
            f"{spec.segment}/{{{spec.param}}}"
        )
        assert by_name[f"upsert_{noun}_mapping"] == base
        assert by_name[f"delete_{noun}_mapping"] == base
        assert by_name[f"list_{noun}_mapping_initiatives"] == base + "/initiatives"


def test_each_target_has_its_store_wrappers() -> None:
    for target_type in cstore._ENTITY_TARGETS:
        noun = target_type.value
        names = (f"upsert_{noun}_mapping", f"delete_{noun}_mapping", f"list_mappings_for_{noun}")
        for name in names:
            assert callable(getattr(cstore, name)), name


def test_the_key_column_belongs_to_its_table() -> None:
    for target in cstore._ENTITY_TARGETS.values():
        assert target.column in target.table.c
        assert "control_id" in target.table.c


@pytest.mark.asyncio
async def test_the_generic_functions_refuse_the_estate_wide_type() -> None:
    with pytest.raises(ValueError, match="not an entity-targeted mapping type"):
        await cstore.list_mappings_for_entity(MappingTargetType.ORGANIZATION, "x", None)  # type: ignore[arg-type]
