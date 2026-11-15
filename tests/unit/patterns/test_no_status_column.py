"""Guard: conformance status, plateau and findings are derived on read, never stored (936 SC-007).

Checks both the store's table metadata and the DDL of every pattern migration (044, 045)."""

from __future__ import annotations

import re
from pathlib import Path

from adp.patterns import adoptions  # noqa: F401 - registers the adoption tables
from adp.patterns import store as pstore

FORBIDDEN = re.compile(r"status|plateau|finding|conformance|verdict", re.I)
MIGRATIONS = (
    Path(__file__).resolve().parents[3] / "src" / "adp" / "store" / "migrations" / "versions"
)


def test_no_pattern_table_stores_a_derived_result() -> None:
    tables = [t for t in pstore._metadata.sorted_tables if t.name.startswith("ea_pattern")]
    assert {t.name for t in tables} >= {"ea_pattern_adoption", "ea_pattern_adoption_pin"}
    for table in tables:
        for column in table.columns:
            assert not FORBIDDEN.search(column.name), f"{table.name}.{column.name}"


def test_pattern_migrations_add_no_such_column() -> None:
    for name in ("044_ea_pattern_registry.py", "045_ea_pattern_adoption.py"):
        text = (MIGRATIONS / name).read_text()
        columns = re.findall(r'sa\.Column\(\s*"([a-z_]+)"', text)
        assert columns, name
        assert not [c for c in columns if FORBIDDEN.search(c)], name
