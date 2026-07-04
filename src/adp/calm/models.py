"""Pydantic v2 models for CALM (Common Architecture Language Model) draft 2025-03.

Field names follow the CALM JSON schema conventions (kebab-case).
Serialization uses `by_alias=True` to produce the correct JSON keys.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

# ── Import result (ADP-SPEC-022) — defined here to avoid circular imports ─────


class CALMImportResult(BaseModel):
    """Result of a CALM pattern import operation."""

    items_created: int = 0
    items_updated: int = 0
    items_failed: int = 0
    errors: list[str] = Field(default_factory=list)
    items: list[dict] = Field(default_factory=list)  # KnowledgeItemSummary dicts


def _kebab(field_name: str) -> str:
    return field_name.replace("_", "-")


_CALM_CONFIG = ConfigDict(populate_by_name=True)


class CALMNode(BaseModel):
    model_config = _CALM_CONFIG

    unique_id: str = Field(alias="unique-id")
    node_type: str = Field(alias="node-type")
    name: str
    description: str
    metadata: list[dict] | None = None

    def model_dump_calm(self) -> dict:
        d: dict = {
            "unique-id": self.unique_id,
            "node-type": self.node_type,
            "name": self.name,
            "description": self.description,
        }
        if self.metadata:
            d["metadata"] = self.metadata
        return d


class CALMConnects(BaseModel):
    model_config = _CALM_CONFIG

    source_node: str = Field(alias="source-node")
    destination_node: str = Field(alias="destination-node")
    protocol: str | None = None

    def model_dump_calm(self) -> dict:
        d: dict = {
            "source-node": self.source_node,
            "destination-node": self.destination_node,
        }
        if self.protocol:
            d["protocol"] = self.protocol
        return d


class CALMRelationship(BaseModel):
    model_config = _CALM_CONFIG

    unique_id: str = Field(alias="unique-id")
    relationship_type: str = Field(alias="relationship-type", default="connects")
    connects: CALMConnects

    def model_dump_calm(self) -> dict:
        return {
            "unique-id": self.unique_id,
            "relationship-type": self.relationship_type,
            "connects": self.connects.model_dump_calm(),
        }


class CALMControl(BaseModel):
    model_config = _CALM_CONFIG

    control_requirement_url: str = Field(alias="control-requirement-url")
    description: str

    def model_dump_calm(self) -> dict:
        return {
            "control-requirement-url": self.control_requirement_url,
            "description": self.description,
        }


class CALMDocument(BaseModel):
    model_config = _CALM_CONFIG

    nodes: list[CALMNode] = Field(default_factory=list)
    relationships: list[CALMRelationship] = Field(default_factory=list)
    controls: list[CALMControl] | None = None
    metadata: list[dict] | None = None

    def model_dump_calm(self) -> dict:
        d: dict = {
            "nodes": [n.model_dump_calm() for n in self.nodes],
            "relationships": [r.model_dump_calm() for r in self.relationships],
        }
        if self.controls:
            d["controls"] = [c.model_dump_calm() for c in self.controls]
        if self.metadata:
            d["metadata"] = self.metadata
        return d
