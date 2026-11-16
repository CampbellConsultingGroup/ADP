#!/usr/bin/env python3
"""Seed ADP with a rich, retail-specific demo portfolio.

This performs a HARD WIPE of all application data (via TRUNCATE, which bypasses
the append-only triggers on ``audit_entries`` and ``llm_reasoning_log``) and then
reloads a coherent omnichannel-retailer dataset: business domains, a three-level
capability model, value streams with stages, a technical-capability taxonomy,
an application portfolio with TIME / 7-R / pace-layer classifications, several
C4 designs, and the full web of traceability links between them.

The generic engineering knowledge base (``knowledge_items`` /
``knowledge_relationships``, loaded by ``seed_knowledge.py``) is industry-agnostic
and is intentionally left untouched.

Usage:
    python scripts/seed_retail.py            # prompts before wiping
    python scripts/seed_retail.py --yes      # non-interactive (CI / re-seed)

Requires ADP_DATABASE_URL (or uses the default local URL). Re-runnable: each run
wipes and rebuilds from scratch.
"""

from __future__ import annotations

import argparse
import asyncio
import os
import sys
from datetime import date, datetime, timezone

from sqlalchemy import text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from adp.agentic import store as agstore
from adp.agentic.models import AgentCreate
from adp.application import store as astore
from adp.application.models import (
    ApplicationCapabilityLinkCreate,
    ApplicationCreate,
    ApplicationDesignLinkCreate,
    ApplicationDomainIntegrationCreate,
    ApplicationIntegrationCreate,
    ApplicationStageLinkCreate,
    ApplicationRiskUpdate,
    ApplicationTechCapLinkCreate,
    HealthAssessmentSubmit,
    TechnicalCapabilityCreate,
)
from adp.application import app_capabilities as acstore
from adp.organization import cap_mappings, regional
from adp.organization import store as ostore
from adp.organization.models import (
    AddMapping,
    OrgUnitCreate,
    SetRegionalAssessment,
    SetRegionScope,
)
from adp.application.app_capability_models import ApplicationCapabilityCreate
from adp.business import store as bstore
from adp.business.models import (
    BusinessCapabilityCreate,
    BusinessDomainCreate,
    CapabilityDomainAssign,
    StageCapabilityLinkCreate,
    ValueStreamCreate,
    ValueStreamStageCreate,
)
from adp.models import (
    SCHEMA_VERSION,
    ArchitectureDescription,
    AuditEntry,
    Element,
    ElementKind,
    LifecycleStatus,
    Relationship,
    Requirement,
)
from adp.store.store import DesignStore

DEFAULT_DB_URL = "postgresql+asyncpg://adp_user:adp_pass@127.0.0.1:5432/adp"

# Every application/business table. Order is irrelevant with CASCADE, but listing
# them all makes the wipe explicit. knowledge_* is deliberately excluded.
WIPE_TABLES = [
    # 936-pattern-conformance: adoptions reference domains and applications, so they go too
    # (re-run scripts/seed_patterns.py afterwards). Pattern families/versions are kept, like
    # the knowledge base.
    "ea_pattern_adoption_pin",
    "ea_pattern_adoption_member",
    "ea_pattern_adoption",
    # 933-agent-registry: agent memberships + agents (agents are not owned by applications,
    # so an applications TRUNCATE ... CASCADE alone would leave them behind).
    "solution_agents",
    "agents",
    # 940-org-units-geography: org units and their geography links. NEVER the geographies table
    # itself -- migration 048 seeds it, and nothing here can recreate it.
    # 942-regional-assessments: assessments and region-specific scope. NEVER geographies.
    "region_specific_capability_geographies",
    "region_specific_capabilities",
    "capability_regional_assessments",
    # 941-capability-org-mappings: owner / performer / contributor mappings (before org_units).
    "capability_org_mappings",
    "org_unit_geographies",
    "org_units",
    # 937-application-capabilities: the middle capability layer and its links.
    "app_capability_realizations",
    "app_capability_tech_cap_links",
    "business_capability_app_capability_links",
    "application_capabilities",
    "application_design_links",
    "application_integrations",
    "application_domain_integrations",
    "application_stage_links",
    "application_tech_cap_links",
    "application_capability_links",
    "technical_capabilities",
    "applications",
    "value_stream_stage_capabilities",
    "value_stream_design_links",
    "capability_design_links",
    "value_stream_stages",
    "value_streams",
    "business_capabilities",
    "business_domains",
    "element_technology_tags",
    "operations",
    "llm_reasoning_log",
    "audit_entries",
    "design_versions",
    "designs",
]

# ── Agentic solution (933-agent-registry, FR-017) ─────────────────────────────
# ADP itself, recorded as an agentic solution made of its own AI agents. prompt_ref values are the
# agent ids registered in adp.admin.prompt_registry (042 prompt management), where one exists.
ADP_SOLUTION = (
    "Architecture Design Platform (ADP)",
    "AI-assisted architecture design: intake, recommendation, validation and chat agents over "
    "a shared architecture model.",
)
# (name, role, autonomy, human_approval, framework, prompt_ref, description)
ADP_AGENTS = [
    ("ADP Chat Assistant", "orchestrator", 1, "on_write", "Anthropic SDK (tool use)",
     "chat_assistant", "Answers questions over the architecture estate with read-only tools."),
    ("ADP Intake Extractor", "worker", 0, "always", "Anthropic SDK",
     "intake_extraction", "Extracts requirements from business text; every proposal is "
     "confirmed by an architect."),
    ("ADP Recommendation Engine", "worker", 0, "always", "LangGraph",
     "recommendation_generation", "Generates and compares solution options grounded in the "
     "knowledge base."),
    ("ADP LLM-as-Judge Critics", "reviewer", 2, "on_irreversible", "asyncio fan-out",
     None, "Parallel critics that score a design; verdicts can be overridden by a reviewer."),
    ("ADP Agent Review", "worker", 0, "always", "Anthropic SDK",
     "agent_review_business_capability", "Reviews capabilities and suggests changes for "
     "architect confirmation."),
]

