Good question — and worth being precise about: in the HTML reference I built, `technical_fit_score` and `business_criticality_score` were placeholder field names for the mockup, not something pulled from ADP's actual data model. I don't know if ADP already has these as stored columns or computed values — that's worth checking against the real `application` package before treating them as real fields.

That said, here's how these scores are typically constructed in APM practice — they're almost always **composite scores**, not a single guess or a single input:

**Technical Fit / Quality — typically an average or weighted sum of:**
- Architecture alignment (does it fit current target-state patterns, or is it an outlier)
- Vendor/platform support status (still supported, EOL, deprecated)
- Code/platform age and maintainability
- Security posture (known vulnerabilities, patch cadence)
- Scalability / performance headroom
- Integration quality (clean APIs vs. brittle point-to-point/legacy integration)
- Test coverage / release cadence (how safely can it be changed)

**Business Criticality — typically an average or weighted sum of:**
- Revenue or process dependency (would the business stop functioning without it)
- Number of users / breadth of usage across the org
- Regulatory/compliance exposure
- Customer-facing vs. internal-only
- SLA tier / uptime requirements
- Downstream dependency (how many other systems or processes rely on it)

**How the composite is usually built:**
- Each sub-factor is scored on a common scale (often 1–5), sometimes weighted differently
- The weighted average (or sum, normalized to 0–100) becomes the single "fit" or "criticality" score
- Some tools let each sub-factor be edited independently and only display the rollup; others let a human enter the composite score directly as a judgment call

**Two common approaches, worth deciding explicitly for ADP:**
1. **Computed** — score derived from structured sub-fields (some objective, some still subjective ratings) that are individually visible and auditable
2. **Direct entry** — an architect just assigns a 0–100 score as a judgment call, with sub-factors as guidance/documentation but not stored data

Given ADP's existing pattern — typed sub-fields over free-text judgment calls, e.g. the objective's typed metric group — a computed composite from stored sub-factors would fit the established convention better than a single freeform number. That'd also make the score explainable (which sub-factor is dragging an app into "Tolerate") rather than a black box, and keeps it consistent with the audit/reasoning-trace expectations already built into the platform.

Using an example app from the mockup — **Claims Core** (fit: 28, criticality: 88, landed in "Tolerate") — here's what each sub-factor might concretely look like:

**Technical Fit / Quality sub-factors**

| Sub-factor | Example for Claims Core |
|---|---|
| Architecture alignment | Monolithic COBOL core, no separation between business logic and data layer — doesn't fit ADP's target microservice/API pattern |
| Vendor/platform support | Runs on a mainframe platform the vendor stopped actively developing in 2019; extended support only |
| Age / maintainability | Originally built 1998, last major refactor 2006; original developers no longer at the company |
| Security posture | 3 open medium-severity CVEs on the underlying platform, no automated patching pipeline |
| Scalability / performance | Batch-oriented, hard-coded overnight processing window — can't handle real-time claim intake at current growth rate |
| Integration quality | Exposes data via nightly flat-file export, not an API — other systems poll a shared drive |
| Test coverage / release cadence | No automated test suite; changes require a 6-week manual regression cycle |

→ Each of these pulls the composite score *down*, landing Claims Core at 28/100.

**Business Criticality sub-factors**

| Sub-factor | Example for Claims Core |
|---|---|
| Revenue/process dependency | Every claim payout in the company flows through this system — a full outage halts claims processing entirely |
| User breadth | Used daily by ~450 claims adjusters across all regions |
| Regulatory/compliance exposure | Subject to state insurance-claims-handling regulations with mandated processing-time SLAs |
| Customer-facing vs. internal | Indirectly customer-facing — claim status and payout timing depend on it |
| SLA tier | Tier 1 — 99.9% uptime requirement, 4-hour max recovery time |
| Downstream dependency | 6 other systems (Billing Gateway, Doc Archive, reporting) consume its output |

→ Each of these pulls the composite score *up*, landing Claims Core at 88/100.

