"""Adoption, conformance and discovery API (936-pattern-conformance; contracts/rest-api.md).

Mounted under the same ``/api/v1/patterns`` prefix as the registry router but registered BEFORE it,
so the literal ``/adoptions`` and ``/evaluate`` paths are never captured by ``GET /{key}``.

GET/POST            /api/v1/patterns/adoptions                         — list (+status) / create
GET/PATCH/DELETE    /api/v1/patterns/adoptions/{id}                    — one adoption
PUT                 /api/v1/patterns/adoptions/{id}/members|pins       — replace members / pins
GET                 /api/v1/patterns/adoptions/{id}/conformance        — derived report
GET                 /api/v1/patterns/adoptions/{id}/views/{view}       — conformance|transition
GET                 /api/v1/patterns/adoptions/{id}/candidates/{role}  — pin picker
GET                 /api/v1/patterns/{key}/versions/{version}/discover — anti-pattern discovery
POST                /api/v1/patterns/evaluate                          — dry run (WRITE_PATTERN)

Writes need WRITE_PATTERN (the `/api/v1/patterns/` prefix rule; Clarification Q2). Reads are
open, but every report is computed per caller: gated application attributes are present only for
callers holding READ_APPLICATION_RISK / _COST / _GOVERNANCE (FR-006). Nothing is cached or stored.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from adp.auth.deps import get_current_user
from adp.auth.models import AuthenticatedUser
from adp.authz.permissions import is_permitted
from adp.authz.roles import ActionType
from adp.patterns import adoptions as ad
from adp.patterns import store as pstore
from adp.patterns.cel import default_engine
from adp.patterns.conformance_models import (
    Adoption,
    AdoptionCreate,
    AdoptionError,
    AdoptionListResponse,
    AdoptionNotFoundError,
    AdoptionUpdate,
    ConformanceReport,
    DiscoveryReport,
    DraftPinError,
    DuplicateAdoptionError,
    ElementRef,
    EvaluateRequest,
    Finding,
    FindingKind,
    InvalidPinError,
    InvalidScopeError,
    MembersIn,
    NotAntiPatternError,
    PinsIn,
    ScopeTargetNotFoundError,
    ScopeType,
)
from adp.patterns.engine import discover, evaluate_pattern, not_applicable_report
from adp.patterns.models import PatternKind, Severity
from adp.patterns.parse import compute_digest, parse_pattern_yaml
from adp.patterns.registry_models import (
    AdoptionViewKind,
    PatternNotFoundError,
    PatternRegistryError,
    PatternVersionNotFoundError,
    PatternViewResponse,
)
from adp.patterns.render import render_conformance, render_transition
from adp.patterns.snapshot import Scope
from adp.patterns.snapshot_store import SnapshotPermissions, build_snapshot

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/patterns", tags=["patterns"])


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


Session = Annotated[AsyncSession, Depends(_get_session)]
User = Annotated[AuthenticatedUser, Depends(get_current_user)]


def _permissions(user: AuthenticatedUser) -> SnapshotPermissions:
    return SnapshotPermissions(
        risk=is_permitted(user.role, ActionType.READ_APPLICATION_RISK),
        cost=is_permitted(user.role, ActionType.READ_APPLICATION_COST),
        governance=is_permitted(user.role, ActionType.READ_APPLICATION_GOVERNANCE),
    )


def _http(exc: Exception) -> HTTPException:
    if isinstance(
        exc,
        (
            AdoptionNotFoundError,
            ScopeTargetNotFoundError,
            PatternNotFoundError,
            PatternVersionNotFoundError,
        ),
    ):
        return HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    if isinstance(exc, DuplicateAdoptionError):
        return HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc))
    if isinstance(exc, InvalidPinError):
        return HTTPException(status_code=422, detail={"message": str(exc), "reasons": exc.reasons})
    if isinstance(exc, (InvalidScopeError, DraftPinError, NotAntiPatternError)):
        return HTTPException(status_code=422, detail=str(exc))
    raise exc


_NOT_FOUND_OR_INVALID = (AdoptionError, PatternRegistryError)


async def _report(
    adoption: Adoption, session: AsyncSession, user: AuthenticatedUser, snapshot: Any = None
) -> ConformanceReport:
    scope = ad.scope_of(adoption)
    resolved = await ad.resolve_definition(adoption, session)
    if resolved is None:
        return not_applicable_report(
            adoption.pattern_key,
            scope,
            Finding(
                code="B1.no_current_version",
                kind=FindingKind.BINDING,
                severity=Severity.INFO,
                rule="The pattern has no current version and the adoption pins none",
            ),
            adoption_id=adoption.id,
        )
    defn, digest = resolved
    snap = snapshot or await build_snapshot(session, _permissions(user))
    return evaluate_pattern(
        defn, snap, scope, list(adoption.pins), digest=digest, adoption_id=adoption.id
    )


def _log(event: str, adoption: Adoption, actor: str) -> None:
    logger.info(
        "patterns.adoption.%s id=%s pattern=%s scope=%s:%s actor=%s",
        event,
        adoption.id,
        adoption.pattern_key,
        adoption.scope_type.value,
        adoption.scope_ref or "",
        actor,
    )


# ── Adoptions (US2) ─────────────────────────────────────────────────────────────────────
@router.get("/adoptions", response_model=AdoptionListResponse)
async def list_adoptions(
    session: Session,
    user: User,
    pattern_key: str | None = None,
    scope_type: ScopeType | None = None,
    with_status: bool = False,
) -> AdoptionListResponse:
    listing = await ad.list_adoptions(session, pattern_key=pattern_key, scope_type=scope_type)
    if not with_status or not listing.items:
        return listing
    snap = await build_snapshot(session, _permissions(user))
    items = [
        a.model_copy(update={"status": (await _report(a, session, user, snap)).status})
        for a in listing.items
    ]
    return AdoptionListResponse(items=items, total=listing.total)


@router.post("/adoptions", response_model=Adoption, status_code=status.HTTP_201_CREATED)
async def create_adoption(body: AdoptionCreate, request: Request, session: Session) -> Adoption:
    try:
        adoption = await ad.create_adoption(body, _get_actor(request), session)
    except _NOT_FOUND_OR_INVALID as exc:
        await session.rollback()
        raise _http(exc) from exc
    await session.commit()
    _log("create", adoption, _get_actor(request))
    return adoption


@router.get("/adoptions/{adoption_id}", response_model=Adoption)
async def get_adoption(adoption_id: str, session: Session) -> Adoption:
    try:
        return await ad.get_adoption(adoption_id, session)
    except _NOT_FOUND_OR_INVALID as exc:
        raise _http(exc) from exc


@router.patch("/adoptions/{adoption_id}", response_model=Adoption)
async def update_adoption(
    adoption_id: str, body: AdoptionUpdate, request: Request, session: Session
) -> Adoption:
    try:
        adoption = await ad.update_adoption(
            adoption_id, body, set(body.model_fields_set), _get_actor(request), session
        )
    except _NOT_FOUND_OR_INVALID as exc:
        await session.rollback()
        raise _http(exc) from exc
    await session.commit()
    _log("update", adoption, _get_actor(request))
    return adoption


@router.put("/adoptions/{adoption_id}/members", response_model=Adoption)
async def set_members(
    adoption_id: str, body: MembersIn, request: Request, session: Session
) -> Adoption:
    try:
        adoption = await ad.set_members(adoption_id, body.member_ids, _get_actor(request), session)
    except _NOT_FOUND_OR_INVALID as exc:
        await session.rollback()
        raise _http(exc) from exc
    await session.commit()
    _log("members", adoption, _get_actor(request))
    return adoption


@router.put("/adoptions/{adoption_id}/pins", response_model=Adoption)
async def set_pins(adoption_id: str, body: PinsIn, request: Request, session: Session) -> Adoption:
    try:
        adoption = await ad.set_pins(adoption_id, body.pins, _get_actor(request), session)
    except _NOT_FOUND_OR_INVALID as exc:
        await session.rollback()
        raise _http(exc) from exc
    await session.commit()
    _log("pins", adoption, _get_actor(request))
    return adoption


@router.delete("/adoptions/{adoption_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_adoption(adoption_id: str, request: Request, session: Session) -> Response:
    try:
        adoption = await ad.get_adoption(adoption_id, session)
        await ad.delete_adoption(adoption_id, session)
    except _NOT_FOUND_OR_INVALID as exc:
        await session.rollback()
        raise _http(exc) from exc
    await session.commit()
    _log("delete", adoption, _get_actor(request))
    return Response(status_code=status.HTTP_204_NO_CONTENT)


# ── Conformance (US1, US3) ──────────────────────────────────────────────────────────────
@router.get("/adoptions/{adoption_id}/conformance", response_model=ConformanceReport)
async def get_conformance(adoption_id: str, session: Session, user: User) -> ConformanceReport:
    try:
        adoption = await ad.get_adoption(adoption_id, session)
    except _NOT_FOUND_OR_INVALID as exc:
        raise _http(exc) from exc
    return await _report(adoption, session, user)


@router.get("/adoptions/{adoption_id}/candidates/{role_key}", response_model=list[ElementRef])
async def get_candidates(
    adoption_id: str, role_key: str, session: Session, user: User
) -> list[ElementRef]:
    """Pin picker: every element of the role's element type, portfolio-wide, by name."""
    try:
        adoption = await ad.get_adoption(adoption_id, session)
    except _NOT_FOUND_OR_INVALID as exc:
        raise _http(exc) from exc
    resolved = await ad.resolve_definition(adoption, session)
    if resolved is None or role_key not in resolved[0].roles:
        raise HTTPException(status_code=404, detail=f"role '{role_key}' not found")
    etype = resolved[0].roles[role_key].element_type
    snap = await build_snapshot(session, _permissions(user))
    refs = [
        ElementRef(type=etype, id=eid, name=str(el.get("name", eid)))
        for eid, el in snap.of_type(etype).items()
    ]
    return sorted(refs, key=lambda r: (r.name, r.id))