# ── Business domains ──────────────────────────────────────────────────────────
# (name, classification, org_unit, scope_statement, [risk_flags])
DOMAINS = [
    ("Merchandising & Product", "differentiating", "Merchandising",
     "Assortment, pricing, and product data that define what the retailer sells.",
     ["margin-sensitive"]),
    ("E-commerce & Digital", "differentiating", "Digital",
     "Online storefront, mobile app, and the digital customer experience.",
     ["peak-scalability"]),
    ("Store Operations", "strategic", "Retail Operations",
     "In-store selling, POS, and the physical store estate.",
     ["aging-pos", "pci-scope"]),
    ("Supply Chain & Fulfillment", "strategic", "Supply Chain",
     "Sourcing, inventory, warehousing, and last-mile delivery.",
     ["single-vendor-dependency"]),
    ("Marketing & Loyalty", "differentiating", "Marketing",
     "Campaigns, customer segmentation, and the loyalty programme.",
     ["consent-management"]),
    ("Customer Service", "commodity", "Customer Care",
     "Contact centre, case handling, and post-purchase support.",
     []),
    ("Finance & Accounting", "commodity", "Finance",
     "General ledger, accounts payable/receivable, and financial reporting.",
     ["sox-compliance"]),
    ("Human Resources", "commodity", "People",
     "Workforce management, payroll, and talent.",
     []),
    ("IT & Data", "strategic", "Technology",
     "Platforms, integration, and enterprise data & analytics.",
     ["legacy-mainframe", "data-residency"]),
]

# ── Business capability model (L1 → L2 → L3) ──────────────────────────────────
# Each L1: (name, domain_name, [L2...]); each L2: (name, [L3 names]).
CAPABILITIES = [
    ("Merchandising", "Merchandising & Product", [
        ("Assortment Planning", ["Category Management", "Range Planning"]),
        ("Pricing & Promotions", ["Markdown Optimization", "Promotion Management"]),
        ("Product Information Management", []),
    ]),
    ("Marketing & Loyalty", "Marketing & Loyalty", [
        ("Campaign Management", []),
        ("Loyalty & Rewards", []),
        ("Customer Segmentation", []),
    ]),
    ("Sales & Channels", "E-commerce & Digital", [
        ("E-commerce Storefront", ["Search & Browse", "Checkout"]),
        ("Point of Sale", []),
        ("Order Management", ["Order Orchestration", "Returns Management"]),
    ]),
    ("Supply Chain", "Supply Chain & Fulfillment", [
        ("Inventory Management", ["Demand Forecasting", "Replenishment"]),
        ("Warehouse Management", []),
        ("Transportation & Delivery", []),
    ]),
    ("Customer Engagement", "Customer Service", [
        ("Customer Service & Support", []),
        ("Contact Center", []),
    ]),
    ("Corporate Services", "Finance & Accounting", [
        ("Financial Management", []),
        # 942-regional-assessments: a Brazil-only statutory function, modelled once and flagged
        # region-specific rather than copied per country.
        ("Human Capital Management", ["Statutory eSocial Reporting"]),
        ("Enterprise Data & Analytics", []),
    ]),
    # 937-application-capabilities: the user's worked Store POS example (ADP-6et). Business L3s
    # are deliberately one function each, so each maps cleanly to one application capability.
    ("Sales & Customer Transactions", "Store Operations", [
        ("In-Store Transaction Management", [
            "Process Checkout", "Apply Promotions", "Accept Payment", "Process Returns",
            "Issue Receipts",
        ]),
    ]),
]

# ── Value streams (name, stakeholder, [stage names in order]) ─────────────────
VALUE_STREAMS = [
    ("Buy Online, Pick Up In Store", "Omnichannel Customer",
     ["Browse & Discover", "Add to Cart & Checkout", "Order Orchestration",
      "Store Fulfillment", "Customer Pickup"]),
    ("Order to Delivery (Home Delivery)", "E-commerce Customer",
     ["Browse", "Checkout", "Payment", "Warehouse Pick/Pack", "Ship", "Deliver"]),
    ("Concept to Shelf", "Merchandising Director",
     ["Range Planning", "Sourcing & Buying", "Pricing", "Allocation", "Availability"]),
    ("Return & Refund", "Customer",
     ["Initiate Return", "Return Logistics", "Inspection", "Refund", "Restock"]),
]

# ── Technical capability taxonomy (L1 → [L2...]) ──────────────────────────────
TECH_CAPS = [
    ("Integration & APIs", ["API Gateway", "Event Streaming", "Data Integration"]),
    ("Data & Analytics", ["Data Warehouse", "BI & Reporting", "ML & Recommendations"]),
    ("Commerce Services", ["Product Search", "Cart & Checkout", "Payment Processing"]),
    ("Platform & Infrastructure", ["Identity & Access", "Cloud Hosting", "Observability"]),
]

# ── Three-layer capability model: the Store POS example (937, ADP-6et) ────────
# Technical L1 -> L2 -> L3 (TECH_CAPS above stops at L2).
POS_TECH_CAPS = ("Integration & Data Services", [
    ("API Services", ["API Gateway Services", "Notification Messaging"]),
    ("Data Storage", ["Local Data Store with Offline Sync", "Distributed Caching"]),
    ("Security", ["Payment Tokenization (P2PE)"]),
])
# Application capability L1 -> L2 -> L3.
APP_CAPS = ("Transaction Processing", [
    ("Checkout", ["Basket Calculation", "Receipt Generation"]),
    ("Pricing", ["Price Rule Evaluation"]),
    ("Payments", ["Tender Authorization"]),
    ("Returns", ["Return Authorization"]),
    # Deliberately has no technical capability yet: demonstrates the governance warning.
    ("Loyalty", ["Loyalty Points Accrual"]),
])
# Leaf chains: business L3 -> application L3 -> [technical L3s]; Store POS realizes each.
CAPABILITY_CHAINS = [
    ("Process Checkout", "Basket Calculation", ["Local Data Store with Offline Sync"]),
    ("Apply Promotions", "Price Rule Evaluation", ["Distributed Caching"]),
    ("Accept Payment", "Tender Authorization",
     ["Payment Tokenization (P2PE)", "API Gateway Services"]),
    ("Process Returns", "Return Authorization", ["API Gateway Services"]),
    ("Issue Receipts", "Receipt Generation", ["Notification Messaging"]),
    (None, "Loyalty Points Accrual", []),
]
# 938-capability-model-analysis (ADP-6et.2): demo data for the analysis views.
# Impact / exposure: offline sync is being retired, so Process Checkout is exposed.
TECH_CAP_LIFECYCLE = {
    "Local Data Store with Offline Sync": ("retiring", date(2027, 6, 30)),
}
# 940-org-units-geography: the org tree (name, parent name), where units operate (seeded
# geography ids from migration 048), and free-text business units left for the review queue.
ORG_UNITS = [
    ("Retail Co", None),
    ("Stores", "Retail Co"),
    ("Digital", "Retail Co"),
    ("Supply Chain", "Retail Co"),
    ("Corporate", "Retail Co"),
    ("Finance", "Corporate"),
    ("HR", "Corporate"),
]
ORG_UNIT_GEOGRAPHIES = {
    "Stores": ["geo-US", "geo-CA", "geo-DE"],
    "Digital": ["geo-US", "geo-GB"],
}
APP_BUSINESS_UNITS = {
    "pos": "Store Systems",
    "loyalty": "Store Systems",
    "pay": "Store systems",  # near-duplicate on purpose: a person decides, nothing is merged
    "commerce": "Digital",
    "cms": "Digital",
    "erp": "Finance",
    "workday": "HR",
    "wms": "Supply Chain",
}
# 941-capability-org-mappings: owners (capability -> org unit), performers (L3, org unit,
# geography or None) and contributors. Chosen so each Business -> Organization -> Findings list
# has an entry: Merchandising and its L2s have no owner; Accept Payment and Apply Promotions are
# shared-service candidates (Stores and Digital); Demand Forecasting is owned (via Supply Chain)
# but has no performer; Category Management and Range Planning are unmapped; Markdown
# Optimization is performed by Stores in the UK, outside where Stores operates.
CAPABILITY_OWNERS = {
    "Sales & Channels": "Digital",
    "Supply Chain": "Supply Chain",
    "Corporate Services": "Corporate",
    "Financial Management": "Finance",
    "Human Capital Management": "HR",
    "In-Store Transaction Management": "Stores",
}
CAPABILITY_PERFORMERS = [
    ("Accept Payment", "Stores", "geo-US"),
    ("Accept Payment", "Stores", "geo-DE"),
    ("Accept Payment", "Digital", None),
    ("Apply Promotions", "Stores", None),
    ("Apply Promotions", "Digital", None),
    ("Process Checkout", "Stores", None),
    ("Process Returns", "Stores", None),
    ("Checkout", "Digital", None),
    ("Search & Browse", "Digital", None),
    ("Replenishment", "Supply Chain", None),
    ("Markdown Optimization", "Stores", "geo-GB"),
]
CAPABILITY_CONTRIBUTORS = [("Accept Payment", "Finance"), ("Replenishment", "Stores")]

