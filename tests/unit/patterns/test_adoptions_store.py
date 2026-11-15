"""Adoption store against SQLite (936 US2, FR-001–FR-004; research D2)."""

from __future__ import annotations

import pytest
import sqlalchemy as sa
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from adp.patterns import adoptions as ad
from adp.patterns import snapshot_store as ss
from adp.patterns import store as pstore
from adp.patterns.conformance_models import (
    AdoptionCreate,
    AdoptionNotFoundError,
    AdoptionUpdate,
    DraftPinError,
    DuplicateAdoptionError,
    InvalidPinError,
    InvalidScopeError,
    PinIn,
    ScopeTargetNotFoundError,
    ScopeType,
)
from adp.patterns.models import ElementType as T
from adp.patterns.registry_models import (
    LifecycleTransitionRequest,
    PatternNotFoundError,
    PatternVersionNotFoundError,
)
from adp.patterns.registry_models import PatternLifecycle as L

from .conftest import load_fixture

BACKBONE = load_fixture("ea.integration.domain-event-backbone@1.0.0.yaml").replace(
    "  principles: [P-API-FIRST, P-NO-P2P]", "  principles: []"
)
MESH = load_fixture("ea.integration.point-to-point-mesh@1.0.0.yaml")
ONE_SOR = load_fixture("ea.data.one-sor-per-capability@1.0.0.yaml").replace(
    "  principles: [P-SINGLE-SOURCE]", "  principles: []"
)
KEY = "ea.integration.domain-event-backbone"


