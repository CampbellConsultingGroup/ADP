# Feature Specification: Capability Model Analysis — roll-ups, impact, gaps and overlaps

**Feature Branch**: `938-capability-model-analysis`
**Created**: 2026-11-15
**Status**: Draft
**Bead**: ADP-6et.2 (spec B of 2 in epic ADP-6et)
**Input**: User description: "spec ADP-6et.2". The bead reads: "Roll-ups of health/cost/risk from leaf links up the business tree; transitive impact (tech cap EOL -> exposed business caps); gap/overlap/rationalization (business L3 realized by >1 app); derived business->technology view; decide technical capability end-of-life source." The worked Store POS example and the mapping guidance are in ADP-6et's notes.

## Background and Resolved Decisions

Spec 937 (ADP-6et.1) stored the three-layer capability model:

> Business capability L3 → Application capability L3 → Technical capability L2 or L3, with each application capability L3 **realized by** one or more applications.

It showed those links and one derived warning (an application capability L3 with no technical capability). This spec builds the analysis the links make possible. Everything it computes is **derived on read and never stored**.

The user's Store POS example defines what the feature must do:
- **Roll-up**: a poor technical-health score on the Store POS application shows "In-Store Transaction Management" (L2) and "Sales & Customer Transactions" (L1) as at risk.
- **Impact**: if "Local Data Store with Offline Sync" reaches end of life, the chain shows that "Process Checkout" is exposed.
- **Overlap**: if e-commerce has its own "Apply Promotions" application capability, two applications realize the same business capability. That is a rationalization candidate.

Decisions confirmed with the user (2026-11-15):

| # | Decision |
|---|---|
| D1 | **Technical capabilities get a lifecycle.** Each has a lifecycle status and an optional end-of-life date, set by architects. Impact analysis starts from these. Application end-of-support dates are not used as a substitute. |
| D2 | **Roll-ups use the worst case plus the spread.** A parent shows the worst value among its leaves, plus a count of leaves in each band, so one weak leaf is neither hidden nor overstated. This matches ADP's health rubric and derived compliance status. |
| D3 | **The analysis extends existing screens.** There is no new navigation entry: <br>• the Business capability heat map gains health, risk, cost and technology-exposure metrics; <br>• technical capabilities gain the lifecycle fields and an Impact panel; <br>• Applications → Capabilities gains gap and overlap views. |

Ground-truth checks against the code (migration head `046`):

| # | Fact | Consequence |
|---|---|---|
| GT-1 | Application health is `Application.health_score`, 1–5, computed from a six-dimension assessment (`src/adp/application/models.py:161`, `:259-286`). It is readable by everyone | The health roll-up uses it. Unassessed applications count as "unassessed", never as a score |
| GT-2 | Risk is a separate record per application: `security_posture` (strong/adequate/weak/unknown), `vulnerability_status` (none_known/open_low/open_high/critical), `end_of_support_date` and others (`models.py:366-388`). Reading it requires `READ_APPLICATION_RISK` (`src/adp/application/router.py:295-299`) | The risk roll-up is shown only to callers holding `READ_APPLICATION_RISK`. Everyone else sees "not available to you", never a blank or a zero |
| GT-3 | Cost is a separate record per application with a computed `tco`. Reading it, including the existing roll-up by business unit, requires `READ_APPLICATION_COST` (`router.py:405-425`) | The cost roll-up has the same gate. Every cost aggregate stays behind the permission, as the existing roll-up does |
| GT-4 | Technical capabilities have `name`, `description`, `parent_id`, `level` and `strategic_relevance`, and no lifecycle field (`src/adp/application/store.py:137-148`) | D1 needs one small additive migration |
| GT-5 | The Business heat map colours each capability by maturity or strategic relevance, both already on the capability, with no extra fetch (`web/src/business/CapabilityHeatMap.tsx`) | The new metrics need data the heat map doesn't load today. Switching between metrics must not need a fetch per switch |
| GT-6 | The "missing technical capability" gaps list already exists on Applications → Capabilities (`web/src/application/AppCapabilitiesView.tsx:82-102`) | The new gap and overlap views sit beside it in the same tab group |
| GT-7 | Business capability → application capability links are L3 to L3 only. Application capability → technical capability links go from an L3 to a technical L2 or L3 (937 FR rules) | Roll-ups start at business L3s. Impact from a technical L2 also covers links made to its L3 children |

