# Feature Specification: Admin Screen for Managing AI Agent System Prompts

**Feature Branch**: `042-admin-prompt-management`
**Created**: 2026-07-24
**Status**: Draft
**Input**: User description: "ADP-t32 — Admin screen: manage/edit LLM system prompts for agents"

## Constitutional Articles Touched *(mandatory — ART-I)*

- **ART-I** — Spec-Driven Development: (always applies)
- **ART-IV** — Test-Driven Development: (always applies)
- **ART-V** — Security by Design: this feature introduces a new privileged surface (editing the instructions that steer every AI agent's behavior) and a new/adjusted permission gate — the threat model below is central, not incidental.
- **ART-VIII** — Human-in-the-Loop for Consequence: a prompt change alters live AI behavior platform-wide for every subsequent AI operation, so saving a change requires an explicit human confirmation step before it goes live — the same attributable-confirmation pattern ADP already uses for other consequential actions (e.g. export, verdict override).
- **ART-IX** — Provenance and Auditability: every prompt change must be attributable (who, when, what changed) and recoverable (prior versions viewable), matching the existing audit-entry pattern used elsewhere in ADP.
- **ART-III** — Everything is Machine-Readable: prompts are already stored as plain text/Markdown (one precedent: `docs/system_prompt_sr_bus_arch.md`); this feature extends that machine-readable, diffable storage to the remaining agents rather than introducing an opaque or binary format.

## Threat Model *(mandatory — ART-V)*

**Assets at risk**: the system prompts that govern every AI-backed feature (Chat Assistant, Recommendation engine, Intake extraction, Agent Review). A corrupted or maliciously altered prompt can silently degrade AI output quality, leak internal instructions, or be used to manipulate the AI into producing harmful, biased, or off-policy responses across every user of the platform — this is a platform-wide blast radius, not a single-record change.

**Trust boundaries crossed**: browser → API (an authenticated admin editing a prompt) → the AI orchestration layer (chat/recommendation/intake) that reads the prompt on every subsequent AI call.

**Abuse cases**:
- A user without genuine admin standing (e.g. an Enterprise Architect who is not intended to be a platform admin) edits a prompt to bias AI recommendations toward a preferred vendor or outcome → mitigated by requiring a distinct Administrator permission (not held by ordinary architect roles, per FR-009) and an audit trail identifying the actor.
- An admin makes an unintentional edit that breaks an agent (e.g. removes required output-format instructions the code parses) → mitigated by keeping a previous-versions history so the change can be identified and reverted, and by scoping this feature to read/edit only (no execution sandbox) so a bad edit is visible in behavior quickly rather than being validated away, keeping the blast radius bounded and reviewable.
- A compromised admin session is used to inject a prompt-injection-style instruction (e.g. "ignore all grounding requirements") → mitigated by the audit trail surfacing exactly what text changed and by ART-VII's grounding requirements living in code/citation validation (not solely in the editable prompt text), so an edited prompt cannot itself disable grounding enforcement.

**Residual risk**: this feature intentionally does not include a prompt-testing/execution sandbox in v1 (per the originating request) — an admin cannot "preview" the effect of an edit before it goes live. This is accepted because the target audience is a small, trusted admin population and the audit trail plus version history make bad edits diagnosable and recoverable after the fact.

## Clarifications

### Session 2026-07-24

- **Q: Should admin-screen access reuse the existing enterprise-architect-gated configuration permission, or introduce a genuinely distinct Administrator permission?** → **A:** A distinct Administrator permission, separate from and not implied by the architect roles. `ADPAdministrator` (the existing Keycloak group, which today falls through to the same role as Enterprise Architect) is the intended path to it. No ordinary architect role — including Enterprise Architect — gains admin-screen access solely by virtue of that role.
- **Q: Does a saved prompt change take effect immediately, or does it require a separate explicit confirmation step, matching ADP's existing human-in-the-loop pattern for other consequential actions (export, verdict override)?** → **A:** Requires an explicit, distinct confirmation step beyond the initial edit/save — the same attributable-confirmation pattern ADP already uses elsewhere. An edited-but-unconfirmed prompt never takes effect.
- **Q: Should the Recommendation engine's no-knowledge-base fallback prompt (`GENERATION_SYSTEM_PROMPT_NO_KB`) be a separate, independently editable agent registration distinct from the main Recommendation Generation prompt, or should editing one always write both?** → **A:** A separate, independently editable registration — six agents in v1 scope, not five. It runs on a distinct code path (no-KB fallback), and an admin tuning the main generation prompt should not be surprised that it silently changed the no-KB variant too, or vice versa.
- **Q: Does restoring a prior prompt version (Story 3 / FR-008) require the same explicit confirmation step as a normal edit (FR-010), or does it apply immediately since the text is already known-good?** → **A:** Yes — restore goes through the identical explicit-confirmation step as a manual edit. It still alters live AI behavior platform-wide, so it uses the same attributable-confirmation gate; there is exactly one path for "change the active prompt," whether the new text comes from the editor or from history.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - See every agent's current system prompt in one place (Priority: P1)

An authorized administrator opens the admin screen and sees a list of every AI agent ADP runs (Chat Assistant, Recommendation — generation, Recommendation — generation (no knowledge base), Recommendation — trade-off analysis, Intake extraction, Agent Review), each showing its current system prompt in full, with a note whether it is being read from a stored file or falling back to a built-in default.

**Why this priority**: this alone solves the problem statement's most acute pain — "there's no single place to see what prompt each agent is actually running" — with zero risk (it's read-only) and delivers value even before any editing capability exists.

**Independent Test**: can be fully tested by logging in as an authorized admin, navigating to the admin screen, and confirming the text shown for each agent exactly matches what that agent actually sends to the LLM (verified by comparing against the agent's current configured prompt).

**Acceptance Scenarios**:

1. **Given** an authorized administrator is signed in, **When** they open the admin screen, **Then** they see every registered agent listed with its full current system prompt visible.
2. **Given** an agent's prompt is currently coming from its fallback/default text (no stored override exists yet), **When** the admin views that agent's entry, **Then** the screen clearly indicates it is showing the default, not a saved override.
3. **Given** a user who is not an authorized administrator, **When** they attempt to reach the admin screen (directly, e.g. via URL), **Then** they are denied access and see no prompt content.

---

### User Story 2 - Edit an agent's system prompt, explicitly confirm it, and have it take effect without a redeploy (Priority: P2)

An authorized administrator edits the displayed system prompt for one agent, explicitly confirms they want the change to go live (a distinct, attributable confirmation step — not just clicking "Save"), and the very next AI operation for that agent uses the new prompt — with no code change or deployment required.

**Why this priority**: this is the core value proposition of the feature (today, tuning any of these prompts requires a code change and redeploy); it depends on Story 1 existing (there must be something to edit) but is the reason this feature is being built at all.

**Independent Test**: can be fully tested by editing one agent's prompt through the screen, explicitly confirming the change, then triggering that agent's AI operation (e.g. sending a Chat Assistant message) and confirming the new prompt text was used — without restarting or redeploying the application.

**Acceptance Scenarios**:

1. **Given** an authorized administrator has edited an agent's prompt text, **When** they attempt to save, **Then** the system requires a distinct, explicit confirmation step (surfacing that this changes live AI behavior platform-wide) before the change is committed.
2. **Given** an administrator completes the explicit confirmation, **When** the confirmation succeeds, **Then** the change is persisted and confirmed with a success indication, attributed to that administrator.
3. **Given** an administrator edits a prompt but does not complete the confirmation step, **When** they abandon the flow, **Then** the prior prompt remains active and unchanged.
4. **Given** a prompt change was confirmed, **When** the corresponding agent next runs an AI operation, **Then** it uses the newly confirmed prompt text, not the prior one.
5. **Given** an administrator attempts to save an empty prompt, **When** they submit the change, **Then** the system rejects the save with a clear validation message rather than allowing an agent to run with no instructions.
6. **Given** two administrators are editing the same agent's prompt concurrently, **When** the second one reaches the confirmation step, **Then** the system does not silently discard the first admin's change without at least surfacing that the underlying prompt changed since the second admin loaded it.

---

### User Story 3 - Review who changed what and revert a bad edit (Priority: P3)

An authorized administrator views the history of changes made to an agent's system prompt (who changed it, when, and what the text was before), so a problematic edit can be identified and undone.

**Why this priority**: this is the safety net that makes Story 2 trustworthy for ongoing operational use, but the platform can operate for an initial period on Story 1 + Story 2 alone if history/audit lands slightly later — it does not block the MVP's core value.

**Independent Test**: can be fully tested by making two successive edits to the same agent's prompt as different admin accounts, then confirming the history view shows both changes with correct attribution and timestamps, and that the prior prompt text can be recovered from the history.

**Acceptance Scenarios**:

1. **Given** an agent's prompt has been changed more than once, **When** an administrator views its history, **Then** they see every prior version with who made the change and when.
2. **Given** an administrator chooses to restore a prior version, **When** they complete the same explicit confirmation step required for a normal edit (FR-010), **Then** that version becomes the agent's active prompt again (itself recorded as a new history entry, not a silent rewrite of the past); an unconfirmed restore attempt has no effect.

---

### Edge Cases

- What happens when an agent's prompt-source file exists on disk but is unreadable (permissions, corrupted encoding)? The screen must show the fallback/default explicitly rather than crashing, and must not let the admin's next save silently write over a broken state they never actually saw.
- How does the system handle an admin navigating away mid-edit with unsaved changes? The system should warn before discarding unsaved edits.
- What happens if the audit/history storage itself is unavailable when an edit is saved? The prompt change and its audit record must succeed or fail together — a prompt must never take effect without a corresponding attributable history entry (this is the ART-IX guarantee this feature depends on).
- What happens when a brand-new agent is added to the codebase after this feature ships? It should appear in the admin screen automatically (or via a small registration step) rather than requiring this feature to be rebuilt per agent.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: System MUST provide a screen, reachable only by authorized administrators, listing every AI agent's current system prompt in full.
- **FR-002**: System MUST clearly distinguish, per agent, whether the displayed prompt is a saved override or the agent's built-in default/fallback.
- **FR-003**: Authorized administrators MUST be able to edit a new system prompt for any listed agent and submit it for the confirmation step in FR-010.
- **FR-004**: System MUST reject a save that would leave an agent with an empty or whitespace-only prompt.
- **FR-005**: System MUST apply a saved prompt change to the corresponding agent's subsequent AI operations without requiring a code deployment or process restart.
- **FR-006**: System MUST record, for every prompt change, who made it, when, and the full text before and after the change.
- **FR-007**: Authorized administrators MUST be able to view the full change history for any agent's prompt.
- **FR-008**: Authorized administrators MUST be able to restore a prior version of a prompt as the new active prompt, subject to the same explicit confirmation step required in FR-010, and doing so MUST itself be recorded as a new, attributed history entry.
- **FR-009**: System MUST deny access to the admin screen and its underlying data to any user who does not hold a distinct Administrator permission — separate from, and not implied by, the existing Enterprise/Solution/Technical Architect roles. Membership in the platform's existing `ADPAdministrator` group is the intended path to this permission, but ordinary architect roles (including Enterprise Architect) MUST NOT gain admin-screen access solely by virtue of their architect role.
- **FR-010**: System MUST require an authorized administrator to complete an explicit, distinct confirmation step — beyond the initial edit/save action — before a prompt change takes effect, matching the platform's existing human-in-the-loop confirmation pattern for other consequential actions (e.g. export, verdict override). An edit that is not explicitly confirmed MUST NOT take effect. This confirmation requirement applies uniformly to both a manual edit (FR-003) and a restore of a prior version (FR-008) — there is one confirmation gate for "change the active prompt," regardless of where the new text originates.
- **FR-011**: System MUST warn an administrator before discarding unsaved edits when navigating away from an in-progress edit.
- **FR-012**: System MUST surface a warning (not silently overwrite) if the underlying prompt has changed since the current editor loaded it, before allowing a save to proceed.

### Key Entities *(include if feature involves data)*

- **Agent Prompt Registration**: represents one AI agent's system-prompt slot (e.g. "Chat Assistant", "Recommendation — Generation", "Intake Extraction"). Attributes: a stable identifier, a display name, its built-in fallback text, and its currently active prompt text (which may equal the fallback if never overridden).
- **Prompt Change Record**: represents one saved edit to an Agent Prompt Registration. Attributes: which agent, the actor who made the change, a timestamp, the full prior text, and the full new text. Ordered per-agent to reconstruct history and support restore.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: An administrator can find the current system prompt for any of the platform's AI agents in under 30 seconds, without reading source code.
- **SC-002**: A prompt tuning change that previously required a code change and deployment (historically on the order of tens of minutes to hours end-to-end) can be made and take effect in under 2 minutes.
- **SC-003**: 100% of prompt changes are attributable to a specific administrator and timestamp, with zero changes able to occur without a corresponding history entry.
- **SC-004**: An administrator can identify who made a specific prompt change and revert to the prior version in under 5 minutes, without engineering assistance.

## Assumptions

- The set of AI agents in scope for v1 is six registrations: the four enumerated in the originating request (Chat Assistant, Recommendation generation, Recommendation trade-off, Intake extraction), the Recommendation engine's no-knowledge-base fallback prompt as its own independently editable registration (a distinct code path from the main generation prompt, per Clarifications), and generalizing Agent Review's existing file-backed pattern so it participates in the same screen — not every future AI feature needs to be anticipated now; new agents can be added to the registration set as a small follow-up each time one ships.
- "Take effect without a redeploy" means the running application picks up the new prompt on its next use (e.g. on next read, or via an in-memory cache with a short/no TTL) — it does not require sub-second propagation or multi-instance cache invalidation guarantees beyond what the platform's existing caching patterns (e.g. the 5-minute JWKS cache) already establish as acceptable staleness windows elsewhere in the system.
- This feature does not include a prompt-testing or "dry run" sandbox in v1 (explicitly out of scope per the originating request); an admin previews the effect of a change by using the live agent afterward.
- No prompt-content validation beyond non-empty is required in v1 (e.g. no linting for required placeholders/output-format instructions) — a bad-but-non-empty edit is caught via the history/revert safety net (Story 3), not prevented at save time.
- Existing ADP conventions are reused rather than reinvented: the audit-entry style already used for other mutations, and the explicit-confirmation pattern already used for other consequential actions (export, verdict override).
- The Administrator permission (FR-009) is new — today the `ADPAdministrator` Keycloak group maps onto the same role as Enterprise Architect, with no distinct permission tier. This feature is expected to introduce a new permission distinct from the existing architect-role permissions, and to change how the `ADPAdministrator` group is mapped so it carries that new permission instead of (or in addition to) folding into Enterprise Architect — the exact mechanism is a planning-phase decision, not dictated here.