**The pattern that emerges:** high criticality + low fit is exactly the "Tolerate" quadrant — a system the business can't live without today, but that's expensive and risky to keep running as-is. That's the kind of finding a composite score with visible sub-factors gives you "for free" — you can see *why* it's Tolerate, not just that it is, which matters if this ever gets audited or challenged by a stakeholder.

Yes — this is a well-known problem in APM practice, and there are several concrete techniques to reduce subjectivity and political influence. The general principle: **replace judgment calls with measurable proxies wherever possible**, and where judgment is unavoidable, **structure and distribute it** so no single stakeholder can skew it.

**1. Swap subjective ratings for objective, system-derived proxies**

Instead of someone rating "scalability" 1–5 from memory, pull it from data that already exists:

| Subjective version | Objective proxy |
|---|---|
| "How well-supported is this platform?" (1–5 guess) | Vendor EOL date pulled from a technology standards registry — days-until-EOL maps to a score band |
| "How risky is this app?" | Count of open CVEs from a vulnerability scanner, weighted by severity |
| "How critical is it?" | Actual incident/outage count + measured downstream dependency count (systems that call its API) |
| "How well-tested is it?" | Automated test coverage % from CI |
| "How widely used?" | Actual login/usage telemetry, not a stakeholder's estimate |

Anything you can pull from a system of record (CMDB, vulnerability scanner, CI pipeline, usage logs) removes a political lever entirely — nobody can argue with a CVE count the way they can argue with a "criticality" opinion.

**2. For factors that truly require judgment, use a structured rubric, not a free number**

Instead of "rate criticality 1–100," force the rater to answer discrete, defensible questions:

> Does an outage of this app halt a regulated business process? (Yes/No)
> Does it have a contractual SLA with an external party? (Yes/No)
> How many other systems have a hard dependency on it? (count)

Each answer maps to a fixed point value. This is the standard technique — it turns "how important is this, really" (arguable) into "does X exist, yes or no" (checkable), which is much harder to politically lean on.

**3. Multi-rater consensus instead of single-owner scoring**

If a factor really can't be made objective (e.g. "strategic alignment"), require 2–3 independent raters (app owner + EA + a domain architect) and take the median, or flag for review if scores diverge beyond a threshold. This is the same principle as LLM-as-judge fan-out in ADP's eval package — independent evaluation, then reconciliation, rather than one person's number becoming truth.

**4. Full provenance / audit trail on every score**

Every sub-factor score should record who set it, when, and — for manual ones — a required justification note. This doesn't prevent political scoring, but it makes it visible and attributable, which is often enough to deter it. This maps directly onto ADP's existing audit/reasoning-trace requirement — same governance pattern, applied to portfolio scoring instead of AI actions.

**5. Recompute on a cadence, not on demand**

If scores can be recalculated ad hoc whenever someone wants a different Portfolio-screen outcome, that's an obvious injection point for politics. Locking recomputation to a scheduled cadence (e.g. quarterly, tied to a data refresh) removes the "just re-score it until it looks right" pathway.

**How this maps onto ADP specifically:**

Given the existing conventions (typed sub-fields over free text, human-confirms-AI-proposal pattern, versioned permission table, audit trail requirement), the natural fit is:

- Store each sub-factor as its own typed column, not just a rollup number
- Source what you can automatically (CVE count, EOL date, usage metrics, dependency count) via scheduled ingestion rather than manual entry
- For the few fields that need human judgment, use bounded rubric options (not a free 1–100 slider) and require a note
- Record `set_by`, `set_at`, and `source` (`system` vs `manual`) per sub-factor
- Compute the rollup score deterministically from sub-factors — never let it be edited directly

That last point is probably the single highest-leverage rule: **if the composite score can be manually overridden, all the objectivity work upstream is moot.** The rollup should be a pure function of its inputs, full stop — same principle ADP already applies to pure status/stage derivation elsewhere in the strategy and Wardley work.