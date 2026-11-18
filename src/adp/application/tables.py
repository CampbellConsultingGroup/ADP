"""Application Registry tables (SQLAlchemy Core, no ORM mapper).

Split out of ``adp.application.store`` (ADP-blp.27), which re-exports every name here.
"""

from __future__ import annotations

import sqlalchemy as sa

from adp.application.models import (
    TCO_BUCKET_NAMES,
)

# ── Table definitions (SQLAlchemy Core — no ORM mapper) ──────────────────────

_metadata = sa.MetaData()

_applications = sa.Table(
    "applications",
    _metadata,
    sa.Column("id", sa.String(36), primary_key=True),
    sa.Column("name", sa.String(255), nullable=False),
    sa.Column("description", sa.Text()),
    sa.Column("vendor", sa.String(255)),
    sa.Column("primary_owner", sa.String(255)),
    sa.Column("time_classification", sa.Text()),
    sa.Column("r_strategy", sa.Text()),
    sa.Column("pace_layer", sa.Text()),
    sa.Column("health_score", sa.Integer()),
    sa.Column("business_value", sa.SmallInteger()),
    sa.Column("business_criticality", sa.SmallInteger()),
    sa.Column("owning_business_unit", sa.String(255)),
    # 940-org-units-geography: a plain column here; migration 048 adds the real FK to org_units
    # (ON DELETE SET NULL). adp.application never imports adp.organization at store level.
    sa.Column("owning_org_unit_id", sa.String(36)),
    sa.Column("business_owner", sa.String(255)),
    sa.Column("technical_owner", sa.String(255)),
    sa.Column("lifecycle_status", sa.Text(), nullable=False, server_default="active"),
    sa.Column("hosting_model", sa.Text()),
    sa.Column("application_type", sa.Text()),
    sa.Column("architecture_pattern", sa.Text()),
    sa.Column("tech_debt_flags", sa.JSON(), nullable=False),
    sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
)

_tech_caps = sa.Table(
    "technical_capabilities",
    _metadata,
    sa.Column("id", sa.String(36), primary_key=True),
    sa.Column("name", sa.String(255), nullable=False),
    sa.Column("description", sa.Text()),
    sa.Column("parent_id", sa.String(36)),
    sa.Column("level", sa.Integer(), nullable=False),
    sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    # ADP-33v: strategic classification (migration 020)
    sa.Column("strategic_relevance", sa.SmallInteger(), nullable=True),
    # 938-capability-model-analysis: lifecycle (migration 047). The Python-side default covers raw
    # inserts that bypass create_technical_capability (some fixtures do).
    sa.Column("lifecycle_status", sa.Text(), nullable=False, default="current"),
    sa.Column("end_of_life_date", sa.Date(), nullable=True),
)

_app_cap_links = sa.Table(
    "application_capability_links",
    _metadata,
    sa.Column("app_id", sa.String(36), nullable=False),
    sa.Column("capability_id", sa.String(36), nullable=False),
    sa.Column("fit_score", sa.Integer(), nullable=False),
)

# business_capabilities reference for JOIN queries
_biz_caps = sa.Table(
    "business_capabilities",
    _metadata,
    sa.Column("id", sa.String(36), primary_key=True),
    sa.Column("name", sa.String(255), nullable=False),
    # 937-application-capabilities: level/parent for the mapping-level rules and L1/L2 paths.
    # Nullable here only so fixtures that create just this metadata still work; the real
    # table has both NOT NULL / indexed.
    sa.Column("level", sa.Integer(), nullable=True),
    sa.Column("parent_id", sa.String(36), nullable=True),
)

_app_tech_cap_links = sa.Table(
    "application_tech_cap_links",
    _metadata,
    sa.Column("app_id", sa.String(36), nullable=False),
    sa.Column("tech_cap_id", sa.String(36), nullable=False),
    sa.Column("usage_type", sa.Text(), nullable=False),
)

# 937-application-capabilities (migration 046): the application capability catalog and its three
# link tables. Defined here (not in adp.application.app_capabilities) so delete_application and
# delete_technical_capability can remove their link rows without a circular import, and so every
# fixture's _metadata.create_all() includes them. The functions live in app_capabilities.py.
_app_caps = sa.Table(
    "application_capabilities",
    _metadata,
    sa.Column("id", sa.String(36), primary_key=True),
    sa.Column("name", sa.String(255), nullable=False),
    sa.Column("description", sa.Text()),
    sa.Column("parent_id", sa.String(36), sa.ForeignKey("application_capabilities.id")),
    sa.Column("level", sa.SmallInteger(), nullable=False),
    sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
)

_biz_app_cap_links = sa.Table(
    "business_capability_app_capability_links",
    _metadata,
    sa.Column(
        "business_capability_id",
        sa.String(36),
        sa.ForeignKey("business_capabilities.id", ondelete="CASCADE"),
        primary_key=True,
    ),
    sa.Column(
        "app_capability_id",
        sa.String(36),
        sa.ForeignKey("application_capabilities.id", ondelete="CASCADE"),
        primary_key=True,
    ),
    sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
)