## Clarifications

### Session 2026-11-15

- Q: Where does a technical capability's end-of-life come from? → A: A lifecycle status plus an optional end-of-life date on the technical capability itself (D1).
- Q: How do health and risk roll up to L2 and L1? → A: Worst case plus the spread (D2).
- Q: Where does the analysis appear in the UI? → A: On the existing screens (D3).
- Q: How is an application's risk band decided? → A: The FR-006 mapping, unchanged. It uses security posture, vulnerability status and end-of-support date only.
- Q: Do Retired or Sunset applications count in the roll-ups? → A: Retired applications are excluded, but the cell detail lists them so the stale link stays visible. Sunset applications still count.
- Q: How does cost show when one application supports several capabilities? → A: The full TCO of each distinct application behind the capability, labelled "not allocated". Nothing is split.

## Constitutional Articles Touched *(mandatory — ART-I)*

- **ART-I** — Spec-Driven Development: (always applies)
- **ART-IV** — Test-Driven Development: (always applies)
- **ART-II** — Single Source of Truth: every roll-up, impact list, gap and overlap is derived on read from the stored links and the existing application records. None of it is stored. The only new stored data is the technical capability lifecycle.
- **ART-V** — Security by Design: in scope. Cost and risk roll-ups are aggregates of permission-gated data and keep those gates (see Threat Model).
- **ART-IX** — Auditability: changes to a technical capability's lifecycle are logged with the actor, the old value and the new value (the domain-package precedent).
- **ART-XI** — Traceability: the derived business → technology view and impact analysis are traceability features.
- **ART-XIII** — Typed Contracts: lifecycle status is a closed set. Roll-up bands are closed sets.
- **ART-XV** — Schema Evolution: one reversible, additive migration (`047`).
- **ART-VII** (AI grounding): not engaged. No AI step is added.

## Threat Model *(mandatory — ART-V)*

**Assets at risk**: application cost (TCO) and risk data (security posture, vulnerability status, end-of-support dates), which are already restricted to holders of `READ_APPLICATION_COST` and `READ_APPLICATION_RISK`.

**Trust boundaries crossed**: browser → API only. No external service.

**Abuse cases**:
- A user without cost access reads the TCO of one application by finding a business capability that only that application supports, and reading its cost roll-up. → Every cost aggregate is withheld from callers without `READ_APPLICATION_COST`, whatever the number of applications behind it, as the existing cost-by-business-unit roll-up is.
- A user without risk access infers risk from the impact or overlap views. → Impact analysis uses only technical capability lifecycle, which is not sensitive. Overlap uses only link structure. Neither includes risk fields.
- A user without risk access sees a "low risk" band because their gated data was read as empty. → Withheld data is shown as "not available to you", never as a low value or as zero.

**Residual risk**: the structure of the model (which applications realize which capabilities) is visible to every reader, as it already is in 937. This is accepted: it is not sensitive under the existing permission model.

## User Scenarios & Testing *(mandatory)*

### User Story 1 — See health, risk and cost rolled up the business capability tree (Priority: P1)

A business or enterprise architect opens the Business capability heat map and chooses **Application health**, **Application risk** or **Application cost** as the metric. Each business L3 is coloured from the applications behind it. Each L2 and L1 shows the worst value among its leaves, and a count of leaves in each band. In the POS example, Store POS has a poor health score, so "Process Checkout" and its siblings show poor health, and so do "In-Store Transaction Management" (L2) and "Sales & Customer Transactions" (L1).

**Why this priority**: the roll-up is the headline use of the three-layer model in the user's example, and the view most stakeholders will look at.

**Independent Test**: with the seeded POS chains, set Store POS's health assessment to a poor score. On the heat map, choose Application health. The five POS business L3s, their L2 and their L1 all show poor health. Each parent's spread counts its leaves correctly.

**Acceptance Scenarios**:

