"""Maps an ADP ArchitectureDescription to a CALM document (ADP-SPEC-021).

Element kind mapping (FR-002 to FR-004):
  person    → actor
  system    → system
  container → service
  component → service

All ADP relationships become CALM `connects` relationships (FR-006).
Protocol inferred from relationship.technology label (FR-007).
Requirements mapped to CALM controls (FR-008).
Provenance metadata added per ART-XI (FR-009).
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import TYPE_CHECKING

from adp.calm.models import (
    CALMConnects,
    CALMControl,
    CALMDocument,
    CALMNode,
    CALMRelationship,
)
from adp.models import ElementKind

if TYPE_CHECKING:
    from adp.models import ArchitectureDescription

# ── Element kind → CALM node-type ────────────────────────────────────────────

_KIND_TO_NODE_TYPE: dict[ElementKind, str] = {
    ElementKind.PERSON: "actor",
    ElementKind.SYSTEM: "system",
    ElementKind.CONTAINER: "service",
    ElementKind.COMPONENT: "service",
}

# ── Protocol inference ────────────────────────────────────────────────────────

_PROTOCOL_RULES: list[tuple[list[str], str]] = [
    (["amqp", "rabbit", "kafka", "event", "pubsub", "queue", "mq"], "AMQP"),
    (["jdbc", "sql", "postgres", "mysql", "db", "database"], "JDBC"),
    (["websocket", "ws://", "wss://"], "WebSocket"),
    (["ldap"], "LDAP"),
    (["ftp", "sftp"], "SFTP"),
    (["mtls", "mutual-tls"], "mTLS"),
    (["tls", "tcp"], "TLS"),
    (["https", "ssl"], "HTTPS"),
    (["http"], "HTTP"),
]


def _infer_protocol(technology: str | None) -> str:
    """Return the closest CALM protocol string for an ADP technology label."""
    if not technology:
        return "HTTPS"
    tech_lower = technology.lower()
    for keywords, protocol in _PROTOCOL_RULES:
        if any(kw in tech_lower for kw in keywords):
            return protocol
    return "HTTPS"


# ── Main mapping function ─────────────────────────────────────────────────────

def map_design_to_calm(design: "ArchitectureDescription") -> CALMDocument:
    """Convert an ADP ArchitectureDescription to a CALM document.

    Produces a valid CALM draft 2025-03 JSON structure with nodes, relationships,
    controls (from requirements), and provenance metadata.
    """
    # Nodes
    nodes: list[CALMNode] = []
    for el in design.elements:
        node_type = _KIND_TO_NODE_TYPE.get(el.kind, "service")
        node_metadata: list[dict] = [
            {"adp-kind": el.kind.value},
            {"adp-design-id": design.id},
        ]
        if el.tags:
            node_metadata.append({"tags": el.tags})
        nodes.append(CALMNode(**{  # type: ignore[arg-type]
            "unique-id": el.id,
            "node-type": node_type,
            "name": el.name,
            "description": el.description or el.name,
            "metadata": node_metadata,
        }))

    # Relationships — all become CALM `connects`
    relationships: list[CALMRelationship] = []
    for rel in design.relationships:
        protocol = _infer_protocol(rel.technology)
        connects = CALMConnects(**{
            "source-node": rel.source,
            "destination-node": rel.target,
            "protocol": protocol,
        })
        relationships.append(CALMRelationship(**{  # type: ignore[arg-type]
            "unique-id": rel.id,
            "relationship-type": "connects",
            "connects": connects,
        }))

    # Controls — one per requirement
    controls: list[CALMControl] | None = None
    if design.requirements:
        controls = [
            CALMControl(**{
                "control-requirement-url": f"urn:adp:requirement:{req.id}",
                "description": req.description,
            })
            for req in design.requirements
        ]

    # Provenance metadata (ART-XI)
    metadata: list[dict] = [
        {"source": "adp"},
        {"adp-version": "1.0.0"},
        {"design-id": design.id},
        {"design-title": design.title},
        {"exported-at": datetime.now(timezone.utc).isoformat()},
    ]

    return CALMDocument(
        nodes=nodes,
        relationships=relationships,
        controls=controls or None,
        metadata=metadata,
    )
