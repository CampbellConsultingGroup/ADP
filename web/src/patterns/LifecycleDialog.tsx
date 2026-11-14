/** Governed lifecycle actions for one pattern version (935 US2, FR-010, ART-VIII).
 *
 * Offers only the transitions the API reports as allowed (the client never re-encodes the state
 * machine). Every transition needs a reason and an explicit confirmation; the confirmation id is
 * generated when the user confirms and is stored in the version's lifecycle history. */

import { useState } from "react";
import { errorDetail, errorIssues, useTransition } from "../api/patterns";
import type { PatternIssue, PatternLifecycle, PatternVersionDetail } from "../api/patterns";
import IssueList from "./IssueList";
import { LIFECYCLE_LABELS, TRANSITION_VERBS } from "./labels";
import { useCanManagePatterns } from "./permissions";

function newConfirmationId(): string {
  const c = globalThis.crypto as Crypto | undefined;
  if (c && typeof c.randomUUID === "function") return c.randomUUID();
  return `confirm-${Date.now()}-${Math.random().toString(36).slice(2)}`;
}

const CONSEQUENCES: Partial<Record<PatternLifecycle, string>> = {
  proposed: "The definition becomes immutable; it can only be edited again by returning it to draft.",
  current:
    "This version becomes the governed current version. Any other current version of this pattern is " +
    "deprecated, and the Knowledge base entry that AI agents cite is updated to this version.",
  deprecated: "If no other version is current, the pattern is hidden from the Knowledge base.",
  decommissioned: "This is final: a decommissioned version can never change state again.",
};

export default function LifecycleDialog({ detail }: { detail: PatternVersionDetail }) {
  const canManage = useCanManagePatterns();
  const [target, setTarget] = useState<PatternLifecycle | null>(null);
  const [reason, setReason] = useState("");
  const [confirmed, setConfirmed] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [issues, setIssues] = useState<PatternIssue[]>([]);
  const transition = useTransition(detail.pattern_key, detail.version);

  if (!canManage || detail.allowed_transitions.length === 0) return null;

  const close = () => {
    setTarget(null);
    setReason("");
    setConfirmed(false);
    setError(null);
    setIssues([]);
  };

  const submit = async () => {
    if (!target) return;
    setError(null);
    setIssues([]);
    try {
      await transition.mutateAsync({ to: target, reason: reason.trim(), confirmation_id: newConfirmationId() });
      close();
    } catch (err) {
      const found = errorIssues(err);
      if (found.length) setIssues(found);
      setError(errorDetail(err));
    }
  };

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
      <div style={{ display: "flex", gap: 6, flexWrap: "wrap" }}>
        {detail.allowed_transitions.map((to) => (
          <button
            key={to}
            type="button"
            className={`ui-btn ui-btn-sm${to === "current" ? " ui-btn-primary" : to === "decommissioned" ? " ui-btn-danger" : ""}`}
            onClick={() => { close(); setTarget(to); }}
          >
            {TRANSITION_VERBS[to]}
          </button>
        ))}
      </div>
      {target && (
        <div role="dialog" aria-label={`${TRANSITION_VERBS[target]} ${detail.version}`} className="ui-card" style={{ padding: 12, display: "flex", flexDirection: "column", gap: 8 }}>
          <strong style={{ fontSize: 13 }}>
            {LIFECYCLE_LABELS[detail.lifecycle]} → {LIFECYCLE_LABELS[target]}
          </strong>
          {CONSEQUENCES[target] && <p style={{ margin: 0, fontSize: 12.5, color: "var(--ink-2)" }}>{CONSEQUENCES[target]}</p>}
          <label style={{ fontSize: 12.5, display: "flex", flexDirection: "column", gap: 4 }}>
            Reason (recorded in the lifecycle history)
            <textarea
              aria-label="Reason"
              className="ui-textarea"
              rows={3}
              maxLength={500}
              value={reason}
              onChange={(e) => setReason(e.target.value)}
            />
          </label>
          <label style={{ fontSize: 12.5, display: "flex", gap: 6, alignItems: "center" }}>
            <input type="checkbox" checked={confirmed} onChange={(e) => setConfirmed(e.target.checked)} />
            I confirm this change to {detail.pattern_key}@{detail.version}
          </label>
          {error && <div className="ui-alert crit" role="alert">{error}</div>}
          <IssueList issues={issues} title="Promotion blocked" />
          <div style={{ display: "flex", gap: 8 }}>
            <button
              type="button"
              className="ui-btn ui-btn-primary ui-btn-sm"
              disabled={!reason.trim() || !confirmed || transition.isPending}
              onClick={() => void submit()}
            >
              {transition.isPending ? "Saving…" : TRANSITION_VERBS[target]}
            </button>
            <button type="button" className="ui-btn ui-btn-sm" onClick={close}>Cancel</button>
          </div>
        </div>
      )}
    </div>
  );
}
