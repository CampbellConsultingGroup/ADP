"""EA pattern registry store -- async SQLAlchemy Core (935-pattern-registry, ADP-mmm.2).

Families (``ea_pattern``) own versions (``ea_pattern_version``); a version's definition is the
canonical JSON from 934 (roles encoded as ordered ``[key, role]`` pairs, because JSONB does not
preserve object key order and role order is semantic). Relation rows are rebuilt from the
definition; lifecycle history rows record every transition with its ART-VIII confirmation id.

Migration 044 owns PK/FK/CHECK constraints; these Table objects are DML-only, except the partial
unique "one current per family" index, which is also declared here (``sqlite_where``) so SQLite
fixtures enforce it exactly like Postgres (research.md D2).

Store functions never commit; the router owns the transaction (adp.agentic precedent).
Cross-domain reads go through narrow mirror tables (applications, controls, knowledge_items) so
this package imports no other domain package (research.md D1).
"""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from typing import Any

import sqlalchemy as sa
from pgvector.sqlalchemy import Vector
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from adp.patterns.cel import CelEngine
from adp.patterns.lifecycle import allowed_transitions_ordered, is_allowed
from adp.patterns.models import PatternDefinition, PatternIssue, PatternKind, Severity
from adp.patterns.parse import (
    compute_digest,
    parse_pattern_yaml,
    to_canonical_json,
    to_canonical_yaml,
)
from adp.patterns.projection import build_projection, projection_id
from adp.patterns.registry_models import (
    ConcurrentPromotionError,
    IllegalTransitionError,
    ImportStatus,
    InvalidPatternUpdateError,
    LifecycleEvent,
    LifecycleTransitionRequest,
    NotDraftError,
    PatternFamily,
    PatternImportResult,
    PatternLifecycle,
    PatternListResponse,
    PatternNotFoundError,
    PatternRelationRow,
    PatternUpdateResult,
    PatternValidateResult,
    PatternVersionDetail,
    PatternVersionNotFoundError,
    PatternVersionSummary,
    PromotionBlockedError,
)
from adp.patterns.render import CatalogEdge, CatalogNode, TraceRef
from adp.patterns.resolve import ReferenceLookups, referenced_ids, resolve_references

EMBEDDING_DIM = 384

_metadata = sa.MetaData()
_JSON = sa.JSON().with_variant(JSONB(), "postgresql")

_patterns = sa.Table(
    "ea_pattern",
    _metadata,
    sa.Column("pattern_key", sa.Text(), primary_key=True),
    sa.Column("kind", sa.Text(), nullable=False),
    sa.Column("owner_role", sa.Text(), nullable=False),
    sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    sa.Column("created_by", sa.Text(), nullable=False),
)

_versions = sa.Table(
    "ea_pattern_version",
    _metadata,
    sa.Column("id", sa.String(36), primary_key=True),
    sa.Column("pattern_key", sa.Text(), nullable=False),
    sa.Column("version", sa.Text(), nullable=False),
    sa.Column("lifecycle", sa.Text(), nullable=False, default="draft"),
    sa.Column("name", sa.Text(), nullable=False),
    sa.Column("summary", sa.Text(), nullable=False),
    sa.Column("definition", _JSON, nullable=False),
    sa.Column("digest", sa.String(64), nullable=False),
    sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    sa.Column("created_by", sa.Text(), nullable=False),
    sa.Column("lifecycle_changed_at", sa.DateTime(timezone=True), nullable=False),
    sa.Column("lifecycle_changed_by", sa.Text(), nullable=False),
    sa.UniqueConstraint("pattern_key", "version", name="uq_ea_pattern_version_key_version"),
)
sa.Index(
    "uq_ea_pattern_version_current",
    _versions.c.pattern_key,
    unique=True,
    postgresql_where=_versions.c.lifecycle == "current",
    sqlite_where=_versions.c.lifecycle == "current",
)