# 942-regional-assessments: per-region maturity (capability, geography, score, note). The
# capabilities' own maturity_level stays the enterprise baseline. Europe (geo-m49-150) and the
# Americas (geo-m49-019) plus two countries, so the regional heat map shows real differences.
REGIONAL_ASSESSMENTS = [
    ("Accept Payment", "geo-m49-150", 4, None),
    ("Accept Payment", "geo-m49-019", 3, None),
    ("Accept Payment", "geo-BR", 2, "Pix and boleto handled by a separate local acquirer"),
    ("Replenishment", "geo-m49-150", 3, None),
    ("Replenishment", "geo-m49-019", 4, None),
    ("Replenishment", "geo-DE", 5, None),
    ("Financial Management", "geo-m49-150", 4, "IFRS group consolidation runs in Dublin"),
    ("Financial Management", "geo-m49-019", 2, None),
    ("Human Capital Management", "geo-BR", 2, None),
    ("Statutory eSocial Reporting", "geo-BR", 2, "eSocial events are still filed manually"),
]
REGION_SPECIFIC = {"Statutory eSocial Reporting": ["geo-BR"]}

# Overlap: e-commerce has its own promotions capability, so two applications realize
# "Apply Promotions" -- a rationalization candidate. (L2 parent, L3 name, business L3, tech, app key)
OVERLAP_APP_CAPS = [
    ("Pricing", "Online Promotion Evaluation", "Apply Promotions", "API Gateway Services", "commerce"),
]

# ── Application portfolio ─────────────────────────────────────────────────────
# key: (name, vendor, owner, time, r_strategy, pace_layer, health, description)
APPS = {
    "erp": ("SAP S/4HANA", "SAP", "Finance IT", "Invest", "Retain", "Record", 4,
            "Core ERP: finance, procurement, and master data."),
    "commerce": ("Salesforce Commerce Cloud", "Salesforce", "Digital Commerce",
                 "Invest", "Retain", "Differentiation", 4,
                 "Headless e-commerce storefront and cart."),
    "oms": ("Manhattan Active OMS", "Manhattan Associates", "Fulfillment IT",
            "Invest", "Retain", "Differentiation", 4,
            "Distributed order management and fulfillment orchestration."),
    "wms": ("Blue Yonder WMS", "Blue Yonder", "Supply Chain IT",
            "Tolerate", "Retain", "Record", 3, "Warehouse management system."),
    "demand": ("Blue Yonder Demand Planning", "Blue Yonder", "Supply Chain IT",
               "Tolerate", "Replatform", "Differentiation", 3,
               "Demand forecasting and replenishment planning."),
    "pos": ("Oracle Retail Xstore POS", "Oracle", "Store Systems",
            "Migrate", "Repurchase", "Record", 2,
            "In-store point of sale — aging, slated for replacement."),
    "pim": ("Akeneo PIM", "Akeneo", "Merchandising IT", "Invest", "Retain", "Record", 4,
            "Product information management and enrichment."),
    "pay": ("Adyen Payments", "Adyen", "Payments", "Invest", "Retain", "Record", 5,
            "Unified payment gateway across web and store."),
    "cms": ("Adobe Experience Manager", "Adobe", "Digital Marketing",
            "Tolerate", "Retain", "Differentiation", 3, "Web content management."),
    "mktg": ("Salesforce Marketing Cloud", "Salesforce", "Marketing",
             "Tolerate", "Retain", "Differentiation", 3,
             "Email, journeys, and campaign orchestration."),
    "loyalty": ("Annex Cloud Loyalty", "Annex Cloud", "Loyalty",
                "Invest", "Repurchase", "Innovation", 3, "Loyalty and rewards platform."),
    "cdp": ("Segment CDP", "Twilio Segment", "Data & Personalization",
            "Invest", "Retain", "Innovation", 4, "Customer data platform."),
    "search": ("Algolia Search", "Algolia", "Digital Commerce",
               "Invest", "Retain", "Innovation", 4, "Product search and discovery."),
    "zendesk": ("Zendesk", "Zendesk", "Customer Care", "Tolerate", "Retain", "Record", 4,
                "Customer service ticketing and support."),
    "snowflake": ("Snowflake Data Cloud", "Snowflake", "Data Platform",
                  "Invest", "Retain", "Differentiation", 5,
                  "Enterprise data warehouse and analytics."),
    "tableau": ("Tableau", "Salesforce", "Analytics", "Tolerate", "Retain", "Record", 3,
                "Business intelligence and dashboards."),
    "workday": ("Workday HCM", "Workday", "HR IT", "Invest", "Retain", "Record", 4,
                "Human capital management and payroll."),
    "legacy_inv": ("Legacy Inventory Mainframe", "In-house", "Store Systems",
                   "Eliminate", "Retire", "Record", 1,
                   "COBOL inventory system — end of life, being decommissioned."),
    # 936-pattern-conformance: the governed event backbone the EA pattern demos pin as
    # "backbone" (scripts/seed_patterns.py). Deliberately linked to no business capability.
    "hub": ("Enterprise Event Hub", "Confluent", "Integration Platform",
            "Invest", "Retain", "Record", 4,
            "Governed event backbone: domains publish and subscribe here instead of "
            "integrating directly."),
}

