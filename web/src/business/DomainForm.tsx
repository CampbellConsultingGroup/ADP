import { useState } from "react";
import type { BusinessDomain } from "../api/business";
import { useOrgUnits } from "../api/organization";

interface DomainFormProps {
  initial?: Partial<BusinessDomain>;
  onSubmit: (data: Partial<BusinessDomain>) => void;
  onCancel: () => void;
  isLoading?: boolean;
}

const CLASSIFICATIONS = [
  { value: "strategic", label: "Strategic" },
  { value: "differentiating", label: "Differentiating" },
  { value: "commodity", label: "Commodity" },
] as const;

export default function DomainForm({ initial = {}, onSubmit, onCancel, isLoading }: DomainFormProps) {
  const [name, setName] = useState(initial.name ?? "");
  const [scopeStatement, setScopeStatement] = useState(initial.scope_statement ?? "");
  const [classification, setClassification] = useState<string>(
    initial.classification ?? "strategic",
  );
  const [ownerId, setOwnerId] = useState(initial.owner_org_unit_id ?? "");
  const orgUnits = useOrgUnits();
  // A domain is owned by a division: a level-2 org unit.
  const divisions = (orgUnits.data?.items ?? [])
    .filter((u) => u.level === 2)
    .sort((a, b) => a.name.localeCompare(b.name));
  const legacyText = !initial.owner_org_unit_id ? initial.org_unit : null;
  const [riskFlagsInput, setRiskFlagsInput] = useState(
    (initial.risk_flags ?? []).join(", "),
  );
  const [error, setError] = useState<string | null>(null);

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!name.trim()) {
      setError("Name is required");
      return;
    }
    const risk_flags = riskFlagsInput
      .split(",")
      .map((f) => f.trim())
      .filter(Boolean);
    onSubmit({
      name: name.trim(),
      scope_statement: scopeStatement.trim() || null,
      classification: classification as BusinessDomain["classification"],
      owner_org_unit_id: ownerId || null,
      // Once a division is chosen the older free text has served its purpose.
      ...(ownerId ? { org_unit: null } : {}),
      risk_flags,
    });
  }

  return (
    <form onSubmit={handleSubmit} style={{ display: "flex", flexDirection: "column", gap: 10 }}>
      {error && <div style={{ color: "var(--crit)", fontSize: 13 }}>{error}</div>}
      <label style={{ fontSize: 13 }}>
        Name *
        <input
          value={name}
          onChange={(e) => setName(e.target.value)}
          style={{ display: "block", width: "100%", marginTop: 2 }}
          placeholder="Customer Domain"
        />
      </label>
      <label style={{ fontSize: 13 }}>
        Classification *
        <select
          value={classification}
          onChange={(e) => setClassification(e.target.value)}
          style={{ display: "block", width: "100%", marginTop: 2 }}
        >
          {CLASSIFICATIONS.map((c) => (
            <option key={c.value} value={c.value}>
              {c.label}
            </option>
          ))}
        </select>
      </label>
      <label style={{ fontSize: 13 }}>
        Owner (division)
        <select
          value={ownerId}
          onChange={(e) => setOwnerId(e.target.value)}
          disabled={orgUnits.isLoading}
          style={{ display: "block", width: "100%", marginTop: 2 }}
        >
          <option value="">{orgUnits.isLoading ? "Loading…" : "No owner"}</option>
          {divisions.map((d) => (
            <option key={d.id} value={d.id}>
              {d.name}
            </option>
          ))}
        </select>
        {legacyText && (
          <span style={{ display: "block", fontSize: 11, color: "var(--ink-3)", marginTop: 2 }}>
            Recorded before as &ldquo;{legacyText}&rdquo;, which matches no division. Choose one.
          </span>
        )}
        {!orgUnits.isLoading && divisions.length === 0 && (
          <span style={{ display: "block", fontSize: 11, color: "var(--ink-3)", marginTop: 2 }}>
            No divisions yet. Add them under Business &rarr; Organization.
          </span>
        )}
      </label>
      <label style={{ fontSize: 13 }}>
        Scope Statement
        <textarea
          value={scopeStatement}
          onChange={(e) => setScopeStatement(e.target.value)}
          rows={3}
          style={{ display: "block", width: "100%", marginTop: 2 }}
          placeholder="In: … Out: …"
        />
      </label>
      <label style={{ fontSize: 13 }}>
        Risk Flags (comma-separated)
        <input
          value={riskFlagsInput}
          onChange={(e) => setRiskFlagsInput(e.target.value)}
          style={{ display: "block", width: "100%", marginTop: 2 }}
          placeholder="PII, GDPR, SOX"
        />
      </label>
      <div style={{ display: "flex", gap: 8 }}>
        <button type="submit" disabled={isLoading}>
          {isLoading ? "Saving…" : "Save"}
        </button>
        <button type="button" onClick={onCancel}>
          Cancel
        </button>
      </div>
    </form>
  );
}
