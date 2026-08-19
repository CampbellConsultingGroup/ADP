import React, { useEffect, useState } from "react";
import { useSubmitIntake, useAddRequirement, type RequirementKind } from "../api/intake";
import { useCreateDesign, useDesign } from "../api/designs";
import { useCapabilities, useLinkDesignToCapabilities } from "../api/business";

interface IntakeTextFormProps {
  // null until a design exists -- Intake is reachable with no design selected
  // (it's where one starts): the first submit creates the design, titled from
  // the Business Problem text, then submits intake against it in the same action.
  designId: string | null;
  // Fired once a design gets created by a submit that had no designId yet, so
  // the caller can adopt it (e.g. App.tsx's currentDesignId).
  onDesignCreated?: (designId: string) => void;
  // Fired once the whole submit (framing + known requirements + capability
  // links) succeeds.
  onSubmitted: (requirementCount: number, capabilityCount: number) => void;
}

interface DraftRequirement {
  id: string;
  statement: string;
  kind: RequirementKind;
}

// Only these two are selectable for now -- more kinds (constraint, driver)
// will be added later, per explicit product decision.
const KIND_OPTIONS: { value: RequirementKind; label: string }[] = [
  { value: "functional", label: "Functional" },
  { value: "non_functional", label: "Non-Functional" },
];

const KIND_COLORS: Record<string, string> = {
  functional: "var(--accent)",
  non_functional: "var(--biz)",
};

const labelStyle: React.CSSProperties = {
  display: "block",
  fontSize: 13,
  fontWeight: 600,
  color: "var(--ink-2)",
  margin: "0 0 4px",
};

const hintStyle: React.CSSProperties = {
  fontSize: 12,
  color: "var(--ink-3)",
  margin: "0 0 6px",
};

/**
 * Intake: Business Problem + Desired Outcome (required, persisted to the
 * canonical model) plus Known Requirements -- entered directly as a typed
 * list (statement + kind), not extracted by an LLM. Everything is queued
 * locally and saved together, in one action, when the form is submitted.
 */
