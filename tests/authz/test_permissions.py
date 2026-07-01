"""Tests for role model, permission table, and enforcement functions (US1–US3)."""

from __future__ import annotations

import subprocess

import pytest

from adp.authz.permissions import (
    PERMISSIONS_VERSION,
    PermissionDeniedError,
    is_permitted,
    require_action,
    requires_confirmation,
)
from adp.authz.roles import ActionType, PersonaRole

# ── US1: Delegated authentication / no credential storage ────────────────────


def test_unrecognized_role_raises() -> None:
    """Unrecognized role strings raise ValueError before any permission check runs (FR-002)."""
    with pytest.raises(ValueError):
        PersonaRole("super_admin")


def test_recognized_role_succeeds() -> None:
    """All four recognized roles construct without error."""
    assert PersonaRole("enterprise_architect") == PersonaRole.ENTERPRISE_ARCHITECT
    assert PersonaRole("reviewer") == PersonaRole.REVIEWER


def test_invalid_role_bypasses_no_permission() -> None:
    """ValueError propagates before is_permitted is reached — proves NFR-001."""
    with pytest.raises(ValueError):
        role = PersonaRole("attacker")
        is_permitted(role, ActionType.MANAGE_ROLES)  # never reached


def test_no_credential_storage_in_authz() -> None:
    """No assignment-context credential patterns in source or test fixtures (FR-002, QG-08)."""
    # Patterns split to avoid triggering on this test file's own source.
    # --exclude skips this file; T029's standalone grep is the canonical CI check.
    pattern = "passw" + "ord=|secr" + "et=|api_k" + "ey=|Beare" + "r |privat" + "e_key"
    result = subprocess.run(
        [
            "grep", "-rn", "-E", pattern,
            "--exclude=test_permissions.py",
            "src/adp/authz/", "src/adp/audit/", "tests/authz/",
        ],
        capture_output=True,
        text=True,
    )
    assert result.stdout.strip() == "", (
        f"Credential pattern found in source/fixtures:\n{result.stdout}"
    )


# ── US2: Permission table exhaustiveness ─────────────────────────────────────

# The expected permission matrix — machine-executable form of the spec table.
_EXPECTED: dict[tuple[PersonaRole, ActionType], bool] = {
    # enterprise_architect: all actions
    (PersonaRole.ENTERPRISE_ARCHITECT, ActionType.READ_DESIGN): True,
    (PersonaRole.ENTERPRISE_ARCHITECT, ActionType.WRITE_DESIGN): True,
    (PersonaRole.ENTERPRISE_ARCHITECT, ActionType.SUBMIT_AI_OPERATION): True,
    (PersonaRole.ENTERPRISE_ARCHITECT, ActionType.CONFIRM_RECOMMENDATION): True,
    (PersonaRole.ENTERPRISE_ARCHITECT, ActionType.OVERRIDE_VERDICT): True,
    (PersonaRole.ENTERPRISE_ARCHITECT, ActionType.ADD_FINDING): True,
    (PersonaRole.ENTERPRISE_ARCHITECT, ActionType.AMEND_STANDARD): True,
    (PersonaRole.ENTERPRISE_ARCHITECT, ActionType.MANAGE_ROLES): True,
    # solution_architect: no amend_standard, no manage_roles
    (PersonaRole.SOLUTION_ARCHITECT, ActionType.READ_DESIGN): True,
    (PersonaRole.SOLUTION_ARCHITECT, ActionType.WRITE_DESIGN): True,
    (PersonaRole.SOLUTION_ARCHITECT, ActionType.SUBMIT_AI_OPERATION): True,
    (PersonaRole.SOLUTION_ARCHITECT, ActionType.CONFIRM_RECOMMENDATION): True,
    (PersonaRole.SOLUTION_ARCHITECT, ActionType.OVERRIDE_VERDICT): True,
    (PersonaRole.SOLUTION_ARCHITECT, ActionType.ADD_FINDING): True,
    (PersonaRole.SOLUTION_ARCHITECT, ActionType.AMEND_STANDARD): False,
    (PersonaRole.SOLUTION_ARCHITECT, ActionType.MANAGE_ROLES): False,
    # technical_architect: no override_verdict, no amend_standard, no manage_roles
    (PersonaRole.TECHNICAL_ARCHITECT, ActionType.READ_DESIGN): True,
    (PersonaRole.TECHNICAL_ARCHITECT, ActionType.WRITE_DESIGN): True,
    (PersonaRole.TECHNICAL_ARCHITECT, ActionType.SUBMIT_AI_OPERATION): True,
    (PersonaRole.TECHNICAL_ARCHITECT, ActionType.CONFIRM_RECOMMENDATION): True,
    (PersonaRole.TECHNICAL_ARCHITECT, ActionType.OVERRIDE_VERDICT): False,
    (PersonaRole.TECHNICAL_ARCHITECT, ActionType.ADD_FINDING): True,
    (PersonaRole.TECHNICAL_ARCHITECT, ActionType.AMEND_STANDARD): False,
    (PersonaRole.TECHNICAL_ARCHITECT, ActionType.MANAGE_ROLES): False,
    # reviewer: read + override_verdict + add_finding only
    (PersonaRole.REVIEWER, ActionType.READ_DESIGN): True,
    (PersonaRole.REVIEWER, ActionType.WRITE_DESIGN): False,
    (PersonaRole.REVIEWER, ActionType.SUBMIT_AI_OPERATION): False,
    (PersonaRole.REVIEWER, ActionType.CONFIRM_RECOMMENDATION): False,
    (PersonaRole.REVIEWER, ActionType.OVERRIDE_VERDICT): True,
    (PersonaRole.REVIEWER, ActionType.ADD_FINDING): True,
    (PersonaRole.REVIEWER, ActionType.AMEND_STANDARD): False,
    (PersonaRole.REVIEWER, ActionType.MANAGE_ROLES): False,
}


