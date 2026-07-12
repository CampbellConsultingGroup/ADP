import { useState } from "react";
import {
  useStageCapabilities,
  useLinkCapabilityToStage,
  useUnlinkCapabilityFromStage,
  useCapabilities,
} from "../api/business";

interface StageCapsEditorProps {
  vsId: string;
  stageId: string;
}

export default function StageCapsEditor({ vsId, stageId }: StageCapsEditorProps) {
  const { data: linked, isLoading } = useStageCapabilities(vsId, stageId);
  const { data: allCaps } = useCapabilities();
  const linkMutation = useLinkCapabilityToStage(vsId, stageId);
  const unlinkMutation = useUnlinkCapabilityFromStage(vsId, stageId);
  const [selectedCapId, setSelectedCapId] = useState("");
  const [linkError, setLinkError] = useState<string | null>(null);

  const linkedIds = new Set((linked?.items ?? []).map((i) => i.capability_id));
  const available = (allCaps?.items ?? []).filter((c) => !linkedIds.has(c.id));

  function handleLink() {
    if (!selectedCapId) return;
    setLinkError(null);
    linkMutation.mutate(selectedCapId, {
      onSuccess: () => setSelectedCapId(""),
      onError: (e: Error & { status?: number }) => {
        setLinkError(e.status === 409 ? "Already linked" : e.message);
      },
    });
  }

  if (isLoading) return <div style={{ fontSize: 12, color: "var(--ink-3)", padding: "4px 0" }}>Loading…</div>;

  return (
    <div style={{ marginTop: 8 }}>
      <div style={{ fontSize: 12, fontWeight: 600, color: "var(--ink-3)", marginBottom: 4 }}>
        Capabilities
      </div>

      {(linked?.items ?? []).length === 0 && (
        <div style={{ fontSize: 12, color: "var(--ink-3)", marginBottom: 6 }}>None linked yet</div>
      )}

      {(linked?.items ?? []).map((item) => (
        <div
          key={item.capability_id}
          style={{
            display: "flex",
            justifyContent: "space-between",
            alignItems: "center",
            fontSize: 12,
            padding: "3px 6px",
            background: "var(--good-wash)",
            borderRadius: 4,
            marginBottom: 3,
          }}
        >
          <span>
            {item.name}
            {item.domain_name && (
              <span style={{ marginLeft: 5, color: "var(--accent-2)", fontSize: 10 }}>
                [{item.domain_name}]
              </span>
            )}
          </span>
          <button
            onClick={() => unlinkMutation.mutate(item.capability_id)}
            disabled={unlinkMutation.isPending}
            style={{ fontSize: 10, color: "var(--crit)", background: "none", border: "none", cursor: "pointer" }}
          >
            ✕
          </button>
        </div>
      ))}

      {linkError && (
        <div style={{ fontSize: 11, color: "var(--crit)", marginBottom: 4 }}>{linkError}</div>
      )}

      {available.length > 0 && (
        <div style={{ display: "flex", gap: 4, marginTop: 4 }}>
          <select
            value={selectedCapId}
            onChange={(e) => setSelectedCapId(e.target.value)}
            style={{ fontSize: 12, flex: 1 }}
          >
            <option value="">Add capability…</option>
            {available.map((c) => (
              <option key={c.id} value={c.id}>
                {c.name} (L{c.level})
              </option>
            ))}
          </select>
          <button
            onClick={handleLink}
            disabled={!selectedCapId || linkMutation.isPending}
            style={{ fontSize: 11 }}
          >
            Link
          </button>
        </div>
      )}
    </div>
  );
}
