"""EA pattern registry API (935-pattern-registry, ADP-mmm.2; contracts/rest-api.md).

GET                 /api/v1/patterns                                        — list (filters)
GET                 /api/v1/patterns/relations                              — relation rows
POST                /api/v1/patterns/import                                 — YAML import
POST                /api/v1/patterns/validate                               — dry-run validate
POST                /api/v1/patterns/render                                 — dry-run structure view
GET                 /api/v1/patterns/{key}                                  — family + versions
GET/PUT/DELETE      /api/v1/patterns/{key}/versions/{version}               — detail / draft edit
GET                 /api/v1/patterns/{key}/versions/{version}/yaml          — canonical YAML
GET                 /api/v1/patterns/{key}/versions/{version}/views/{view}  — flowchart view
POST                /api/v1/patterns/{key}/versions/{version}/lifecycle     — governed transition

ART-V: mutations need WRITE_PATTERN via the `/api/v1/patterns/` prefix rule; the lifecycle route
needs GOVERN_PATTERN (explicit rule) and carries an ART-VIII confirmation id. Reads are open.
ART-IX: every mutation emits an actor-attributed structured log line (research.md D5, GT-3).
"""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Callable
from datetime import datetime, timezone
from typing import Annotated, Any, Literal

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response, status
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession

from adp.api.common import session_dependency
from adp.auth.actor import actor_of
from adp.patterns import store as pstore
from adp.patterns.models import PatternKind
from adp.patterns.parse import compute_digest, parse_pattern_yaml
from adp.patterns.projection import build_projection
from adp.patterns.registry_models import (
    MAX_YAML_BYTES,
    ConcurrentPromotionError,
    IllegalTransitionError,
    ImportStatus,
    InvalidPatternUpdateError,
    LifecycleTransitionRequest,
    NotDraftError,
    PatternFamily,
    PatternImportResult,
    PatternLifecycle,
    PatternListResponse,
    PatternNotFoundError,
    PatternRegistryError,
    PatternRelationRow,
    PatternRenderRequest,
    PatternUpdateResult,
    PatternValidateResult,
    PatternVersionDetail,
    PatternVersionNotFoundError,
    PatternViewKind,
    PatternViewResponse,
    PromotionBlockedError,
)
from adp.patterns.render import (
    RenderedView,
    RenderOptions,
    render_catalog,
    render_structure,
    render_traceability,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/patterns", tags=["patterns"])

EmbedFn = Callable[[str, str], list[float]]

_YAML_BODY = {
    "requestBody": {
        "required": True,
        "content": {
            "application/yaml": {"schema": {"type": "string"}},
            "text/plain": {"schema": {"type": "string"}},
        },
    }
}


def _get_actor(request: Request) -> str:
    return actor_of(request)


_get_session = session_dependency("adp.patterns.store")


def _get_embed() -> EmbedFn:
    """The knowledge-projection embedder (overridden in tests; research.md D6)."""
    from adp.knowledge.embedder import embed_or_zero

    return embed_or_zero


async def _read_yaml_body(request: Request) -> bytes:
    body = await request.body()
    if len(body) > MAX_YAML_BYTES:
        raise HTTPException(
            status_code=413,
            detail=f"pattern documents are limited to {MAX_YAML_BYTES} bytes",
        )
    return body


def _not_found(exc: PatternNotFoundError | PatternVersionNotFoundError) -> HTTPException:
    return HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))


Session = Annotated[AsyncSession, Depends(_get_session)]


