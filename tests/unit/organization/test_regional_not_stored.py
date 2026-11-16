"""Guard: regional analysis is derived on read, never stored (942 FR-012 / SC-004).

Applicability, heat map cells, deltas against the baseline and "scope needs updating" must never
get a column, and migration 050 must not alter any existing table -- in particular it must not
touch business_capabilities.maturity_level, the enterprise baseline."""

from __future__ import annotations

import re
from pathlib import Path

from adp.application import store as astore
from adp.business import store as bstore
from adp.organization import store as ostore

FORBIDDEN = re.compile(r"applicable|delta|heatmap|baseline|scope_needs|cell_state", re.I)
MIGRATIONS = (
    Path(__file__).resolve().parents[3] / "src" / "adp" / "store" / "migrations" / "versions"
)


def test_no_table_stores_a_regional_analysis_result() -> None:
    for metadata in (ostore._metadata, bstore._metadata, astore._metadata):
        for table in metadata.sorted_tables:
            assert not FORBIDDEN.search(table.name), table.name
            for column in table.columns:
                assert not FORBIDDEN.search(column.name), f"{table.name}.{column.name}"


def test_migration_050_only_creates_its_three_tables() -> None:
    text = (MIGRATIONS / "050_regional_assessments.py").read_text()
    created = re.findall(r'create_table\(\s*"([a-z_]+)"', text)
    assert sorted(created) == [
        "capability_regional_assessments",
        "region_specific_capabilities",
        "region_specific_capability_geographies",
    ]
    for op in ("add_column", "alter_column", "drop_column", "execute("):
        assert op not in text, op
