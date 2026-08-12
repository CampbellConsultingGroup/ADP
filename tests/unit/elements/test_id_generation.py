"""Unit tests: max-plus-one element/relationship id generation (ADP-SPEC-054,
research.md Decision 2) -- collision-safe once deletion exists, unlike the
recommendation-orchestrator's own additions-only len+1 precedent."""

from __future__ import annotations

from types import SimpleNamespace

from adp.api.routers.elements import next_element_id, next_relationship_id
from adp.models import Element, Relationship


def _design(elements: list[Element] | None = None, relationships: list[Relationship] | None = None):
    return SimpleNamespace(elements=elements or [], relationships=relationships or [])


def test_next_element_id_for_empty_design() -> None:
    assert next_element_id(_design()) == "ELM-001"


def test_next_element_id_after_three_contiguous() -> None:
    design = _design([
        Element(id="ELM-001", name="A", kind="person"),
        Element(id="ELM-002", name="B", kind="system"),
        Element(id="ELM-003", name="C", kind="system"),
    ])
    assert next_element_id(design) == "ELM-004"


def test_next_element_id_is_collision_safe_after_a_gap() -> None:
    # ELM-002 was deleted; a naive len()+1 formula would produce "ELM-003" again,
    # colliding with the surviving element -- max()+1 does not.
    design = _design([
        Element(id="ELM-001", name="A", kind="person"),
        Element(id="ELM-003", name="C", kind="system"),
    ])
    assert next_element_id(design) == "ELM-004"


def test_next_relationship_id_for_empty_design() -> None:
    assert next_relationship_id(_design()) == "REL-001"


def test_next_relationship_id_is_collision_safe_after_a_gap() -> None:
    design = _design(relationships=[
        Relationship(id="REL-001", source="ELM-001", target="ELM-002"),
        Relationship(id="REL-003", source="ELM-002", target="ELM-003"),
    ])
    assert next_relationship_id(design) == "REL-004"
