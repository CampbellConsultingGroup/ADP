# Data Model: LLM-as-a-Judge Validation

**Branch**: `008-llm-as-judge` | **Date**: 2026-07-01  
**Source**: `src/adp/validation/models.py`

---

## `FindingSeverity` (StrEnum)

| Value | Meaning | Blocks gate? |
|---|---|---|
| `critical` | Mandatory standard violated or structural failure | Yes (if count > max_critical) |
| `major` | Significant gap or strong principle misalignment | Yes (if count > max_major) |
| `minor` | Non-blocking observation; best-practice deviation | Yes (if count > max_minor) |
| `advisory` | Finding without a verified citation; informational only | **Never** |

---

## `VerdictStatus` (StrEnum)

| Value | Meaning |
|---|---|
| `pass` | All gates passed; design compliant |
| `fail` | One or more gates failed |
| `indeterminate` | All LLM critics failed to run; gate could not be evaluated |
| `overridden` | Previously `fail`; a human reviewer overrode with justification |

---

## `Finding`

One identified issue or compliance observation produced by a critic.

| Field | Type | Required | Notes |
|---|---|---|---|
| `finding_id` | `str` | Yes | UUID4 |
| `operation_id` | `str` | Yes | Parent validation job |
| `critic_name` | `str` | Yes | e.g., `"standards"`, `"structural"` |
| `element_id` | `str \| None` | No | Design element this finding concerns; `None` for design-level findings |
| `severity` | `FindingSeverity` | Yes | Derived deterministically from score range |
| `description` | `str` | Yes | Human-readable description (max 400 chars) |
| `citation` | `CitationRef \| None` | No | Knowledge item cited; `None` for structural findings; `None` makes severity `advisory` |
| `score` | `float` | No | Critic's 0–1 score at the time this finding was raised |

---

## `GatingThreshold`

The threshold configuration in effect for a validation run. Versioned alongside the validation.

| Field | Type | Default | Notes |
|---|---|---|---|
| `max_critical` | `int` | 0 | Any critical finding fails the design |
| `max_major` | `int` | 3 | >3 major findings fails the design |
| `max_minor` | `int` | 10 | >10 minor findings fails the design |
| `version` | `str` | `"1.0.0"` | Threshold set version; snapshot is stored in the Verdict |

---

## `CriticOutput`

The raw output of one critic before aggregation.

| Field | Type | Notes |
|---|---|---|
| `critic_name` | `str` | One of the 5 critic names |
| `score` | `float \| None` | 0–1; `None` if critic failed to run |
| `findings` | `list[Finding]` | May be empty for a passing critic |
| `retrieved_knowledge_refs` | `list[str]` | `item_id@version` strings |
| `input_tokens` | `int` | 0 for structural critic |
| `output_tokens` | `int` | 0 for structural critic |
| `cost_usd` | `float` | 0 for structural critic |
| `latency_ms` | `float` | Critic wall-clock time |
| `error` | `str \| None` | Set if critic raised an exception |

---

## `Verdict`

The aggregated result of one validation run. Stored transiently in the operation store (TTL 24h).

| Field | Type | Required | Notes |
|---|---|---|---|
| `verdict_id` | `str` | Yes | UUID4 |
| `operation_id` | `str` | Yes | Parent job id |
| `design_id` | `str` | Yes | Design that was validated |
| `design_version` | `int` | Yes | Design version number at time of validation (NFR-002) |
| `status` | `VerdictStatus` | Yes | `pass` / `fail` / `indeterminate` / `overridden` |
| `composite_score` | `float \| None` | No | Mean of all LLM critic scores; `None` if indeterminate |
| `findings` | `list[Finding]` | Yes | All findings from all critics |
| `thresholds_snapshot` | `GatingThreshold` | Yes | Thresholds in effect at evaluation time |
| `overridden_by` | `str \| None` | No | Principal id of overriding reviewer |
| `override_at` | `datetime \| None` | No | UTC timestamp of override |
| `override_justification` | `str \| None` | No | Required non-empty string when status=overridden |
| `audit_entry_id` | `str \| None` | No | Audit trail entry from the override |
| `critic_outputs` | `list[CriticOutput]` | Yes | One per critic; for debugging and telemetry |
| `citations_present` | `bool` | Yes | True if at least one finding has a verified citation (ART-VII bridge) |

---

## `ValidationState` (TypedDict — internal pipeline state)

Threaded through the validation orchestration steps.

| Field | Type | Notes |
|---|---|---|
| `operation_id` | `str` | |
| `design_id` | `str` | |
| `design_version` | `int` | |
| `design` | `ArchitectureDescription` | Loaded at job start |
| `retrieved_knowledge` | `list[RetrievalResultEntry]` | From ADP-SPEC-005 |
| `structural_findings` | `list[Finding]` | From pre-check step |
| `structural_passed` | `bool` | If False, LLM critics are skipped |
| `critic_outputs` | `list[CriticOutput]` | Populated by LLM critics |
| `verdict` | `Verdict \| None` | Set after gating |
| `correlation_id` | `str \| None` | |
| `thresholds` | `GatingThreshold` | |

---

## Pipeline State Machine

```
INPUT: design_id, design_version, correlation_id
        │
        ▼
[Structural check — pure Python, fast]
  - Check all elements have satisfies links (FR-005 / ART-XI)
  - Check all Relationship.target ids resolve (FR-005)
  → findings if violations
  → structural_passed = (no critical structural findings)
        │
        ├─ structural_passed=False → skip LLM critics → go to AGGREGATE
        │
        └─ structural_passed=True ──┐
                                    │
        [Fan-out: asyncio.gather]   │
        ├── standards_critic()      │
        ├── principles_critic()     │
        ├── pattern_fit_critic()    │
        └── consistency_critic()   │
                    │               │
                    ▼               │
        [AGGREGATE] ←──────────────┘
          merge all findings + structural_findings
          compute composite_score
          evaluate citations_present
                    │
                    ▼
        [GATE — pure function, deterministic]
          gate(findings, thresholds) → pass/fail/indeterminate
                    │
                    ▼
        Verdict stored in operation_store
                    │
        ├── [architect accepts: no action needed for pass]
        │
        └── [reviewer overrides fail verdict]
                └── → Verdict.status = overridden
                    → AuditEntry written (ADP-SPEC-004)
```
