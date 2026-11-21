// 947 GEO-02 (ADP-bo1.2): an application's Geography tab -- the legal entities that use it and
// its typed, dated geography links (deployed in, stores data in, processes personal data of
// people in, serves customers in). Regulators trigger on different ones, so there is no single
// "region" field. Writes need write_application (the routes are under /api/v1/applications).

import { useState } from "react";
import type React from "react";
import { errorDetail } from "../api/appCapabilities";
import {
  useApplicationLegalEntities,
  useLegalEntities,
  useLinkApplicationLegalEntity,
  useUnlinkApplicationLegalEntity,
} from "../api/organization";
import GeoLinksEditor from "../business/GeoLinksEditor";
import { useApplicationWrite } from "./appCapNav";

const muted: React.CSSProperties = { fontSize: 12, color: "var(--ink-3)" };
const field: React.CSSProperties = { fontSize: 12, padding: "3px 6px", border: "1px solid var(--border)", borderRadius: 3 };
const chip: React.CSSProperties = { fontSize: 11, background: "var(--surface-2)", padding: "1px 6px", borderRadius: 8, display: "inline-flex", gap: 4, alignItems: "center" };

export default function ApplicationGeography({ appId }: { appId: string }): React.ReactElement {
  const canWrite = useApplicationWrite().allowed;
  const linked = useApplicationLegalEntities(appId);
  const all = useLegalEntities();
  const link = useLinkApplicationLegalEntity();
  const unlink = useUnlinkApplicationLegalEntity();
  const [error, setError] = useState<string | null>(null);
  const run = async (fn: () => Promise<unknown>) => {
    setError(null);
    try {
      await fn();
    } catch (err) {
      setError(errorDetail(err));
    }
  };
  const items = linked.data ?? [];
  const ids = new Set(items.map((e) => e.id));

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
      <h4 style={{ fontSize: 13, margin: "0 0 6px", color: "var(--ink-2)" }}>Legal entities</h4>
      <div style={muted}>The companies that use or operate this application. Licences and incorporation are recorded on the legal entity (Business → Organization → Legal entities).</div>
      <div style={{ display: "flex", gap: 4, flexWrap: "wrap" }}>
        {linked.isLoading ? (
          <span style={muted}>Loading…</span>
        ) : items.length === 0 ? (
          <span style={muted}>None linked.</span>
        ) : (
          items.map((e) => (
            <span key={e.id} style={chip}>
              {e.name}
              {canWrite && (
                <button type="button" className="ui-btn-plain" aria-label={`Unlink ${e.name}`} onClick={() => void run(() => unlink.mutateAsync({ appId, legalEntityId: e.id }))} style={{ color: "var(--ink-3)" }}>
                  ×
                </button>
              )}
            </span>
          ))
        )}
      </div>
      {canWrite && (
        <select
          aria-label="Link a legal entity"
          value=""
          onChange={(e) => {
            const le = e.target.value;
            if (le) void run(() => link.mutateAsync({ appId, legalEntityId: le }));
          }}
          style={{ ...field, alignSelf: "flex-start" }}
        >
          <option value="">{(all.data?.items ?? []).length === 0 ? "No legal entities yet" : "Link a legal entity…"}</option>
          {(all.data?.items ?? [])
            .filter((e) => !ids.has(e.id))
            .map((e) => (
              <option key={e.id} value={e.id}>
                {e.name}
              </option>
            ))}
        </select>
      )}
      {error && (
        <div role="alert" style={{ fontSize: 12, color: "var(--crit)" }}>
          {error}
        </div>
      )}
      <GeoLinksEditor
        subject="application"
        subjectId={appId}
        canWrite={canWrite}
        hint="Where it runs and stores data, whose personal data it processes and whose customers it serves. Leave the dates empty for always."
      />
    </div>
  );
}
