"""Typed enumerations for ADP personas and protected action categories."""

from enum import StrEnum


class PersonaRole(StrEnum):
    """Recognized organizational personas. Unrecognized strings raise ValueError."""

    ENTERPRISE_ARCHITECT = "enterprise_architect"
    SOLUTION_ARCHITECT = "solution_architect"
    TECHNICAL_ARCHITECT = "technical_architect"
    REVIEWER = "reviewer"


class ActionType(StrEnum):
    """Protected action categories. Every protected operation maps to one of these."""

    READ_DESIGN = "read_design"
    WRITE_DESIGN = "write_design"
    SUBMIT_AI_OPERATION = "submit_ai_operation"
    CONFIRM_RECOMMENDATION = "confirm_recommendation"
    OVERRIDE_VERDICT = "override_verdict"
    ADD_FINDING = "add_finding"
    AMEND_STANDARD = "amend_standard"
    MANAGE_ROLES = "manage_roles"
