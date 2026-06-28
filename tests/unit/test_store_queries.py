"""Unit tests for store query logic — pure Python, no database required (US4 / FR-005)."""

from __future__ import annotations

import json
from datetime import datetime, timezone

import pytest

from adp.models import (
    ArchitectureDescription,
    AuditEntry,
    Element,
    ElementKind,
    Finding,
    Relationship,
    Requirement,
    SolutionOption,
    Verdict,
    VerdictStatus,
)
from adp.store.queries import (
    query_by_provenance,
    query_orphan_requirements,
    query_relationships,
    query_satisfies,
    query_verdict_chain,
)
from adp.store.store import EntityNotFoundError

_NOW = datetime(2026, 6, 27, 12, 0, 0, tzinfo=timezone.utc)


def _content(**overrides) -> dict:  # type: ignore[type-arg]
    """Build a minimal ArchitectureDescription content dict with optional overrides."""
    base = ArchitectureDescription(
        schema_version="1.0.0",
        id="D-001",
        title="Test",
        created_at=_NOW,
        updated_at=_NOW,
    )
    merged = json.loads(base.model_dump_json())
    merged.update(overrides)
    return merged


def _req(rid: str) -> dict:  # type: ignore[type-arg]
    return {"id": rid, "title": f"Req {rid}", "description": "D", "tags": []}


def _elm(eid: str, satisfies: list = None, provenance: str | None = None) -> dict:  # type: ignore[type-arg]
    return {
        "id": eid, "name": f"Elm {eid}", "kind": "container",
        "satisfies": satisfies or [], "provenance": provenance, "tags": [],
    }


def _opt(oid: str, satisfies: list = None, provenance: str | None = None) -> dict:  # type: ignore[type-arg]
    return {
        "id": oid, "title": f"Opt {oid}", "description": "D",
        "status": "pending", "satisfies": satisfies or [], "provenance": provenance,
    }


def _rel(rid: str, source: str, target: str) -> dict:  # type: ignore[type-arg]
    return {"id": rid, "source": source, "target": target}


def _verdict(vid: str, option_id: str) -> dict:  # type: ignore[type-arg]
    return {
        "id": vid, "option_id": option_id, "status": "accepted",
        "rationale": "R", "decided_by": "board",
        "decided_at": _NOW.isoformat(),
    }


# ── query_satisfies ───────────────────────────────────────────────────────────


def test_query_satisfies_returns_matching_elements() -> None:
    content = _content(
        requirements=[_req("REQ-001")],
        elements=[
            _elm("ELM-001", satisfies=["REQ-001"]),
            _elm("ELM-002", satisfies=["REQ-001"]),
            _elm("ELM-003", satisfies=[]),
        ],
    )
    result = query_satisfies(content, "REQ-001")
    ids = {e.id for e in result}
    assert ids == {"ELM-001", "ELM-002"}


def test_query_satisfies_returns_empty_for_unknown_requirement() -> None:
    content = _content(elements=[_elm("ELM-001", satisfies=["REQ-001"])])
    result = query_satisfies(content, "REQ-999")
    assert result == []


# ── query_orphan_requirements ─────────────────────────────────────────────────


def test_query_orphan_requirements_identifies_orphans() -> None:
    content = _content(
        requirements=[_req("REQ-001"), _req("REQ-002")],
        elements=[_elm("ELM-001", satisfies=["REQ-001"])],
    )
    orphans = query_orphan_requirements(content)
    ids = {r.id for r in orphans}
    assert ids == {"REQ-002"}


def test_query_orphan_requirements_option_satisfies_counts() -> None:
    """An option satisfying a requirement removes it from orphans."""
    content = _content(
        requirements=[_req("REQ-001"), _req("REQ-002")],
        options=[_opt("OPT-001", satisfies=["REQ-002"])],
    )
    orphans = query_orphan_requirements(content)
    ids = {r.id for r in orphans}
    assert ids == {"REQ-001"}


def test_query_orphan_requirements_empty_when_all_satisfied() -> None:
    content = _content(
        requirements=[_req("REQ-001")],
        elements=[_elm("ELM-001", satisfies=["REQ-001"])],
    )
    assert query_orphan_requirements(content) == []


