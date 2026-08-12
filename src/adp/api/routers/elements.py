"""Element/Relationship CRUD API — ADP-SPEC-054.

Replaces the currently-broken whole-design PUT (usePlaceElement/useDrawRelationship
called PUT /api/v1/designs/{id}, which has never had a matching route) with granular,
per-entity endpoints — the actual fix for ADP-914.1-.4. Mirrors tags.py's exact
fetch -> mutate -> audit -> save structure.

Every write produces an ART-IX audit entry. No cross-design concurrency handling is
added (research.md Decision 7) -- matches every other existing design-mutation
endpoint's own precedent of calling store.save() without expected_version.
"""

from __future__ import annotations

import logging
import re
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, ConfigDict, Field

from adp.models import AuditEntry, Element, ElementKind, Relationship

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/designs", tags=["elements"])

_ELM_ID_RE = re.compile(r"^ELM-(\d+)$")
_REL_ID_RE = re.compile(r"^REL-(\d+)$")


async def _get_design_store():  # type: ignore[return]
    from adp.api.deps import get_design_store
    return await get_design_store()


def _get_actor(request: Request) -> str:
    from adp.auth.models import UNAUTHENTICATED_USER
    user = getattr(request.state, "user", UNAUTHENTICATED_USER)
    if user is not UNAUTHENTICATED_USER:
        return user.username
    return request.headers.get("X-Actor", "architect")


def next_element_id(design) -> str:  # type: ignore[no-untyped-def]
    """Return the next ELM-NNN id via max(existing) + 1 -- collision-safe once
    deletion exists (research.md Decision 2; count+1 is NOT safe once ids can have
    gaps, unlike the recommendation-orchestrator's own additions-only precedent)."""
    max_n = 0
    for element in design.elements:
        m = _ELM_ID_RE.match(element.id)
        if m:
            max_n = max(max_n, int(m.group(1)))
    return f"ELM-{(max_n + 1):03d}"


def next_relationship_id(design) -> str:  # type: ignore[no-untyped-def]
    """Return the next REL-NNN id via max(existing) + 1 (same rationale as
    next_element_id)."""
    max_n = 0
    for relationship in design.relationships:
        m = _REL_ID_RE.match(relationship.id)
        if m:
            max_n = max(max_n, int(m.group(1)))
    return f"REL-{(max_n + 1):03d}"


# ── Request models ──────────────────────────────────────────────────────────────

class ElementCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    kind: ElementKind
    name: str = Field(min_length=1, max_length=120)


class ElementUpdate(BaseModel):
    """Name only for v1 (data-model.md) -- changing an element's kind is not a
    supported interaction; delete and recreate instead."""

    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1, max_length=120)


class RelationshipCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    source: str
    target: str
    label: str | None = Field(default=None, max_length=80)


# ── Helpers ───────────────────────────────────────────────────────────────────

async def _get_design_or_404(design_id: str, store):  # type: ignore[no-untyped-def]
    """Shared 404 handling for every endpoint below."""
    from adp.store.store import DesignNotFoundError  # type: ignore[attr-defined]

    try:
        return await store.get(design_id)
    except DesignNotFoundError:
        raise HTTPException(status_code=404, detail=f"Design {design_id!r} not found")


def _append_audit(design, actor: str, action: str, affected_entity: str, summary: str) -> None:  # type: ignore[no-untyped-def]
    from adp.audit.writer import next_audit_id

    design.audit_log.append(AuditEntry(
        id=next_audit_id(design),
        actor=actor,
        action=action,
        affected_entity=affected_entity,
        summary=summary[:240],
        timestamp=datetime.now(timezone.utc),
        origin="human",
    ))


# ── Element endpoints ─────────────────────────────────────────────────────────

@router.post("/{design_id}/elements", response_model=Element, status_code=201)
async def create_element(
    design_id: str,
    body: ElementCreate,
    raw_request: Request,
    store=Depends(_get_design_store),
) -> Element:
    """FR-002: add a new element directly, replacing the broken whole-design PUT."""
    design = await _get_design_or_404(design_id, store)

    new_id = next_element_id(design)
    element = Element(id=new_id, name=body.name, kind=body.kind)
    design.elements.append(element)

    actor = _get_actor(raw_request)
    _append_audit(
        design, actor, "create-element", new_id, f"Created {body.kind.value} {body.name!r}",
    )

    await store.save(design, actor=actor)
    logger.info("elements.create design=%s element=%s actor=%s", design_id, new_id, actor)
    return element