# ── Collection routes (declared before /{key}) ───────────────────────────────────────────
@router.get("", response_model=PatternListResponse)
async def list_patterns(
    session: Session,
    kind: PatternKind | None = None,
    lifecycle: PatternLifecycle | None = None,
    tag: str | None = None,
    q: str | None = None,
    limit: Annotated[int, Query(ge=1, le=200)] = 100,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> PatternListResponse:
    return await pstore.list_versions(
        session, kind=kind, lifecycle=lifecycle, tag=tag, q=q, limit=limit, offset=offset
    )


@router.get("/relations", response_model=list[PatternRelationRow])
async def list_relations(session: Session, key: str | None = None) -> list[PatternRelationRow]:
    return await pstore.list_relations(session, key)


@router.post(
    "/import",
    response_model=PatternImportResult,
    status_code=status.HTTP_201_CREATED,
    openapi_extra=_YAML_BODY,
    responses={200: {"model": PatternImportResult}, 422: {"model": PatternImportResult}},
)
async def import_pattern(request: Request, session: Session) -> Any:
    body = await _read_yaml_body(request)
    actor = _get_actor(request)
    result = await pstore.import_pattern(body, actor, session)
    if result.status == ImportStatus.CREATED:
        await session.commit()
    v = result.version
    logger.info(
        "patterns.import key=%s version=%s status=%s digest=%s actor=%s",
        v.pattern_key if v else None,
        v.version if v else None,
        result.status.value,
        v.digest if v else None,
        actor,
    )
    if result.status == ImportStatus.CREATED:
        return result
    code = status.HTTP_200_OK if result.status == ImportStatus.UNCHANGED else 422
    return JSONResponse(status_code=code, content=result.model_dump(mode="json"))


# ── Family / version routes ───────────────────────────────────────────────────────────
@router.get("/{key}", response_model=PatternFamily)
async def get_family(key: str, session: Session) -> PatternFamily:
    try:
        return await pstore.get_family(key, session)
    except PatternNotFoundError as exc:
        raise _not_found(exc) from exc


@router.get("/{key}/versions/{version}", response_model=PatternVersionDetail)
async def get_version(key: str, version: str, session: Session) -> PatternVersionDetail:
    try:
        return await pstore.get_version_detail(key, version, session)
    except (PatternNotFoundError, PatternVersionNotFoundError) as exc:
        raise _not_found(exc) from exc


@router.get("/{key}/versions/{version}/yaml", response_class=Response)
async def get_version_yaml(key: str, version: str, session: Session) -> Response:
    try:
        text = await pstore.get_yaml(key, version, session)
    except (PatternNotFoundError, PatternVersionNotFoundError) as exc:
        raise _not_found(exc) from exc
    return Response(
        content=text,
        media_type="application/yaml",
        headers={"Content-Disposition": f'attachment; filename="{key}@{version}.yaml"'},
    )


# ── Lifecycle (US2) ───────────────────────────────────────────────────────────────────
def _registry_http_error(exc: Exception) -> HTTPException:
    """Map a store exception to its HTTP status (data-model.md)."""
    if isinstance(exc, (PatternNotFoundError, PatternVersionNotFoundError)):
        return _not_found(exc)
    if isinstance(exc, (IllegalTransitionError, ConcurrentPromotionError, NotDraftError)):
        return HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc))
    if isinstance(exc, (PromotionBlockedError, InvalidPatternUpdateError)):
        return HTTPException(
            status_code=422,
            detail={
                "message": str(exc),
                "issues": [i.model_dump(mode="json") for i in exc.issues],
            },
        )
    raise exc


@router.post("/{key}/versions/{version}/lifecycle", response_model=PatternVersionDetail)
async def transition_version(
    key: str,
    version: str,
    body: LifecycleTransitionRequest,
    request: Request,
    session: Session,
    embed: Annotated[EmbedFn, Depends(_get_embed)],
) -> PatternVersionDetail:
    actor = _get_actor(request)
    try:
        embedding = None
        if body.to == PatternLifecycle.CURRENT:
            # Compute the knowledge projection's embedding before any write (research.md D6).
            projected = build_projection(await pstore.get_definition(key, version, session))
            embedding = await asyncio.to_thread(embed, projected.title, projected.full_text)
        before = await pstore.get_version_detail(key, version, session)
        detail = await pstore.transition(key, version, body, actor, session, embedding=embedding)
    except PatternRegistryError as exc:
        await session.rollback()
        raise _registry_http_error(exc) from exc
    await session.commit()
    logger.info(
        "patterns.transition key=%s version=%s from=%s to=%s reason=%r confirmation_id=%s actor=%s",
        key,
        version,
        before.lifecycle.value,
        detail.lifecycle.value,
        body.reason,
        body.confirmation_id,
        actor,
    )
    return detail