_relations = sa.Table(
    "ea_pattern_relation",
    _metadata,
    sa.Column("source_version_id", sa.String(36), primary_key=True),
    sa.Column("target_pattern_key", sa.Text(), primary_key=True),
    sa.Column("relation_type", sa.Text(), primary_key=True),
    sa.Column("note", sa.Text()),
)

_events = sa.Table(
    "ea_pattern_lifecycle_event",
    _metadata,
    sa.Column("id", sa.String(36), primary_key=True),
    sa.Column("version_id", sa.String(36), nullable=False),
    sa.Column("from_state", sa.Text(), nullable=False),
    sa.Column("to_state", sa.Text(), nullable=False),
    sa.Column("reason", sa.Text(), nullable=False),
    sa.Column("confirmation_id", sa.Text(), nullable=False),
    sa.Column("actor", sa.Text(), nullable=False),
    sa.Column("at", sa.DateTime(timezone=True), nullable=False),
    sa.Column("caused_by_event_id", sa.String(36)),
)

# ── Narrow read-only mirrors (research.md D1) ──────────────────────────────────────────
# Also read by adp.patterns.snapshot_store (936): every column the portfolio snapshot exposes.
_applications_mirror = sa.Table(
    "applications",
    _metadata,
    sa.Column("id", sa.String(36), primary_key=True),
    sa.Column("name", sa.String(255)),
    sa.Column("lifecycle_status", sa.Text()),
    sa.Column("application_type", sa.Text()),
    sa.Column("time_classification", sa.Text()),
    sa.Column("r_strategy", sa.Text()),
    sa.Column("pace_layer", sa.Text()),
    sa.Column("hosting_model", sa.Text()),
    sa.Column("architecture_pattern", sa.Text()),
    sa.Column("business_criticality", sa.SmallInteger()),
    sa.Column("health_score", sa.Integer()),
    sa.Column("tech_debt_flags", _JSON),
)
_controls_mirror = sa.Table(
    "controls",
    _metadata,
    sa.Column("id", sa.String(36), primary_key=True),
    sa.Column("code", sa.String(100)),
    sa.Column("title", sa.String(255)),
)
# Full-column mirror: the registry writes its knowledge projection rows (research.md D6).
_knowledge_items = sa.Table(
    "knowledge_items",
    _metadata,
    sa.Column("id", sa.String, primary_key=True),
    sa.Column("version", sa.Text(), nullable=False),
    sa.Column("kind", sa.Text(), nullable=False),
    sa.Column("title", sa.Text(), nullable=False),
    sa.Column("full_text", sa.Text(), nullable=False),
    sa.Column("metadata", _JSON, nullable=False),
    sa.Column("source_ref", sa.Text(), nullable=False),
    sa.Column("schema_version", sa.Text(), nullable=False),
    sa.Column("active", sa.Boolean(), nullable=False),
    sa.Column("embedding", Vector(384).with_variant(sa.JSON(), "sqlite"), nullable=False),
    sa.Column("indexed_at", sa.DateTime(timezone=True), nullable=False),
)

_engine: Any = None
_session_factory: async_sessionmaker | None = None


def _get_session_factory() -> async_sessionmaker:
    global _engine, _session_factory
    if _session_factory is None:
        import os

        db_url = os.environ.get(
            "ADP_DATABASE_URL", "postgresql+asyncpg://adp_user:adp_pass@127.0.0.1:5432/adp"
        )
        _engine = create_async_engine(db_url, echo=False)
        _session_factory = async_sessionmaker(_engine, expire_on_commit=False)
    return _session_factory


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _semver_desc(version: str) -> tuple[int, ...]:
    return tuple(-p for p in semver_key(version))


def semver_key(version: str) -> tuple[int, ...]:
    """Numeric semver ordering (``1.10.0`` sorts after ``1.9.0``)."""
    return tuple(int(part) for part in version.split("."))


# ── Definition (de)serialisation ───────────────────────────────────────────────────────
def definition_to_db(defn: PatternDefinition) -> dict[str, Any]:
    data: dict[str, Any] = json.loads(to_canonical_json(defn))
    return data


