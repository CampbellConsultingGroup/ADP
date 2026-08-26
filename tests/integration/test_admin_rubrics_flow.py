"""Integration test: a confirmed rubric weight edit takes effect for the very
next business-value computation, against a real Postgres container -- no
restart, no redeploy (ADP-68z, mirrors test_admin_prompts_flow.py's own
identical guarantee for agent prompts).

adp.admin.rubric_service and adp.admin.rubric_registry each own a lazy,
process-global session factory keyed off ADP_DATABASE_URL (see
test_admin_prompts_flow.py's own identical comment for prompt_registry/
service -- the same reasoning applies here unchanged). This test points that
env var at the real test container and resets both modules' cached engine/
factory first, so this test doesn't depend on whatever a previous test in
the same process already initialized them to.
"""

from __future__ import annotations

import pytest


@pytest.fixture(autouse=True)
def _reset_admin_module_state(db_url, monkeypatch):
    from adp.admin import rubric_registry, rubric_service

    monkeypatch.setenv("ADP_DATABASE_URL", db_url)
    for mod in (rubric_registry, rubric_service):
        monkeypatch.setattr(mod, "_engine", None)
        monkeypatch.setattr(mod, "_session_factory", None)
    monkeypatch.setattr(rubric_registry, "_engine_loop", None)


_VALID_WEIGHTS = {
    "strategic_alignment": 0.50, "revenue_cost_impact": 0.10,
    "customer_stakeholder_impact": 0.10, "competitive_differentiation": 0.10,
    "risk_compliance_contribution": 0.10, "evidence_measurability": 0.10,
}


async def test_confirmed_edit_takes_effect_for_next_business_value_computation(
    db_engine, db_session,
) -> None:
    from adp.admin import rubric_service
    from adp.admin.rubric_registry import get_effective_weights
    from adp.application import store as astore
    from adp.application.models import ApplicationCreate, BusinessValueAssessmentSubmit

    # Before any edit: business_value is on its built-in fallback.
    before = await get_effective_weights("business_value")
    assert before.is_override is False

    # Confirm an edit via the service layer (mirrors what the confirm endpoint
    # does) using its OWN fresh session against the real container.
    factory = rubric_service._get_session_factory()
    async with factory() as session:
        result = await rubric_service.save_weights(
            "business_value", _VALID_WEIGHTS, expected_version=0, actor="alice",
            confirmation_id="CONFIRM-bv-integration-1", session=session,
        )
        await session.commit()
    assert result.version == 1

    # The next lookup -- a completely separate call, its own fresh
    # resolution, no shared in-process state, no restart -- must see the new
    # weights immediately.
    after = await get_effective_weights("business_value")
    assert after.is_override is True
    assert after.weights == _VALID_WEIGHTS

    # And the real compute_business_value_score() call sites (not just the
    # registry directly) pick it up too, proving the store.py rewire actually
    # works end-to-end against a real DB.
    app = await astore.create_application(ApplicationCreate(name="Rubric Flow Test"), db_session)
    result = await astore.upsert_business_value_assessment(
        app.id,
        BusinessValueAssessmentSubmit(
            strategic_alignment=5, revenue_cost_impact=1, customer_stakeholder_impact=1,
            competitive_differentiation=1, risk_compliance_contribution=1,
            evidence_measurability=5,
        ),
        actor="alice",
        session=db_session,
    )
    assert result.result is not None
    # raw = 5*0.50 + 1*0.10*4 + 5*0.10 = 2.5 + 0.4 + 0.5 = 3.4 -- the OVERRIDDEN
    # weights, not the default (0.25/0.25/0.15/0.15/0.10/0.10) set, which would
    # instead have produced 2.4 for these same scores.
    assert result.result.weighted_average == 3.4


async def test_two_edits_by_different_actors_recorded_and_restorable(db_engine) -> None:
    """Mirrors test_admin_prompts_flow.py's identical User Story 2 setup: two
    successive edits by different actors, then restore the first."""
    from adp.admin import rubric_service

    factory = rubric_service._get_session_factory()

    async with factory() as session:
        await rubric_service.save_weights(
            "business_value", _VALID_WEIGHTS, 0, "alice", "CONFIRM-1", session,
        )
        await session.commit()

    other_weights = dict(_VALID_WEIGHTS, strategic_alignment=0.30, revenue_cost_impact=0.30)
    async with factory() as session:
        await rubric_service.save_weights(
            "business_value", other_weights, 1, "bob", "CONFIRM-2", session,
        )
        await session.commit()

    async with factory() as session:
        history = await rubric_service.get_history("business_value", session)
    assert len(history) == 2
    assert history[0].actor == "bob"  # newest first
    assert history[1].actor == "alice"

    alice_entry = history[1]
    async with factory() as session:
        restored = await rubric_service.restore_weights(
            "business_value", alice_entry.id, expected_version=2, actor="alice",
            confirmation_id="CONFIRM-3", session=session,
        )
        await session.commit()

    assert restored.active_weights == _VALID_WEIGHTS
    assert restored.version == 3

    async with factory() as session:
        final_history = await rubric_service.get_history("business_value", session)
    assert len(final_history) == 3
    assert final_history[0].change_type == "restore"
    assert final_history[0].new_weights == _VALID_WEIGHTS