@pytest.mark.parametrize("role,action,expected", [
    (role, action, expected)
    for (role, action), expected in _EXPECTED.items()
])
def test_permission_table_completeness(
    role: PersonaRole, action: ActionType, expected: bool
) -> None:
    """All 32 role×action combinations match the spec's permission matrix (FR-003, SC-002)."""
    assert is_permitted(role, action) == expected, (
        f"Expected is_permitted({role!r}, {action!r}) == {expected}"
    )


def test_permission_table_covers_all_roles_and_actions() -> None:
    """Every PersonaRole and ActionType appears in the expected table."""
    covered_roles = {r for r, _ in _EXPECTED}
    covered_actions = {a for _, a in _EXPECTED}
    assert covered_roles == set(PersonaRole)
    assert covered_actions == set(ActionType)


def test_require_action_raises_on_denied() -> None:
    """require_action raises PermissionDeniedError with correct role and action."""
    with pytest.raises(PermissionDeniedError) as exc_info:
        require_action(PersonaRole.REVIEWER, ActionType.WRITE_DESIGN)
    assert exc_info.value.role == PersonaRole.REVIEWER
    assert exc_info.value.action == ActionType.WRITE_DESIGN
    assert "reviewer" in str(exc_info.value)
    assert "write_design" in str(exc_info.value)


def test_require_action_passes_on_permitted() -> None:
    """require_action does not raise when the role is permitted."""
    require_action(PersonaRole.REVIEWER, ActionType.READ_DESIGN)  # must not raise


def test_require_action_logs_warning_on_denial(caplog: pytest.LogCaptureFixture) -> None:
    """Denied actions are observable via WARNING log (spec US2 scenario 1)."""
    import logging

    with caplog.at_level(logging.WARNING, logger="adp.authz"):
        with pytest.raises(PermissionDeniedError):
            require_action(PersonaRole.TECHNICAL_ARCHITECT, ActionType.OVERRIDE_VERDICT)

    assert any("permission_denied" in r.message for r in caplog.records)


def test_permissions_version_constant() -> None:
    """PERMISSIONS_VERSION exists and is 1.0.0 — any permission change must bump it."""
    assert PERMISSIONS_VERSION == "1.0.0"


# ── US3: Per-action confirmation requirements ────────────────────────────────

_CONFIRMATION_EXPECTED: dict[ActionType, bool] = {
    ActionType.READ_DESIGN: False,
    ActionType.WRITE_DESIGN: False,
    ActionType.SUBMIT_AI_OPERATION: False,
    ActionType.CONFIRM_RECOMMENDATION: True,
    ActionType.OVERRIDE_VERDICT: True,
    ActionType.ADD_FINDING: False,
    ActionType.AMEND_STANDARD: True,
    ActionType.MANAGE_ROLES: True,
}


@pytest.mark.parametrize("action,expected", list(_CONFIRMATION_EXPECTED.items()))
def test_requires_confirmation_set(action: ActionType, expected: bool) -> None:
    """requires_confirmation returns True for exactly the four consequential actions (FR-004)."""
    assert requires_confirmation(action) == expected, (
        f"Expected requires_confirmation({action!r}) == {expected}"
    )


def test_requires_confirmation_covers_all_actions() -> None:
    """Every ActionType appears in the expected confirmation table."""
    assert set(_CONFIRMATION_EXPECTED) == set(ActionType)
