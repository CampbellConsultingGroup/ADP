"""Unit tests: Regulatory Framework Legal Dates & Identity (COMPLY-01a,
specs/926-framework-versioning-correction/).

Mirrors tests/unit/compliance/test_compliance_status.py's own in-memory SQLite `_metadata`
fixture convention. `regulation_number`'s UNIQUE constraint (migration 035's own DDL) is added
manually here, same convention `test_compliance_registry_api.py` already uses for
`controls`' own `UNIQUE(framework_id, code)`.
"""

from __future__ import annotations

from datetime import date, datetime, timezone

import pytest
import sqlalchemy as sa
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from adp.compliance import store as cstore
from adp.compliance.models import (
    FrameworkAmendmentCreate,
    FrameworkApplicationPhaseCreate,
    RegulatoryFrameworkCreate,
    RegulatoryFrameworkUpdate,
)

_UNIQUE_DDL = [
    "CREATE UNIQUE INDEX uq_regulatory_frameworks_regulation_number "
    "ON regulatory_frameworks(regulation_number)",
]


@pytest.fixture()
async def session(tmp_path):
    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path}/framework_legal_dates.db")
    async with engine.begin() as conn:
        await conn.run_sync(cstore._metadata.create_all)
        for ddl in _UNIQUE_DDL:
            await conn.execute(sa.text(ddl))
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as s:
        yield s
    await engine.dispose()


async def _mk_framework(session, name="GDPR", **extra) -> str:
    fw = await cstore.create_framework(
        RegulatoryFrameworkCreate(
            name=name, jurisdiction="EU", authority="European Commission",
            version="2016/679", **extra,
        ),
        session,
    )
    await session.commit()
    return fw.id


class TestNewFrameworkFieldsRoundTrip:
    """T002 -- US1: create_framework()/update_framework() accept and persist the seven new
    optional fields; a framework that never sets them is unaffected."""

    async def test_create_with_all_new_fields(self, session):
        fw = await cstore.create_framework(
            RegulatoryFrameworkCreate(
                name="EU AI Act", jurisdiction="EU", authority="AI Office", version="2024/1689",
                regulation_number="2024/1689", celex_number="32024R1689",
                adoption_date=date(2024, 6, 13), oj_publication_date=date(2024, 7, 12),
                entry_into_force_date=date(2024, 8, 1), consolidated_as_of=date(2024, 7, 12),
                status="in_force",
            ),
            session,
        )
        assert fw.regulation_number == "2024/1689"
        assert fw.celex_number == "32024R1689"
        assert fw.adoption_date == date(2024, 6, 13)
        assert fw.status == "in_force"

    async def test_create_with_none_of_the_new_fields_is_unaffected(self, session):
        fw = await cstore.create_framework(
            RegulatoryFrameworkCreate(
                name="GDPR", jurisdiction="EU", authority="EDPB",
                version="Regulation (EU) 2016/679",
            ),
            session,
        )
        # Existing fields exactly as provided; every new field None/default, nothing required.
        assert fw.name == "GDPR"
        assert fw.version == "Regulation (EU) 2016/679"
        assert fw.regulation_number is None
        assert fw.celex_number is None
        assert fw.adoption_date is None
        assert fw.status == "in_force"

    async def test_update_sets_new_fields_without_touching_existing_ones(self, session):
        fw_id = await _mk_framework(session)
        updated = await cstore.update_framework(
            fw_id,
            RegulatoryFrameworkUpdate(
                regulation_number="2016/679", consolidated_as_of=date(2016, 5, 4),
            ),
            session,
        )
        assert updated is not None
        assert updated.regulation_number == "2016/679"
        assert updated.consolidated_as_of == date(2016, 5, 4)
        # Original fields, never touched by this update, remain exactly as created.
        assert updated.name == "GDPR"
        assert updated.jurisdiction == "EU"
        assert updated.version == "2016/679"

    async def test_duplicate_regulation_number_raises(self, session):
        await _mk_framework(session, name="GDPR", regulation_number="2016/679")
        with pytest.raises(cstore.DuplicateRegulationNumberError):
            await cstore.create_framework(
                RegulatoryFrameworkCreate(
                    name="GDPR Duplicate", jurisdiction="EU", authority="EDPB",
                    version="x", regulation_number="2016/679",
                ),
                session,
            )

    async def test_two_frameworks_without_regulation_number_do_not_conflict(self, session):
        # NULLs never collide under a UNIQUE constraint (research.md D2).
        id1 = await _mk_framework(session, name="Framework A")
        id2 = await _mk_framework(session, name="Framework B")
        assert id1 != id2

    async def test_pre_existing_row_seeded_without_new_columns_reads_status_default(self, session):
        """Mirrors test_compliance_status.py's own raw-insert fixture pattern (bypassing
        create_framework() entirely) -- confirms the store-layer Table()'s Python-side default
        (not just the migration's server_default) keeps a bare insert working, the same as it
        did before this feature (regression guard)."""
        now = datetime.now(timezone.utc)
        await session.execute(
            cstore._frameworks.insert().values(
                id="fw-raw", name="Raw Insert Framework", jurisdiction="Global",
                authority="Test Authority", version="1.0", effective_date=None,
                source_url=None, created_at=now, updated_at=now,
                # status/regulation_number/etc. intentionally omitted, as this precedent test
                # already does for every column added by earlier specs.
            )
        )
        await session.commit()
        fw = await cstore.get_framework("fw-raw", session)
        assert fw is not None
        assert fw.status == "in_force"
        assert fw.regulation_number is None


