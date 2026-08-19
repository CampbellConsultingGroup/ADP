It's almost always a mix, and the mix is deliberate — words carry precision and accountability, pictures carry relationships and scannability. Neither alone tends to survive contact with an organization.

**Text-based capture**
- **Narrative statements** — mission/vision, a strategic narrative ("why now, why us, why this bet"). Good for alignment and buy-in, bad for traceability — you can't cross-reference a paragraph.
- **Objectives and key results (OKRs)** or **balanced scorecard objectives** — decompose the narrative into measurable statements tied to a time horizon. This is the layer that actually connects to execution, because each objective can be linked to owning teams and target metrics.
- **Strategic themes/pillars** — short labels (3-5 words) used as tags to filter everything else against ("operational excellence," "usage-based pricing," "embedded distribution"). These act as the taxonomy that pictures and OKRs both hang off of.

**Picture-based capture**
- **Strategy maps** (Kaplan & Norton) — cause-and-effect chains across financial/customer/process/learning perspectives, showing how an operational improvement is hypothesized to ladder up to a financial outcome. This is the classic "words wouldn't show the causality, a diagram does."
- **Business Model Canvas / Value Proposition Canvas** — spatial layout of value props, channels, cost/revenue structure. Captures the shape of the business model, not the intent to change it.
- **Wardley maps** — plot capabilities/components on an evolution axis (genesis → commodity) against a value chain. Distinctly useful for strategy because they show *where* to attack (attack undifferentiated commodity components with buy/outsource, invest custom build in genesis-stage differentiators) — words struggle to convey that positioning argument.
- **Capability heat maps** — a capability model with color overlays for investment priority or maturity gap. This is the picture that operationalizes the OKRs/themes onto the capability layer we talked about above.
- **Roadmaps/timelines** — sequencing view, usually the artifact furthest from "strategy" and closest to "plan," but often what people mean when they say "show me the strategy."

**Where the combination actually lands in practice**
Most mature strategy processes end up with a small stack: a short narrative (words, sets intent) → a strategy map or set of themes with measurable objectives (words + causal picture) → a heat-mapped capability/value-stream model (picture, operationalizes it) → a roadmap (picture, sequences it). The narrative is qualitative and rarely versioned tightly; everything below it benefits from being structured data, because that's what lets you regenerate the pictures from a single source instead of hand-maintaining slides.

That last point is probably the relevant one for ADP: if `StrategicObjective` is structured (theme, metric, target, horizon, linked capability/value-stream refs) rather than a text blob, the heat map and the strategy-map-style causal view become renderable outputs of the model instead of separate artifacts someone has to keep in sync by hand.

This mirrors the `StrategicObjective` shape from earlier — theme, owner, statement, metric/target/horizon, and the two capability/value-stream link fields as tag inputs since those are many-to-many relationships, not free text.

A couple of design notes worth calling out for when you build this for real in ADP: the capability and value-stream search-and-add fields should validate against your actual capability/value-stream registry rather than accept free text, otherwise you get theme drift (the same idea entered three different ways across objectives) — which defeats the point of making this structured. And target/metric are probably worth splitting into a typed value (number + unit) rather than the free-text "reduce by 40%" shown here, so the heat map can compute progress instead of just displaying a string.

