import { useEffect, useState } from "react";
import { useApplicationCost, useUpdateApplicationCost } from "../api/application";
import type { ApplicationCostUpdate, CostBucket, TcoBucketKey } from "../api/application";
import { TCO_BUCKET_KEYS } from "../api/application";

/** APM US4 — Total Cost of Ownership (ADP-9x6, sensitive: gated server-side). */

interface Props { appId: string; }

const BUCKET_LABELS: Record<TcoBucketKey, string> = {
  acquisition: "Acquisition",
  implementation: "Implementation & Setup",
  training: "Training",
  operational: "Operational",
  maintenance: "Maintenance & Support",
  upgrades: "Upgrades & Enhancements",
  risk_downtime: "Risk & Downtime",
  end_of_life: "End-of-Life",
};

const zeroBucket = (): CostBucket => ({ one_time: "0", annual: "0" });

const field: React.CSSProperties = {
  width: "100%", padding: "5px 7px", fontSize: 13, border: "1px solid var(--border)", borderRadius: 4,
};
const label: React.CSSProperties = { fontSize: 12, color: "var(--ink-2)" };

function formatMoney(value: string): string {
  const n = Number(value);
  return Number.isFinite(n)
    ? n.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })
    : value;
}

export default function CostPanel({ appId }: Props) {
  const { data: cost, isLoading, error } = useApplicationCost(appId);
  const updateCost = useUpdateApplicationCost(appId);

  const [currency, setCurrency] = useState("USD");
  const [horizon, setHorizon] = useState("5");
  const [buckets, setBuckets] = useState<Record<TcoBucketKey, CostBucket>>(
    () => Object.fromEntries(TCO_BUCKET_KEYS.map((k) => [k, zeroBucket()])) as Record<TcoBucketKey, CostBucket>,
  );
  const [toast, setToast] = useState<string | null>(null);

  useEffect(() => {
    if (!cost) return;
    setCurrency(cost.currency);
    setHorizon(String(cost.horizon_years));
    setBuckets(
      Object.fromEntries(TCO_BUCKET_KEYS.map((k) => [k, cost[k]])) as Record<TcoBucketKey, CostBucket>,
    );
  }, [cost]);

  if (isLoading) return <div style={{ fontSize: 13, color: "var(--ink-3)" }}>Loading…</div>;

  if (error) {
    const forbidden = (error as Error).message.includes("403");
    return (
      <div style={{ fontSize: 13, color: "var(--ink-3)" }}>
        {forbidden
          ? "You don't have permission to view cost data for this application."
          : "Could not load cost data."}
      </div>
    );
  }

  const showToast = (msg: string) => {
    setToast(msg);
    setTimeout(() => setToast(null), 3000);
  };

  const setBucketField = (key: TcoBucketKey, part: "one_time" | "annual", value: string) => {
    setBuckets((prev) => ({ ...prev, [key]: { ...prev[key], [part]: value } }));
  };

  const handleSave = async () => {
    const horizonNum = parseInt(horizon, 10);
    if (!horizonNum || horizonNum < 1) { showToast("Horizon must be a positive integer"); return; }
    const body = { currency, horizon_years: horizonNum, ...buckets } as ApplicationCostUpdate;
    try {
      await updateCost.mutateAsync(body);
      showToast("Saved");
    } catch (e) {
      const forbidden = (e as Error).message.includes("403");
      showToast(forbidden ? "You don't have permission to edit cost data" : "Save failed");
    }
  };

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 14, maxWidth: 560 }}>
      <h4 style={{ margin: 0, fontSize: 13, fontWeight: 600, color: "var(--ink-2)" }}>Total Cost of Ownership</h4>
      {toast && <div style={{ fontSize: 11, color: toast === "Saved" ? "var(--ink-2)" : "var(--crit)" }}>{toast}</div>}

      {cost && (
        <div style={{ display: "flex", gap: 16, flexWrap: "wrap", padding: "8px 12px", background: "var(--surface-2)", borderRadius: 6, fontSize: 12 }}>
          <div>
            <strong>{cost.currency} {formatMoney(cost.tco)}</strong>{" "}
            <span style={{ color: "var(--ink-3)" }}>TCO over {cost.horizon_years}y</span>
          </div>
          <div style={{ color: "var(--ink-3)" }}>
            Run: {formatMoney(cost.run_total)} · Change: {formatMoney(cost.change_total)}
          </div>
        </div>
      )}

      <div style={{ display: "flex", gap: 10 }}>
        <label style={{ ...label, flex: 1 }}>Currency
          <input style={field} value={currency} onChange={(e) => setCurrency(e.target.value.toUpperCase())} maxLength={3} />
        </label>
        <label style={{ ...label, flex: 1 }}>Horizon (years)
          <input style={field} type="number" min={1} value={horizon} onChange={(e) => setHorizon(e.target.value)} />
        </label>
      </div>

      <div style={{ overflowX: "auto" }}>
        <table style={{ borderCollapse: "collapse", width: "100%", fontSize: 12 }}>
          <thead>
            <tr style={{ textAlign: "left", color: "var(--ink-3)" }}>
              <th style={{ padding: "4px 6px", fontWeight: 500 }}>Bucket</th>
              <th style={{ padding: "4px 6px", fontWeight: 500 }}>One-Time</th>
              <th style={{ padding: "4px 6px", fontWeight: 500 }}>Annual</th>
            </tr>
          </thead>
          <tbody>
            {TCO_BUCKET_KEYS.map((key) => (
              <tr key={key}>
                <td style={{ padding: "4px 6px", color: "var(--ink-2)", whiteSpace: "nowrap" }}>{BUCKET_LABELS[key]}</td>
                <td style={{ padding: "4px 6px" }}>
                  <input
                    style={field}
                    type="number"
                    step="0.01"
                    value={buckets[key]?.one_time ?? "0"}
                    onChange={(e) => setBucketField(key, "one_time", e.target.value)}
                  />
                </td>
                <td style={{ padding: "4px 6px" }}>
                  <input
                    style={field}
                    type="number"
                    step="0.01"
                    value={buckets[key]?.annual ?? "0"}
                    onChange={(e) => setBucketField(key, "annual", e.target.value)}
                  />
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <div>
        <button
          type="button"
          onClick={handleSave}
          disabled={updateCost.isPending}
          style={{
            padding: "6px 14px", fontSize: 13, border: "1px solid var(--border)", borderRadius: 6,
            background: "var(--accent, #2874A6)", color: "#fff", cursor: "pointer",
          }}
        >
          {updateCost.isPending ? "Saving…" : "Save"}
        </button>
      </div>
    </div>
  );
}