# ── Views (US4, FR-017–FR-019) ────────────────────────────────────────────────────────
def _view_response(
    view: PatternViewKind, rendered: RenderedView, digest: str
) -> PatternViewResponse:
    return PatternViewResponse(
        view=view,
        flowchart=rendered.text,
        digest=digest,
        generated_at=datetime.now(timezone.utc),
        truncated=rendered.truncated,
    )


@router.get("/{key}/versions/{version}/views/{view}", response_model=PatternViewResponse)
async def get_view(
    key: str,
    version: str,
    view: PatternViewKind,
    session: Session,
    depth: Annotated[int, Query(ge=1, le=3)] = 1,
    direction: Literal["LR", "TB"] = "LR",
    legend: bool = False,
) -> PatternViewResponse:
    opts = RenderOptions(direction=direction, include_legend=legend)
    try:
        if view == PatternViewKind.CATALOG:
            focus, digest, nodes, edges = await pstore.catalog_inputs(key, version, session)
            return _view_response(
                view, render_catalog(focus, digest, nodes, edges, depth, opts), digest
            )
        defn = await pstore.get_definition(key, version, session)
    except PatternRegistryError as exc:
        raise _registry_http_error(exc) from exc
    digest = compute_digest(defn)
    if view == PatternViewKind.STRUCTURE:
        return _view_response(view, render_structure(defn, opts), digest)
    principles, controls, apps = await pstore.traceability_inputs(defn, session)
    rendered = render_traceability(defn, digest, principles, controls, apps, opts)
    return _view_response(view, rendered, digest)


@router.post("/render", response_model=PatternViewResponse)
async def render_draft(body: PatternRenderRequest) -> PatternViewResponse:
    """Dry run: the structure view of unsaved YAML. Nothing is stored (FR-019)."""
    parsed = parse_pattern_yaml(body.yaml)
    if not parsed.ok or parsed.definition is None:
        raise HTTPException(
            status_code=422,
            detail={
                "message": "the YAML is not a valid pattern",
                "issues": [i.model_dump(mode="json") for i in parsed.issues],
            },
        )
    defn = parsed.definition
    return _view_response(PatternViewKind.STRUCTURE, render_structure(defn), compute_digest(defn))


# ── Draft editing (US5) ───────────────────────────────────────────────────────────────
@router.post("/validate", response_model=PatternValidateResult, openapi_extra=_YAML_BODY)
async def validate_draft(request: Request, session: Session) -> PatternValidateResult:
    """Dry run: parse, validate and resolve without storing anything (FR-019)."""
    return await pstore.validate_only(await _read_yaml_body(request), session)


@router.put(
    "/{key}/versions/{version}", response_model=PatternUpdateResult, openapi_extra=_YAML_BODY
)
async def update_draft(
    key: str, version: str, request: Request, session: Session
) -> PatternUpdateResult:
    body = await _read_yaml_body(request)
    actor = _get_actor(request)
    try:
        result, digest_before = await pstore.update_draft(key, version, body, actor, session)
    except PatternRegistryError as exc:
        await session.rollback()
        raise _registry_http_error(exc) from exc
    await session.commit()
    logger.info(
        "patterns.update key=%s version=%s digest_before=%s digest_after=%s actor=%s",
        key,
        version,
        digest_before,
        result.version.digest,
        actor,
    )
    return result


@router.delete("/{key}/versions/{version}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_draft(key: str, version: str, request: Request, session: Session) -> Response:
    actor = _get_actor(request)
    try:
        digest = (await pstore.get_version_detail(key, version, session)).digest
        family_deleted = await pstore.delete_draft(key, version, session)
    except PatternRegistryError as exc:
        await session.rollback()
        raise _registry_http_error(exc) from exc
    await session.commit()
    logger.info(
        "patterns.delete key=%s version=%s digest=%s family_deleted=%s actor=%s",
        key,
        version,
        digest,
        family_deleted,
        actor,
    )
    return Response(status_code=status.HTTP_204_NO_CONTENT)