export default function IntakeTextForm({ designId, onDesignCreated, onSubmitted }: IntakeTextFormProps): React.ReactElement {
  const [businessProblem, setBusinessProblem] = useState("");
  const [desiredOutcome, setDesiredOutcome] = useState("");
  const [requirements, setRequirements] = useState<DraftRequirement[]>([]);
  const [draftStatement, setDraftStatement] = useState("");
  const [draftKind, setDraftKind] = useState<RequirementKind>("functional");
  const [draftError, setDraftError] = useState("");
  const [selectedCapabilityIds, setSelectedCapabilityIds] = useState<string[]>([]);
  const [draftCapabilityId, setDraftCapabilityId] = useState("");
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [submitError, setSubmitError] = useState<string | null>(null);

  const createDesign = useCreateDesign();
  const submit = useSubmitIntake();
  const addRequirement = useAddRequirement();
  const capabilities = useCapabilities();
  const linkCapability = useLinkDesignToCapabilities();

  // Prefill Business Problem / Desired Outcome from the existing design when
  // opening Intake for a design that already has them recorded (e.g. via the
  // Designs screen's "Open" action) -- previously these always started blank,
  // discarding data that was already saved. `useDesign` is disabled while
  // designId is null (a not-yet-created design has nothing to prefill from).
  const existingDesign = useDesign(designId ?? "");
  const [prefilledFor, setPrefilledFor] = useState<string | null>(null);
  useEffect(() => {
    if (designId && designId !== prefilledFor && existingDesign.data) {
      setBusinessProblem(existingDesign.data.business_problem ?? "");
      setDesiredOutcome(existingDesign.data.desired_outcome ?? "");
      setPrefilledFor(designId);
    }
  }, [designId, existingDesign.data, prefilledFor]);

  const requiredFilled = businessProblem.trim().length > 0 && desiredOutcome.trim().length > 0;
  const canSubmit = requiredFilled && !isSubmitting;

  const allCapabilities = capabilities.data?.items ?? [];
  const availableCapabilities = allCapabilities.filter((c) => !selectedCapabilityIds.includes(c.id));
  const selectedCapabilities = selectedCapabilityIds
    .map((id) => allCapabilities.find((c) => c.id === id))
    .filter((c): c is NonNullable<typeof c> => c !== undefined);

  const handleAddRequirement = () => {
    const statement = draftStatement.trim();
    if (statement.length < 10) {
      setDraftError("Requirement must be at least 10 characters.");
      return;
    }
    setRequirements((prev) => [...prev, { id: crypto.randomUUID(), statement, kind: draftKind }]);
    setDraftStatement("");
    setDraftError("");
  };

  const handleRemoveRequirement = (id: string) => {
    setRequirements((prev) => prev.filter((r) => r.id !== id));
  };

  const handleAddCapability = () => {
    if (!draftCapabilityId) return;
    setSelectedCapabilityIds((prev) => [...prev, draftCapabilityId]);
    setDraftCapabilityId("");
  };

  const handleRemoveCapability = (id: string) => {
    setSelectedCapabilityIds((prev) => prev.filter((c) => c !== id));
  };

  const handleSubmit = async () => {
    setSubmitError(null);
    setIsSubmitting(true);
    try {
      let targetDesignId = designId;
      if (!targetDesignId) {
        // No design yet -- Intake is where one starts. Title it from the
        // Business Problem so it isn't just "Untitled" in the Designs list.
        const design = await createDesign.mutateAsync({
          title: businessProblem.trim().slice(0, 80),
        });
        targetDesignId = design.id;
        onDesignCreated?.(targetDesignId);
      }

      await submit.mutateAsync({
        designId: targetDesignId,
        mode: "bulk_text",
        text: "",
        business_problem: businessProblem,
        desired_outcome: desiredOutcome,
      });

      // Sequential, not Promise.all: each requirement's id is derived from
      // the design's current requirement count server-side, so concurrent
      // requests could race and collide on the same id.
      for (const req of requirements) {
        await addRequirement.mutateAsync({
          designId: targetDesignId,
          statement: req.statement,
          kind: req.kind,
        });
      }

      for (const capabilityId of selectedCapabilityIds) {
        try {
          await linkCapability.mutateAsync({ designId: targetDesignId, capabilityId });
        } catch (err) {
          // Already linked (e.g. re-submitting) isn't a failure worth
          // blocking the rest of the submit over.
          if ((err as { status?: number })?.status !== 409) throw err;
        }
      }

      const addedCount = requirements.length;
      const linkedCount = selectedCapabilityIds.length;
      setRequirements([]);
      setSelectedCapabilityIds([]);
      onSubmitted(addedCount, linkedCount);
    } catch {
      setSubmitError("Submission failed. Check the server logs and try again.");
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <div>
      {/* Business Problem — required */}
      <label style={labelStyle} htmlFor="intake-business-problem">
        Business Problem <span style={{ color: "var(--crit)" }}>*</span>
      </label>
      <p style={hintStyle}>What problem are we solving, and why does it matter?</p>
      <textarea
        id="intake-business-problem"
        className="ui-textarea"
        value={businessProblem}
        onChange={(e) => setBusinessProblem(e.target.value)}
        placeholder="e.g. Peak-hour checkout latency causes cart abandonment and lost revenue."
        rows={3}
      />

      {/* Desired Outcome — required */}
      <label style={{ ...labelStyle, marginTop: 14 }} htmlFor="intake-desired-outcome">
        Desired Outcome <span style={{ color: "var(--crit)" }}>*</span>
      </label>
      <p style={hintStyle}>What does success look like?</p>
      <textarea
        id="intake-desired-outcome"
        className="ui-textarea"
        value={desiredOutcome}
        onChange={(e) => setDesiredOutcome(e.target.value)}
        placeholder="e.g. Sub-second checkout sustained at 10,000 concurrent users."
        rows={3}
      />

      {/* Known Requirements — optional, typed list entered directly */}
      <label style={{ ...labelStyle, marginTop: 14 }} htmlFor="intake-known-requirement">
        Known Requirements <span style={{ color: "var(--ink-3)", fontWeight: 400 }}>(optional)</span>
      </label>
      <p style={hintStyle}>Any requirements you already know, each with a type — added to the list below.</p>

      <div style={{ display: "flex", gap: 8, alignItems: "flex-start" }}>
        <input
          id="intake-known-requirement"
          type="text"
          className="ui-input"
          style={{ flex: 1 }}
          value={draftStatement}
          onChange={(e) => { setDraftStatement(e.target.value); setDraftError(""); }}
          placeholder="e.g. The system must support single sign-on."
          onKeyDown={(e) => e.key === "Enter" && (e.preventDefault(), handleAddRequirement())}
        />
        <select
          className="ui-select"
          value={draftKind}
          onChange={(e) => setDraftKind(e.target.value as RequirementKind)}
          style={{ flexShrink: 0 }}
        >
          {KIND_OPTIONS.map((k) => <option key={k.value} value={k.value}>{k.label}</option>)}
        </select>
        <button
          type="button"
          onClick={handleAddRequirement}
          style={{
            padding: "8px 14px", background: "var(--surface-2)", color: "var(--ink)",
            border: "1px solid var(--border)", borderRadius: 4, cursor: "pointer",
            fontSize: 13, fontWeight: 600, flexShrink: 0,
          }}
        >
          Add
        </button>
      </div>
      {draftError && (
        <div style={{ fontSize: 12, color: "var(--crit)", marginTop: 4 }}>{draftError}</div>
      )}

      {requirements.length > 0 && (
        <ul style={{ listStyle: "none", margin: "10px 0 0", padding: 0 }}>
          {requirements.map((r) => (
            <li
              key={r.id}
              style={{ display: "flex", alignItems: "center", gap: 8, padding: "6px 8px", borderBottom: "1px solid var(--surface-2)" }}
            >
              <span
                style={{
                  flexShrink: 0, background: KIND_COLORS[r.kind] ?? "var(--ink-3)", color: "#fff",
                  fontSize: 10, fontWeight: "bold", padding: "2px 5px", borderRadius: 3,
                }}
              >
                {r.kind.replace("_", " ")}
              </span>
              <span style={{ fontSize: 13, flex: 1 }}>{r.statement}</span>
              <button
                type="button"
                onClick={() => handleRemoveRequirement(r.id)}
                title="Remove"
                style={{ background: "none", border: "none", cursor: "pointer", color: "var(--ink-3)", fontSize: 14, padding: 2 }}
              >
                ✕
              </button>
            </li>
          ))}
        </ul>
      )}

      {/* Business Capabilities Impacted — optional, one or more */}
      <label style={{ ...labelStyle, marginTop: 14 }} htmlFor="intake-capability">
        Business Capabilities Impacted <span style={{ color: "var(--ink-3)", fontWeight: 400 }}>(optional)</span>
      </label>
      <p style={hintStyle}>Which business capabilities does this design affect? — added to the list below.</p>

      <div style={{ display: "flex", gap: 8, alignItems: "center" }}>
        <select
          id="intake-capability"
          className="ui-select"
          style={{ flex: 1 }}
          value={draftCapabilityId}
          onChange={(e) => setDraftCapabilityId(e.target.value)}
        >
          <option value="">— select a capability —</option>
          {availableCapabilities.map((c) => (
            <option key={c.id} value={c.id}>{c.name}</option>
          ))}
        </select>
        <button
          type="button"
          onClick={handleAddCapability}
          disabled={!draftCapabilityId}
          style={{
            padding: "8px 14px", background: "var(--surface-2)", color: "var(--ink)",
            border: "1px solid var(--border)", borderRadius: 4,
            cursor: draftCapabilityId ? "pointer" : "not-allowed",
            fontSize: 13, fontWeight: 600, flexShrink: 0,
          }}
        >
          Add
        </button>
      </div>

      {selectedCapabilities.length > 0 && (
        <ul style={{ listStyle: "none", margin: "10px 0 0", padding: 0 }}>
          {selectedCapabilities.map((c) => (
            <li
              key={c.id}
              style={{ display: "flex", alignItems: "center", gap: 8, padding: "6px 8px", borderBottom: "1px solid var(--surface-2)" }}
            >
              <span style={{ fontSize: 13, flex: 1 }}>{c.name}</span>
              <button
                type="button"
                onClick={() => handleRemoveCapability(c.id)}
                title="Remove"
                style={{ background: "none", border: "none", cursor: "pointer", color: "var(--ink-3)", fontSize: 14, padding: 2 }}
              >
                ✕
              </button>
            </li>
          ))}
        </ul>
      )}

      {/* Submit */}
      <div style={{ marginTop: 16 }}>
        <button
          disabled={!canSubmit}
          onClick={handleSubmit}
          title={!requiredFilled ? "Business Problem and Desired Outcome are required" : undefined}
          style={{
            padding: "8px 18px",
            background: canSubmit ? "var(--accent)" : "var(--border)",
            color: "var(--surface)",
            border: "none",
            borderRadius: 4,
            cursor: canSubmit ? "pointer" : "not-allowed",
            fontSize: 14,
            fontWeight: 600,
          }}
        >
          {isSubmitting ? "Submitting..." : "Submit Intake"}
        </button>
      </div>

      {submitError && <div style={{ marginTop: 8, color: "var(--crit)", fontSize: 13 }}>{submitError}</div>}
    </div>
  );
}