# 936: extra application attributes (keys of APPS) the pattern demos select on.
APP_EXTRA = {
    "hub": {"application_type": "cots", "architecture_pattern": "event-backbone"},
}

# ── C4 designs (compact spec, expanded into ArchitectureDescription) ──────────
# reqs: (id, title, description); elements: (id, name, kind, desc, [satisfies]);
# rels: (id, source, target, label); audits: (id, actor, action, entity, summary, origin)
DESIGNS = [
    {
        "id": "DSN-CHECKOUT", "title": "Omnichannel Checkout Platform",
        "desc": "Unified checkout serving web, mobile, and store.",
        "lifecycle": LifecycleStatus.CURRENT,
        "reqs": [
            ("REQ-001", "Unified checkout", "One checkout across web, mobile, and store."),
            ("REQ-002", "PCI-compliant payments", "Card data never touches retailer systems."),
        ],
        "elements": [
            ("ELM-001", "Customer", ElementKind.PERSON, "A shopper checking out.", []),
            ("ELM-002", "Commerce Storefront", ElementKind.SYSTEM, "Customer-facing store.", []),
            ("ELM-003", "Checkout API", ElementKind.CONTAINER, "Runs checkout.", ["REQ-001"]),
            ("ELM-004", "Cart Service", ElementKind.CONTAINER, "Holds cart state.", []),
            ("ELM-005", "Payment Gateway", ElementKind.SYSTEM, "Tokenized payments.", ["REQ-002"]),
            ("ELM-006", "Order Management System", ElementKind.SYSTEM, "Downstream orders.", []),
        ],
        "rels": [
            ("REL-001", "ELM-001", "ELM-002", "Browses & checks out"),
            ("REL-002", "ELM-002", "ELM-003", "Submits order"),
            ("REL-003", "ELM-003", "ELM-004", "Reads cart"),
            ("REL-004", "ELM-003", "ELM-005", "Authorizes payment"),
            ("REL-005", "ELM-003", "ELM-006", "Creates order"),
        ],
        "audits": [
            ("AUD-001", "j.muir", "create", "DSN-CHECKOUT", "Initial checkout design.", "human"),
        ],
    },
    {
        "id": "DSN-OMS", "title": "Order Management & Fulfillment",
        "desc": "Orchestrates fulfillment across DCs and stores.",
        "lifecycle": LifecycleStatus.CURRENT,
        "reqs": [
            ("REQ-001", "Optimal sourcing", "Route each order to the best node."),
        ],
        "elements": [
            ("ELM-001", "Order Management System", ElementKind.SYSTEM, "Router.", ["REQ-001"]),
            ("ELM-002", "Warehouse Management System", ElementKind.SYSTEM, "DC fulfillment.", []),
            ("ELM-003", "Store Fulfillment App", ElementKind.CONTAINER, "Ship-from-store.", []),
            ("ELM-004", "Inventory Service", ElementKind.CONTAINER, "Availability lookup.", []),
            ("ELM-005", "Carrier Integration", ElementKind.CONTAINER, "Books shipments.", []),
        ],
        "rels": [
            ("REL-001", "ELM-001", "ELM-004", "Checks availability"),
            ("REL-002", "ELM-001", "ELM-002", "Routes to DC"),
            ("REL-003", "ELM-001", "ELM-003", "Routes to store"),
            ("REL-004", "ELM-002", "ELM-005", "Books shipment"),
        ],
        "audits": [
            ("AUD-002", "j.muir", "create", "DSN-OMS", "Fulfillment design.", "human"),
        ],
    },
    {
        "id": "DSN-INVENTORY", "title": "Inventory & Replenishment Platform",
        "desc": "Real-time inventory and automated replenishment.",
        "lifecycle": LifecycleStatus.PROPOSED,
        "reqs": [
            ("REQ-001", "Real-time visibility", "Single view of stock across channels."),
            ("REQ-002", "Automated replenishment", "Forecast-driven purchase orders."),
        ],
        "elements": [
            ("ELM-001", "Demand Forecasting Engine", ElementKind.SYSTEM, "Forecasts.", ["REQ-002"]),
            ("ELM-002", "Inventory Ledger", ElementKind.CONTAINER, "Real-time stock.", ["REQ-001"]),
            ("ELM-003", "Replenishment Service", ElementKind.CONTAINER, "Raises POs.", ["REQ-002"]),
            ("ELM-004", "ERP", ElementKind.SYSTEM, "Procurement & finance.", []),
            ("ELM-005", "Data Platform", ElementKind.SYSTEM, "History & events.", []),
        ],
        "rels": [
            ("REL-001", "ELM-002", "ELM-005", "Streams stock events"),
            ("REL-002", "ELM-001", "ELM-005", "Reads sales history"),
            ("REL-003", "ELM-001", "ELM-003", "Feeds forecast"),
            ("REL-004", "ELM-003", "ELM-004", "Raises purchase orders"),
        ],
        "audits": [
            ("AUD-003", "s.chen", "create", "DSN-INVENTORY", "Replenishment proposal.", "human"),
        ],
    },
    {
        "id": "DSN-LOYALTY", "title": "Customer Loyalty Service",
        "desc": "Unified points and rewards across channels.",
        "lifecycle": LifecycleStatus.DRAFT,
        "reqs": [
            ("REQ-001", "Unified points", "One balance across web and store."),
        ],
        "elements": [
            ("ELM-001", "Customer", ElementKind.PERSON, "A loyalty member.", []),
            ("ELM-002", "Loyalty Platform", ElementKind.SYSTEM, "Points engine.", ["REQ-001"]),
            ("ELM-003", "Points Ledger", ElementKind.CONTAINER, "Transaction record.", []),
            ("ELM-004", "Customer Data Platform", ElementKind.SYSTEM, "Unified profile.", []),
            ("ELM-005", "Marketing Cloud", ElementKind.SYSTEM, "Segmented campaigns.", []),
        ],
        "rels": [
            ("REL-001", "ELM-001", "ELM-002", "Earns & redeems points"),
            ("REL-002", "ELM-002", "ELM-003", "Records transactions"),
            ("REL-003", "ELM-002", "ELM-004", "Publishes profile events"),
            ("REL-004", "ELM-005", "ELM-004", "Reads segments"),
        ],
        "audits": [],
    },
    {
        "id": "DSN-POS", "title": "Store POS Modernization",
        "desc": "Cloud-native POS replacing legacy Xstore.",
        "lifecycle": LifecycleStatus.PROPOSED,
        "reqs": [
            ("REQ-001", "Cloud-native POS", "Replace on-prem Xstore with a cloud POS."),
            ("REQ-002", "Offline-capable", "Transactions continue during network loss."),
        ],
        "elements": [
            ("ELM-001", "Store Associate", ElementKind.PERSON, "Operates the till.", []),
            ("ELM-002", "New POS App", ElementKind.CONTAINER, "Cloud POS.", ["REQ-001", "REQ-002"]),
            ("ELM-003", "Legacy Xstore POS", ElementKind.SYSTEM, "System being retired.", []),
            ("ELM-004", "Payment Gateway", ElementKind.SYSTEM, "Card capture.", []),
            ("ELM-005", "Order Management System", ElementKind.SYSTEM, "Posts transactions.", []),
        ],
        "rels": [
            ("REL-001", "ELM-001", "ELM-002", "Processes sale"),
            ("REL-002", "ELM-002", "ELM-004", "Captures payment"),
            ("REL-003", "ELM-002", "ELM-005", "Posts transaction"),
            ("REL-004", "ELM-002", "ELM-003", "Migrates from"),
        ],
        "audits": [
            ("AUD-004", "s.chen", "create", "DSN-POS", "POS modernization proposal.", "human"),
        ],
    },
]