@router.patch("/{design_id}/elements/{element_id}", response_model=Element)
async def update_element(
    design_id: str,
    element_id: str,
    body: ElementUpdate,
    raw_request: Request,
    store=Depends(_get_design_store),
) -> Element:
    """FR-011: preserves every field except name -- description/satisfies/provenance/
    tags/technology_metadata are never touched here."""
    design = await _get_design_or_404(design_id, store)

    element = next((e for e in design.elements if e.id == element_id), None)
    if element is None:
        raise HTTPException(
            status_code=404, detail=f"Element {element_id!r} not found in design {design_id!r}",
        )

    old_name = element.name
    element.name = body.name

    actor = _get_actor(raw_request)
    _append_audit(
        design, actor, "update-element", element_id, f"Renamed {old_name!r} -> {body.name!r}",
    )

    await store.save(design, actor=actor)
    logger.info("elements.update design=%s element=%s actor=%s", design_id, element_id, actor)
    return element


@router.delete("/{design_id}/elements/{element_id}", status_code=204)
async def delete_element(
    design_id: str,
    element_id: str,
    raw_request: Request,
    store=Depends(_get_design_store),
) -> None:
    """FR-005 + Edge Cases: cascades to remove any relationship referencing this
    element -- required, since ArchitectureDescription's own model_validator
    (validate_references) rejects a relationship whose endpoint doesn't resolve."""
    design = await _get_design_or_404(design_id, store)

    element = next((e for e in design.elements if e.id == element_id), None)
    if element is None:
        raise HTTPException(
            status_code=404, detail=f"Element {element_id!r} not found in design {design_id!r}",
        )

    actor = _get_actor(raw_request)

    cascaded = [
        r for r in design.relationships if r.source == element_id or r.target == element_id
    ]
    design.relationships = [r for r in design.relationships if r not in cascaded]
    design.elements = [e for e in design.elements if e.id != element_id]

    for rel in cascaded:
        _append_audit(
            design, actor, "delete-relationship", rel.id, f"Cascaded from deleting {element_id}",
        )
    _append_audit(
        design, actor, "delete-element", element_id,
        f"Deleted {element.kind.value} {element.name!r}",
    )

    await store.save(design, actor=actor)
    logger.info(
        "elements.delete design=%s element=%s cascaded_relationships=%d actor=%s",
        design_id, element_id, len(cascaded), actor,
    )


# ── Relationship endpoints ────────────────────────────────────────────────────

@router.post("/{design_id}/relationships", response_model=Relationship, status_code=201)
async def create_relationship(
    design_id: str,
    body: RelationshipCreate,
    raw_request: Request,
    store=Depends(_get_design_store),
) -> Relationship:
    """FR-003: draw a relationship directly, replacing the broken whole-design PUT."""
    design = await _get_design_or_404(design_id, store)

    element_ids = {e.id for e in design.elements}
    if body.source not in element_ids:
        raise HTTPException(
            status_code=422,
            detail=f"source {body.source!r} is not an element in design {design_id!r}",
        )
    if body.target not in element_ids:
        raise HTTPException(
            status_code=422,
            detail=f"target {body.target!r} is not an element in design {design_id!r}",
        )

    new_id = next_relationship_id(design)
    relationship = Relationship(id=new_id, source=body.source, target=body.target, label=body.label)
    design.relationships.append(relationship)

    actor = _get_actor(raw_request)
    _append_audit(
        design, actor, "create-relationship", new_id,
        f"Connected {body.source} -> {body.target}" + (f" ({body.label})" if body.label else ""),
    )

    await store.save(design, actor=actor)
    logger.info("relationships.create design=%s relationship=%s actor=%s", design_id, new_id, actor)
    return relationship


@router.delete("/{design_id}/relationships/{relationship_id}", status_code=204)
async def delete_relationship(
    design_id: str,
    relationship_id: str,
    raw_request: Request,
    store=Depends(_get_design_store),
) -> None:
    """FR-005: no cascade needed -- deleting a relationship never affects its
    endpoint elements."""
    design = await _get_design_or_404(design_id, store)

    relationship = next((r for r in design.relationships if r.id == relationship_id), None)
    if relationship is None:
        raise HTTPException(
            status_code=404,
            detail=f"Relationship {relationship_id!r} not found in design {design_id!r}",
        )

    design.relationships = [r for r in design.relationships if r.id != relationship_id]

    actor = _get_actor(raw_request)
    _append_audit(
        design, actor, "delete-relationship", relationship_id,
        f"Deleted {relationship.source} -> {relationship.target}",
    )

    await store.save(design, actor=actor)
    logger.info(
        "relationships.delete design=%s relationship=%s actor=%s",
        design_id, relationship_id, actor,
    )