class TestApplicationPhases:
    """T008 -- US2: add_/list_/delete_application_phase()."""

    async def test_add_and_list_ordered_by_date(self, session):
        fw_id = await _mk_framework(session)
        await cstore.add_application_phase(
            fw_id,
            FrameworkApplicationPhaseCreate(
                phase_label="GPAI obligations", applies_from_date=date(2025, 8, 2),
            ),
            session,
        )
        await cstore.add_application_phase(
            fw_id,
            FrameworkApplicationPhaseCreate(
                phase_label="Prohibited practices", applies_from_date=date(2025, 2, 2),
            ),
            session,
        )
        await session.commit()

        phases = await cstore.list_application_phases(fw_id, session)
        assert [p.phase_label for p in phases] == ["Prohibited practices", "GPAI obligations"]

    async def test_zero_phases_is_empty_list_not_an_error(self, session):
        fw_id = await _mk_framework(session)
        assert await cstore.list_application_phases(fw_id, session) == []

    async def test_delete_removes_phase(self, session):
        fw_id = await _mk_framework(session)
        phase = await cstore.add_application_phase(
            fw_id,
            FrameworkApplicationPhaseCreate(
                phase_label="Phase 1", applies_from_date=date(2025, 1, 1)
            ),
            session,
        )
        await session.commit()
        await cstore.delete_application_phase(fw_id, phase.id, session)
        await session.commit()
        assert await cstore.list_application_phases(fw_id, session) == []

    async def test_delete_unknown_phase_raises(self, session):
        fw_id = await _mk_framework(session)
        with pytest.raises(cstore.ApplicationPhaseNotFoundError):
            await cstore.delete_application_phase(fw_id, "does-not-exist", session)


class TestAmendments:
    """T014 -- US3: add_/list_/delete_amendment()."""

    async def test_add_and_list_ordered_by_date_nulls_last(self, session):
        fw_id = await _mk_framework(session)
        await cstore.add_amendment(
            fw_id,
            FrameworkAmendmentCreate(amending_title="No date yet"),
            session,
        )
        await cstore.add_amendment(
            fw_id,
            FrameworkAmendmentCreate(amending_title="RTS 1", effective_date=date(2024, 1, 1)),
            session,
        )
        await session.commit()

        amendments = await cstore.list_amendments(fw_id, session)
        assert [a.amending_title for a in amendments] == ["RTS 1", "No date yet"]

    async def test_zero_amendments_is_empty_list_not_an_error(self, session):
        fw_id = await _mk_framework(session)
        assert await cstore.list_amendments(fw_id, session) == []

    async def test_delete_removes_amendment(self, session):
        fw_id = await _mk_framework(session)
        amendment = await cstore.add_amendment(
            fw_id, FrameworkAmendmentCreate(amending_title="RTS 1"), session
        )
        await session.commit()
        await cstore.delete_amendment(fw_id, amendment.id, session)
        await session.commit()
        assert await cstore.list_amendments(fw_id, session) == []

    async def test_delete_unknown_amendment_raises(self, session):
        fw_id = await _mk_framework(session)
        with pytest.raises(cstore.AmendmentNotFoundError):
            await cstore.delete_amendment(fw_id, "does-not-exist", session)

    async def test_no_limit_on_amendment_count(self, session):
        fw_id = await _mk_framework(session)
        for i in range(5):
            await cstore.add_amendment(
                fw_id, FrameworkAmendmentCreate(amending_title=f"RTS {i}"), session
            )
        await session.commit()
        assert len(await cstore.list_amendments(fw_id, session)) == 5


class TestFrameworkDetailNestsPhasesAndAmendments:
    """T007/T012/T018 -- research.md D4: get_framework_detail() nests application_phases and
    amendments alongside the existing controls."""

    async def test_detail_includes_empty_lists_when_none_recorded(self, session):
        fw_id = await _mk_framework(session)
        detail = await cstore.get_framework_detail(fw_id, session)
        assert detail is not None
        assert detail.application_phases == []
        assert detail.amendments == []
        assert detail.controls == []

    async def test_detail_includes_populated_lists(self, session):
        fw_id = await _mk_framework(session)
        await cstore.add_application_phase(
            fw_id,
            FrameworkApplicationPhaseCreate(
                phase_label="Phase 1", applies_from_date=date(2025, 1, 1)
            ),
            session,
        )
        await cstore.add_amendment(fw_id, FrameworkAmendmentCreate(amending_title="RTS 1"), session)
        await session.commit()

        detail = await cstore.get_framework_detail(fw_id, session)
        assert detail is not None
        assert len(detail.application_phases) == 1
        assert len(detail.amendments) == 1
