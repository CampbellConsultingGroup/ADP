#!/usr/bin/env python3
"""Seed the ADP knowledge base with industry-standard best practices.

Usage:
    python scripts/seed_knowledge.py

Requires ADP_DATABASE_URL environment variable (or uses the default local URL).
Generates real 384-dim embeddings via sentence-transformers all-MiniLM-L6-v2.
"""

from __future__ import annotations

import asyncio
import os
import sys

# ── Knowledge items ───────────────────────────────────────────────────────────
# Each dict: id, version, kind, title, full_text, source_ref, metadata
ITEMS: list[dict] = [
    # ── Principles ───────────────────────────────────────────────────────────
    {
        "id": "PRIN-001",
        "version": "1.0.0",
        "kind": "principle",
        "title": "Separation of Concerns",
        "source_ref": "https://en.wikipedia.org/wiki/Separation_of_concerns",
        "metadata": {"domain": "software-design", "tags": ["modularity", "cohesion"]},
        "full_text": (
            "Separation of Concerns (SoC) is a design principle for separating a computer program "
            "into distinct sections such that each section addresses a separate concern. "
            "Each component should have a single, well-defined responsibility and should not "
            "know about the internal workings of other components. "
            "Apply SoC at every level: separate UI from business logic, separate business logic "
            "from data access, separate configuration from code. "
            "Benefits include improved maintainability, testability, and the ability to change "
            "one part of the system without affecting others."
        ),
    },
    {
        "id": "PRIN-002",
        "version": "1.0.0",
        "kind": "principle",
        "title": "Design for Failure",
        "source_ref": "https://aws.amazon.com/architecture/well-architected/",
        "metadata": {"domain": "reliability", "tags": ["resilience", "fault-tolerance"]},
        "full_text": (
            "Design for Failure assumes that any component can and will fail at any time. "
            "Systems must be designed to detect failures, isolate them, and recover gracefully "
            "without data loss or prolonged unavailability. "
            "Key practices: implement health checks, use circuit breakers to stop cascading failures, "
            "adopt bulkheads to isolate failure domains, implement retries with exponential backoff "
            "and jitter, use timeouts on all external calls, and design idempotent operations "
            "so retries are safe. "
            "Test failure scenarios using chaos engineering to validate recovery paths. "
            "Every dependency is a potential failure point; treat them accordingly."
        ),
    },
    {
        "id": "PRIN-003",
        "version": "1.0.0",
        "kind": "principle",
        "title": "API First Design",
        "source_ref": "https://swagger.io/resources/articles/adopting-an-api-first-approach/",
        "metadata": {"domain": "integration", "tags": ["api", "contract", "openapi"]},
        "full_text": (
            "API First means designing the API contract before writing any implementation code. "
            "The contract (OpenAPI/Swagger specification) is the single source of truth and is "
            "agreed upon by all consuming teams before development begins. "
            "Benefits: enables parallel development of clients and servers, enforces consistent "
            "interface design, makes the API the primary product artifact, and allows automated "
            "validation, mocking, and documentation generation. "
            "All services must expose versioned, documented REST or GraphQL APIs. "
            "Breaking changes require a new major version. Internal services are not exempt — "
            "treat every service boundary as a published API."
        ),
    },
    {
        "id": "PRIN-004",
        "version": "1.0.0",
        "kind": "principle",
        "title": "Loose Coupling and High Cohesion",
        "source_ref": "https://martinfowler.com/ieeeSoftware/coupling.pdf",
        "metadata": {"domain": "software-design", "tags": ["coupling", "cohesion", "modularity"]},
        "full_text": (
            "Loose coupling minimises the dependencies between components so that changes in one "
            "component do not force changes in others. High cohesion ensures that the elements "
            "within a component are strongly related and focused on a single purpose. "
            "Achieve loose coupling through: well-defined interfaces, asynchronous messaging "
            "for non-critical paths, dependency injection, event-driven communication, and "
            "avoiding shared mutable state. "
            "Measure coupling by counting the number of times a component calls another; "
            "reduce this by introducing abstraction layers, anti-corruption layers, or message buses. "
            "Services should be independently deployable and scalable."
        ),
    },
    {
        "id": "PRIN-005",
        "version": "1.0.0",
        "kind": "principle",
        "title": "Zero Trust Security",
        "source_ref": "https://nvlpubs.nist.gov/nistpubs/SpecialPublications/NIST.SP.800-207.pdf",
        "metadata": {"domain": "security", "tags": ["zero-trust", "identity", "authentication"]},
        "full_text": (
            "Zero Trust security assumes no implicit trust for any entity — inside or outside the "
            "network perimeter. Every access request must be authenticated, authorised, and "
            "continuously validated regardless of source. "
            "Core tenets: verify explicitly (always authenticate and authorise based on all available "
            "data points), use least privilege access (limit user access with just-in-time and "
            "just-enough access), assume breach (minimise blast radius, segment access, verify "
            "end-to-end encryption, use analytics to drive visibility and threat detection). "
            "Implement: strong identity verification (MFA), device health checks, network micro-"
            "segmentation, encryption in transit and at rest, and continuous session monitoring. "
            "Replace perimeter-based firewalls with identity-aware proxies."
        ),
    },
    {
        "id": "PRIN-006",
        "version": "1.0.0",
        "kind": "principle",
        "title": "Observability by Design",
        "source_ref": "https://opentelemetry.io/docs/concepts/observability-primer/",
        "metadata": {"domain": "operations", "tags": ["observability", "telemetry", "monitoring"]},
        "full_text": (
            "Observability is the ability to measure the internal state of a system from its "
            "external outputs. Build observability in from day one — not as an afterthought. "
            "The three pillars are: structured logs (machine-readable, searchable, correlated), "
            "metrics (quantitative measurements over time — latency percentiles, error rates, "
            "saturation), and distributed traces (end-to-end request journeys across services). "
            "Use OpenTelemetry as the vendor-neutral instrumentation standard. "
            "Every service must emit structured logs with a correlation/trace ID, expose a "
            "/health endpoint (liveness + readiness), and emit RED metrics (Rate, Errors, Duration). "
            "Define SLIs and SLOs before deployment; alert on SLO burn rates not raw thresholds."
        ),
    },
    # ── Patterns ─────────────────────────────────────────────────────────────
    {
        "id": "PAT-001",
        "version": "1.0.0",
        "kind": "pattern",
        "title": "API Gateway Pattern",
        "source_ref": "https://microservices.io/patterns/apigateway.html",
        "metadata": {"domain": "integration", "tags": ["api-gateway", "routing", "ingress"]},
        "full_text": (
            "An API Gateway is a single entry point for all clients that sits in front of multiple "
            "backend services. It handles cross-cutting concerns including: request routing, "
            "protocol translation, authentication and authorisation, rate limiting, SSL termination, "
            "request/response transformation, caching, and logging. "
            "Use when: multiple client types (web, mobile, third-party) need different data shapes, "
            "when you need to aggregate calls to multiple downstream services, or when you need "
            "consistent enforcement of security policies. "
            "Risks: the gateway can become a single point of failure (mitigate with redundancy) "
            "and a bottleneck (mitigate with horizontal scaling and caching). "
            "Avoid putting business logic in the gateway — it should be a thin routing/security layer."
        ),
    },
    {
        "id": "PAT-002",
        "version": "1.0.0",
        "kind": "pattern",
        "title": "Circuit Breaker Pattern",
        "source_ref": "https://martinfowler.com/bliki/CircuitBreaker.html",
        "metadata": {"domain": "resilience", "tags": ["circuit-breaker", "fault-tolerance", "resilience"]},
        "full_text": (
            "A Circuit Breaker wraps calls to external services and monitors for failures. "
            "When the failure rate exceeds a threshold, the circuit opens and subsequent calls "
            "fail fast without waiting for timeouts, allowing the upstream service to recover. "
            "States: Closed (normal operation, calls pass through), Open (calls fail immediately "
            "with a fallback response), Half-Open (a trial call is allowed through to test recovery). "
            "Configure: failure threshold (e.g., 50% over 10 seconds), timeout duration, "
            "half-open probe interval. "
            "Combine with retries using exponential backoff + jitter for transient errors. "
            "Do not retry on permanent failures (4xx, validation errors). "
            "Always provide a meaningful fallback: cached data, degraded response, or clear error."
        ),
    },
    {
        "id": "PAT-003",
        "version": "1.0.0",
        "kind": "pattern",
        "title": "Strangler Fig Migration Pattern",
        "source_ref": "https://martinfowler.com/bliki/StranglerFigApplication.html",
        "metadata": {"domain": "migration", "tags": ["migration", "legacy", "incremental"]},
        "full_text": (
            "The Strangler Fig pattern enables incremental migration from a legacy monolith to a "
            "new architecture by gradually replacing specific pieces of functionality. "
            "A facade (proxy/gateway) intercepts all incoming requests. New functionality is "
            "implemented in the new system; the facade routes those requests to it. "
            "Old functionality is retained in the legacy system until it is fully replaced. "
            "Over time the legacy system shrinks (strangled) until it can be decommissioned. "
            "Benefits: reduces risk compared to big-bang replacement, delivers value incrementally, "
            "allows teams to learn the new platform progressively. "
            "Key practices: identify seams in the monolith along domain boundaries, start with "
            "low-risk high-value domains, maintain data consistency during dual-write period, "
            "keep feature parity tests running against both systems."
        ),
    },
    {
        "id": "PAT-004",
        "version": "1.0.0",
        "kind": "pattern",
        "title": "Saga Pattern for Distributed Transactions",
        "source_ref": "https://microservices.io/patterns/data/saga.html",
        "metadata": {"domain": "data", "tags": ["saga", "distributed-transactions", "consistency"]},
        "full_text": (
            "The Saga pattern manages data consistency across multiple services without using "
            "distributed ACID transactions, which are fragile and create tight coupling. "
            "A saga is a sequence of local transactions; each local transaction publishes an event "
            "that triggers the next step. If any step fails, compensating transactions are executed "
            "in reverse to undo the completed steps. "
            "Two implementations: Choreography (services listen for events and react, no central "
            "coordinator — simpler but harder to track overall state) and Orchestration (a central "
            "saga orchestrator directs participants — easier to visualise but the orchestrator "
            "can become a bottleneck). "
            "Use sagas when a business transaction spans multiple microservices and eventual "
            "consistency is acceptable. Design compensating transactions carefully — they must "
            "be idempotent and cannot always fully undo side effects (e.g., sent emails)."
        ),
    },
    {
        "id": "PAT-005",
        "version": "1.0.0",
        "kind": "pattern",
        "title": "CQRS — Command Query Responsibility Segregation",
        "source_ref": "https://martinfowler.com/bliki/CQRS.html",
        "metadata": {"domain": "data", "tags": ["cqrs", "read-model", "write-model", "scalability"]},
        "full_text": (
            "CQRS separates read (Query) and write (Command) models into distinct objects and "
            "often distinct data stores. Commands change state and return no data; Queries return "
            "data and change no state. "
            "Benefits: each side can be scaled, optimised, and secured independently. "
            "Read models can be denormalised for query performance. Write models can enforce "
            "invariants and domain rules without performance constraints. "
            "Often combined with Event Sourcing: commands produce events that are stored as the "
            "system of record; read models are projections rebuilt from events. "
            "Complexity trade-off: CQRS adds architectural complexity (synchronisation lag, "
            "eventual consistency, dual codepaths). Only apply when the domain genuinely has "
            "different read and write performance/scale requirements or complex domain logic."
        ),
    },
    {
        "id": "PAT-006",
        "version": "1.0.0",
        "kind": "pattern",
        "title": "Event-Driven Architecture",
        "source_ref": "https://martinfowler.com/articles/201701-event-driven.html",
        "metadata": {"domain": "integration", "tags": ["events", "async", "decoupling", "messaging"]},
        "full_text": (
            "Event-Driven Architecture (EDA) structures systems around the production, detection, "
            "and consumption of events. Producers emit events without knowing who consumes them; "
            "consumers subscribe to event types and react independently. "
            "Event types: Event Notification (something happened, minimal data, consumer fetches "
            "details), Event-Carried State Transfer (event contains all data needed — no callback), "
            "Event Sourcing (events as the system of record). "
            "Use EDA to decouple services, enable fan-out (one event, many consumers), support "
            "audit trails, and enable temporal decoupling (consumer can be offline). "
            "Technology choices: Apache Kafka for high-throughput durable streams, RabbitMQ/SQS "
            "for task queues, event buses (EventBridge, Google Pub/Sub) for cloud-native fan-out. "
            "Design events with schema registries (Avro/Protobuf) and version them carefully "
            "to avoid breaking consumers."
        ),
    },
    {
        "id": "PAT-007",
        "version": "1.0.0",
        "kind": "pattern",
        "title": "Sidecar Pattern",
        "source_ref": "https://learn.microsoft.com/en-us/azure/architecture/patterns/sidecar",
        "metadata": {"domain": "infrastructure", "tags": ["sidecar", "service-mesh", "proxy"]},
        "full_text": (
            "The Sidecar pattern deploys a helper process alongside each primary application "
            "instance in the same execution context (same pod in Kubernetes). The sidecar handles "
            "cross-cutting concerns independently of the primary application. "
            "Common sidecar responsibilities: service mesh proxy (mutual TLS, traffic management, "
            "observability — e.g., Envoy in Istio), log aggregation, secret injection, "
            "configuration reloading, health reporting. "
            "Benefits: keeps the primary application focused on business logic, allows cross-cutting "
            "concerns to be updated independently, enables a polyglot environment. "
            "Drawbacks: adds operational complexity, increases resource consumption per instance. "
            "When to use: cross-cutting infrastructure concerns that would otherwise require "
            "library changes in every service."
        ),
    },
    # ── Standards ─────────────────────────────────────────────────────────────
    {
        "id": "STD-001",
        "version": "1.0.0",
        "kind": "standard",
        "title": "12-Factor App Methodology",
        "source_ref": "https://12factor.net/",
        "metadata": {"domain": "deployment", "tags": ["12-factor", "cloud-native", "portability"]},
        "full_text": (
            "The 12-Factor App methodology describes practices for building software-as-a-service "
            "apps that are portable, scalable, and maintainable. "
            "The 12 factors: (1) Codebase — one codebase tracked in version control, many deploys; "
            "(2) Dependencies — explicitly declare and isolate dependencies; "
            "(3) Config — store config in the environment (not code); "
            "(4) Backing services — treat databases, queues, caches as attached resources; "
            "(5) Build/release/run — strictly separate stages; "
            "(6) Processes — execute the app as stateless processes; "
            "(7) Port binding — export services via port binding; "
            "(8) Concurrency — scale out via the process model; "
            "(9) Disposability — maximise robustness with fast startup and graceful shutdown; "
            "(10) Dev/prod parity — keep development, staging, and production as similar as possible; "
            "(11) Logs — treat logs as event streams; "
            "(12) Admin processes — run admin/management tasks as one-off processes."
        ),
    },
    {
        "id": "STD-002",
        "version": "1.0.0",
        "kind": "standard",
        "title": "OAuth2 and OIDC for Authentication and Authorisation",
        "source_ref": "https://oauth.net/2/",
        "metadata": {"domain": "security", "tags": ["oauth2", "oidc", "jwt", "authentication"]},
        "full_text": (
            "OAuth2 is the industry-standard authorisation framework. OpenID Connect (OIDC) adds "
            "an identity layer on top of OAuth2. Together they provide standardised, secure "
            "authentication and authorisation for modern applications. "
            "Use OAuth2 authorisation code flow + PKCE for web and mobile apps. "
            "Use client credentials flow for machine-to-machine (M2M) communication. "
            "Never implement custom authentication — use a proven Identity Provider (IdP) "
            "such as Keycloak, Auth0, Azure AD, or Okta. "
            "JWTs (access tokens) must be short-lived (< 1 hour), signed with RS256 or ES256, "
            "and validated on every request including expiry, issuer, and audience. "
            "Refresh tokens must be rotated on each use and stored securely. "
            "Scopes must follow least privilege — only request permissions actually needed."
        ),
    },
    {
        "id": "STD-003",
        "version": "1.0.0",
        "kind": "standard",
        "title": "RESTful API Design with OpenAPI 3.x",
        "source_ref": "https://restfulapi.net/",
        "metadata": {"domain": "integration", "tags": ["rest", "openapi", "http", "versioning"]},
        "full_text": (
            "REST APIs must follow consistent conventions to be predictable and maintainable. "
            "Resources are nouns in the URL path (e.g., /users/{id}), HTTP verbs express actions: "
            "GET (read), POST (create), PUT/PATCH (update), DELETE (remove). "
            "Version via URL prefix: /api/v1/. Status codes must be semantically correct: "
            "200 OK, 201 Created, 204 No Content, 400 Bad Request, 401 Unauthenticated, "
            "403 Forbidden, 404 Not Found, 409 Conflict, 422 Unprocessable Entity, 429 Rate Limited, "
            "500 Internal Server Error. "
            "All APIs must be documented with OpenAPI 3.x specification. "
            "Error responses must include a machine-readable error code (string) and human-readable "
            "message. Pagination: use cursor-based pagination for large datasets. "
            "HTTPS only; HSTS required in production. Support conditional requests with ETags "
            "for cache-friendly read-heavy resources."
        ),
    },
    # ── Reference Architectures ───────────────────────────────────────────────
    {
        "id": "ARCH-001",
        "version": "1.0.0",
        "kind": "reference_architecture",
        "title": "Cloud-Native Microservices Architecture",
        "source_ref": "https://www.cncf.io/blog/2017/05/15/developing-cloud-native-applications/",
        "metadata": {"domain": "architecture", "tags": ["microservices", "cloud-native", "containers"]},
        "full_text": (
            "Cloud-Native Microservices architecture decomposes a system into small, independently "
            "deployable services, each responsible for a bounded domain context. "
            "Core characteristics: services are containerised (Docker), orchestrated (Kubernetes), "
            "communicate over lightweight protocols (REST/gRPC/events), have independent data stores "
            "(no shared databases), and are continuously delivered via CI/CD pipelines. "
            "Service boundaries follow Domain-Driven Design bounded contexts. Each service owns "
            "its data and exposes it only via APIs. "
            "Operational requirements: each service must have health checks, structured logging "
            "with trace IDs, metrics (RED: Rate, Errors, Duration), and distributed tracing. "
            "Use a service mesh (Istio/Linkerd) for mTLS, traffic management, and observability "
            "when managing more than ~10 services. "
            "Governance: define service ownership, deprecation policies, and SLOs for each service."
        ),
    },
    {
        "id": "ARCH-002",
        "version": "1.0.0",
        "kind": "reference_architecture",
        "title": "Modular Monolith (Majestic Monolith)",
        "source_ref": "https://www.modularmonolith.net/",
        "metadata": {"domain": "architecture", "tags": ["monolith", "modularity", "simplicity"]},
        "full_text": (
            "A Modular Monolith is a single deployable unit that is internally organised into "
            "well-defined, loosely coupled modules with clear boundaries. It avoids the operational "
            "complexity of microservices while preserving good modularity for maintainability. "
            "Structure: modules communicate via well-defined in-process interfaces, not network calls. "
            "Each module has its own database schema (or schema prefix) to avoid tight data coupling. "
            "Modules can be extracted into separate services later if independent scaling is needed. "
            "When to prefer over microservices: small team (< 8 engineers), early-stage product "
            "with high change frequency, unclear domain boundaries, or when operational complexity "
            "of distributed systems is not justified by scale requirements. "
            "Apply the same modularity discipline (bounded contexts, clear interfaces) as you would "
            "for microservices — the difference is deployment unit, not design quality."
        ),
    },
    {
        "id": "ARCH-003",
        "version": "1.0.0",
        "kind": "reference_architecture",
        "title": "Event-Driven Data Mesh Architecture",
        "source_ref": "https://martinfowler.com/articles/data-mesh-principles.html",
        "metadata": {"domain": "data", "tags": ["data-mesh", "data-platform", "domain-ownership"]},
        "full_text": (
            "Data Mesh is a decentralised data architecture that treats data as a product owned by "
            "domain teams rather than centralised data engineering teams. "
            "Four principles: (1) Domain ownership — each domain owns its data products end-to-end; "
            "(2) Data as a product — data is discoverable, addressable, trustworthy, self-describing, "
            "interoperable, and secure; "
            "(3) Self-serve data platform — infrastructure that enables domain teams to build, "
            "deploy, and monitor data products independently; "
            "(4) Federated computational governance — global standards enforced automatically "
            "with local autonomy for implementation. "
            "Applicable when: multiple domains generate and consume data independently, "
            "a central data team is a bottleneck, and data quality varies wildly across the org. "
            "Not suitable for small organisations or those without strong domain-team autonomy."
        ),
    },
    {
        "id": "ARCH-004",
        "version": "1.0.0",
        "kind": "reference_architecture",
        "title": "Layered (N-Tier) Architecture",
        "source_ref": "https://www.oreilly.com/library/view/software-architecture-patterns/9781491971437/",
        "metadata": {"domain": "architecture", "tags": ["layered", "n-tier", "traditional"]},
        "full_text": (
            "Layered (N-Tier) architecture organises components into horizontal layers, each with "
            "a specific role. Typical layers: Presentation (UI/API), Application (use cases), "
            "Domain (business logic and rules), Infrastructure (databases, external services). "
            "Each layer only communicates with the layer directly below it. "
            "Benefits: clear separation of concerns, well-understood by most developers, easy "
            "to apply consistent cross-cutting concerns (logging, auth) per layer. "
            "Drawbacks: can lead to 'lasagna code' where simple changes touch every layer, "
            "not naturally suited to high scalability requirements, and can create an anemic "
            "domain model if business logic leaks into the application layer. "
            "Apply Clean Architecture / Ports and Adapters (Hexagonal) variant to ensure the "
            "domain layer has no dependencies on infrastructure — making it independently testable "
            "and portable across different databases or frameworks."
        ),
    },
    {
        "id": "ARCH-005",
        "version": "1.0.0",
        "kind": "reference_architecture",
        "title": "Backend for Frontend (BFF) Pattern",
        "source_ref": "https://samnewman.io/patterns/architectural/bff/",
        "metadata": {"domain": "integration", "tags": ["bff", "api", "frontend", "gateway"]},
        "full_text": (
            "The Backend for Frontend (BFF) pattern creates dedicated backend services for each "
            "type of frontend client (web, mobile, third-party). Each BFF is owned by the team "
            "that builds the corresponding frontend, allowing them to evolve independently. "
            "Unlike a general-purpose API gateway, a BFF aggregates, transforms, and optimises "
            "data specifically for one client type — returning exactly what that client needs "
            "in the shape it expects. "
            "Benefits: reduces over-fetching and under-fetching (no more generic endpoints), "
            "each client team controls their own backend, reduces coupling between frontend and "
            "downstream services. "
            "When to use: multiple distinct client types with significantly different data needs, "
            "when a general API gateway is becoming a bottleneck for client-specific optimisations. "
            "Avoid: for a single client type or when clients have nearly identical data requirements."
        ),
    },
]


