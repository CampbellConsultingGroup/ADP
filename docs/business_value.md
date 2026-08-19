Here's an equivalent rubric for **Business Value**, mirroring the same 5-column structure:

| Dimension | 1 — Minimal | 2 — Marginal | 3 — Moderate | 4 — Strong | 5 — Exceptional |
|---|---|---|---|---|---|
| **Strategic Alignment** | No connection to any stated strategic objective or theme. | Loosely related to strategy; connection is inferred, not documented. | Supports a secondary or lower-priority objective. | Directly supports a stated strategic objective. | Directly and measurably drives a top-priority strategic objective. |
| **Revenue / Cost Impact** | No identifiable financial impact, or net negative with no offsetting benefit. | Financial impact is assumed but unquantified. | Modest, quantified impact on revenue or cost. | Clear, quantified impact with a credible business case. | Material, quantified impact validated against actuals, not just projections. |
| **Customer / Stakeholder Impact** | No identifiable customer or stakeholder benefit. | Benefit is anecdotal or affects a very narrow group. | Improves experience or outcomes for a defined segment. | Measurably improves experience/outcomes for a broad or key segment. | Materially changes a key customer/stakeholder metric (satisfaction, retention, adoption) at scale. |
| **Competitive Differentiation** | Table stakes at best; absence would go unnoticed by the market. | Keeps pace with competitors; no distinct advantage. | Provides a modest edge in specific situations. | Provides a clear, defensible advantage in the market or industry. | Establishes a durable differentiator competitors can't easily replicate. |
| **Risk / Compliance Contribution** | Increases risk exposure or compliance burden with no offsetting value. | Neutral; neither reduces nor materially adds risk. | Modestly reduces a known risk or compliance gap. | Meaningfully reduces risk or closes a compliance gap. | Eliminates a significant risk or is required for regulatory/compliance standing. |
| **Evidence & Measurability** | Value is asserted with no supporting data or metric. | A metric exists but isn't tracked or reported. | Tracked informally; not reviewed on a regular cadence. | Tracked with a defined metric, reviewed on a regular cadence. | Tracked, reviewed, and tied to a target with demonstrated trend evidence. |

A couple of notes given how ADP already models this:

- This slots naturally next to the existing **strategic relevance / maturity scoring** on capabilities (Business domain, Layer 1) and would pair well with an objective's typed metric/target group in Strategy (Layer 0) — "Evidence & Measurability" above is really asking "does this objective's metric group exist and get updated," which ADP already captures structurally.
- If you want this to feed a rendered view (heat map, portfolio scatter like the TIME model HTML) rather than stay a static rubric, the six dimensions above map cleanly to typed fields — worth flagging as a candidate spec rather than free text, consistent with your "typed entity, not a slide" thesis.

Different logic, not the same rule — here's why.

**Health uses "lowest score wins" because it's a risk gate.** One critical dimension — no security patching, no one who can support it — can sink the whole system regardless of how good everything else is. A system with perfect documentation and a well-resourced team is still critical if it has a known exploitable vulnerability. The weakest link *is* the risk.

**Business value doesn't have that same failure-mode logic.** The dimensions are more independent signals of value, not risk gates. A capability can be exceptional on revenue impact and weak on competitive differentiation and still be genuinely valuable — a weak "differentiation" score shouldn't zero out real, measured revenue impact the way a critical vuln should zero out "health."

So I'd use an **average (likely weighted)** for Business Value, not a minimum:

| Approach | When it fits |
|---|---|
| **Simple average** | Treats all six dimensions as equally important contributors to value. Easiest to implement and explain. |
| **Weighted average** | Lets you say Strategic Alignment and Revenue/Cost Impact matter more than, say, Competitive Differentiation — closer to how EAs actually reason about value. Requires deciding and documenting weights. |
| **Minimum (like Health)** | Only makes sense if you want a "value gate" — e.g., no matter how strong everything else is, a total absence of Evidence & Measurability caps the score, because unmeasured value is unproven value. Worth considering as a *partial* rule, not the whole formula. |

If it were me, I'd lean weighted average with one exception: **Evidence & Measurability** could act as a soft cap rather than just another averaged input — an asserted-but-unmeasured value claim probably shouldn't score as "Strong" or "Exceptional" overall even if the other five dimensions are high, since the whole premise of ADP's model is that value should be a queryable, evidenced fact, not an assertion.

Given your STRAT-01 pattern of pure status-derivation functions in the store layer, this composite logic (weighted average + evidence cap) would fit the same shape — a pure, testable `compute_business_value_score()` alongside `compute_evolution_stage()` — rather than being computed ad hoc in the router.

A "soft cap" means: the overall score is still built from the weighted average of all six dimensions, but the **Evidence & Measurability** score puts a ceiling on how high that overall score is allowed to land — regardless of what the other five dimensions add up to.

The contrast is with a **hard cap / gate** (like Health's minimum), where one bad dimension *becomes* the whole score. A soft cap doesn't override the average — it just clips it from above.

**Mechanically, something like:**

1. Compute the weighted average of all six dimensions as normal → call it `raw_score`.
2. Look at the Evidence & Measurability score on its own.
3. `final_score = min(raw_score, cap(evidence_score))`

Where the cap table might look like:

| Evidence & Measurability score | Ceiling applied to overall score |
|---|---|
| 1 — Value asserted, no data | Overall capped at 2 (Marginal) |
| 2 — Metric exists, not tracked | Overall capped at 3 (Moderate) |
| 3 — Tracked informally | Overall capped at 4 (Strong) |
| 4 or 5 — Tracked and reviewed on cadence | No cap; raw average stands |

**Concrete example:** a capability scores 5 on Strategic Alignment, 5 on Revenue Impact, 4 on Customer Impact, 4 on Differentiation, 3 on Risk — a weighted average that lands around 4.3, "Strong." But if Evidence & Measurability is a 1 (someone just asserts the value, nothing tracked), the soft cap pulls the final score down to 2, "Marginal" — because you're not allowed to claim strong value you can't show evidence for, even though everything else about the case *looks* strong.

Why this fits ADP specifically: it mirrors the constitution's stance that a claim is only real once it's a typed, queryable fact rather than prose — an unmeasured value assertion is structurally the same problem as an AI proposal that hasn't been human-confirmed. The cap operationalizes "we don't trust the number until it's evidenced," the same way the confirm/reject gate says "we don't trust the write until it's confirmed."