_app_cap_tech_links = sa.Table(
    "app_capability_tech_cap_links",
    _metadata,
    sa.Column(
        "app_capability_id",
        sa.String(36),
        sa.ForeignKey("application_capabilities.id", ondelete="CASCADE"),
        primary_key=True,
    ),
    sa.Column(
        "tech_cap_id",
        sa.String(36),
        sa.ForeignKey("technical_capabilities.id", ondelete="CASCADE"),
        primary_key=True,
    ),
    sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
)

_app_cap_realizations = sa.Table(
    "app_capability_realizations",
    _metadata,
    sa.Column(
        "app_capability_id",
        sa.String(36),
        sa.ForeignKey("application_capabilities.id", ondelete="CASCADE"),
        primary_key=True,
    ),
    sa.Column(
        "app_id",
        sa.String(36),
        sa.ForeignKey("applications.id", ondelete="CASCADE"),
        primary_key=True,
    ),
    sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    # 943-mapping-rationale: NULL = unclassified / everywhere. geography_id's FK (SET NULL) lives
    # only in migration 051 -- geographies are on the organization metadata (research R1).
    sa.Column("rationale", sa.Text(), nullable=True),
    sa.Column("geography_id", sa.String(36), nullable=True),
)

_app_stage_links = sa.Table(
    "application_stage_links",
    _metadata,
    sa.Column("app_id", sa.String(36), nullable=False),
    sa.Column("stage_id", sa.String(36), nullable=False),
)

# value_stream_stages reference for JOIN queries
_stages = sa.Table(
    "value_stream_stages",
    _metadata,
    sa.Column("id", sa.String(36), primary_key=True),
    sa.Column("name", sa.String(255), nullable=False),
)

_app_domain_integrations = sa.Table(
    "application_domain_integrations",
    _metadata,
    sa.Column("id", sa.String(36), primary_key=True),
    sa.Column("app_id", sa.String(36), nullable=False),
    sa.Column("domain_id", sa.String(36)),
    sa.Column("integration_type", sa.String(255), nullable=False),
    sa.Column("direction", sa.Text(), nullable=False),
    sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
)

# business_domains reference for JOIN queries
_domains = sa.Table(
    "business_domains",
    _metadata,
    sa.Column("id", sa.String(36), primary_key=True),
    sa.Column("name", sa.String(255), nullable=False),
)

_app_integrations = sa.Table(
    "application_integrations",
    _metadata,
    sa.Column("id", sa.String(36), primary_key=True),
    sa.Column("source_app_id", sa.String(36), nullable=False),
    sa.Column("target_app_id", sa.String(36), nullable=False),
    sa.Column("integration_type", sa.Text(), nullable=False),
    sa.Column("description", sa.Text()),
    sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
)

_app_design_links = sa.Table(
    "application_design_links",
    _metadata,
    sa.Column("app_id", sa.String(36), nullable=False),
    sa.Column("design_id", sa.String(36), nullable=False),
)

# designs reference for existence checks (ADP-SPEC-002)
_designs = sa.Table(
    "designs",
    _metadata,
    sa.Column("id", sa.Text(), primary_key=True),
)

# APM US3: risk & compliance register (1:1 with applications; cascade-deletes)
# 932-regulatory-framework-tags (ADP-bkg): regulatory_tags is no longer a column here -- it is
# now derived from _application_framework_tags below (migration 041 dropped the column).
_application_risk = sa.Table(
    "application_risk",
    _metadata,
    sa.Column("app_id", sa.String(36), primary_key=True),
    sa.Column("security_posture", sa.Text()),
    sa.Column("vulnerability_status", sa.Text()),
    sa.Column("data_classification", sa.Text()),
    sa.Column("dr_bc_status", sa.Text()),
    sa.Column("end_of_life_date", sa.Date()),
    sa.Column("end_of_support_date", sa.Date()),
    sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
)

# 932-regulatory-framework-tags (ADP-bkg, COMPLY-01 consumer): a bare, unassessed "this framework
# applies to this application" tag -- no compliance_status of its own, unlike a ControlMapping.
# DML-only Table object (no Python-level PK/FK), matching this package's existing table-definition
# convention elsewhere in this file; the real composite PK + ON DELETE CASCADE constraints live in
# migration 041 (research.md D1, mirroring adp.strategy.store's theme_framework_links precedent
# one level up, 927-theme-framework-mapping).
_application_framework_tags = sa.Table(
    "application_framework_tags",
    _metadata,
    sa.Column("application_id", sa.String(36), nullable=False),
    sa.Column("framework_id", sa.String(36), nullable=False),
    sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
)