async def seed(db_url: str) -> None:
    from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

    from adp.knowledge.index import KnowledgeIndex, knowledge_items
    from adp.knowledge.schema import KnowledgeItem, KnowledgeType

    print("Loading sentence-transformers model (all-MiniLM-L6-v2)...")
    from sentence_transformers import SentenceTransformer
    model = SentenceTransformer("all-MiniLM-L6-v2")
    print(f"  embedding dim = {model.get_embedding_dimension()}")

    engine = create_async_engine(db_url, echo=False)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)

    idx = KnowledgeIndex(session_factory=session_factory)

    print(f"\nSeeding {len(ITEMS)} knowledge items...")
    async with session_factory() as session:
        for raw in ITEMS:
            item = KnowledgeItem(
                id=raw["id"],
                version=raw["version"],
                kind=KnowledgeType(raw["kind"]),
                title=raw["title"],
                full_text=raw["full_text"],
                source_ref=raw["source_ref"],
                metadata=raw["metadata"],
            )
            text_for_embedding = f"{item.title}\n{item.full_text}"
            embedding = model.encode(text_for_embedding, normalize_embeddings=True).tolist()
            await idx.upsert_item(item, embedding, session)
            print(f"  ✓ {item.id}  {item.title}")

        await session.commit()

    await engine.dispose()

    # Verify
    from sqlalchemy import text
    engine2 = create_async_engine(db_url, echo=False)
    async with engine2.connect() as conn:
        result = await conn.execute(text("SELECT count(*) FROM knowledge_items WHERE active = true"))
        count = result.scalar()
    await engine2.dispose()
    print(f"\nKnowledge base now contains {count} active items.")


if __name__ == "__main__":
    db_url = os.environ.get(
        "ADP_DATABASE_URL",
        "postgresql+asyncpg://adp_user:adp_pass@127.0.0.1:5432/adp",
    )
    asyncio.run(seed(db_url))
