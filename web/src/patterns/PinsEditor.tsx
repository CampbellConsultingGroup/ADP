/** Pin registry elements to the adopted pattern's roles (936 US2, FR-003). Pins are
 * authoritative: a pinned role binds exactly its pins (spec GT-8). */

import { useState } from "react";
import { errorDetail, useCandidates, useSetPins } from "../api/patterns";
import { ApiError } from "../api/client";
import type { Adoption, Pin, RoleBinding } from "../api/patterns";

function reasonsOf(err: unknown): string[] {
  if (err instanceof ApiError && err.body && typeof err.body === "object") {
    const detail = (err.body as { detail?: { reasons?: unknown } }).detail;
    if (detail && Array.isArray(detail.reasons)) return detail.reasons as string[];
  }
  return [];
}

export default function PinsEditor({ adoption, roles }: { adoption: Adoption; roles: RoleBinding[] }) {
  const [role, setRole] = useState<string>(roles[0]?.role_key ?? "");
  const [element, setElement] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [reasons, setReasons] = useState<string[]>([]);
  const candidates = useCandidates(adoption.id, role || null);
  const setPins = useSetPins(adoption.id);
  const roleType = roles.find((r) => r.role_key === role)?.element_type;

  const save = async (pins: Pin[]) => {
    setError(null);
    setReasons([]);
    try {
      await setPins.mutateAsync(pins);
      setElement("");
    } catch (err) {
      const found = reasonsOf(err);
      if (found.length) setReasons(found);
      else setError(errorDetail(err));
    }
  };

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
      {adoption.pins.length === 0 ? (
        <div style={{ fontSize: 12.5, color: "var(--ink-3)" }}>No pins: every role is bound by its selector.</div>
      ) : (
        <ul aria-label="Pins" style={{ margin: 0, paddingLeft: 18, fontSize: 12.5 }}>
          {adoption.pins.map((p) => (
            <li key={`${p.role_key}-${p.element_id}`}>
              {p.role_key} ← {candidates.data?.find((c) => c.id === p.element_id)?.name ?? p.element_id}{" "}
              <button
                type="button"
                className="ui-btn ui-btn-sm ui-btn-ghost"
                aria-label={`Remove pin ${p.element_id}`}
                onClick={() => void save(adoption.pins.filter((x) => x !== p))}
              >
                Remove
              </button>
            </li>
          ))}
        </ul>
      )}
      <div style={{ display: "flex", gap: 6, alignItems: "center", fontSize: 12.5 }}>
        <select aria-label="Pin role" value={role} onChange={(e) => { setRole(e.target.value); setElement(""); }}>
          {roles.map((r) => <option key={r.role_key} value={r.role_key}>{r.label}</option>)}
        </select>
        <select aria-label="Pin element" value={element} onChange={(e) => setElement(e.target.value)}>
          <option value="">Choose…</option>
          {(candidates.data ?? []).map((c) => <option key={c.id} value={c.id}>{c.name}</option>)}
        </select>
        <button
          type="button"
          className="ui-btn ui-btn-sm"
          disabled={!element || !roleType || setPins.isPending}
          onClick={() => roleType && void save([...adoption.pins, { role_key: role, element_type: roleType, element_id: element }])}
        >
          Pin
        </button>
      </div>
      {error && <div className="ui-alert crit" role="alert">{error}</div>}
      {reasons.length > 0 && (
        <ul className="ui-alert crit" role="alert" style={{ margin: 0 }}>
          {reasons.map((r) => <li key={r}>{r}</li>)}
        </ul>
      )}
    </div>
  );
}
