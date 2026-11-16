"""Guard: capability <-> org unit analysis is derived on read, never stored (941 FR-013 / SC-004).

Effective owners, findings (no owner, shared-service candidates, unmapped, owned-no-performer),
geography notes and footprints must never get a column. The only stored addition is the mapping
table itself (migration 049)."""

from __future__ import annotations

import re
from pathlib import Path

from adp.application import store as astore
from adp.business import store as bstore
from adp.organization import store as ostore

FORBIDDEN = re.compile(
    r"effective|inherited|shared_service|unmapped|footprint|branch|outside|finding|no_owner", re.I
)
MIGRATIONS = (
    Path(__file__).resolve().parents[3] / "src" / "adp" / "store" / "migrations" / "versions"
)


def test_no_table_stores_a_capability_org_analysis_result() -> None:
    for metadata in (ostore._metadata, bstore._metadata, astore._metadata):
        for table in metadata.sorted_tables:
            assert not FORBIDDEN.search(table.name), table.name
            for column in table.columns:
                assert not FORBIDDEN.search(column.name), f"{table.name}.{column.name}"


def test_migration_049_adds_only_the_mapping_table() -> None:
    text = (MIGRATIONS / "049_capability_org_mappings.py").read_text()
    columns = re.findall(r'sa\.Column\(\s*"([a-z_]+)"', text)
    assert sorted(columns) == [
        "capability_id",
        "created_at",
        "geography_id",
        "id",
        "org_unit_id",
        "role",
    ]
    assert text.count("create_table") == 1
    assert "add_column" not in text