@router.get("/adoptions/{adoption_id}/views/{view}", response_model=PatternViewResponse)
async def get_adoption_view(
    adoption_id: str,
    view: AdoptionViewKind,
    session: Session,
    user: User,
    max_per_role: Annotated[int, Query(ge=2, le=50)] = 8,
) -> PatternViewResponse:
    try:
        adoption = await ad.get_adoption(adoption_id, session)
    except _NOT_FOUND_OR_INVALID as exc:
        raise _http(exc) from exc
    resolved = await ad.resolve_definition(adoption, session)
    if resolved is None:
        raise HTTPException(status_code=422, detail="the adoption has no version to render")
    defn, digest = resolved
    snap = await build_snapshot(session, _permissions(user))
    report = await _report(adoption, session, user, snap)
    if view == AdoptionViewKind.TRANSITION:
        if defn.kind != PatternKind.TRANSITION:
            raise HTTPException(status_code=422, detail="not a transition pattern")
        rendered = render_transition(defn, digest, report.plateau)
    else:
        rendered = render_conformance(defn, digest, report, snap, max_per_role=max_per_role)
    return PatternViewResponse(
        view=view,
        flowchart=rendered.text,
        digest=digest,
        generated_at=datetime.now(timezone.utc),
        truncated=rendered.truncated,
    )


