# Intake Test Scenario — Answer Key

This is the test oracle for [intake-scenario-unified-inventory.md](intake-scenario-unified-inventory.md). Paste **only** that file into Intake. This key is for the tester and must never be submitted.

It exercises Requirements Intake (ADP-SPEC-006) on five behaviours:
- extraction and kind classification (FR-002);
- source-excerpt grounding (FR-007);
- knowledge-base linking (FR-005 / SC-005);
- per-proposal human confirmation and audit (FR-003 / FR-004);
- capability gap analysis (ADP-zg3.4).

The input is 3,910 characters, within SC-003's 5,000-character / 60-second envelope.

## How to run

1. Sign in and open (or create) a test design, e.g. "Intake Test — Unified Inventory". Use a scratch design: confirmed requirements stay on it.
2. Open **Intake** for that design. Choose bulk text mode and paste the full contents of the scenario file. Note the submit time.
3. Wait for extraction to finish. Record the elapsed time and the number of proposals.
4. Review every proposal against the tables below, and fill in the results log.
5. Confirmation checks (FR-003 / FR-004):
   - **Confirm** FR-02 as-is.
   - **Edit and confirm** NFR-01: change "300 ms" to "250 ms".
   - **Reject** any noise proposal (N-01 or N-02). If neither appears, reject FR-09 instead.
   - Confirm that only the two confirmed items appear under the design's requirements. Check the audit trail shows the confirming user, a timestamp, the source submission, and the edited flag on NFR-01.
6. Confirm the remaining expected requirements, then open the **Capability Gaps** panel and check it against the gap-analysis table.
7. Structured-form check: submit the single statement `The system must show real-time available-to-sell quantity per SKU for every store and DC.` in structured mode. Expect exactly 1 proposal: kind `functional`, VERIFIED, confidence 1.0, no LLM call.

API equivalents, all under `/api/v1/designs/{design_id}`:

| Step | Request |
|---|---|
| Submit | `POST /intake` |
| Poll | `GET /intake/{operation_id}` |
| Confirm a proposal | `POST /intake/{operation_id}/proposals/{proposal_id}/confirm` |
| Reject a proposal | `POST /intake/{operation_id}/proposals/{proposal_id}/reject` |
| List requirements | `GET /requirements` |
| Gap analysis | `GET /capability-gaps` |

## Expected extraction

Excerpts are verbatim substrings of the input. A proposal's own excerpt may be shorter or longer, but it must still appear word-for-word in the input, otherwise it shows as UNVERIFIED. "KB link" lists the seeded knowledge items the proposal should link to.

### Drivers (business problem / desired outcome)

| ID | Expected kind | Source excerpt | KB link |
|---|---|---|---|
| D-01 | driver | `About 4% of online orders are cancelled because of phantom stock` | — |
| D-02 | driver | `9% of BOPIS orders are cancelled after the customer has already been told the order is ready` | — |
| D-03 | driver | `Stock positions are up to 18 hours stale.` | — |
| D-04 | driver | `We estimate $14M a year in lost sales and a further $3M in avoidable markdowns` | — |
| D-05 | driver *(or non_functional)* | `Reduce the online order cancellation rate from 4% to under 1% within two quarters of go-live.` | — |
| D-06 | driver *(or non_functional)* | `Make every store and DC stock change visible to the online channel within 60 seconds.` | — |
| D-07 | driver *(or constraint)* | `Launch ship-from-store in 40 pilot stores within two quarters` | — |

### Functional

| ID | Expected kind | Source excerpt | KB link |
|---|---|---|---|
| FR-01 | functional | `The system must show real-time available-to-sell quantity per SKU for every store and DC.` | — |
| FR-02 | functional | `The system must reserve stock for an order at checkout so the same unit cannot be sold twice.` | — |
| FR-03 | functional | `Order Orchestration must route each online order to the nearest store or DC that can fulfil it complete.` | — |
| FR-04 | functional | `Customers must receive a pickup-ready notification only after a store associate has physically picked the BOPIS order.` | — |
| FR-05 | functional | `Store associates need a Store Associate Task Management screen` | — |
| FR-06 | functional | `Returned items must go back into available stock as soon as Returns Inspection & Disposition marks them resellable.` | — |
| FR-07 | functional *(or constraint)* | `Each store must hold a configurable safety-stock buffer that is never offered online.` | — |
| FR-08 | functional | `Demand Forecasting and Replenishment must consume real-time stock positions instead of the overnight batch.` | — |
| FR-09 | functional | `Delivery orders should use Carbon-aware delivery routing` | — |
| FR-10 | functional | `All reservations must be recorded in a Real-time Stock Reservation Ledger that can be audited per order.` | — |

### Non-functional

| ID | Expected kind | Source excerpt | KB link |
|---|---|---|---|
| NFR-01 | non_functional | `Availability queries must return in under 300 ms at the 95th percentile.` | — |
| NFR-02 | non_functional | `The inventory service must achieve 99.9% availability during peak trading periods.` | — |
| NFR-03 | non_functional | `The platform must sustain a Black Friday peak of 2,000 orders per minute without degradation.` | — |
| NFR-04 | non_functional | `every order must be traceable end to end from checkout through reservation to fulfilment` | Observability by Design |
| NFR-05 | non_functional | `APIs used by store devices must follow Zero Trust Security` | Zero Trust Security |
| NFR-06 | non_functional | `the storefront must fall back to last-known stock using the Circuit Breaker Pattern rather than failing checkout` | Design for Failure, Circuit Breaker Pattern |
| NFR-07 | non_functional **and** constraint *(ambiguity probe)* | `The new services must run on our existing Azure tenancy and respond within 300 ms.` | — |