# ── Traceability links (all keyed by human-readable names) ────────────────────

# app_key -> [(business capability name, fit_score 1-5)]
APP_CAP_LINKS = {
    "commerce": [("E-commerce Storefront", 5), ("Checkout", 4)],
    "pos": [("Point of Sale", 2)],
    "oms": [("Order Orchestration", 5), ("Returns Management", 4)],
    "wms": [("Warehouse Management", 4)],
    "demand": [("Demand Forecasting", 4), ("Replenishment", 3)],
    "pim": [("Product Information Management", 5)],
    "pay": [("Checkout", 4)],
    "loyalty": [("Loyalty & Rewards", 4)],
    "mktg": [("Campaign Management", 4)],
    "cdp": [("Customer Segmentation", 4)],
    "erp": [("Financial Management", 4)],
    "workday": [("Human Capital Management", 5)],
    "zendesk": [("Customer Service & Support", 4)],
    "snowflake": [("Enterprise Data & Analytics", 5)],
    "search": [("Search & Browse", 5)],
}

# app_key -> [(technical capability name, "provides"|"consumes")]
APP_TECH_LINKS = {
    "pay": [("Payment Processing", "provides")],
    "search": [("Product Search", "provides")],
    "snowflake": [("Data Warehouse", "provides")],
    "tableau": [("BI & Reporting", "provides"), ("Data Warehouse", "consumes")],
    "commerce": [("Cart & Checkout", "provides"), ("Payment Processing", "consumes"),
                 ("Product Search", "consumes")],
    "cdp": [("ML & Recommendations", "consumes"), ("Event Streaming", "provides")],
    "oms": [("API Gateway", "consumes")],
    "hub": [("Event Streaming", "provides")],
}

# app_key -> [(value stream name, stage name)]
APP_STAGE_LINKS = {
    "commerce": [("Buy Online, Pick Up In Store", "Browse & Discover"),
                 ("Buy Online, Pick Up In Store", "Add to Cart & Checkout"),
                 ("Order to Delivery (Home Delivery)", "Browse"),
                 ("Order to Delivery (Home Delivery)", "Checkout")],
    "oms": [("Buy Online, Pick Up In Store", "Order Orchestration"),
            ("Order to Delivery (Home Delivery)", "Warehouse Pick/Pack")],
    "pos": [("Buy Online, Pick Up In Store", "Customer Pickup")],
    "wms": [("Order to Delivery (Home Delivery)", "Warehouse Pick/Pack")],
    "pay": [("Order to Delivery (Home Delivery)", "Payment")],
}

# app_key -> [(domain name, integration_type, direction)]
APP_DOMAIN_LINKS = {
    "commerce": [("E-commerce & Digital", "API", "bidirectional")],
    "oms": [("Supply Chain & Fulfillment", "API", "inbound")],
    "erp": [("Finance & Accounting", "API", "bidirectional")],
    "workday": [("Human Resources", "API", "bidirectional")],
    "mktg": [("Marketing & Loyalty", "event", "outbound")],
    "zendesk": [("Customer Service", "API", "inbound")],
    "snowflake": [("IT & Data", "database", "inbound")],
    "pos": [("Store Operations", "file", "outbound")],
}

# (source app_key, target app_key, integration_type, description)
APP_INTEGRATIONS = [
    ("commerce", "oms", "API", "Order handoff at checkout"),
    ("oms", "wms", "API", "Fulfillment dispatch to DC"),
    ("oms", "erp", "API", "Financial posting of shipments"),
    ("pos", "pay", "API", "In-store card authorization"),
    ("commerce", "pay", "API", "Online payment authorization"),
    ("loyalty", "mktg", "event", "Loyalty events for campaigns"),
    ("erp", "snowflake", "database", "Nightly finance extract"),
    ("commerce", "snowflake", "event", "Clickstream ingestion"),
    ("oms", "snowflake", "database", "Order facts for analytics"),
    ("pim", "search", "API", "Product catalog index feed"),
    ("commerce", "search", "API", "Search & browse queries"),
    ("legacy_inv", "oms", "file", "Legacy nightly stock file"),
    # 936: hub-routed event flows. Marketing & Loyalty is fully routed through the hub (it
    # conforms to the Domain Event Backbone pattern); E-commerce & Digital is only partly routed,
    # and keeps direct cross-domain integrations above (it does not conform).
    ("loyalty", "hub", "event", "Loyalty events published to the backbone"),
    ("hub", "loyalty", "event", "Customer events delivered to loyalty"),
    ("mktg", "hub", "event", "Campaign responses published to the backbone"),
    ("hub", "mktg", "event", "Audience events delivered to marketing"),
    ("cdp", "hub", "event", "Profile updates published to the backbone"),
    ("hub", "cdp", "event", "Behavioural events delivered to the CDP"),
    ("commerce", "hub", "event", "Order placed events"),
    ("hub", "commerce", "event", "Inventory and price change events"),
    ("oms", "hub", "event", "Fulfilment status events"),
    ("hub", "oms", "event", "Order placed events delivered to fulfilment"),
]