1. **Given** a business L3 linked to application capabilities realized by applications A (health 2) and B (health 4), **When** the health metric is shown, **Then** the L3 shows health 2 (worst) and a spread of one application at 2 and one at 4.
2. **Given** an L2 with three L3 children showing health 2, 4 and "no data", **When** the health metric is shown, **Then** the L2 shows 2, with a spread of one leaf at 2, one at 4 and one with no data.
3. **Given** a business L3 with no application capability linked, or whose application capabilities have no realizing application, **When** any roll-up metric is shown, **Then** the L3 shows "no data", not a score, and parents count it in "no data".
4. **Given** an application that has never been assessed, **When** health is shown, **Then** it counts as "unassessed" in the spread and does not set the worst value.
5. **Given** a caller with `READ_APPLICATION_RISK`, **When** they choose the risk metric, **Then** each L3 shows the worst risk band of its applications (see FR-006). **Given** a caller without it, **Then** the risk metric is shown as not available to them, with no colours and no counts.
6. **Given** a caller with `READ_APPLICATION_COST`, **When** they choose the cost metric, **Then** each capability shows the total TCO of the distinct applications behind its leaves, each application counted once per capability, labelled as not allocated. **Given** a caller without it, **Then** the cost metric is not available to them.
7. **Given** the heat map is open, **When** the user switches between the health, risk, cost and existing metrics, **Then** the colours change without a visible reload.
8. **Given** any roll-up cell, **When** the user hovers over or focuses it, **Then** they see which applications (and through which application capabilities) produced the value.
9. **Given** a business L3 realized by application A (active, health 4) and application B (Retired, health 1), **When** health is shown, **Then** the L3 shows 4, and its detail lists B as excluded (retired). **Given** B is Sunset instead, **Then** the L3 shows 1.

---

### User Story 2 — Record a technical capability's lifecycle (Priority: P1)

A technical or enterprise architect sets a technical capability's lifecycle status and, optionally, its end-of-life date. For example, "Local Data Store with Offline Sync" is set to Retiring with an end-of-life date of 2027-06-30.

**Why this priority**: impact analysis and technology exposure (User Stories 3 and 4) have no starting point without it.

**Independent Test**: edit a technical capability's lifecycle and end-of-life date, reload, and see the values. A reviewer sees them but cannot change them.

**Acceptance Scenarios**:

1. **Given** an existing technical capability, **When** the migration runs, **Then** its lifecycle status is "Current" and it has no end-of-life date. No existing data changes.
2. **Given** a user with `WRITE_APPLICATION`, **When** they set the status to Retiring with an end-of-life date, **Then** both are saved and shown on the technical capability.
3. **Given** a user without `WRITE_APPLICATION`, **When** they view a technical capability, **Then** they see its lifecycle but have no control to change it.
4. **Given** a status of Retired, **When** no end-of-life date is given, **Then** the save still succeeds. The date is optional for every status.
5. **Given** an end-of-life date in the past and a status of Current or Emerging, **When** the capability is shown, **Then** it is flagged as past its end-of-life date. The flag is derived and does not change the status.

---

### User Story 3 — See what a technical capability's end of life affects (Priority: P1)

The architect opens a technical capability and reads its **Impact** panel. The panel lists:
- the application capabilities that depend on it;
- the applications that realize them;
- the business capabilities those support, with their L2 and L1 ancestors.

In the POS example, "Local Data Store with Offline Sync" shows "Basket Calculation", realized by Store POS, supporting "Process Checkout" under "In-Store Transaction Management" and "Sales & Customer Transactions".

**Why this priority**: the user named it as a required use of the model. It needs a traversal from technical to business that no screen offers today.

**Independent Test**: with the seeded POS chains, open "Local Data Store with Offline Sync". The Impact panel names exactly Basket Calculation, Store POS and Process Checkout, with its ancestors.

**Acceptance Scenarios**:

1. **Given** a technical L3 linked to one application capability, **When** its Impact panel opens, **Then** it lists that application capability, its realizing applications, and every business L3 it supports, each with its L1 › L2 path.
2. **Given** a technical L2, **When** its Impact panel opens, **Then** it includes application capabilities linked to the L2 itself and to any of its L3 children, and says which technical capability each link is to.
3. **Given** a business capability reached through two different application capabilities, **When** the panel lists it, **Then** it appears once, with both routes shown.
4. **Given** a technical capability that no application capability depends on, **When** its Impact panel opens, **Then** it says nothing depends on it.
5. **Given** any listed item, **When** the user selects it, **Then** they go to that item on its own screen.

---

