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
    EXPORT_DESIGN = "export_design"
    WRITE_BUSINESS_ARCH = "write_business_arch"
    WRITE_APPLICATION = "write_application"
    MANAGE_CONFIG = "manage_config"
    # ADP-SPEC-038 (APM US3): sensitive application risk & compliance data.
    READ_APPLICATION_RISK = "read_application_risk"
    WRITE_APPLICATION_RISK = "write_application_risk"
    # ADP-SPEC-038 (APM US4): sensitive application cost (TCO) data.
    READ_APPLICATION_COST = "read_application_cost"
    WRITE_APPLICATION_COST = "write_application_cost"
    # ADP-SPEC-038 (APM US7): sensitive application governance/contract data.
    READ_APPLICATION_GOVERNANCE = "read_application_governance"
    WRITE_APPLICATION_GOVERNANCE = "write_application_governance"
    # ADP-SPEC-039: confirming (accepting/rejecting) an Agent Review suggestion,
    # distinct from WRITE_BUSINESS_ARCH (the underlying store write when a
    # suggestion is applied) and from SUBMIT_AI_OPERATION (reused, triggers
    # the review itself).
    CONFIRM_AGENT_SUGGESTION = "confirm_agent_suggestion"