def definition_from_db(data: dict[str, Any]) -> PatternDefinition:
    copy = dict(data)
    copy["roles"] = {key: role for key, role in data["roles"]}
    return PatternDefinition.model_validate(copy)


def _issue(code: str, message: str) -> PatternIssue:
    return PatternIssue(path="", code=code, message=message, severity=Severity.ERROR)


# ── Row mapping ────────────────────────────────────────────────────────────────────────
def _summary(row: Any) -> PatternVersionSummary:
    return PatternVersionSummary(
        id=row.id,
        pattern_key=row.pattern_key,
        version=row.version,
        kind=PatternKind(row.kind),
        lifecycle=PatternLifecycle(row.lifecycle),
        name=row.name,
        summary=row.summary,
        tags=list((row.definition or {}).get("tags", [])),
        digest=row.digest,
        created_at=row.created_at,
        created_by=row.created_by,
        lifecycle_changed_at=row.lifecycle_changed_at,
    )


def _version_select() -> sa.Select[Any]:
    return sa.select(_versions, _patterns.c.kind).join(
        _patterns, _patterns.c.pattern_key == _versions.c.pattern_key
    )


def _sort_versions(rows: list[Any]) -> list[Any]:
    """Current first, then semver descending."""
    return sorted(
        rows,
        key=lambda r: (
            r.lifecycle != PatternLifecycle.CURRENT.value,
            tuple(-p for p in semver_key(r.version)),
        ),
    )


async def _version_row(key: str, version: str, session: AsyncSession) -> Any:
    row = (
        await session.execute(
            _version_select().where(_versions.c.pattern_key == key, _versions.c.version == version)
        )
    ).first()
    if row is None:
        if not await _family_exists(key, session):
            raise PatternNotFoundError(key)
        raise PatternVersionNotFoundError(key, version)
    return row


async def _family_exists(key: str, session: AsyncSession) -> bool:
    found = await session.execute(
        sa.select(_patterns.c.pattern_key).where(_patterns.c.pattern_key == key)
    )
    return found.first() is not None


# ── Reference lookups (research.md D3) ─────────────────────────────────────────────────
async def _existing(
    session: AsyncSession, column: Any, ids: list[str], *where: Any
) -> frozenset[str]:
    if not ids:
        return frozenset()
    rows = await session.execute(sa.select(column).where(column.in_(set(ids)), *where))
    return frozenset(r[0] for r in rows)


async def load_lookups(defn: PatternDefinition, session: AsyncSession) -> ReferenceLookups:
    refs = referenced_ids(defn)
    return ReferenceLookups(
        principles=await _existing(
            session,
            _knowledge_items.c.id,
            refs.principles,
            _knowledge_items.c.kind == "principle",
            _knowledge_items.c.active.is_(True),
        ),
        controls=await _existing(session, _controls_mirror.c.id, refs.controls),
        patterns=await _existing(session, _patterns.c.pattern_key, refs.patterns),
        applications=await _existing(session, _applications_mirror.c.id, refs.applications),
    )


async def _replace_relations(
    version_id: str, defn: PatternDefinition, session: AsyncSession
) -> None:
    await session.execute(_relations.delete().where(_relations.c.source_version_id == version_id))
    for rel in defn.relations:
        await session.execute(
            _relations.insert().values(
                source_version_id=version_id,
                target_pattern_key=rel.target,
                relation_type=rel.type.value,
                note=rel.note,
            )
        )