### User Story 4 — See which business capabilities are exposed to retiring technology (Priority: P2)

On the Business heat map, the architect chooses **Technology exposure**. Each business L3 is coloured by the worst lifecycle state among the technical capabilities it depends on through the application layer. Each L2 and L1 rolls up by worst case plus the spread. On a business L3, the architect can also see the full derived list of technical capabilities it depends on (the business → technology view).

**Why this priority**: it turns impact analysis around, from "what does this technology affect" to "where is the business exposed". It reuses User Stories 2 and 3.

**Independent Test**: set "Local Data Store with Offline Sync" to Retiring. Under Technology exposure, "Process Checkout", its L2 and its L1 show Retiring. The other four POS L3s stay Current.

**Acceptance Scenarios**:

1. **Given** a business L3 whose chain reaches technical capabilities that are Current and Retiring, **When** technology exposure is shown, **Then** the L3 shows Retiring.
2. **Given** a technical capability that is Current but past its end-of-life date, **When** exposure is computed, **Then** it counts as past end of life, which is the most severe band (see FR-012).
3. **Given** a technical capability with an end-of-life date within the next 12 months, **When** exposure is computed, **Then** it counts as at least Retiring, whatever its status.
4. **Given** a business L3, **When** the user expands its technology dependencies, **Then** they see each technical capability it depends on, with the application capability that links them and the technical capability's lifecycle.
5. **Given** a business L3 with no chain to any technical capability, **When** exposure is shown, **Then** it shows "no data".

---

### User Story 5 — Find gaps and overlaps to rationalize (Priority: P2)

On Applications → Capabilities, next to the existing "Missing technical capability" list, the architect opens:
- **Overlaps**: business L3s whose application capabilities are realized by more than one distinct application. For example, "Apply Promotions" served by both Store POS's "Price Rule Evaluation" and the e-commerce platform's own promotions capability. These are rationalization candidates.
- **Gaps**: business L3s with no application capability; application capability L3s with no business capability; and application capability L3s with no realizing application.
- **Shared**: application capability L3s that support three or more business capabilities. This view is informational and is not a problem in itself.

**Why this priority**: the user named overlap as a required use. Gaps follow from the same data at little extra cost.

**Independent Test**: seed an e-commerce application capability that supports "Apply Promotions". The Overlaps view lists "Apply Promotions" with both applications and both application capabilities. Removing the extra link clears it.

**Acceptance Scenarios**:

1. **Given** a business L3 supported by two application capabilities realized by different applications, **When** Overlaps is shown, **Then** the L3 is listed with each application and the application capability it acts through.
2. **Given** a business L3 supported by two application capabilities that are both realized only by the same application, **When** Overlaps is shown, **Then** the L3 is not listed. One application is not an overlap.
3. **Given** a business L3 with no application capability, **When** Gaps is shown, **Then** it is listed under "Business capabilities with no application capability", with its L1 › L2 path.
4. **Given** an application capability L3 with no business capability, or no realizing application, **When** Gaps is shown, **Then** it is listed under the matching heading.
5. **Given** an application capability L3 supporting three or more business capabilities, **When** Shared is shown, **Then** it is listed with the count and the business capabilities.
6. **Given** any listed item, **When** the user selects it, **Then** they go to that item on its own screen.
7. **Given** a reviewer without `WRITE_APPLICATION`, **When** they open these views, **Then** they see the same lists. The views are read-only for everyone.

---

### Edge Cases

- An application realizes an application capability that supports several business L3s under different L2s: the application counts once in each L3, and once in each ancestor's roll-up, never twice in the same capability.
- An application that is Retired still realizes an application capability: it does not count in the roll-ups, and the cell detail lists it as excluded (retired), so the stale link stays visible. Cleaning up the link is a governance task. A Sunset application still counts.
- A business L3 whose only contributing applications are Retired shows "no data", and its detail names the excluded applications.
- A business L1 or L2 with no L3 children: it shows "no data" for every roll-up metric.
- A business capability whose links were removed while the heat map is open: the next refresh reflects it. Nothing is cached in stored form.
- A technical capability is deleted: its links go with it (937 cascade rules), so it no longer appears in any impact or exposure result.
- An end-of-life date exactly today counts as past end of life.
- The estate has no application capabilities at all: every new metric shows "no data", the Impact panel says nothing depends on the capability, and Gaps lists every business L3. Nothing errors.
- A caller holds `READ_APPLICATION_COST` but not `READ_APPLICATION_RISK`, or the reverse: each metric follows its own gate independently.