# app_key -> [design id]
APP_DESIGN_LINKS = {
    "commerce": ["DSN-CHECKOUT"],
    "oms": ["DSN-CHECKOUT", "DSN-OMS", "DSN-POS"],
    "wms": ["DSN-OMS"],
    "demand": ["DSN-INVENTORY"],
    "erp": ["DSN-INVENTORY"],
    "loyalty": ["DSN-LOYALTY"],
    "mktg": ["DSN-LOYALTY"],
    "pos": ["DSN-POS"],
    "pay": ["DSN-CHECKOUT", "DSN-POS"],
    "snowflake": ["DSN-INVENTORY"],
}

# business capability name -> [design id]
CAP_DESIGN_LINKS = {
    "Checkout": ["DSN-CHECKOUT"],
    "E-commerce Storefront": ["DSN-CHECKOUT"],
    "Order Orchestration": ["DSN-OMS"],
    "Order Management": ["DSN-OMS"],
    "Replenishment": ["DSN-INVENTORY"],
    "Demand Forecasting": ["DSN-INVENTORY"],
    "Loyalty & Rewards": ["DSN-LOYALTY"],
    "Point of Sale": ["DSN-POS"],
}

# value stream name -> [design id]
VS_DESIGN_LINKS = {
    "Order to Delivery (Home Delivery)": ["DSN-CHECKOUT", "DSN-OMS"],
    "Buy Online, Pick Up In Store": ["DSN-CHECKOUT", "DSN-POS"],
    "Concept to Shelf": ["DSN-INVENTORY"],
    "Return & Refund": ["DSN-OMS"],
}

# (value stream name, stage name) -> capability name
STAGE_CAP_LINKS = [
    ("Buy Online, Pick Up In Store", "Browse & Discover", "Search & Browse"),
    ("Buy Online, Pick Up In Store", "Add to Cart & Checkout", "Checkout"),
    ("Buy Online, Pick Up In Store", "Order Orchestration", "Order Orchestration"),
    ("Buy Online, Pick Up In Store", "Store Fulfillment", "Point of Sale"),
    ("Order to Delivery (Home Delivery)", "Warehouse Pick/Pack", "Warehouse Management"),
    ("Order to Delivery (Home Delivery)", "Payment", "Checkout"),
    ("Concept to Shelf", "Range Planning", "Range Planning"),
    ("Concept to Shelf", "Pricing", "Promotion Management"),
    ("Return & Refund", "Restock", "Returns Management"),
]


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _build_description(spec: dict) -> ArchitectureDescription:
    now = _now()
    lifecycle: LifecycleStatus = spec["lifecycle"]
    return ArchitectureDescription(
        schema_version=SCHEMA_VERSION,
        id=spec["id"],
        title=spec["title"],
        description=spec["desc"],
        requirements=[
            Requirement(id=r[0], title=r[1], description=r[2]) for r in spec["reqs"]
        ],
        elements=[
            Element(id=e[0], name=e[1], kind=e[2], description=e[3], satisfies=list(e[4]))
            for e in spec["elements"]
        ],
        relationships=[
            Relationship(id=r[0], source=r[1], target=r[2], label=r[3]) for r in spec["rels"]
        ],
        audit_log=[
            AuditEntry(id=a[0], actor=a[1], action=a[2], affected_entity=a[3],
                       summary=a[4], timestamp=now, origin=a[5])
            for a in spec["audits"]
        ],
        created_at=now,
        updated_at=now,
        lifecycle_status=lifecycle,
        proposed_date=now if lifecycle == LifecycleStatus.PROPOSED else None,
        current_since=now if lifecycle == LifecycleStatus.CURRENT else None,
    )


async def wipe(engine) -> None:
    stmt = f"TRUNCATE TABLE {', '.join(WIPE_TABLES)} RESTART IDENTITY CASCADE"
    async with engine.begin() as conn:
        await conn.execute(text(stmt))
    print(f"  wiped {len(WIPE_TABLES)} tables (knowledge base preserved)")