# ── Import (FR-002) ────────────────────────────────────────────────────────────────────
async def import_pattern(
    text: str | bytes, actor: str, session: AsyncSession, *, engine: CelEngine | None = None
) -> PatternImportResult:
    """Parse, validate, resolve and store one pattern version as ``draft``.

    Every rejection happens before any write, so a rejected import leaves no rows behind.
    """
    parsed = parse_pattern_yaml(text, engine)
    if not parsed.ok or parsed.definition is None:
        return PatternImportResult(status=ImportStatus.REJECTED, issues=list(parsed.issues))
    defn = parsed.definition
    digest = compute_digest(defn)
    warnings = resolve_references(defn, await load_lookups(defn, session), blocking=False)

    existing = (
        await session.execute(
            _version_select().where(
                _versions.c.pattern_key == defn.pattern, _versions.c.version == defn.version
            )
        )
    ).first()
    if existing is not None:
        if existing.digest == digest:
            return PatternImportResult(
                status=ImportStatus.UNCHANGED, version=_summary(existing), issues=warnings
            )
        if existing.lifecycle == PatternLifecycle.DRAFT.value:
            issue = _issue(
                "I1.version_exists_use_update",
                f"{defn.pattern}@{defn.version} already exists as a draft with different "
                "content; update the draft instead",
            )
        else:
            issue = _issue(
                "I2.version_immutable",
                f"{defn.pattern}@{defn.version} is {existing.lifecycle} and immutable; "
                "import a new version number",
            )
        return PatternImportResult(status=ImportStatus.REJECTED, issues=[issue])

    family = (
        await session.execute(sa.select(_patterns).where(_patterns.c.pattern_key == defn.pattern))
    ).first()
    if family is not None and family.kind != defn.kind.value:
        issue = _issue(
            "I3.kind_mismatch",
            f"family '{defn.pattern}' is {family.kind}; a different kind needs a new key",
        )
        return PatternImportResult(status=ImportStatus.REJECTED, issues=[issue])

    now = _now()
    if family is None:
        await session.execute(
            _patterns.insert().values(
                pattern_key=defn.pattern,
                kind=defn.kind.value,
                owner_role=defn.owner_role.value,
                created_at=now,
                created_by=actor,
            )
        )
    version_id = str(uuid.uuid4())
    await session.execute(
        _versions.insert().values(
            id=version_id,
            pattern_key=defn.pattern,
            version=defn.version,
            lifecycle=PatternLifecycle.DRAFT.value,
            name=defn.name,
            summary=defn.summary,
            definition=definition_to_db(defn),
            digest=digest,
            created_at=now,
            created_by=actor,
            lifecycle_changed_at=now,
            lifecycle_changed_by=actor,
        )
    )
    await _replace_relations(version_id, defn, session)
    row = await _version_row(defn.pattern, defn.version, session)
    return PatternImportResult(status=ImportStatus.CREATED, version=_summary(row), issues=warnings)


# ── Reads (FR-005, FR-006) ─────────────────────────────────────────────────────────────
async def list_versions(
    session: AsyncSession,
    *,
    kind: PatternKind | None = None,
    lifecycle: PatternLifecycle | None = None,
    tag: str | None = None,
    q: str | None = None,
    limit: int = 100,
    offset: int = 0,
) -> PatternListResponse:
    stmt = _version_select()
    if kind is not None:
        stmt = stmt.where(_patterns.c.kind == kind.value)
    if lifecycle is not None:
        stmt = stmt.where(_versions.c.lifecycle == lifecycle.value)
    if q:
        like = f"%{q.lower()}%"
        stmt = stmt.where(
            sa.or_(
                sa.func.lower(_versions.c.name).like(like),
                sa.func.lower(_versions.c.summary).like(like),
            )
        )
    rows = list((await session.execute(stmt)).all())
    if tag:
        # Tags live inside the JSON definition; filtered in Python for dialect portability
        # (demo-scale catalogs: tens of patterns).
        rows = [r for r in rows if tag in (r.definition or {}).get("tags", [])]
    rows.sort(key=lambda r: (r.pattern_key, tuple(-p for p in semver_key(r.version))))
    page = rows[offset : offset + limit]
    return PatternListResponse(items=[_summary(r) for r in page], total=len(rows))


