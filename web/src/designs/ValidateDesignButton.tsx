/**
 * ValidateDesignButton — the minimal frontend trigger for LLM-as-Judge validation
 * (ADP-SPEC-008 / ADP-3ei). An endpoint nobody calls captures nothing, so this is
 * the smallest viable way to actually exercise the pipeline: run it, see the
 * verdict + findings, and override a FAIL verdict inline. Styled like
 * LifecycleTransitionButton — one row action, no new screen or nav entry.
 */
import React, { useState } from "react";
import { useStartValidation, useValidationStatus, useOverrideVerdict } from "../api/validate";
import { Button, StatusBadge, type BadgeTone } from "../ui";

interface ValidateDesignButtonProps {
  designId: string;
}

const STATUS_TONE: Record<string, BadgeTone> = {
  pass: "good",
  fail: "crit",
  indeterminate: "warn",
  overridden: "info",
};

export default function ValidateDesignButton({
  designId,
}: ValidateDesignButtonProps): React.ReactElement {
  const [open, setOpen] = useState(false);
  const [operationId, setOperationId] = useState<string | null>(null);
  const [justification, setJustification] = useState("");

  const start = useStartValidation(designId);
  const { data: status } = useValidationStatus(designId, operationId);
  const override = useOverrideVerdict(designId, operationId ?? "");

  const handleRun = () => {
    start.mutate({}, { onSuccess: (data) => setOperationId(data.operation_id) });
  };

  const handleOverride = () => {
    if (!justification.trim()) return;
    override.mutate({ justification }, { onSuccess: () => setJustification("") });
  };

  const verdict = status?.verdict ?? null;
  const isRunning = status?.status === "pending" || status?.status === "running";

  return (
    <div style={{ position: "relative", display: "inline-block" }}>
      <Button size="sm" onClick={() => setOpen((o) => !o)}>Validate ▾</Button>

      {open && (
        <div className="ui-menu" style={{ right: 0, top: "100%", marginTop: 4, width: 300, padding: 14 }}>
          <div style={{ fontSize: 13, fontWeight: 600, marginBottom: 10, color: "var(--ink)" }}>
            LLM-as-Judge Validation
          </div>

          {!operationId && (
            <Button variant="primary" size="sm" style={{ width: "100%" }} onClick={handleRun} disabled={start.isPending}>
              {start.isPending ? "Starting…" : "Run Validation"}
            </Button>
          )}

          {operationId && isRunning && (
            <div style={{ fontSize: 12, color: "var(--ink-3)" }}>Running…</div>
          )}

          {operationId && status?.status === "failed" && (
            <div style={{ fontSize: 12, color: "var(--crit)" }}>
              Validation failed: {status.error_description}
            </div>
          )}

          {verdict && (
            <div>
              <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 8 }}>
                <StatusBadge tone={STATUS_TONE[verdict.status] ?? "neutral"}>
                  {verdict.status}
                </StatusBadge>
                <span style={{ fontSize: 12, color: "var(--ink-3)" }}>
                  {verdict.findings.length} finding{verdict.findings.length !== 1 ? "s" : ""}
                </span>
              </div>

              {verdict.findings.length > 0 && (
                <ul style={{ margin: "0 0 10px", padding: 0, listStyle: "none", maxHeight: 160, overflowY: "auto" }}>
                  {verdict.findings.map((f) => (
                    <li key={f.finding_id} style={{ fontSize: 12, marginBottom: 6, color: "var(--ink-2)" }}>
                      <strong>{f.severity}</strong> ({f.critic_name}): {f.description}
                    </li>
                  ))}
                </ul>
              )}

              {verdict.status === "fail" && (
                <div>
                  <label className="ui-label" htmlFor="validate-override-justification">
                    Override justification
                  </label>
                  <textarea
                    id="validate-override-justification"
                    className="ui-textarea"
                    value={justification}
                    onChange={(e) => setJustification(e.target.value)}
                    rows={2}
                  />
                  {override.isError && (
                    <div style={{ fontSize: 12, color: "var(--crit)", marginTop: 4 }}>
                      {override.error?.message}
                    </div>
                  )}
                  <Button
                    variant="primary"
                    size="sm"
                    style={{ width: "100%", marginTop: 6 }}
                    onClick={handleOverride}
                    disabled={override.isPending || !justification.trim()}
                  >
                    {override.isPending ? "Overriding…" : "Override Verdict"}
                  </Button>
                </div>
              )}

              {verdict.status === "overridden" && (
                <div style={{ fontSize: 12, color: "var(--ink-3)" }}>
                  Overridden by {verdict.overridden_by}: {verdict.override_justification}
                </div>
              )}
            </div>
          )}

          <Button size="sm" style={{ width: "100%", marginTop: 10 }} onClick={() => setOpen(false)}>
            Close
          </Button>
        </div>
      )}
    </div>
  );
}
