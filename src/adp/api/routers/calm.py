"""CALM Export and Import HTTP API — ADP-SPEC-021/022.

GET  /api/v1/designs/{design_id}/export/calm  → download CALM JSON (ADP-SPEC-021)
POST /api/v1/knowledge/import/calm            → import CALM pattern (ADP-SPEC-022, added later)
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status

from adp.calm.exporter import map_design_to_calm
from adp.calm.models import CALMImportResult

logger = logging.getLogger(__name__)

router = APIRouter(tags=["calm"])


# ── Shared helpers (reused from recommend router) ─────────────────────────────

def _get_actor(request: Request) -> str:
    """Return actor identity: authenticated user if available, else X-Actor header."""
    from adp.auth.models import UNAUTHENTICATED_USER
    user = getattr(request.state, "user", UNAUTHENTICATED_USER)
    if user is not UNAUTHENTICATED_USER:
        return user.username
    return request.headers.get("X-Actor", "architect")


async def _get_design_store_dep():  # type: ignore[return]
    from adp.api.deps import get_design_store
    return await get_design_store()


# ── ADP-SPEC-021: CALM Export ─────────────────────────────────────────────────

@router.get("/api/v1/designs/{design_id}/export/calm")
async def export_calm(
    design_id: str,
    raw_request: Request,
    store=Depends(_get_design_store_dep),
) -> Response:
    """FR-001: Export design as a CALM-compliant JSON document (ADP-SPEC-021).

    ART-IX: writes a calm-export audit entry.
    ART-XI: CALM document carries source=adp and design-id provenance.
    """
    from adp.audit.writer import next_audit_id as _next_audit_id
    from adp.models import AuditEntry
    from adp.store.store import DesignNotFoundError  # type: ignore[attr-defined]

    try:
        design = await store.get(design_id)
    except DesignNotFoundError:
        raise HTTPException(status_code=404, detail=f"Design {design_id!r} not found")

    # Map to CALM
    calm_doc = map_design_to_calm(design)
    payload = json.dumps(calm_doc.model_dump_calm(), indent=2)

    # ART-IX: audit entry
    actor = _get_actor(raw_request)
    audit_id = _next_audit_id(design)
    entry = AuditEntry(
        id=audit_id,
        actor=actor,
        action="calm-export",
        affected_entity=design_id,
        summary=(
            f"Design exported as CALM JSON "
            f"({len(design.elements)} nodes, {len(design.relationships)} relationships)"
        ),
        timestamp=datetime.now(timezone.utc),
        origin="human",
    )
    design.audit_log.append(entry)
    try:
        await store.save(design)
    except Exception as exc:
        logger.warning("calm-export: audit save failed (non-fatal): %s", exc)

    logger.info(
        "calm.export design=%s nodes=%d relationships=%d actor=%s",
        design_id, len(design.elements), len(design.relationships), actor,
    )

    return Response(
        content=payload,
        media_type="application/json",
        headers={
            "Content-Disposition": f'attachment; filename="{design_id}-calm.json"',
        },
    )


# ── ADP-SPEC-022: CALM Pattern Import ─────────────────────────────────────────

from adp.api.deps import get_kb_session as _get_kb_session  # noqa: E402 (import after functions)


@router.post(
    "/api/v1/knowledge/import/calm",
    response_model=CALMImportResult,
    status_code=status.HTTP_201_CREATED,
)
async def import_calm_pattern(
    request: Request,
    session=Depends(_get_kb_session),
) -> CALMImportResult:
    """FR-007: Import a CALM pattern JSON document into the ADP knowledge base.

    Accepts a raw CALM JSON body. Returns items_created/updated counts.
    ART-VIII: always user-initiated; no auto-import.
    """
    from adp.calm.importer import parse_calm_document
    from adp.knowledge.embedder import EmbeddingProvider
    from adp.knowledge.index import KnowledgeIndex

    # Parse body
    try:
        body_bytes = await request.body()
        data = json.loads(body_bytes)
        if not isinstance(data, dict):
            raise ValueError("CALM document must be a JSON object")
    except (json.JSONDecodeError, ValueError) as exc:
        raise HTTPException(
            status_code=422,
            detail=f"Invalid CALM JSON: {exc}",
        )

    # Parse CALM
    try:
        item, full_text = parse_calm_document(data, source_ref=str(request.url))
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))

    # Generate embedding
    embedding: list[float]
    try:
        embedder = EmbeddingProvider("all-MiniLM-L6-v2")
        embedding = embedder.embed(f"{item.title}\n{full_text}")
    except Exception as exc:
        logger.warning("calm-import: embedding failed, using zero vector: %s", exc)
        embedding = [0.0] * 384

    # Check exists before upsert (created vs updated)
    idx = KnowledgeIndex(session_factory=None)
    existing = await idx.get_item(item.id, None, session)
    await idx.upsert_item(item, embedding, session)
    await session.commit()

    item_dict = {
        "id": item.id,
        "version": item.version,
        "kind": item.kind.value,
        "title": item.title,
        "source_ref": item.source_ref,
        "metadata": item.metadata,
    }

    if existing:
        return CALMImportResult(items_updated=1, items=[item_dict])
    return CALMImportResult(items_created=1, items=[item_dict])
