"""Pattern registry store against SQLite (935 US1–US3, US5; research D2–D6).

The store's Core tables include the partial unique index with ``sqlite_where``, so "at most one
current version per family" is enforced here exactly as on Postgres.
"""

from __future__ import annotations

import re

import pytest
import sqlalchemy as sa
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from adp.patterns import parse_pattern_yaml, to_canonical_yaml
from adp.patterns import store as pstore
from adp.patterns.models import PatternKind
from adp.patterns.registry_models import ImportStatus
from adp.patterns.registry_models import PatternLifecycle as L

from .conftest import load_fixture

BACKBONE = load_fixture("ea.integration.domain-event-backbone@1.0.0.yaml")
MESH = load_fixture("ea.integration.point-to-point-mesh@1.0.0.yaml")
ONE_SOR = load_fixture("ea.data.one-sor-per-capability@1.0.0.yaml")
TRANSITION = load_fixture("ea.integration.mesh-to-backbone@1.0.0.yaml")
KEY = "ea.integration.domain-event-backbone"
ACTOR = "test-architect"


def with_version(text: str, version: str) -> str:
    return re.sub(r"^version: .*$", f"version: {version}", text, count=1, flags=re.M)


def with_summary(text: str, summary: str) -> str:
    return re.sub(r"^summary: .*$", f"summary: {summary}", text, count=1, flags=re.M)


