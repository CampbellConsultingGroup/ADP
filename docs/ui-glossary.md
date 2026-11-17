# UI glossary

The words the ADP interface uses, and what each one means. Use these in labels, buttons, headings
and messages so the same action is called the same thing on every screen (ADP-blp.50).

## Relationships between things

| Word | Meaning | Example |
|---|---|---|
| **Link** | A plain association between two things. It carries no data of its own. | Link an objective to a capability. |
| **Map** | A compliance assessment of one thing against a control. It carries a status, evidence and a date. | Map a control to an application: *Non-compliant*. |
| **Realized by** | Which applications deliver an application capability. | *Take Payment* is realized by *Adyen Payments*. |
| **Automates / Automated by** | Which business capability, value stream stage or value chain activity an AI agent carries out. | The triage agent automates *Classify Request*. |
| **Owns / Performs / Contributes** | An org unit's role for a business capability. | *Finance* owns *Financial Management*. |
| **Adopts** | A pattern applied to a domain, a set of applications or the whole portfolio. | The mesh pattern is adopted by *E-commerce*. |

Section headings for the things already associated use **Linked …** (*Linked objectives*); for
compliance they use **Mappings**.

## Actions

| Word | Meaning |
|---|---|
| **Add** | Create a new record on this screen. *Add framework*. |
| **Link** | Associate two existing records. |
| **Delete** | Destroy a record. Always confirmed, and the confirmation says what goes with it. |
| **Remove** | Take away a link or mapping. Both records stay. |
| **Save / Cancel** | Commit or abandon a form. Save is the primary button. |
| **Discard** | Abandon unsaved changes when leaving a form. |

Controls that save as soon as a value is chosen (a maturity or lifecycle select, a link picker)
have no Save button; the "Saved" confirmation at the bottom of the screen shows that they did.

## Names of things

Write these out in full in the interface. The short forms are fine in code and commit messages.

| Use | Not |
|---|---|
| Application Portfolio | APM |
| Technical capabilities | Tech caps |
| Application capabilities | App caps |
| Business capabilities | Biz caps, capabilities (when another kind is also on the screen) |
| New Design | Intake |
| Design Validation (Governance tab) | Compliance |
| Regulatory Mappings (application tab) | Regulatory Compliance |
| Risk Profile (application tab) | Risk & Compliance |

**Compliance** on its own means the Compliance screen: regulatory frameworks, their controls and
the mappings assessed against them.

## Status colours

| Colour | Meaning | Examples |
|---|---|---|
| Green | On track, healthy, in force | Current, Compliant, Achieved |
| Amber | Needs attention soon | At risk, Retiring, Partial |
| Red | Failing or blocked now | Non-compliant, Non-conformant, High risk |
| Blue | In progress, or cannot be judged yet | Proposed, Indeterminate |
| Grey | Inactive or ended; nothing to do | Draft, Decommissioned, Abandoned, Not assessed |

Red is for things someone must act on. An ended state (decommissioned, abandoned, retired) is grey.
