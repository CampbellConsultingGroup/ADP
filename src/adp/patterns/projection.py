"""Knowledge-base projection of a pattern family's current version (935 FR-013, research D6).

Pure: builds the text and metadata of the single ``knowledge_items`` row the registry owns for a
family. The store writes it; nothing else may edit it (FR-015).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from adp.patterns.models import PatternDefinition, PatternKind

PROJECTION_PREFIX = "adp-pattern:"
MANAGED_BY = "pattern-registry"


@dataclass(frozen=True)
class ProjectedItem:
    id: str
    source_ref: str
    kind: str
    version: str
    title: str
    full_text: str
    metadata: dict[str, Any] = field(default_factory=dict)


def projection_id(pattern_key: str) -> str:
    return f"{PROJECTION_PREFIX}{pattern_key}"


def knowledge_kind_for(kind: PatternKind | str) -> str:
    """Reference architectures project as ``reference_architecture``; the rest as ``pattern``."""
    return (
        "reference_architecture"
        if PatternKind(kind) == PatternKind.REFERENCE_ARCHITECTURE
        else "pattern"
    )


def build_projection(defn: PatternDefinition) -> ProjectedItem:
    m = defn.motivation
    lines = [defn.summary, f"Context: {m.context}", f"Problem: {m.problem}"]
    for label, items in (
        ("Forces", m.forces),
        ("Benefits", m.benefits),
        ("Liabilities", m.liabilities),
    ):
        if items:
            lines.append(f"{label}: {'; '.join(items)}")
    if defn.tags:
        lines.append(f"Tags: {', '.join(defn.tags)}")
    pid = projection_id(defn.pattern)
    return ProjectedItem(
        id=pid,
        source_ref=pid,
        kind=knowledge_kind_for(defn.kind),
        version=defn.version,
        title=defn.name,
        full_text="\n".join(lines),
        metadata={
            "managed_by": MANAGED_BY,
            "pattern_key": defn.pattern,
            "pattern_version": defn.version,
            "pattern_kind": defn.kind.value,
        },
    )