@pytest.fixture()
async def session(tmp_path):
    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path}/patterns.db")
    async with engine.begin() as conn:
        await conn.run_sync(pstore._metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as s:
        yield s
    await engine.dispose()


async def _principle(session, pid: str, *, active: bool = True, kind: str = "principle") -> None:
    await session.execute(
        pstore._knowledge_items.insert().values(
            id=pid,
            version="1.0.0",
            kind=kind,
            title=pid,
            full_text=pid,
            metadata={},
            source_ref="seed",
            schema_version="1.0.0",
            active=active,
            embedding=[0.0] * 384,
            indexed_at=pstore._now(),
        )
    )


async def _count(session, table: sa.Table) -> int:
    return (await session.execute(sa.select(sa.func.count()).select_from(table))).scalar_one()


async def _import(session, text: str = BACKBONE):  # type: ignore[no-untyped-def]
    result = await pstore.import_pattern(text, ACTOR, session)
    await session.commit()
    return result


async def _set_lifecycle(session, key: str, version: str, lc: L) -> None:
    v = pstore._versions
    await session.execute(
        v.update().where(v.c.pattern_key == key, v.c.version == version).values(lifecycle=lc.value)
    )
    await session.commit()


# ── US1: import outcomes (FR-002) ─────────────────────────────────────────────────
async def test_import_created_as_draft_with_resolution_warnings(session) -> None:
    result = await _import(session)
    assert result.status == ImportStatus.CREATED
    assert result.version is not None
    assert result.version.lifecycle == L.DRAFT
    assert result.version.kind == PatternKind.REFERENCE_ARCHITECTURE
    assert result.version.name == "Domain Event Backbone"
    codes = {i.code for i in result.issues}
    assert codes == {"R1.unresolved_principle", "R3.unresolved_relation"}
    assert await _count(session, pstore._patterns) == 1
    assert await _count(session, pstore._relations) == 2


async def test_reimport_same_digest_is_unchanged(session) -> None:
    first = await _import(session)
    again = await _import(session)
    assert again.status == ImportStatus.UNCHANGED
    assert again.version is not None and first.version is not None
    assert again.version.id == first.version.id
    assert await _count(session, pstore._versions) == 1


async def test_same_version_different_content_on_draft_says_use_update(session) -> None:
    await _import(session)
    result = await _import(session, with_summary(BACKBONE, "Changed."))
    assert result.status == ImportStatus.REJECTED
    assert [i.code for i in result.issues] == ["I1.version_exists_use_update"]


async def test_same_version_different_content_after_proposal_is_immutable(session) -> None:
    await _import(session)
    await _set_lifecycle(session, KEY, "1.0.0", L.PROPOSED)
    result = await _import(session, with_summary(BACKBONE, "Changed."))
    assert result.status == ImportStatus.REJECTED
    assert [i.code for i in result.issues] == ["I2.version_immutable"]


async def test_kind_mismatch_with_family_is_rejected(session) -> None:
    await _import(session)
    other = with_version(BACKBONE, "2.0.0").replace(
        "kind: reference-architecture", "kind: portfolio-rule"
    )
    result = await _import(session, other)
    assert result.status == ImportStatus.REJECTED
    assert [i.code for i in result.issues] == ["I3.kind_mismatch"]
    assert await _count(session, pstore._versions) == 1


async def test_invalid_yaml_is_rejected_and_stores_nothing(session) -> None:
    result = await _import(session, load_fixture("V2.unknown_role-relationship.yaml"))
    assert result.status == ImportStatus.REJECTED
    assert result.issues
    for table in (pstore._patterns, pstore._versions, pstore._relations):
        assert await _count(session, table) == 0


async def test_principles_resolve_only_when_active_and_of_kind_principle(session) -> None:
    await _principle(session, "P-API-FIRST")
    await _principle(session, "P-NO-P2P", active=False)
    result = await _import(session)
    r1 = [i.path for i in result.issues if i.code == "R1.unresolved_principle"]
    assert r1 == ["motivation.principles[1]"]


async def test_relation_targets_resolve_against_families(session) -> None:
    await _import(session, MESH)
    result = await _import(session)
    r3 = [i.path for i in result.issues if i.code == "R3.unresolved_relation"]
    assert r3 == ["relations[1].target"]  # one-sor-per-capability not imported yet


# ── US1: reads (FR-005, FR-006) ───────────────────────────────────────────────────
async def test_list_filters(session) -> None:
    for text in (BACKBONE, MESH, ONE_SOR):
        await _import(session, text)
    everything = await pstore.list_versions(session)
    assert everything.total == 3
    by_kind = await pstore.list_versions(session, kind=PatternKind.ANTI_PATTERN)
    assert [v.pattern_key for v in by_kind.items] == ["ea.integration.point-to-point-mesh"]
    by_tag = await pstore.list_versions(session, tag="event-driven")
    assert [v.pattern_key for v in by_tag.items] == [KEY]
    by_q = await pstore.list_versions(session, q="BACKBONE")
    assert [v.pattern_key for v in by_q.items] == [KEY]
    by_lc = await pstore.list_versions(session, lifecycle=L.CURRENT)
    assert by_lc.total == 0


async def test_family_versions_current_first_then_semver_descending(session) -> None:
    for v in ("1.2.0", "1.9.0", "1.10.0"):
        await _import(session, with_version(BACKBONE, v))
    await _set_lifecycle(session, KEY, "1.2.0", L.CURRENT)
    family = await pstore.get_family(KEY, session)
    assert [v.version for v in family.versions] == ["1.2.0", "1.10.0", "1.9.0"]
    assert family.current_version == "1.2.0"


async def test_detail_round_trips_definition_with_role_order(session) -> None:
    await _import(session)
    detail = await pstore.get_version_detail(KEY, "1.0.0", session)
    original = parse_pattern_yaml(BACKBONE).definition
    assert original is not None
    assert detail.definition == original
    assert list(detail.definition.roles) == list(original.roles)
    assert detail.allowed_transitions == [L.PROPOSED]
    assert {r.target_pattern_key for r in detail.relations} == {
        "ea.integration.point-to-point-mesh",
        "ea.data.one-sor-per-capability",
    }
    assert not any(r.target_resolved for r in detail.relations)


async def test_yaml_download_is_canonical(session) -> None:
    await _import(session)
    original = parse_pattern_yaml(BACKBONE).definition
    assert original is not None
    assert await pstore.get_yaml(KEY, "1.0.0", session) == to_canonical_yaml(original)


async def test_missing_family_and_version_raise(session) -> None:
    from adp.patterns.registry_models import PatternNotFoundError, PatternVersionNotFoundError

    with pytest.raises(PatternNotFoundError):
        await pstore.get_family("ea.no.such", session)
    await _import(session)
    with pytest.raises(PatternVersionNotFoundError):
        await pstore.get_version_detail(KEY, "9.9.9", session)


# ── US2: lifecycle (FR-007–FR-011) ────────────────────────────────────────────────
def _req(to: L, reason: str = "Reviewed by ARB", confirmation: str = "conf-1"):  # type: ignore[no-untyped-def]
    from adp.patterns.registry_models import LifecycleTransitionRequest

    return LifecycleTransitionRequest(to=to, reason=reason, confirmation_id=confirmation)


async def _resolvable(session) -> None:
    """Make every reference in the backbone fixture resolve, so it can be promoted."""
    await _principle(session, "P-API-FIRST")
    await _principle(session, "P-NO-P2P")
    await _import(session, MESH)
    await _import(session, ONE_SOR)


async def _move(session, version: str, *states: L, key: str = KEY):  # type: ignore[no-untyped-def]
    detail = None
    for state in states:
        detail = await pstore.transition(key, version, _req(state), ACTOR, session)
        await session.commit()
    return detail


async def test_illegal_transition_is_refused(session) -> None:
    from adp.patterns.registry_models import IllegalTransitionError

    await _import(session)
    with pytest.raises(IllegalTransitionError):
        await pstore.transition(KEY, "1.0.0", _req(L.CURRENT), ACTOR, session)


async def test_propose_and_back_to_draft_records_history(session) -> None:
    await _import(session)
    detail = await _move(session, "1.0.0", L.PROPOSED)
    assert detail.lifecycle == L.PROPOSED
    assert detail.allowed_transitions == [L.DRAFT, L.CURRENT]
    detail = await _move(session, "1.0.0", L.DRAFT)
    assert detail.lifecycle == L.DRAFT
    assert [(e.from_state, e.to_state) for e in detail.history] == [
        (L.DRAFT, L.PROPOSED),
        (L.PROPOSED, L.DRAFT),
    ]
    event = detail.history[0]
    assert (event.reason, event.confirmation_id, event.actor) == (
        "Reviewed by ARB",
        "conf-1",
        ACTOR,
    )


async def test_promotion_blocked_by_unresolved_references(session) -> None:
    from adp.patterns.registry_models import PromotionBlockedError

    await _import(session)
    await _move(session, "1.0.0", L.PROPOSED)
    with pytest.raises(PromotionBlockedError) as exc:
        await pstore.transition(KEY, "1.0.0", _req(L.CURRENT), ACTOR, session)
    assert {i.code for i in exc.value.issues} == {
        "R1.unresolved_principle",
        "R3.unresolved_relation",
    }
    assert all(i.severity == "error" for i in exc.value.issues)
    await session.rollback()
    assert (await pstore.get_version_detail(KEY, "1.0.0", session)).lifecycle == L.PROPOSED


async def test_promotion_swaps_the_current_version(session) -> None:
    await _resolvable(session)
    await _import(session)
    await _move(session, "1.0.0", L.PROPOSED, L.CURRENT)
    await _import(session, with_version(BACKBONE, "1.1.0"))
    v2 = await _move(session, "1.1.0", L.PROPOSED, L.CURRENT)
    assert v2.lifecycle == L.CURRENT
    v1 = await pstore.get_version_detail(KEY, "1.0.0", session)
    assert v1.lifecycle == L.DEPRECATED
    demotion = v1.history[-1]
    assert (demotion.from_state, demotion.to_state) == (L.CURRENT, L.DEPRECATED)
    promotion = v2.history[-1]
    assert demotion.caused_by_event_id == promotion.id
    assert demotion.confirmation_id == promotion.confirmation_id
    family = await pstore.get_family(KEY, session)
    assert family.current_version == "1.1.0"


async def test_rollback_from_deprecated_demotes_the_other_current(session) -> None:
    await _resolvable(session)
    await _import(session)
    await _move(session, "1.0.0", L.PROPOSED, L.CURRENT)
    await _import(session, with_version(BACKBONE, "1.1.0"))
    await _move(session, "1.1.0", L.PROPOSED, L.CURRENT)
    back = await _move(session, "1.0.0", L.CURRENT)
    assert back.lifecycle == L.CURRENT
    assert (await pstore.get_version_detail(KEY, "1.1.0", session)).lifecycle == L.DEPRECATED


async def test_decommissioned_is_terminal(session) -> None:
    from adp.patterns.registry_models import IllegalTransitionError

    await _resolvable(session)
    await _import(session)
    await _move(session, "1.0.0", L.PROPOSED, L.CURRENT, L.DEPRECATED, L.DECOMMISSIONED)
    for state in L:
        with pytest.raises(IllegalTransitionError):
            await pstore.transition(KEY, "1.0.0", _req(state), ACTOR, session)


async def test_concurrent_second_current_maps_to_conflict(session, monkeypatch) -> None:
    """The partial unique index is the last line of defence (research D4)."""
    from adp.patterns.registry_models import ConcurrentPromotionError

    await _resolvable(session)
    await _import(session)
    await _move(session, "1.0.0", L.PROPOSED, L.CURRENT)
    await _import(session, with_version(BACKBONE, "1.1.0"))
    await _move(session, "1.1.0", L.PROPOSED)

    async def _no_demote(*args, **kwargs):  # simulate a racing transaction that saw no current
        return None

    monkeypatch.setattr(pstore, "_demote_current", _no_demote)
    with pytest.raises(ConcurrentPromotionError):
        await pstore.transition(KEY, "1.1.0", _req(L.CURRENT), ACTOR, session)
    await session.rollback()
    assert (await pstore.get_family(KEY, session)).current_version == "1.0.0"