@pytest.fixture()
async def session(tmp_path):
    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path}/adoptions.db")
    async with engine.begin() as conn:
        await conn.run_sync(pstore._metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as s:
        now = pstore._now()
        await s.execute(
            ss._domains.insert(),
            [
                {"id": "d1", "name": "Claims", "classification": "strategic", "risk_flags": []},
                {"id": "d2", "name": "Billing", "classification": "commodity", "risk_flags": []},
            ],
        )
        await s.execute(
            pstore._applications_mirror.insert(),
            [
                {
                    "id": "app1",
                    "name": "Claims Core",
                    "lifecycle_status": "active",
                    "tech_debt_flags": [],
                },
                {
                    "id": "hub",
                    "name": "Event Hub",
                    "lifecycle_status": "active",
                    "tech_debt_flags": [],
                },
            ],
        )
        await s.execute(
            ss._integrations.insert().values(
                id="i1", source_app_id="app1", target_app_id="hub", integration_type="event"
            )
        )
        for text in (MESH, ONE_SOR, BACKBONE):
            await pstore.import_pattern(text, "t", s)
        await s.commit()
        _ = now
        yield s
    await engine.dispose()


async def _promote(s, key: str = KEY, version: str = "1.0.0") -> None:  # type: ignore[no-untyped-def]
    for to in (L.PROPOSED, L.CURRENT):
        req = LifecycleTransitionRequest(to=to, reason="r", confirmation_id="c")
        await pstore.transition(key, version, req, "t", s)
    await s.commit()


def _create(**kw) -> AdoptionCreate:  # type: ignore[no-untyped-def]
    base = {
        "pattern_key": KEY,
        "name": "Claims backbone",
        "scope_type": "business_domain",
        "scope_ref": "d1",
    }
    base.update(kw)
    return AdoptionCreate.model_validate(base)


HUB = PinIn(role_key="backbone", element_type=T.APPLICATION, element_id="hub")


async def test_create_domain_adoption_following_current(session) -> None:
    await _promote(session)
    a = await ad.create_adoption(_create(pins=[HUB]), "ea", session)
    await session.commit()
    assert (a.scope_type, a.scope_ref, a.scope_name) == (ScopeType.BUSINESS_DOMAIN, "d1", "Claims")
    assert (a.pinned_version, a.resolved_version, a.pattern_name) == (
        None,
        "1.0.0",
        "Domain Event Backbone",
    )
    assert a.pins == [HUB]
    listing = await ad.list_adoptions(session)
    assert [x.id for x in listing.items] == [a.id]


async def test_duplicates_per_scope_and_name(session) -> None:
    await _promote(session)
    await ad.create_adoption(_create(), "ea", session)
    await session.commit()
    with pytest.raises(DuplicateAdoptionError):
        await ad.create_adoption(_create(name="Other name"), "ea", session)
    with pytest.raises(DuplicateAdoptionError):
        await ad.create_adoption(_create(scope_ref="d2"), "ea", session)  # same name
    await ad.create_adoption(
        _create(name="All", scope_type="portfolio", scope_ref=None), "ea", session
    )
    with pytest.raises(DuplicateAdoptionError):
        await ad.create_adoption(
            _create(name="All 2", scope_type="portfolio", scope_ref=None), "ea", session
        )
    for name in ("Set A", "Set B"):  # several application sets are fine
        await ad.create_adoption(
            _create(name=name, scope_type="application_set", scope_ref=None, member_ids=["app1"]),
            "ea",
            session,
        )


async def test_scope_targets_must_exist(session) -> None:
    with pytest.raises(PatternNotFoundError):
        await ad.create_adoption(_create(pattern_key="ea.no.such"), "ea", session)
    with pytest.raises(ScopeTargetNotFoundError):
        await ad.create_adoption(_create(scope_ref="nope"), "ea", session)
    with pytest.raises(ScopeTargetNotFoundError):
        await ad.create_adoption(
            _create(scope_type="application_set", scope_ref=None, member_ids=["ghost"]),
            "ea",
            session,
        )


async def test_pinned_version_rules(session) -> None:
    with pytest.raises(PatternVersionNotFoundError):
        await ad.create_adoption(_create(pinned_version="9.9.9"), "ea", session)
    with pytest.raises(DraftPinError):
        await ad.create_adoption(_create(pinned_version="1.0.0"), "ea", session)  # still draft
    await _promote(session)
    a = await ad.create_adoption(_create(pinned_version="1.0.0"), "ea", session)
    assert a.resolved_version == "1.0.0"


async def test_no_current_version_resolves_to_none(session) -> None:
    a = await ad.create_adoption(_create(), "ea", session)  # family has only a draft
    assert a.resolved_version is None
    assert await ad.resolve_definition(a, session) is None


async def test_pin_validation(session) -> None:
    await _promote(session)
    bad = [
        PinIn(role_key="nope", element_type=T.APPLICATION, element_id="hub"),
        PinIn(role_key="backbone", element_type=T.AGENT, element_id="hub"),
        PinIn(role_key="backbone", element_type=T.APPLICATION, element_id="ghost"),
    ]
    with pytest.raises(InvalidPinError) as exc:
        await ad.create_adoption(_create(pins=bad), "ea", session)
    assert len(exc.value.reasons) == 3
    a = await ad.create_adoption(_create(), "ea", session)
    with pytest.raises(InvalidPinError):
        await ad.set_pins(a.id, bad[:1], "ea", session)
    pinned = await ad.set_pins(
        a.id,
        [
            HUB,
            PinIn(role_key="cross_domain_integration", element_type=T.INTEGRATION, element_id="i1"),
        ],
        "ea",
        session,
    )
    assert len(pinned.pins) == 2
    assert (await ad.set_pins(a.id, [], "ea", session)).pins == []


async def test_members_only_for_application_sets(session) -> None:
    await _promote(session)
    a = await ad.create_adoption(
        _create(name="Set", scope_type="application_set", scope_ref=None, member_ids=["app1"]),
        "ea",
        session,
    )
    assert a.member_ids == ["app1"]
    assert (await ad.set_members(a.id, ["app1", "hub"], "ea", session)).member_ids == [
        "app1",
        "hub",
    ]
    with pytest.raises(ScopeTargetNotFoundError):
        await ad.set_members(a.id, ["ghost"], "ea", session)
    d = await ad.create_adoption(_create(), "ea", session)
    with pytest.raises(InvalidScopeError):
        await ad.set_members(d.id, ["app1"], "ea", session)


async def test_update_name_and_version_pin(session) -> None:
    await _promote(session)
    a = await ad.create_adoption(_create(), "ea", session)
    u = await ad.update_adoption(a.id, AdoptionUpdate(name="Renamed"), {"name"}, "ea", session)
    assert u.name == "Renamed"
    u = await ad.update_adoption(
        a.id, AdoptionUpdate(pinned_version="1.0.0"), {"pinned_version"}, "ea", session
    )
    assert u.pinned_version == "1.0.0"
    u = await ad.update_adoption(
        a.id, AdoptionUpdate(pinned_version=None), {"pinned_version"}, "ea", session
    )
    assert u.pinned_version is None


async def test_delete_removes_members_and_pins(session) -> None:
    await _promote(session)
    a = await ad.create_adoption(
        _create(
            name="Set",
            scope_type="application_set",
            scope_ref=None,
            member_ids=["app1"],
            pins=[HUB],
        ),
        "ea",
        session,
    )
    await ad.delete_adoption(a.id, session)
    for table in (ad._adoptions, ad._members, ad._pins):
        n = (await session.execute(sa.select(sa.func.count()).select_from(table))).scalar_one()
        assert n == 0
    with pytest.raises(AdoptionNotFoundError):
        await ad.get_adoption(a.id, session)
