/** Create an adoption: pattern, name, scope (domain / application set / portfolio), optional
 * version pin (936 US2, FR-001). Pins are added on the adoption page. */

import { useState } from "react";
import { errorDetail, useApplicationChoices, useCreateAdoption, usePatternFamilies } from "../api/patterns";
import type { Adoption, ScopeType } from "../api/patterns";
import { useDomains } from "../api/business";
import { SCOPE_LABELS } from "./labels";

export default function AdoptionForm({ onCreated, onCancel }: { onCreated: (a: Adoption) => void; onCancel: () => void }) {
  const { families } = usePatternFamilies();
  const domains = useDomains();
  const apps = useApplicationChoices();
  const create = useCreateAdoption();
  const [patternKey, setPatternKey] = useState("");
  const [name, setName] = useState("");
  const [scopeType, setScopeType] = useState<ScopeType>("business_domain");
  const [domain, setDomain] = useState("");
  const [members, setMembers] = useState<string[]>([]);
  const [version, setVersion] = useState("");
  const [error, setError] = useState<string | null>(null);
  const family = families.find((f) => f.key === patternKey);

  const valid =
    !!patternKey && !!name.trim() &&
    (scopeType !== "business_domain" || !!domain) &&
    (scopeType !== "application_set" || members.length > 0);

  const submit = async () => {
    setError(null);
    try {
      const adoption = await create.mutateAsync({
        pattern_key: patternKey,
        name: name.trim(),
        scope_type: scopeType,
        scope_ref: scopeType === "business_domain" ? domain : null,
        member_ids: scopeType === "application_set" ? members : [],
        pinned_version: version || null,
      });
      onCreated(adoption);
    } catch (err) {
      setError(errorDetail(err));
    }
  };

  const row: React.CSSProperties = { display: "flex", flexDirection: "column", gap: 4, fontSize: 12.5 };
  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 10, maxWidth: 560 }}>
      <label style={row}>
        Pattern
        <select aria-label="Pattern" value={patternKey} onChange={(e) => { setPatternKey(e.target.value); setVersion(""); }}>
          <option value="">Choose…</option>
          {families.map((f) => <option key={f.key} value={f.key}>{f.name} ({f.key})</option>)}
        </select>
      </label>
      <label style={row}>
        Name
        <input aria-label="Adoption name" value={name} maxLength={120} onChange={(e) => setName(e.target.value)} />
      </label>
      <label style={row}>
        Scope
        <select aria-label="Scope type" value={scopeType} onChange={(e) => setScopeType(e.target.value as ScopeType)}>
          {(Object.keys(SCOPE_LABELS) as ScopeType[]).map((s) => <option key={s} value={s}>{SCOPE_LABELS[s]}</option>)}
        </select>
      </label>
      {scopeType === "business_domain" && (
        <label style={row}>
          Business domain
          <select aria-label="Business domain" value={domain} onChange={(e) => setDomain(e.target.value)}>
            <option value="">Choose…</option>
            {(domains.data?.items ?? []).map((d) => <option key={d.id} value={d.id}>{d.name}</option>)}
          </select>
        </label>
      )}
      {scopeType === "application_set" && (
        <label style={row}>
          Applications
          <select
            aria-label="Applications"
            multiple
            size={8}
            value={members}
            onChange={(e) => setMembers(Array.from(e.target.selectedOptions, (o) => o.value))}
          >
            {(apps.data ?? []).map((a) => <option key={a.id} value={a.id}>{a.name}</option>)}
          </select>
        </label>
      )}
      <label style={row}>
        Version
        <select aria-label="Version" value={version} onChange={(e) => setVersion(e.target.value)}>
          <option value="">Follow the current version</option>
          {(family?.versions ?? []).map((v) => <option key={v} value={v}>Pin {v}</option>)}
        </select>
      </label>
      {error && <div className="ui-alert crit" role="alert">{error}</div>}
      <div style={{ display: "flex", gap: 8 }}>
        <button type="button" className="ui-btn ui-btn-primary ui-btn-sm" disabled={!valid || create.isPending} onClick={() => void submit()}>
          Adopt pattern
        </button>
        <button type="button" className="ui-btn ui-btn-sm" onClick={onCancel}>Cancel</button>
      </div>
    </div>
  );
}
