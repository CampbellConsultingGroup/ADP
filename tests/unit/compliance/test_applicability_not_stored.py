"""948 GEO-03 FR-006: applicability is derived on read and never stored."""

from __future__ import annotations

import re
from pathlib import Path

import adp.compliance.jurisdiction  # noqa: F401 -- registers the jurisdiction tables
from tests.support.schema import STORE_MODULES

MIGRATION = (
    Path(__file__).parents[3] / "src/adp/store/migrations/versions/059_framework_jurisdiction.py"
)


def test_no_table_or_column_stores_applicability() -> None:
    import importlib

    for name in STORE_MODULES:
        metadata = getattr(importlib.import_module(name), "_metadata", None)
        if metadata is None:
            continue
        for table in metadata.tables.values():
            assert "applicab" not in table.name, table.name
            assert not any("applicab" in c.name for c in table.columns), table.name


def test_migration_059_creates_only_the_jurisdiction() -> None:
    text = MIGRATION.read_text()
    created = re.findall(r'create_table\(\s*"([^"]+)"', text)
    assert created == ["framework_jurisdiction_geographies", "framework_jurisdiction_triggers"]
    assert "add_column" not in text and "alter_column" not in text
