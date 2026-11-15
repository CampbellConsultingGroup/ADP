"""Guard: capability-model analysis is derived on read, never stored (938 FR-022 / SC-006).

Roll-ups, bands, impact, exposure, gaps, overlaps and shared findings must never get a column.
The only stored additions are the technical capability lifecycle fields (migration 047)."""

from __future__ import annotations

import re
from pathlib import Path

from adp.application import store as astore

FORBIDDEN = re.compile(r"rollup|worst|spread|band|exposure|impact|overlap|gap|finding", re.I)
MIGRATIONS = (
    Path(__file__).resolve().parents[3] / "src" / "adp" / "store" / "migrations" / "versions"
)


def test_no_application_table_stores_an_analysis_result() -> None:
    for table in astore._metadata.sorted_tables:
        assert not FORBIDDEN.search(table.name), table.name
        for column in table.columns:
            assert not FORBIDDEN.search(column.name), f"{table.name}.{column.name}"


def test_migration_047_adds_only_the_lifecycle_columns() -> None:
    text = (MIGRATIONS / "047_tech_cap_lifecycle.py").read_text()
    columns = re.findall(r'sa\.Column\(\s*"([a-z_]+)"', text)
    assert sorted(columns) == ["end_of_life_date", "lifecycle_status"]
    assert "create_table" not in text