# ── Discovery (US4) and dry run (US6) ──────────────────────────────────────────────────
@router.get("/{key}/versions/{version}/discover", response_model=DiscoveryReport)
async def discover_version(key: str, version: str, session: Session, user: User) -> DiscoveryReport:
    try:
        defn = await pstore.get_definition(key, version, session)
    except _NOT_FOUND_OR_INVALID as exc:
        raise _http(exc) from exc
    if defn.kind != PatternKind.ANTI_PATTERN:
        raise _http(NotAntiPatternError(key))
    snap = await build_snapshot(session, _permissions(user))
    return discover(defn, snap, engine=default_engine(), digest=compute_digest(defn))


@router.post("/evaluate", response_model=ConformanceReport)
async def evaluate(body: EvaluateRequest, session: Session, user: User) -> ConformanceReport:
    """Dry run against a scope: unsaved YAML or a stored version. Nothing is stored."""
    if body.yaml is not None:
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
    else:
        if body.pattern_key is None or body.version is None:  # validator guarantees otherwise
            raise HTTPException(
                status_code=422, detail="give either yaml, or pattern_key and version"
            )
        try:
            defn = await pstore.get_definition(body.pattern_key, body.version, session)
        except _NOT_FOUND_OR_INVALID as exc:
            raise _http(exc) from exc
    scope = Scope(body.scope.scope_type, body.scope.scope_ref, frozenset(body.scope.member_ids))
    snap = await build_snapshot(session, _permissions(user))
    return evaluate_pattern(defn, snap, scope, list(body.pins), digest=compute_digest(defn))