async def get_family(key: str, session: AsyncSession) -> PatternFamily:
    family = (
        await session.execute(sa.select(_patterns).where(_patterns.c.pattern_key == key))
    ).first()
    if family is None:
        raise PatternNotFoundError(key)
    rows = _sort_versions(
        list((await session.execute(_version_select().where(_versions.c.pattern_key == key))).all())
    )
    current = next((r.version for r in rows if r.lifecycle == PatternLifecycle.CURRENT.value), None)
    return PatternFamily(
        pattern_key=family.pattern_key,
        kind=PatternKind(family.kind),
        owner_role=family.owner_role,
        created_at=family.created_at,
        created_by=family.created_by,
        current_version=current,
        versions=[_summary(r) for r in rows],
    )


async def list_relations(session: AsyncSession, key: str | None = None) -> list[PatternRelationRow]:
    target = _patterns.alias("target")
    stmt = (
        sa.select(
            _relations,
            _versions.c.pattern_key.label("source_pattern_key"),
            target.c.pattern_key.label("resolved_key"),
        )
        .join(_versions, _versions.c.id == _relations.c.source_version_id)
        .outerjoin(target, target.c.pattern_key == _relations.c.target_pattern_key)
    )
    if key is not None:
        stmt = stmt.where(
            sa.or_(_versions.c.pattern_key == key, _relations.c.target_pattern_key == key)
        )
    rows = (await session.execute(stmt)).all()
    out = [
        PatternRelationRow(
            source_version_id=r.source_version_id,
            source_pattern_key=r.source_pattern_key,
            target_pattern_key=r.target_pattern_key,
            relation_type=r.relation_type,
            note=r.note,
            target_resolved=r.resolved_key is not None,
        )
        for r in rows
    ]
    return sorted(out, key=lambda r: (r.source_pattern_key, r.relation_type, r.target_pattern_key))


async def get_history(version_id: str, session: AsyncSession) -> list[LifecycleEvent]:
    rows = (
        await session.execute(
            sa.select(_events)
            .where(_events.c.version_id == version_id)
            .order_by(_events.c.at, _events.c.id)
        )
    ).all()
    return [
        LifecycleEvent(
            id=r.id,
            from_state=PatternLifecycle(r.from_state),
            to_state=PatternLifecycle(r.to_state),
            reason=r.reason,
            confirmation_id=r.confirmation_id,
            actor=r.actor,
            at=r.at,
            caused_by_event_id=r.caused_by_event_id,
        )
        for r in rows
    ]


async def get_version_detail(key: str, version: str, session: AsyncSession) -> PatternVersionDetail:
    row = await _version_row(key, version, session)
    defn = definition_from_db(row.definition)
    relations = [r for r in await list_relations(session, key) if r.source_version_id == row.id]
    issues = resolve_references(defn, await load_lookups(defn, session), blocking=False)
    knowledge = (
        await session.execute(
            sa.select(_knowledge_items.c.id).where(_knowledge_items.c.id == projection_id(key))
        )
    ).first()
    return PatternVersionDetail(
        **_summary(row).model_dump(),
        definition=defn,
        relations=relations,
        issues=issues,
        allowed_transitions=allowed_transitions_ordered(PatternLifecycle(row.lifecycle)),
        history=await get_history(row.id, session),
        knowledge_item_id=knowledge.id if knowledge is not None else None,
    )


async def get_definition(key: str, version: str, session: AsyncSession) -> PatternDefinition:
    return definition_from_db((await _version_row(key, version, session)).definition)


async def get_yaml(key: str, version: str, session: AsyncSession) -> str:
    """Canonical YAML; byte-identical to the export file (FR-006, FR-020)."""
    return to_canonical_yaml(await get_definition(key, version, session))


# ── Lifecycle (FR-007–FR-011, research.md D4) ──────────────────────────────────────────
async def _insert_event(
    version_id: str,
    src: PatternLifecycle,
    dst: PatternLifecycle,
    reason: str,
    confirmation_id: str,
    actor: str,
    at: datetime,
    session: AsyncSession,
    caused_by: str | None = None,
) -> str:
    event_id = str(uuid.uuid4())
    await session.execute(
        _events.insert().values(
            id=event_id,
            version_id=version_id,
            from_state=src.value,
            to_state=dst.value,
            reason=reason,
            confirmation_id=confirmation_id,
            actor=actor,
            at=at,
            caused_by_event_id=caused_by,
        )
    )
    return event_id


