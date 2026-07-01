"""Tests for GitConnector and DesignStoreConnector (US2, FR-004, FR-006)."""

from __future__ import annotations

from pathlib import Path

import pytest

from adp.knowledge.connectors.git import GitConnector
from adp.knowledge.schema import KnowledgeType, SchemaValidationError


def _write_md(tmp_path: Path, name: str, content: str) -> Path:
    p = tmp_path / name
    p.write_text(content)
    return p


def test_git_connector_parses_frontmatter(tmp_path: Path) -> None:
    """GitConnector reads id, version, kind, title from frontmatter (FR-004)."""
    _write_md(tmp_path, "pat-001.md", """---
id: PAT-001
version: "1.0.0"
kind: pattern
title: "API Gateway Pattern"
tags: [api, gateway]
---

## Overview
This pattern provides a single entry point.
""")
    connector = GitConnector(repo_url="", local_path=str(tmp_path))
    items = list(connector.read_items())
    assert len(items) == 1
    item = items[0]
    assert item.id == "PAT-001"
    assert item.version == "1.0.0"
    assert item.kind == KnowledgeType.PATTERN
    assert item.title == "API Gateway Pattern"
    assert "Overview" in item.full_text


def test_git_connector_id_from_frontmatter(tmp_path: Path) -> None:
    """id is taken from frontmatter, not from filename."""
    _write_md(tmp_path, "random_name.md", """---
id: STD-005
version: "2.1.0"
kind: standard
title: "TLS Requirement"
---
All services must use TLS 1.3 or later.
""")
    connector = GitConnector(repo_url="", local_path=str(tmp_path))
    items = list(connector.read_items())
    assert items[0].id == "STD-005"


def test_git_connector_rejects_missing_id(tmp_path: Path) -> None:
    """Frontmatter without id raises SchemaValidationError (FR-006)."""
    _write_md(tmp_path, "bad.md", """---
version: "1.0.0"
kind: pattern
title: "Missing ID"
---
Content.
""")
    connector = GitConnector(repo_url="", local_path=str(tmp_path))
    with pytest.raises(SchemaValidationError, match="id"):
        list(connector.read_items())


def test_git_connector_rejects_unknown_kind(tmp_path: Path) -> None:
    """Unknown kind value raises SchemaValidationError."""
    _write_md(tmp_path, "bad_kind.md", """---
id: XXX-001
version: "1.0.0"
kind: blueprint
title: "Unknown Kind"
---
Content.
""")
    connector = GitConnector(repo_url="", local_path=str(tmp_path))
    with pytest.raises(SchemaValidationError, match="kind"):
        list(connector.read_items())


def test_git_connector_parses_relationship_frontmatter(tmp_path: Path) -> None:
    """GitConnector reads satisfies relationships from frontmatter (US3)."""
    _write_md(tmp_path, "pat-001.md", """---
id: PAT-001
version: "1.0.0"
kind: pattern
title: "Stateless Pattern"
satisfies: [PR-001, PR-002]
---
Stateless services are easier to scale.
""")
    connector = GitConnector(repo_url="", local_path=str(tmp_path))
    rels = list(connector.read_relationships())
    assert len(rels) == 2
    types = {r.relationship_type for r in rels}
    assert types == {"satisfies"}
    targets = {r.target_id for r in rels}
    assert targets == {"PR-001", "PR-002"}
    sources = {r.source_id for r in rels}
    assert sources == {"PAT-001"}


def test_git_connector_yaml_file(tmp_path: Path) -> None:
    """GitConnector reads YAML files in addition to Markdown."""
    _write_md(tmp_path, "ref-001.yaml", """---
id: REF-001
version: "1.0.0"
kind: reference_architecture
title: "Microservices Reference"
---
Reference architecture for microservices.
""")
    connector = GitConnector(repo_url="", local_path=str(tmp_path))
    items = list(connector.read_items())
    assert len(items) == 1
    assert items[0].kind == KnowledgeType.REFERENCE_ARCHITECTURE