## Requirements *(mandatory)*

### Functional Requirements

**Technical capability lifecycle (D1)**

- **FR-001**: Each technical capability MUST have a lifecycle status from the closed set Emerging, Current, Contained, Retiring, Retired, and MAY have an end-of-life date. Existing capabilities MUST default to Current with no date.
- **FR-002**: Users with `WRITE_APPLICATION` MUST be able to change a technical capability's lifecycle status and end-of-life date. Everyone who can read technical capabilities MUST see them.
- **FR-003**: Every change to a technical capability's lifecycle MUST be logged with the actor and the old and new values.
- **FR-004**: The lifecycle and end-of-life date MUST be included wherever technical capabilities are already exported.

**Roll-ups (D2)**

- **FR-005**: For each business L3, the set of **contributing applications** MUST be every distinct application, other than Retired applications, realizing any application capability linked to it. For each business L2 and L1, it MUST be the distinct union over its L3 descendants. Planned, active and sunset applications count. Retired applications MUST be listed as excluded in the capability's detail (FR-010).
- **FR-006**: The system MUST compute these roll-up metrics:
  - **Health**: the worst `health_score` among contributing applications, plus a count per score 1–5 and a count of unassessed applications.
  - **Risk**: the worst risk band among contributing applications, plus a count per band. Each application's band is derived from its risk record:
    - **High**: vulnerability status open_high or critical, or security posture weak, or end-of-support date already passed;
    - **Medium**: vulnerability status open_low, or security posture adequate, or end-of-support date within 12 months;
    - **Low**: security posture strong and vulnerability status none_known;
    - **Unknown**: anything else, including no risk record.

    Unknown never sets the worst band.
  - **Cost**: the sum of TCO over the distinct contributing applications, each counted once per capability, plus the number of applications with no cost record.
- **FR-007**: At an L2 or L1, the spread MUST be counted over its **leaf L3s**, not over applications. Each leaf is assigned its own worst value. This is what "one weak leaf is neither hidden nor overstated" means.
- **FR-008**: The risk metric MUST be returned only to callers holding `READ_APPLICATION_RISK`, and the cost metric only to callers holding `READ_APPLICATION_COST`. For anyone else the metric MUST be marked as unavailable to them, distinguishable from "no data", and MUST NOT leak a value, a colour or a count.
- **FR-009**: A capability with no contributing applications MUST show "no data" for health, risk and cost, never a score of zero or a best-case band.
- **FR-010**: Every roll-up value MUST let the user see what produced it: the contributing applications, the application capabilities they act through, and any Retired applications excluded from it.

**Impact and technology exposure**

- **FR-011**: For any technical capability, the system MUST list:
  - the application capabilities linked to it, or, for a technical L2, linked to it or to any of its children;
  - the applications realizing those application capabilities;
  - the business capabilities those support, each with its L1 › L2 path and each listed once, with every route that reaches it.
- **FR-012**: Each technical capability MUST have an **effective lifecycle band**, worst first:
  1. Past end of life: the end-of-life date is today or earlier, or the status is Retired.
  2. Retiring: the status is Retiring, or the end-of-life date is within 12 months.
  3. Contained.
  4. Current.
  5. Emerging.

  The band is derived, never stored.
- **FR-013**: For each business L3, technology exposure MUST be the worst effective band among the technical capabilities reached through its application capabilities (including the children of a linked technical L2). L2 and L1 MUST roll up by worst case plus the spread over leaves (FR-007).
- **FR-014**: For each business L3, the user MUST be able to see its derived technology dependencies: each technical capability, the application capability that links them, and its effective band. This view MUST be derived, never stored, and there MUST still be no direct business → technical link.

**Gaps and overlaps**

- **FR-015**: The system MUST list as overlaps the business L3s whose linked application capabilities are realized, in total, by two or more distinct applications. Each entry MUST name each application and the application capabilities it acts through.
- **FR-016**: The system MUST list these gaps:
  - business L3s with no linked application capability;
  - application capability L3s with no linked business capability;
  - application capability L3s with no realizing application.

  Each entry MUST show its L1 › L2 path.