async def _demote_current(
    key: str,
    keep_id: str,
    promoted_version: str,
    req: LifecycleTransitionRequest,
    promotion_event_id: str,
    actor: str,
    at: datetime,
    session: AsyncSession,
) -> str | None:
    """Deprecate the family's other current version, if any; returns its version string."""
    other = (
        await session.execute(
            sa.select(_versions.c.id, _versions.c.version).where(
                _versions.c.pattern_key == key,
                _versions.c.lifecycle == PatternLifecycle.CURRENT.value,
                _versions.c.id != keep_id,
            )
        )
    ).first()
    if other is None:
        return None
    await session.execute(
        _versions.update()
        .where(_versions.c.id == other.id)
        .values(
            lifecycle=PatternLifecycle.DEPRECATED.value,
            lifecycle_changed_at=at,
            lifecycle_changed_by=actor,
        )
    )
    await _insert_event(
        other.id,
        PatternLifecycle.CURRENT,
        PatternLifecycle.DEPRECATED,
        f"Superseded by {promoted_version}: {req.reason}"[:500],
        req.confirmation_id,
        actor,
        at,
        session,
        caused_by=promotion_event_id,
    )
    return str(other.version)


async def _promotion_issues(defn: PatternDefinition, session: AsyncSession) -> list[PatternIssue]:
    """Full re-validation plus blocking reference resolution (FR-009)."""
    from adp.patterns.cel import default_engine
    from adp.patterns.parse import validate_pattern

    issues = [i for i in validate_pattern(defn, default_engine()) if i.severity == Severity.ERROR]
    issues += resolve_references(defn, await load_lookups(defn, session), blocking=True)
    return issues


async def _sync_projection(key: str, session: AsyncSession, embedding: list[float] | None) -> None:
    """Keep the family's single knowledge item in step with its current version (FR-013).

    A current version -> upsert (select-then-update/insert, dialect-portable; research.md D6).
    No current version -> deactivate, never delete, so control_pattern_mapping rows survive.
    """
    k = _knowledge_items
    pid = projection_id(key)
    current = (
        await session.execute(
            sa.select(_versions.c.definition).where(
                _versions.c.pattern_key == key,
                _versions.c.lifecycle == PatternLifecycle.CURRENT.value,
            )
        )
    ).first()
    exists = (await session.execute(sa.select(k.c.id).where(k.c.id == pid))).first() is not None
    if current is None:
        if exists:
            await session.execute(k.update().where(k.c.id == pid).values(active=False))
        return
    item = build_projection(definition_from_db(current.definition))
    values: dict[str, Any] = {
        "version": item.version,
        "kind": item.kind,
        "title": item.title,
        "full_text": item.full_text,
        "metadata": item.metadata,
        "source_ref": item.source_ref,
        "schema_version": "1.0.0",
        "active": True,
        "indexed_at": _now(),
    }
    if embedding is not None or not exists:
        values["embedding"] = embedding if embedding is not None else [0.0] * EMBEDDING_DIM
    if exists:
        await session.execute(k.update().where(k.c.id == pid).values(**values))
    else:
        await session.execute(k.insert().values(id=pid, **values))