async def seed(db_url: str) -> None:
    engine = create_async_engine(db_url, echo=False)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)

    print("Wiping existing data...")
    await wipe(engine)

    domain_ids: dict[str, str] = {}
    cap_ids: dict[str, str] = {}
    vs_ids: dict[str, str] = {}
    stage_ids: dict[tuple[str, str], str] = {}
    tech_ids: dict[str, str] = {}
    app_ids: dict[str, str] = {}

    # ── Phase A: domains, capabilities, value streams, tech caps, apps ────────
    print("Seeding business & application entities...")
    async with session_factory() as session:
        for name, cls, org, scope, flags in DOMAINS:
            d = await bstore.create_domain(
                BusinessDomainCreate(name=name, classification=cls, org_unit=org,
                                     scope_statement=scope, risk_flags=flags),
                session,
            )
            domain_ids[name] = d.id
        print(f"  {len(domain_ids)} domains")

        cap_count = 0
        for l1_name, domain_name, l2_list in CAPABILITIES:
            l1 = await bstore.create_capability(
                BusinessCapabilityCreate(name=l1_name, level=1), session)
            cap_ids[l1_name] = l1.id
            cap_count += 1
            await bstore.assign_capability_domain(
                l1.id, CapabilityDomainAssign(domain_id=domain_ids[domain_name]), session)
            for l2_name, l3_list in l2_list:
                l2 = await bstore.create_capability(
                    BusinessCapabilityCreate(name=l2_name, level=2, parent_id=l1.id), session)
                cap_ids[l2_name] = l2.id
                cap_count += 1
                for l3_name in l3_list:
                    l3 = await bstore.create_capability(
                        BusinessCapabilityCreate(name=l3_name, level=3, parent_id=l2.id), session)
                    cap_ids[l3_name] = l3.id
                    cap_count += 1
        print(f"  {cap_count} capabilities (L1-L3)")

        for vs_name, stakeholder, stages in VALUE_STREAMS:
            vs = await bstore.create_value_stream(
                ValueStreamCreate(name=vs_name, stakeholder=stakeholder), session)
            vs_ids[vs_name] = vs.id
            for pos, stage_name in enumerate(stages):
                st = await bstore.add_stage(
                    vs.id, ValueStreamStageCreate(name=stage_name, position=pos), session)
                stage_ids[(vs_name, stage_name)] = st.id
        print(f"  {len(vs_ids)} value streams, {len(stage_ids)} stages")

        for l1_name, l2_names in TECH_CAPS:
            t1 = await astore.create_technical_capability(
                TechnicalCapabilityCreate(name=l1_name), session)
            tech_ids[l1_name] = t1.id
            for l2_name in l2_names:
                t2 = await astore.create_technical_capability(
                    TechnicalCapabilityCreate(name=l2_name, parent_id=t1.id), session)
                tech_ids[l2_name] = t2.id
        print(f"  {len(tech_ids)} technical capabilities")

        for key, (name, vendor, owner, tc, r, pace, health, desc) in APPS.items():
            app = await astore.create_application(
                ApplicationCreate(name=name, vendor=vendor, primary_owner=owner,
                                  time_classification=tc, r_strategy=r, pace_layer=pace,
                                  description=desc, **APP_EXTRA.get(key, {})),
                session,
            )
            # health_score is not a create field: it is derived (the minimum) from the six-
            # dimension health assessment, so record every dimension at the seeded score.
            await astore.upsert_health_assessment(
                app.id,
                HealthAssessmentSubmit(
                    stability_incidents=health, technical_currency_debt=health,
                    security_posture=health, support_team_capacity=health,
                    documentation_knowledge=health, business_value_criticality=health,
                ),
                "seed", session,
            )
            app_ids[key] = app.id
        print(f"  {len(app_ids)} applications")

        await session.commit()

    # ── Phase B: designs (DesignStore manages its own transaction) ────────────
    print("Seeding C4 designs...")
    store = DesignStore(db_url)
    try:
        for spec in DESIGNS:
            desc = _build_description(spec)
            await store.save(desc, actor="seed_retail")
            print(f"  {spec['id']}  {spec['title']} ({spec['lifecycle'].value})")
    finally:
        await store._engine.dispose()

    # ── Phase C: traceability links ───────────────────────────────────────────
    print("Seeding traceability links...")
    async with session_factory() as session:
        n = 0
        for vs_name, stage_name, cap_name in STAGE_CAP_LINKS:
            await bstore.link_cap_to_stage(
                vs_ids[vs_name], stage_ids[(vs_name, stage_name)],
                StageCapabilityLinkCreate(capability_id=cap_ids[cap_name]), session)
            n += 1
        print(f"  {n} stage-capability links")

        n = 0
        for key, links in APP_CAP_LINKS.items():
            for cap_name, fit in links:
                await astore.create_app_capability_link(
                    app_ids[key],
                    ApplicationCapabilityLinkCreate(capability_id=cap_ids[cap_name], fit_score=fit),
                    session)
                n += 1
        print(f"  {n} app-capability links")

        n = 0
        for key, links in APP_TECH_LINKS.items():
            for tech_name, usage in links:
                await astore.create_app_tech_cap_link(
                    app_ids[key],
                    ApplicationTechCapLinkCreate(tech_cap_id=tech_ids[tech_name], usage_type=usage),
                    session)
                n += 1
        print(f"  {n} app-tech-capability links")

        n = 0
        for key, links in APP_STAGE_LINKS.items():
            for vs_name, stage_name in links:
                await astore.create_app_stage_link(
                    app_ids[key],
                    ApplicationStageLinkCreate(stage_id=stage_ids[(vs_name, stage_name)]),
                    session)
                n += 1
        print(f"  {n} app-stage links")

        n = 0
        for key, links in APP_DOMAIN_LINKS.items():
            for domain_name, itype, direction in links:
                await astore.create_app_domain_integration(
                    app_ids[key],
                    ApplicationDomainIntegrationCreate(
                        domain_id=domain_ids[domain_name], integration_type=itype,
                        direction=direction),
                    session)
                n += 1
        print(f"  {n} app-domain integrations")

        for src, tgt, itype, description in APP_INTEGRATIONS:
            await astore.create_integration(
                ApplicationIntegrationCreate(
                    source_app_id=app_ids[src], target_app_id=app_ids[tgt],
                    integration_type=itype, description=description),
                session)
        print(f"  {len(APP_INTEGRATIONS)} app-to-app integrations")

        n = 0
        for key, design_list in APP_DESIGN_LINKS.items():
            for design_id in design_list:
                await astore.create_app_design_link(
                    app_ids[key], ApplicationDesignLinkCreate(design_id=design_id), session)
                n += 1
        print(f"  {n} app-design links")

        n = 0
        for cap_name, design_list in CAP_DESIGN_LINKS.items():
            for design_id in design_list:
                await bstore.link_design_to_capability(cap_ids[cap_name], design_id, session)
                n += 1
        print(f"  {n} capability-design links")

        n = 0
        for vs_name, design_list in VS_DESIGN_LINKS.items():
            for design_id in design_list:
                await bstore.link_design_to_value_stream(vs_ids[vs_name], design_id, session)
                n += 1
        print(f"  {n} value-stream-design links")

        await session.commit()

    # ── Phase C2: application capabilities, the Store POS example (937) ───────
    print("Seeding the three-layer capability model (Store POS)...")
    async with session_factory() as session:
        t1_name, t2_list = POS_TECH_CAPS
        t1 = await astore.create_technical_capability(
            TechnicalCapabilityCreate(name=t1_name), session)
        tech_ids[t1_name] = t1.id
        for t2_name, t3_names in t2_list:
            t2 = await astore.create_technical_capability(
                TechnicalCapabilityCreate(name=t2_name, parent_id=t1.id), session)
            tech_ids[t2_name] = t2.id
            for t3_name in t3_names:
                status, eol = TECH_CAP_LIFECYCLE.get(t3_name, ("current", None))
                t3 = await astore.create_technical_capability(
                    TechnicalCapabilityCreate(name=t3_name, parent_id=t2.id,
                                              lifecycle_status=status, end_of_life_date=eol),
                    session)
                tech_ids[t3_name] = t3.id

        app_cap_ids: dict[str, str] = {}
        a2_ids: dict[str, str] = {}
        a1_name, a2_list = APP_CAPS
        a1 = await acstore.create_app_capability(ApplicationCapabilityCreate(name=a1_name), session)
        for a2_name, a3_names in a2_list:
            a2 = await acstore.create_app_capability(
                ApplicationCapabilityCreate(name=a2_name, parent_id=a1.id), session)
            a2_ids[a2_name] = a2.id
            for a3_name in a3_names:
                a3 = await acstore.create_app_capability(
                    ApplicationCapabilityCreate(name=a3_name, parent_id=a2.id), session)
                app_cap_ids[a3_name] = a3.id

        for biz_name, app_cap_name, tech_names in CAPABILITY_CHAINS:
            ac_id = app_cap_ids[app_cap_name]
            if biz_name is not None:
                await acstore.add_business_link(ac_id, cap_ids[biz_name], session)
            for tech_name in tech_names:
                await acstore.add_tech_link(ac_id, tech_ids[tech_name], session)
            await acstore.add_realization(ac_id, app_ids["pos"], session)
        for a2_name, a3_name, biz_name, tech_name, app_key in OVERLAP_APP_CAPS:
            a3 = await acstore.create_app_capability(
                ApplicationCapabilityCreate(name=a3_name, parent_id=a2_ids[a2_name]), session)
            app_cap_ids[a3_name] = a3.id
            await acstore.add_business_link(a3.id, cap_ids[biz_name], session)
            await acstore.add_tech_link(a3.id, tech_ids[tech_name], session)
            await acstore.add_realization(a3.id, app_ids[app_key], session)
        # Risk roll-up demo: the aging POS has a weak security posture.
        await astore.upsert_application_risk(
            app_ids["pos"], ApplicationRiskUpdate(security_posture="weak"), session)
        await session.commit()
        print(f"  {len(app_cap_ids)} application capability L3s, "
              f"{len(CAPABILITY_CHAINS) - 1} business -> application -> technical chains, "
              f"{len(OVERLAP_APP_CAPS)} overlap")

    # ── Phase C3: org units + operating geographies (940-org-units-geography) ──
    # Free-text owning_business_unit values are set but NOT linked, so the review queue
    # (Business -> Organization -> Unmatched) has something to resolve -- including a
    # near-duplicate ("Store systems") that must be decided by a person, not merged.
    print("Seeding org units...")
    async with session_factory() as session:
        org_ids: dict[str, str] = {}
        for name, parent in ORG_UNITS:
            ou = await ostore.create_org_unit(
                OrgUnitCreate(name=name, parent_id=org_ids[parent] if parent else None), session)
            org_ids[name] = ou.id
        for name, geo_ids in ORG_UNIT_GEOGRAPHIES.items():
            for geo_id in geo_ids:
                await ostore.link_geography(org_ids[name], geo_id, session)
        for app_key, bu in APP_BUSINESS_UNITS.items():
            await session.execute(
                ostore._applications.update()
                .where(ostore._applications.c.id == app_ids[app_key])
                .values(owning_business_unit=bu)
            )
        await session.commit()
        print(f"  {len(org_ids)} org units, {len(APP_BUSINESS_UNITS)} unmatched business-unit values")

    # ── Phase C4: capability <-> org unit mappings (941-capability-org-mappings) ──
    print("Seeding capability org mappings...")
    async with session_factory() as session:
        for cap_name, ou_name in CAPABILITY_OWNERS.items():
            await cap_mappings.set_owner(cap_ids[cap_name], org_ids[ou_name], session)
        for cap_name, ou_name, geo_id in CAPABILITY_PERFORMERS:
            await cap_mappings.add_mapping(
                AddMapping(capability_id=cap_ids[cap_name], org_unit_id=org_ids[ou_name],
                           role="performer", geography_id=geo_id), session)
        for cap_name, ou_name in CAPABILITY_CONTRIBUTORS:
            await cap_mappings.add_mapping(
                AddMapping(capability_id=cap_ids[cap_name], org_unit_id=org_ids[ou_name],
                           role="contributor"), session)
        await session.commit()
        print(f"  {len(CAPABILITY_OWNERS)} owners, {len(CAPABILITY_PERFORMERS)} performers, "
              f"{len(CAPABILITY_CONTRIBUTORS)} contributors")

    # ── Phase C5: regional assessments (942-regional-assessments) ──────────────
    print("Seeding regional assessments...")
    async with session_factory() as session:
        for cap_name, geo_id, maturity, note in REGIONAL_ASSESSMENTS:
            await regional.set_assessment(
                cap_ids[cap_name], geo_id,
                SetRegionalAssessment(maturity_level=maturity, note=note), session)
        for cap_name, geo_ids in REGION_SPECIFIC.items():
            await regional.set_scope(
                cap_ids[cap_name], SetRegionScope(region_specific=True, geography_ids=geo_ids),
                session)
        await session.commit()
        print(f"  {len(REGIONAL_ASSESSMENTS)} assessments, "
              f"{len(REGION_SPECIFIC)} region-specific capabilities")

    # ── Phase D: agentic solution + agents (933-agent-registry) ───────────────
    print("Seeding agent registry...")
    async with session_factory() as session:
        solution = await astore.create_application(
            ApplicationCreate(
                name=ADP_SOLUTION[0], description=ADP_SOLUTION[1], application_type="agentic",
                primary_owner="Architecture Platform Team",
            ),
            session,
        )
        for name, role, autonomy, approval, framework, prompt_ref, desc in ADP_AGENTS:
            agent = await agstore.create_agent(
                AgentCreate(
                    name=name, description=desc, owner="Architecture Platform Team",
                    model_provider="Anthropic", framework=framework, prompt_ref=prompt_ref,
                    autonomy_level=autonomy, human_approval=approval,
                    data_classification_max="internal",
                ),
                session,
            )
            await agstore.add_solution_agent(solution.id, agent.id, role, session)
        await session.commit()
        print(f"  1 agentic solution, {len(ADP_AGENTS)} agents")

    await engine.dispose()
    print("\nDone. Retail portfolio seeded.")


def main() -> None:
    parser = argparse.ArgumentParser(description="Seed ADP with a retail demo portfolio.")
    parser.add_argument("--yes", "-y", action="store_true",
                        help="Skip the wipe confirmation prompt.")
    args = parser.parse_args()

    db_url = os.environ.get("ADP_DATABASE_URL", DEFAULT_DB_URL)

    if not args.yes:
        print(f"This will TRUNCATE all application data in:\n  {db_url}\n"
              "(the knowledge base is preserved).")
        if input("Type 'wipe' to continue: ").strip() != "wipe":
            print("Aborted.")
            sys.exit(1)

    asyncio.run(seed(db_url))


if __name__ == "__main__":
    main()
