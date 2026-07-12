/** DesignLinkEditor — reusable add/remove design links for capabilities and value streams (ADP-SPEC-034). */

import React, { useState } from "react";
import {
  useDesigns,
  useLinkedCapabilityDesigns,
  useLinkDesignToCapability,
  useUnlinkDesignFromCapability,
  useLinkedValueStreamDesigns,
  useLinkDesignToValueStream,
  useUnlinkDesignFromValueStream,
  type DesignRef,
} from "../api/business";

interface Props {
  entityType: "capability" | "value-stream";
  entityId: string;
}

export default function DesignLinkEditor({ entityType, entityId }: Props): React.ReactElement {
  const [selectedDesignId, setSelectedDesignId] = useState<string>("");
  const [linkError, setLinkError] = useState<string | null>(null);

  const isCapability = entityType === "capability";

  const capLinkedQuery = useLinkedCapabilityDesigns(isCapability ? entityId : null);
  const vsLinkedQuery = useLinkedValueStreamDesigns(!isCapability ? entityId : null);
  const linkedQuery = isCapability ? capLinkedQuery : vsLinkedQuery;

  const allDesigns = useDesigns();

  const linkToCapability = useLinkDesignToCapability(entityId);
  const unlinkFromCapability = useUnlinkDesignFromCapability(entityId);
  const linkToVs = useLinkDesignToValueStream(entityId);
  const unlinkFromVs = useUnlinkDesignFromValueStream(entityId);

  const link = isCapability ? linkToCapability : linkToVs;
  const unlink = isCapability ? unlinkFromCapability : unlinkFromVs;

  const linkedIds = new Set((linkedQuery.data?.items ?? []).map((d: DesignRef) => d.design_id));
  const available = (allDesigns.data?.designs ?? []).filter((d) => !linkedIds.has(d.id));

  function handleAdd() {
    if (!selectedDesignId) return;
    setLinkError(null);
    link.mutate(selectedDesignId, {
      onSuccess: () => {
        setSelectedDesignId("");
      },
      onError: (err: Error & { status?: number }) => {
        if (err.status === 409) {
          setLinkError("Already linked");
        } else {
          setLinkError(err.message || "Failed to link design");
        }
      },
    });
  }

  if (linkedQuery.isLoading) {
    return <p style={{ fontSize: "0.85rem", color: "var(--text-secondary)" }}>Loading links…</p>;
  }

  return (
    <div style={{ marginTop: "0.75rem" }}>
      <div style={{ marginBottom: "0.5rem" }}>
        {linkedQuery.data?.items.length === 0 && (
          <p style={{ fontSize: "0.85rem", color: "var(--text-secondary)", margin: "0 0 0.5rem" }}>
            No designs linked yet.
          </p>
        )}
        {linkedQuery.data?.items.map((d: DesignRef) => (
          <div
            key={d.design_id}
            style={{
              display: "flex",
              alignItems: "center",
              gap: "0.5rem",
              padding: "0.35rem 0",
              borderBottom: "1px solid var(--border)",
            }}
          >
            <span style={{ flex: 1, fontSize: "0.85rem" }}>{d.title}</span>
            <span
              style={{
                fontSize: "0.75rem",
                color: "var(--text-secondary)",
                textTransform: "capitalize",
              }}
            >
              {d.lifecycle_status}
            </span>
            <button
              onClick={() => unlink.mutate(d.design_id)}
              disabled={unlink.isPending}
              style={{
                background: "none",
                border: "1px solid var(--border)",
                borderRadius: "4px",
                cursor: "pointer",
                padding: "2px 8px",
                fontSize: "0.75rem",
                color: "var(--text-secondary)",
              }}
            >
              Remove
            </button>
          </div>
        ))}
      </div>

      <div style={{ display: "flex", gap: "0.5rem", alignItems: "center", flexWrap: "wrap" }}>
        <select
          value={selectedDesignId}
          onChange={(e) => {
            setSelectedDesignId(e.target.value);
            setLinkError(null);
          }}
          style={{
            flex: 1,
            minWidth: "160px",
            padding: "0.3rem 0.5rem",
            fontSize: "0.85rem",
            border: "1px solid var(--border)",
            borderRadius: "4px",
            background: "var(--bg)",
            color: "var(--text)",
          }}
        >
          <option value="">— select design —</option>
          {available.map((d) => (
            <option key={d.id} value={d.id}>
              {d.title}
            </option>
          ))}
        </select>
        <button
          onClick={handleAdd}
          disabled={!selectedDesignId || link.isPending}
          style={{
            padding: "0.3rem 0.75rem",
            fontSize: "0.85rem",
            borderRadius: "4px",
            border: "none",
            background: "var(--accent)",
            color: "#fff",
            cursor: selectedDesignId ? "pointer" : "not-allowed",
            opacity: selectedDesignId ? 1 : 0.5,
          }}
        >
          Link
        </button>
      </div>
      {linkError && (
        <p style={{ color: "var(--error, var(--crit))", fontSize: "0.8rem", margin: "0.35rem 0 0" }}>
          {linkError}
        </p>
      )}
    </div>
  );
}
