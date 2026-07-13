"""Unit tests for the CALM exporter (ADP-SPEC-021 T003-T010)."""

from __future__ import annotations

import pytest

from adp.calm.exporter import _infer_protocol, map_design_to_calm
from adp.models import ArchitectureDescription


def _make_design(**kwargs) -> ArchitectureDescription:
    base = {
        "schema_version": "1.0.0",
        "id": "D-001",
        "title": "Test Design",
        "created_at": "2026-07-03T00:00:00Z",
        "updated_at": "2026-07-03T00:00:00Z",
        "elements": [],
        "requirements": [],
        "relationships": [],
    }
    base.update(kwargs)
    return ArchitectureDescription.model_validate(base)


def _el(id: str, kind: str, name: str = "Test", description: str = "desc") -> dict:
    # ElementId pattern: ^ELM-\d{3}$
    return {"id": id, "kind": kind, "name": name, "description": description}


def _req(id: str, title: str = "Req", description: str = "Some requirement") -> dict:
    # RequirementId pattern: ^REQ-\d{3}$
    return {"id": id, "title": title, "description": description}


def _rel(id: str, source: str, target: str, technology: str | None = None) -> dict:
    # RelationshipId pattern: ^REL-\d{3}$
    return {"id": id, "source": source, "target": target, "technology": technology}


# ── T003: person → actor ──────────────────────────────────────────────────────

def test_person_element_maps_to_actor():
    design = _make_design(elements=[_el("ELM-001", "person", "Alice")])
    doc = map_design_to_calm(design)
    assert len(doc.nodes) == 1
    assert doc.nodes[0].node_type == "actor"
    assert doc.nodes[0].unique_id == "ELM-001"


# ── T004: system → system ─────────────────────────────────────────────────────

def test_system_element_maps_to_system():
    design = _make_design(elements=[_el("ELM-002", "system", "Payment Service")])
    doc = map_design_to_calm(design)
    assert doc.nodes[0].node_type == "system"


# ── T005: container and component → service ───────────────────────────────────

def test_container_element_maps_to_service():
    design = _make_design(elements=[_el("ELM-003", "container", "API Container")])
    doc = map_design_to_calm(design)
    assert doc.nodes[0].node_type == "service"


def test_component_element_maps_to_service():
    design = _make_design(elements=[_el("ELM-004", "component", "Auth Handler")])
    doc = map_design_to_calm(design)
    assert doc.nodes[0].node_type == "service"


# ── T006: relationship maps to connects ──────────────────────────────────────

def test_relationship_maps_to_connects():
    design = _make_design(
        elements=[_el("ELM-001", "person"), _el("ELM-002", "system")],
        relationships=[_rel("REL-001", "ELM-001", "ELM-002", "HTTPS")],
    )
    doc = map_design_to_calm(design)
    assert len(doc.relationships) == 1
    rel = doc.relationships[0]
    assert rel.relationship_type == "connects"
    assert rel.unique_id == "REL-001"
    assert rel.connects.source_node == "ELM-001"
    assert rel.connects.destination_node == "ELM-002"


# ── T007: requirement maps to control ────────────────────────────────────────

def test_requirement_maps_to_control():
    design = _make_design(
        elements=[_el("ELM-001", "system")],
        requirements=[_req("REQ-001", "Scalability", "System must handle 10k concurrent users")],
    )
    doc = map_design_to_calm(design)
    assert doc.controls is not None
    assert len(doc.controls) == 1
    ctrl = doc.controls[0]
    assert ctrl.control_requirement_url == "urn:adp:requirement:REQ-001"
    assert ctrl.description == "System must handle 10k concurrent users"


# ── T008: metadata carries provenance ────────────────────────────────────────

def test_metadata_carries_provenance():
    design = _make_design()
    doc = map_design_to_calm(design)
    assert doc.metadata is not None
    metadata_map = {list(m.keys())[0]: list(m.values())[0] for m in doc.metadata}
    assert metadata_map["source"] == "adp"
    assert metadata_map["design-id"] == "D-001"
    assert "exported-at" in metadata_map


# ── T009: empty design produces valid CALM ────────────────────────────────────

def test_empty_design_produces_valid_calm():
    design = _make_design()
    doc = map_design_to_calm(design)
    assert doc.nodes == []
    assert doc.relationships == []
    assert doc.controls is None
    # Serializes without error
    data = doc.model_dump_calm()
    assert "nodes" in data
    assert "relationships" in data
    assert isinstance(data["nodes"], list)


# ── T010: protocol inference ──────────────────────────────────────────────────

@pytest.mark.parametrize("technology,expected_protocol", [
    ("kafka", "AMQP"),
    ("rabbitmq", "AMQP"),
    ("event-bus", "AMQP"),
    ("https", "HTTPS"),
    ("HTTPS", "HTTPS"),
    ("http", "HTTP"),
    ("jdbc", "JDBC"),
    ("postgresql", "JDBC"),
    ("websocket", "WebSocket"),
    ("mtls", "mTLS"),
    ("tls", "TLS"),
    ("sftp", "SFTP"),
    ("ldap", "LDAP"),
    ("unknown-protocol", "HTTPS"),
    (None, "HTTPS"),
    ("", "HTTPS"),
])
def test_protocol_inference(technology, expected_protocol):
    assert _infer_protocol(technology) == expected_protocol


# ── Additional: model_dump_calm round-trip ────────────────────────────────────

def test_model_dump_calm_produces_kebab_case_keys():
    design = _make_design(
        elements=[_el("ELM-001", "person", "Alice", "End user")],
        relationships=[_rel("REL-001", "ELM-001", "ELM-001", "https")],
        requirements=[_req("REQ-001")],
    )
    doc = map_design_to_calm(design)
    data = doc.model_dump_calm()

    # Node keys
    node = data["nodes"][0]
    assert "unique-id" in node
    assert "node-type" in node
    assert "unique_id" not in node

    # Relationship keys
    rel = data["relationships"][0]
    assert "unique-id" in rel
    assert "relationship-type" in rel
    assert rel["connects"]["source-node"] == "ELM-001"
    assert rel["connects"]["destination-node"] == "ELM-001"

    # Control keys
    ctrl = data["controls"][0]
    assert "control-requirement-url" in ctrl
