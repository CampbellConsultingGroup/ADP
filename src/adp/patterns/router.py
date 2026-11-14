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

import logging
from collections.abc import Callable
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response, status
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession

from adp.patterns import store as pstore
from adp.patterns.models import PatternKind
from adp.patterns.registry_models import (
    MAX_YAML_BYTES,
    ImportStatus,
    PatternFamily,
    PatternImportResult,
    PatternLifecycle,
    PatternListResponse,
    PatternNotFoundError,
    PatternRelationRow,
    PatternVersionDetail,
    PatternVersionNotFoundError,
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
    from adp.auth.models import UNAUTHENTICATED_USER

    user = getattr(request.state, "user", UNAUTHENTICATED_USER)
    if user is not UNAUTHENTICATED_USER:
        return str(user.username)
    return request.headers.get("X-Actor", "architect")


async def _get_session():  # type: ignore[no-untyped-def]
    factory = pstore._get_session_factory()
    async with factory() as session:
        yield session


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