- **FR-017**: The system MUST list as shared the application capability L3s linked to three or more business capabilities, with the count. Shared MUST be presented as informational, not as a problem.
- **FR-018**: Every item in the impact, exposure, gap, overlap and shared lists MUST navigate to that item on its own screen.

**Presentation (D3) and general**

- **FR-019**: The Business heat map MUST offer Health, Risk, Cost and Technology exposure as metrics alongside its existing ones. Switching between any of them MUST NOT require a separate request per switch.
- **FR-020**: The technical capability screen MUST show and (for writers) edit the lifecycle, and MUST show the Impact panel.
- **FR-021**: Applications → Capabilities MUST offer Overlaps, Gaps and Shared views beside the existing Missing technical capability view.
- **FR-022**: Nothing this spec computes (roll-ups, bands, impact, exposure, gaps, overlaps, shared) may be stored. A guard test MUST fail if a column or table for any of them is added.
- **FR-023**: The seed data MUST let every user story be demonstrated:
  - a poor health score on Store POS;
  - "Local Data Store with Offline Sync" set to Retiring with an end-of-life date;
  - an e-commerce application capability that also supports "Apply Promotions";
  - at least one business L3 with no application capability.

### Key Entities

- **Technical capability lifecycle** (new, stored): a status from Emerging / Current / Contained / Retiring / Retired, and an optional end-of-life date, on each technical capability.
- **Effective lifecycle band** (derived): a technical capability's status and date combined into one ordered band (FR-012).
- **Capability roll-up** (derived): per business capability and metric, the worst value, the spread over leaves, and the contributing applications.
- **Impact result** (derived): for one technical capability, the application capabilities, applications and business capabilities that depend on it, with routes.
- **Gap / overlap / shared entry** (derived): one finding about a business capability or application capability, with the items that cause it.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: With the seeded POS data, an architect can show the Store POS health problem rolled up to "Sales & Customer Transactions" in under 30 seconds from opening the Business screen.
- **SC-002**: With the seeded POS data, the Impact panel for "Local Data Store with Offline Sync" names exactly one application capability, one application and one business L3 (with its ancestors), no more and no fewer.
- **SC-003**: The Overlaps view lists "Apply Promotions" once the e-commerce link is seeded, and drops it within one refresh once the link is removed.
- **SC-004**: For a caller without cost or risk access, no response or screen in this feature exposes a cost figure or risk band. This is checked for every new view.
- **SC-005**: With an estate of 500 business capabilities, 500 application capabilities and 2,000 links, every view in this feature appears within 2 seconds, and switching heat-map metrics is immediate.
- **SC-006**: Every acceptance scenario above is covered by an automated test. Nothing derived appears in the database schema (guard test).

## Assumptions

- "Health" in the user's example means the existing application health score. A separate "technical health" score is not introduced.
- The risk bands in FR-006 map existing risk fields, confirmed with the user (Clarifications). The mapping is fixed. Making it editable is a follow-on, like the scoring-rubric admin (931).
- The 12-month horizon for "end of support soon" (risk) and "end of life soon" (exposure) is a fixed default. A configurable horizon is a follow-on.
- Cost is the TCO of the applications involved, not allocated across capabilities (confirmed with the user). An application supporting many capabilities shows its full TCO in each, and the UI labels this as not allocated, so L3 costs do not add up to their parent. Cost allocation needs data ADP doesn't have.
- Roll-ups use only the new layer: business L3 → application capability → applications. The older direct application ↔ business capability links (fit score) are not used, so the two never get mixed (937 D5).
- The "shared" threshold of three business capabilities is a fixed default.
- No new permission is needed. Reads follow existing gates. The lifecycle write uses the existing `WRITE_APPLICATION` rule for technical capabilities.

## Out of Scope (follow-ons)

- A Governance dashboard roll-up of these findings (like ADP-loz for patterns).
- History or trends of roll-ups and exposure over time.
- Editable risk-band mapping, horizon and shared threshold.
- Cost allocation across capabilities.
- Organization and region dimensions (ADP-55k).
- Teaching the EA pattern engine about application capabilities or technical lifecycle.
- Chat assistant and agent review tools over this analysis.
- Retiring or deriving the old direct application ↔ business / technical links.