async def transition(
    key: str,
    version: str,
    req: LifecycleTransitionRequest,
    actor: str,
    session: AsyncSession,
    *,
    embedding: list[float] | None = None,
) -> PatternVersionDetail:
    """Apply one governed lifecycle transition.

    On ``-> current`` this re-validates, requires every reference to resolve, deprecates the
    family's other current version (with its own history event pointing at the promotion) and
    refreshes the knowledge projection. ``embedding`` is the projection's embedding, computed by
    the caller *before* this call so no model work happens inside the transaction.
    """
    row = await _version_row(key, version, session)
    src = PatternLifecycle(row.lifecycle)
    dst = req.to
    if not is_allowed(src, dst):
        raise IllegalTransitionError(src.value, dst.value)
    if dst == PatternLifecycle.CURRENT:
        issues = await _promotion_issues(definition_from_db(row.definition), session)
        if issues:
            raise PromotionBlockedError(issues)

    now = _now()
    try:
        event_id = await _insert_event(
            row.id, src, dst, req.reason, req.confirmation_id, actor, now, session
        )
        if dst == PatternLifecycle.CURRENT:
            await _demote_current(key, row.id, version, req, event_id, actor, now, session)
        await session.execute(
            _versions.update()
            .where(_versions.c.id == row.id)
            .values(lifecycle=dst.value, lifecycle_changed_at=now, lifecycle_changed_by=actor)
        )
        await session.flush()
    except IntegrityError as exc:
        await session.rollback()
        raise ConcurrentPromotionError(key) from exc
    await _sync_projection(key, session, embedding)
    return await get_version_detail(key, version, session)


# ── View inputs (US4, research.md D10) ───────────────────────────────────────────────────
_REPRESENTATIVE_ORDER = {
    PatternLifecycle.CURRENT.value: 0,
    PatternLifecycle.PROPOSED.value: 1,
    PatternLifecycle.DRAFT.value: 2,
    PatternLifecycle.DEPRECATED.value: 3,
    PatternLifecycle.DECOMMISSIONED.value: 4,
}


def _representative(rows: list[Any]) -> Any:
    """Current, else the latest proposed, else the latest draft (else the latest of any state)."""
    return sorted(
        rows,
        key=lambda r: (
            _REPRESENTATIVE_ORDER[r.lifecycle],
            tuple(-p for p in semver_key(r.version)),
        ),
    )[0]


async def catalog_inputs(
    key: str, version: str, session: AsyncSession
) -> tuple[CatalogNode, str, list[CatalogNode], list[CatalogEdge]]:
    """The focus version plus one representative version per family and their relations.

    The focus family contributes the *requested* version's relations; every other family
    contributes its representative version's relations.
    """
    focus_row = await _version_row(key, version, session)
    rows = list((await session.execute(_version_select())).all())
    by_family: dict[str, list[Any]] = {}
    for r in rows:
        by_family.setdefault(r.pattern_key, []).append(r)
    chosen = {k: _representative(v) for k, v in by_family.items()}
    chosen[key] = focus_row

    def node(r: Any) -> CatalogNode:
        return CatalogNode(r.pattern_key, r.name, r.version, r.lifecycle, r.kind)

    source_ids = {r.id: k for k, r in chosen.items()}
    rel_rows = (
        await session.execute(
            sa.select(_relations).where(_relations.c.source_version_id.in_(list(source_ids)))
        )
    ).all()
    edges = [
        CatalogEdge(source_ids[r.source_version_id], r.target_pattern_key, r.relation_type)
        for r in rel_rows
    ]
    return node(focus_row), focus_row.digest, [node(r) for r in chosen.values()], edges


async def traceability_inputs(
    defn: PatternDefinition, session: AsyncSession
) -> tuple[list[TraceRef], list[TraceRef], list[TraceRef]]:
    """Labels for the definition's principles, controls and known implementations; unresolved
    ones are returned with ``resolved=False`` (shown, never dropped)."""
    refs = referenced_ids(defn)

    async def labels(
        table_col: Any, label_expr: Any, ids: list[str], *where: Any
    ) -> dict[str, str]:
        if not ids:
            return {}
        result = await session.execute(
            sa.select(table_col, label_expr).where(table_col.in_(set(ids)), *where)
        )
        return {row[0]: str(row[1] or row[0]) for row in result}

    k = _knowledge_items
    principles = await labels(
        k.c.id, k.c.title, refs.principles, k.c.kind == "principle", k.c.active.is_(True)
    )
    c = _controls_mirror
    control_label = sa.func.coalesce(c.c.code, "") + " " + sa.func.coalesce(c.c.title, "")
    controls = await labels(c.c.id, control_label, refs.controls)
    a = _applications_mirror
    apps = await labels(a.c.id, a.c.name, refs.applications)

    def trace(ids: list[str], found: dict[str, str]) -> list[TraceRef]:
        return [TraceRef(i, found.get(i, i).strip() or i, i in found) for i in ids]

    return (
        trace(refs.principles, principles),
        trace(refs.controls, controls),
        trace(refs.applications, apps),
    )