# 933-agent-registry (research.md D3): narrow mirror of adp.agentic's solution_agents, used only
# for the reclassify guard in update_application and the explicit membership delete in
# delete_application. adp.agentic.store owns the full table definition; any fixture creating both
# metadatas on one connection must exclude this table from this module's create_all.
_solution_agents = sa.Table(
    "solution_agents",
    _metadata,
    sa.Column("solution_app_id", sa.String(36), nullable=False),
    sa.Column("agent_id", sa.String(36), nullable=False),
)

# Read-only mirror of regulatory_frameworks (research.md D1) -- existence + status validation for
# _application_framework_tags only, never written to from this module. adp.application continues
# to import zero other domain packages at the store layer, mirroring adp.strategy.store's own
# _regulatory_frameworks mirror (927-theme-framework-mapping) and adp.compliance.store's
# _applications_mirror (the identical idiom in the opposite direction).
_regulatory_frameworks = sa.Table(
    "regulatory_frameworks",
    _metadata,
    sa.Column("id", sa.String(36), primary_key=True),
    sa.Column("name", sa.Text(), nullable=False),
    sa.Column("status", sa.Text(), nullable=False),
)

# docs/application-health-assessment-spec.md: one *current* row per
# (application, dimension); a re-assessment upserts in place (no history).
_health_assessment = sa.Table(
    "application_health_assessment",
    _metadata,
    sa.Column("application_id", sa.String(36), primary_key=True),
    sa.Column("dimension", sa.Text(), primary_key=True),
    sa.Column("score", sa.SmallInteger(), nullable=False),
    sa.Column("assessed_at", sa.DateTime(timezone=True), nullable=False),
    sa.Column("assessed_by", sa.Text()),
)

# docs/application-business-value-assessment-spec.md: same shape as
# _health_assessment above, different dimension keys.
_business_value_assessment = sa.Table(
    "application_business_value_assessment",
    _metadata,
    sa.Column("application_id", sa.String(36), primary_key=True),
    sa.Column("dimension", sa.Text(), primary_key=True),
    sa.Column("score", sa.SmallInteger(), nullable=False),
    sa.Column("assessed_at", sa.DateTime(timezone=True), nullable=False),
    sa.Column("assessed_by", sa.Text()),
)

# APM US4: Total Cost of Ownership (1:1 with applications; cascade-deletes)
_cost_columns: list[sa.Column] = [
    sa.Column("app_id", sa.String(36), primary_key=True),
    sa.Column("currency", sa.CHAR(3), nullable=False, server_default="USD"),
    sa.Column("horizon_years", sa.SmallInteger(), nullable=False, server_default="5"),
]
for _bucket in TCO_BUCKET_NAMES:
    _cost_columns.append(
        sa.Column(f"{_bucket}_one_time", sa.Numeric(14, 2), nullable=False, server_default="0")
    )
    _cost_columns.append(
        sa.Column(f"{_bucket}_annual", sa.Numeric(14, 2), nullable=False, server_default="0")
    )
_cost_columns.append(sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False))

_application_cost = sa.Table("application_cost", _metadata, *_cost_columns)

# APM US6: transformation initiatives + application links (many-to-many)
_transformation_initiatives = sa.Table(
    "transformation_initiatives",
    _metadata,
    sa.Column("id", sa.String(36), primary_key=True),
    sa.Column("name", sa.String(255), nullable=False),
    sa.Column("description", sa.Text()),
    sa.Column("target_date", sa.Date()),
    sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
)

_app_initiative_links = sa.Table(
    "application_initiative_links",
    _metadata,
    sa.Column("app_id", sa.String(36), nullable=False),
    sa.Column("initiative_id", sa.String(36), nullable=False),
    sa.Column("planned_disposition", sa.Text(), nullable=False),
)

# APM US7: ownership & governance (1:1 with applications; cascade-deletes)
_application_contracts = sa.Table(
    "application_contracts",
    _metadata,
    sa.Column("app_id", sa.String(36), primary_key=True),
    sa.Column("contract_terms", sa.Text()),
    sa.Column("renewal_date", sa.Date()),
    sa.Column("sla", sa.Text()),
    sa.Column("business_sponsor", sa.String(255)),
    sa.Column("it_owner", sa.String(255)),
    sa.Column("decision_rights", sa.Text()),
    sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
)

# APM US8: quality & performance signals (1:1 with applications; cascade-deletes)
_application_quality_metrics = sa.Table(
    "application_quality_metrics",
    _metadata,
    sa.Column("app_id", sa.String(36), primary_key=True),
    sa.Column("uptime_pct", sa.Numeric(5, 2)),
    sa.Column("incidents_ytd", sa.Integer()),
    sa.Column("satisfaction_score", sa.SmallInteger()),
    sa.Column("perf_note", sa.Text()),
    sa.Column("ticket_volume_30d", sa.Integer()),
    sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
)