### Constraints

| ID | Expected kind | Source excerpt | KB link |
|---|---|---|---|
| C-01 | constraint | `The solution must integrate with Manhattan Active OMS and Oracle Retail Xstore POS; neither may be replaced in this program.` | — |
| C-02 | constraint | `The Legacy Inventory Mainframe must be retired incrementally using the Strangler Fig Migration Pattern` | Strangler Fig Migration Pattern |
| C-03 | constraint | `All new inventory capabilities must follow API First Design` | API First Design |
| C-04 | constraint | `Stock change events must be published using Event-Driven Architecture` | Event-Driven Architecture |
| C-05 | constraint | `Customer data must remain in US data center regions.` | — |
| C-06 | constraint | `Total program budget is capped at $6M` | — |
| C-07 | constraint | `the pilot must not start during the November–December peak freeze` | — |

**Total: 31 intended requirements** (7 drivers, 10 functional, 7 non-functional, 7 constraints). C-06 and C-07 may come back as one combined proposal. NFR-07 may come back as one mixed proposal or as two separate ones. Either is acceptable, but record which.

### Probes that should NOT produce new requirements

| ID | Type | Text | Expected |
|---|---|---|---|
| N-01 | Out of scope | `RFID shelf tags are out of scope this year.` | Not proposed, or confidence < 0.5 |
| N-02 | Out of scope | `We may revisit marketplace sellers later, but nothing is planned.` | Not proposed, or confidence < 0.5 |
| N-03 | Background | the whole "Background" section (220 stores, 3 DCs, overnight batch) | Context only. It may be cited inside D-03, but must not become standalone requirements |
| N-04 | Duplicate | `no unit may be sold twice, so stock must be reserved at checkout` | Ideally merged with FR-02. A separate proposal counts as a "duplicate not caught" finding, not a failure |

## Gap analysis (after confirming all requirements)

Gap analysis compares each confirmed requirement with the business and technical capability registries using keyword overlap (threshold 0.34). It is advisory, and wording affects matches, so record exceptions as findings rather than failures.

**Expected "present"** (cited against an existing capability):

| Requirement | Likely matching capability |
|---|---|
| FR-01 | Inventory Management / Availability Management |
| FR-03 | Order Orchestration |
| FR-04 | BOPIS Fulfillment & Customer Pickup |
| FR-06 | Returns Inspection & Disposition |
| FR-08 | Demand Forecasting / Replenishment |

**Expected "missing"** (gap probes, none of which exist in the registry):

| Requirement | Probe name |
|---|---|
| FR-05 | Store Associate Task Management |
| FR-09 | Carbon-aware delivery routing |
| FR-10 | Real-time Stock Reservation Ledger |

## Pass criteria

| # | Criterion | Spec | Pass if |
|---|---|---|---|
| P1 | Recall | FR-002 | ≥ 28 of the 31 intended requirements are proposed (≥ 90%) |
| P2 | Kind accuracy | FR-002 | ≥ 85% of proposed items match the expected kind; an *(or …)* alternative counts as correct |
| P3 | Grounding | FR-007 | Every proposal is VERIFIED. Each UNVERIFIED proposal is a finding; if more than 2, it's a failure |
| P4 | KB linking | FR-005 / SC-005 | ≥ 90% of the 7 expected KB links appear — i.e. all 7 (6 of 7 = 86% is a marginal fail; record which link was missed) |
| P5 | Noise | — | N-01 and N-02 not proposed, or confidence < 0.5 |
| P6 | Latency | SC-003 / NFR-001 | Operation handle returned within 2 s; results ready within 60 s |
| P7 | Human-in-the-loop | FR-003 / FR-004 | Only confirmed items are on the design; the audit trail shows actor, timestamp, submission id and the edited flag |
| P8 | Gap analysis | ADP-zg3.4 | All 3 gap probes are "missing", and ≥ 4 of the 5 expected "present" items are cited |
| P9 | Structured form | FR-001 | Exactly 1 proposal: functional, VERIFIED, confidence 1.0 |

## Results log

Environment: _______  Date: _______  Tester: _______  LLM model: _______

| Measure | Result |
|---|---|
| Submit → handle (s) |  |
| Submit → results ready (s) |  |
| Proposals returned |  |
| Matched to an expected ID |  |
| UNVERIFIED count |  |
| KB links found (of 7) |  |

| Expected ID | Proposed? (Y/N) | Kind returned | Verified? | Confidence | Links returned | Notes |
|---|---|---|---|---|---|---|
| D-01 |  |  |  |  |  |  |
| … |  |  |  |  |  |  |

**Unexpected proposals** (not in the key):

| Proposal statement | Kind | Confidence | Assessment (noise / valid miss in key / hallucination) |
|---|---|---|---|

**Findings to file as beads:** _list each failed P-criterion or notable finding, with its operation_id_.