# ── Draft editing (US5, FR-008) ──────────────────────────────────────────────────────────
async def update_draft(
    key: str,
    version: str,
    text: str | bytes,
    actor: str,
    session: AsyncSession,
    *,
    engine: CelEngine | None = None,
) -> tuple[PatternUpdateResult, str]:
    """Replace a draft's definition (same key, version and kind). Returns the result and the
    digest before the change (for the audit log line)."""
    row = await _version_row(key, version, session)
    if row.lifecycle != PatternLifecycle.DRAFT.value:
        raise NotDraftError(key, version, row.lifecycle)
    parsed = parse_pattern_yaml(text, engine)
    if not parsed.ok or parsed.definition is None:
        raise InvalidPatternUpdateError(list(parsed.issues))
    defn = parsed.definition
    if defn.pattern != key or defn.version != version:
        raise InvalidPatternUpdateError(
            [
                _issue(
                    "U1.identity_changed",
                    f"a draft is edited in place: the document must stay {key}@{version} "
                    f"(got {defn.pattern}@{defn.version}); import a new version instead",
                )
            ]
        )
    if defn.kind.value != row.kind:
        raise InvalidPatternUpdateError(
            [_issue("I3.kind_mismatch", f"family '{key}' is {row.kind}; kind cannot change")]
        )
    await session.execute(
        _versions.update()
        .where(_versions.c.id == row.id)
        .values(
            name=defn.name,
            summary=defn.summary,
            definition=definition_to_db(defn),
            digest=compute_digest(defn),
        )
    )
    await _replace_relations(row.id, defn, session)
    warnings = resolve_references(defn, await load_lookups(defn, session), blocking=False)
    updated = await _version_row(key, version, session)
    return PatternUpdateResult(version=_summary(updated), issues=warnings), str(row.digest)


async def delete_draft(key: str, version: str, session: AsyncSession) -> bool:
    """Delete a draft version; returns True when that was the family's last version (the family
    is deleted too). Child rows are removed explicitly so SQLite behaves like Postgres."""
    row = await _version_row(key, version, session)
    if row.lifecycle != PatternLifecycle.DRAFT.value:
        raise NotDraftError(key, version, row.lifecycle)
    await session.execute(_relations.delete().where(_relations.c.source_version_id == row.id))
    await session.execute(_events.delete().where(_events.c.version_id == row.id))
    await session.execute(_versions.delete().where(_versions.c.id == row.id))
    remaining = (
        await session.execute(
            sa.select(sa.func.count()).select_from(_versions).where(_versions.c.pattern_key == key)
        )
    ).scalar_one()
    if remaining == 0:
        await session.execute(_patterns.delete().where(_patterns.c.pattern_key == key))
        return True
    return False


async def validate_only(
    text: str | bytes, session: AsyncSession, *, engine: CelEngine | None = None
) -> PatternValidateResult:
    """Dry run (FR-019): parse, validate and resolve without storing anything."""
    parsed = parse_pattern_yaml(text, engine)
    issues = list(parsed.issues)
    digest = None
    if parsed.definition is not None:
        digest = compute_digest(parsed.definition)
        issues += resolve_references(
            parsed.definition, await load_lookups(parsed.definition, session), blocking=False
        )
    return PatternValidateResult(ok=parsed.ok, digest=digest, issues=issues)
