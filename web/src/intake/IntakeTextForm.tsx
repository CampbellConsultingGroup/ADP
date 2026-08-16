import React, { useState } from "react";
import { useSubmitIntake } from "../api/intake";
import { useLLMConfig } from "../api/config";
import ModelSelector from "./ModelSelector";

interface IntakeTextFormProps {
  designId: string;
  // extractionRequested is true when Known Requirements text was submitted (so
  // the caller can distinguish "nothing extracted" from "framing-only save").
  onOperationCreated: (operationId: string, extractionRequested: boolean) => void;
}

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
 * Guided intake (ADP-SPEC intake framing): three purpose-built inputs that feed
 * the recommendation system. Business Problem + Desired Outcome are required and
 * persisted to the canonical model; Known Requirements is optional free-text run
 * through the existing extraction pipeline.
 */
export default function IntakeTextForm({ designId, onOperationCreated }: IntakeTextFormProps): React.ReactElement {
  const [businessProblem, setBusinessProblem] = useState("");
  const [desiredOutcome, setDesiredOutcome] = useState("");
  const [knownRequirements, setKnownRequirements] = useState("");
  const { data: llmConfig } = useLLMConfig();
  const [selectedModel, setSelectedModel] = useState<string>(llmConfig?.extraction_model ?? "claude-sonnet-4-6");
  const submit = useSubmitIntake(designId);

  // Sync selected model with global config default when it loads
  React.useEffect(() => {
    if (llmConfig?.extraction_model && !submit.isPending) {
      setSelectedModel(llmConfig.extraction_model);
    }
  }, [llmConfig?.extraction_model]);

  const knownReqTooShort = knownRequirements.length > 0 && knownRequirements.length < 20;
  const hasKnownReq = knownRequirements.trim().length > 0;
  const hasApiKey = llmConfig?.api_key_configured ?? false;
  const requiredFilled = businessProblem.trim().length > 0 && desiredOutcome.trim().length > 0;
  const canSubmit = requiredFilled && !knownReqTooShort && !submit.isPending;

  const handleSubmit = () => {
    const extractionRequested = hasKnownReq;
    submit.mutate(
      {
        mode: "bulk_text",
        text: knownRequirements,
        business_problem: businessProblem,
        desired_outcome: desiredOutcome,
        model: selectedModel,
      },
      { onSuccess: (data) => onOperationCreated(data.operation_id, extractionRequested) },
    );
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

      {/* Known Requirements — optional */}
      <label style={{ ...labelStyle, marginTop: 14 }} htmlFor="intake-known-requirements">
        Known Requirements <span style={{ color: "var(--ink-3)", fontWeight: 400 }}>(optional)</span>
      </label>
      <p style={hintStyle}>Any requirements, user stories, or notes you already have — extracted into typed requirements.</p>
      <textarea
        id="intake-known-requirements"
        className="ui-textarea"
        value={knownRequirements}
        onChange={(e) => setKnownRequirements(e.target.value)}
        placeholder="Paste requirements, user stories, or notes… (optional; min 20 characters if provided)"
        rows={6}
      />
      {knownReqTooShort && (
        <div style={{ fontSize: 12, color: "var(--crit)", marginTop: 4 }}>
          If provided, known requirements must be at least 20 characters.
        </div>
      )}

      {/* Model selector + Submit button row */}
      <div style={{ display: "flex", alignItems: "center", gap: 12, marginTop: 12, flexWrap: "wrap" }}>
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
            flexShrink: 0,
          }}
        >
          {submit.isPending ? "Submitting..." : hasKnownReq ? "Submit & Extract" : "Submit Intake"}
        </button>
        <ModelSelector purpose="extraction" value={selectedModel} onChange={setSelectedModel} />
      </div>

      {hasKnownReq && !hasApiKey && (
        <div className="ui-alert warn" style={{ marginTop: 8, fontSize: 12 }}>
          ⚠ Set ADP_LLM_API_KEY to extract requirements from the Known Requirements text.
        </div>
      )}
      <div className="ui-alert info" style={{ marginTop: 8, fontSize: 12 }}>
        ℹ Source text is stored with this design for traceability
      </div>

      {submit.isError && <div style={{ marginTop: 8, color: "var(--crit)", fontSize: 13 }}>Submission failed. Check the server logs.</div>}
    </div>
  );
}