# ── query_verdict_chain ───────────────────────────────────────────────────────


def test_query_verdict_chain_returns_full_chain() -> None:
    content = _content(
        requirements=[_req("REQ-001")],
        elements=[_elm("ELM-001", satisfies=["REQ-001"])],
        options=[_opt("OPT-001", satisfies=["REQ-001"])],
        verdicts=[_verdict("VRD-001", "OPT-001")],
    )
    chain = query_verdict_chain(content, "OPT-001")
    assert chain.option.id == "OPT-001"
    assert chain.verdict is not None
    assert chain.verdict.id == "VRD-001"
    assert any(r.id == "REQ-001" for r in chain.satisfies_requirements)
    assert any(e.id == "ELM-001" for e in chain.satisfying_elements)


def test_query_verdict_chain_no_verdict_returns_none() -> None:
    content = _content(
        options=[_opt("OPT-001", satisfies=[])],
    )
    chain = query_verdict_chain(content, "OPT-001")
    assert chain.verdict is None


def test_query_verdict_chain_unknown_option_raises() -> None:
    content = _content()
    with pytest.raises(EntityNotFoundError):
        query_verdict_chain(content, "OPT-999")


# ── query_by_provenance ───────────────────────────────────────────────────────


def test_query_by_provenance_unit() -> None:
    content = _content(
        elements=[
            _elm("ELM-001", provenance="ai-rec-42"),
            _elm("ELM-002", provenance="human"),
            _elm("ELM-003"),  # no provenance
        ],
        options=[_opt("OPT-001", provenance="ai-rec-42")],
    )
    result = query_by_provenance(content, "ai-rec-42")
    ids = {x.id for x in result}
    assert ids == {"ELM-001", "OPT-001"}


def test_query_by_provenance_returns_empty_when_no_match() -> None:
    content = _content(elements=[_elm("ELM-001", provenance="human")])
    assert query_by_provenance(content, "nonexistent") == []


# ── query_relationships ───────────────────────────────────────────────────────


def test_query_relationships_unit() -> None:
    content = _content(
        elements=[_elm("ELM-001"), _elm("ELM-002"), _elm("ELM-003")],
        relationships=[
            _rel("REL-001", "ELM-001", "ELM-002"),
            _rel("REL-002", "ELM-003", "ELM-001"),  # ELM-001 is target here
            _rel("REL-003", "ELM-002", "ELM-003"),  # unrelated
        ],
    )
    result = query_relationships(content, "ELM-001")
    ids = {r.id for r in result}
    assert ids == {"REL-001", "REL-002"}


def test_query_relationships_returns_empty_for_isolated_element() -> None:
    content = _content(
        elements=[_elm("ELM-001"), _elm("ELM-002")],
        relationships=[_rel("REL-001", "ELM-001", "ELM-002")],
    )
    assert query_relationships(content, "ELM-999") == []


# ── store/logging unit tests ──────────────────────────────────────────────────


def test_save_emits_structured_log(caplog) -> None:  # type: ignore[type-arg]
    """log_operation emits JSON with required fields; never logs content or database_url."""
    import logging

    from adp.store.logging import log_operation

    with caplog.at_level(logging.INFO, logger="adp.store"):
        log_operation("save", "D-001", version_num=1, actor="jmuir", duration_ms=42.5)

    assert len(caplog.records) == 1
    entry = json.loads(caplog.records[0].message)
    assert entry["operation"] == "save"
    assert entry["design_id"] == "D-001"
    assert entry["duration_ms"] == 42.5
    assert "content" not in entry
    assert "database_url" not in entry


def test_log_operation_error_level_on_exception(caplog) -> None:  # type: ignore[type-arg]
    import logging

    from adp.store.logging import log_operation

    with caplog.at_level(logging.ERROR, logger="adp.store"):
        log_operation("get", "D-001", error=ValueError("boom"))

    assert len(caplog.records) == 1
    assert caplog.records[0].levelno == logging.ERROR
    entry = json.loads(caplog.records[0].message)
    assert "boom" in entry["error"]
