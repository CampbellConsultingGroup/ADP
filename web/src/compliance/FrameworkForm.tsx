import { useState } from "react";
import type { RegulatoryFramework } from "../api/compliance";

interface FrameworkFormProps {
  initial?: Partial<RegulatoryFramework>;
  onSubmit: (data: {
    name: string;
    jurisdiction: string;
    authority: string;
    version: string;
    effective_date: string | null;
    source_url: string | null;
  }) => void;
  onCancel: () => void;
  isLoading?: boolean;
}

export default function FrameworkForm({ initial = {}, onSubmit, onCancel, isLoading }: FrameworkFormProps) {
  const [name, setName] = useState(initial.name ?? "");
  const [jurisdiction, setJurisdiction] = useState(initial.jurisdiction ?? "");
  const [authority, setAuthority] = useState(initial.authority ?? "");
  const [version, setVersion] = useState(initial.version ?? "");
  const [effectiveDate, setEffectiveDate] = useState(initial.effective_date ?? "");
  const [sourceUrl, setSourceUrl] = useState(initial.source_url ?? "");
  const [error, setError] = useState<string | null>(null);

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!name.trim() || !jurisdiction.trim() || !authority.trim() || !version.trim()) {
      setError("Name, jurisdiction, authority, and version are all required");
      return;
    }
    onSubmit({
      name: name.trim(),
      jurisdiction: jurisdiction.trim(),
      authority: authority.trim(),
      version: version.trim(),
      effective_date: effectiveDate.trim() || null,
      source_url: sourceUrl.trim() || null,
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
          maxLength={255}
          style={{ display: "block", width: "100%", marginTop: 2 }}
          placeholder="NIST 800-53 Rev 5"
        />
      </label>
      <label style={{ fontSize: 13 }}>
        Jurisdiction *
        <input
          value={jurisdiction}
          onChange={(e) => setJurisdiction(e.target.value)}
          maxLength={255}
          style={{ display: "block", width: "100%", marginTop: 2 }}
          placeholder="US-Federal"
        />
      </label>
      <label style={{ fontSize: 13 }}>
        Authority *
        <input
          value={authority}
          onChange={(e) => setAuthority(e.target.value)}
          maxLength={255}
          style={{ display: "block", width: "100%", marginTop: 2 }}
          placeholder="NIST"
        />
      </label>
      <label style={{ fontSize: 13 }}>
        Version *
        <input
          value={version}
          onChange={(e) => setVersion(e.target.value)}
          maxLength={100}
          style={{ display: "block", width: "100%", marginTop: 2 }}
          placeholder="Rev 5"
        />
      </label>
      <label style={{ fontSize: 13 }}>
        Effective Date (optional — leave blank if perpetually current)
        <input
          type="date"
          value={effectiveDate}
          onChange={(e) => setEffectiveDate(e.target.value)}
          style={{ display: "block", width: "100%", marginTop: 2 }}
        />
      </label>
      <label style={{ fontSize: 13 }}>
        Source URL (optional)
        <input
          value={sourceUrl}
          onChange={(e) => setSourceUrl(e.target.value)}
          style={{ display: "block", width: "100%", marginTop: 2 }}
          placeholder="https://..."
        />
      </label>
      <div style={{ display: "flex", gap: 8, marginTop: 4 }}>
        <button type="submit" disabled={isLoading} style={{ fontSize: 13 }}>
          {isLoading ? "Saving…" : "Save"}
        </button>
        <button type="button" onClick={onCancel} style={{ fontSize: 13 }}>
          Cancel
        </button>
      </div>
    </form>
  );
}
