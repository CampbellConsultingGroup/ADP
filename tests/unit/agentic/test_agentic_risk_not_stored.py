"""Guard (944-agent-traceability, ADP-12x, SC-006): the agentic risk band and an agent's
compliance status are derived on read and never stored. No column in migration 052 or in the
agentic / compliance metadata may hold a risk band or a derived agent status.
"""

from __future__ import annotations

import pathlib
import re

from adp.agentic import store as agstore
from adp.compliance import store as cstore

_FORBIDDEN = re.compile(r"risk|band", re.IGNORECASE)
_MIGRATION = (
    pathlib.Path(__file__).resolve().parents[3]
    / "src/adp/store/migrations/versions/052_agent_traceability.py"
)


def test_no_risk_or_band_column_in_metadata():
    for metadata in (agstore._metadata, cstore._metadata):
        for table in metadata.tables.values():
            for column in table.columns:
                assert not _FORBIDDEN.search(column.name), f"{table.name}.{column.name}"


def test_migration_052_adds_no_risk_or_status_column_to_agents():
    text = _MIGRATION.read_text()
    assert not _FORBIDDEN.search(text.split('"""', 2)[2]), "migration 052 stores a risk value"
    assert "add_column" not in text, "migration 052 must only add tables"
