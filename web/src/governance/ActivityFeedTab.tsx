import React, { useState } from "react";
import { useActivityFeed, downloadActivityCSV } from "../api/governance";

const ACTION_TYPES = [
  { value: "", label: "All Actions" },
  { value: "design-created", label: "Design Created" },
  { value: "lifecycle-transition", label: "Lifecycle Transition" },
  { value: "accept-recommendation", label: "Accept Recommendation" },
  { value: "reject-requirement-proposal", label: "Reject Requirement" },
  { value: "confirm-requirement", label: "Confirm Requirement" },
  { value: "add-requirement", label: "Add Requirement" },
  { value: "update-element-technology-tags", label: "Update Technology Tags" },
  { value: "calm-export", label: "CALM Export" },
  { value: "validate", label: "Validate" },
];

function toDateStr(d: Date): string {
  return d.toISOString().split("T")[0];
}

export default function ActivityFeedTab(): React.ReactElement {
  const today = new Date();
  const thirtyDaysAgo = new Date(today);
  thirtyDaysAgo.setDate(today.getDate() - 30);

  const [fromDate, setFromDate] = useState(toDateStr(thirtyDaysAgo));
  const [toDate, setToDate] = useState(toDateStr(today));
  const [actionFilter, setActionFilter] = useState("");
  const [actorFilter, setActorFilter] = useState("");
  const [page, setPage] = useState(1);
  const [rangeError, setRangeError] = useState("");

  const daysDiff =
    (new Date(toDate).getTime() - new Date(fromDate).getTime()) / (1000 * 60 * 60 * 24);
  const rangeValid = daysDiff >= 0 && daysDiff <= 90;

  const { data, isLoading } = useActivityFeed(
    fromDate,
    toDate,
    actionFilter || undefined,
    actorFilter || undefined,
    page,
    rangeValid,
  );

  const handleApply = () => {
    if (daysDiff > 90) {
      setRangeError("Date range cannot exceed 90 days.");
      return;
    }
    setRangeError("");
    setPage(1);
  };

  const totalPages = data ? Math.ceil(data.total / data.page_size) : 0;

  return (
    <div>
      {/* Filter controls */}
      <div style={{ display: "flex", flexWrap: "wrap", gap: 10, marginBottom: 16, alignItems: "flex-end" }}>
        <div>
          <label style={{ display: "block", fontSize: 12, color: "#6B7280", marginBottom: 3 }}>From</label>
          <input
            type="date"
            value={fromDate}
            onChange={(e) => { setFromDate(e.target.value); setRangeError(""); }}
            style={{ padding: "6px 10px", borderRadius: 6, border: "1px solid #D1D5DB", fontSize: 14 }}
          />
        </div>
        <div>
          <label style={{ display: "block", fontSize: 12, color: "#6B7280", marginBottom: 3 }}>To</label>
          <input
            type="date"
            value={toDate}
            onChange={(e) => { setToDate(e.target.value); setRangeError(""); }}
            style={{ padding: "6px 10px", borderRadius: 6, border: "1px solid #D1D5DB", fontSize: 14 }}
          />
        </div>
        <div>
          <label style={{ display: "block", fontSize: 12, color: "#6B7280", marginBottom: 3 }}>Action</label>
          <select
            value={actionFilter}
            onChange={(e) => setActionFilter(e.target.value)}
            style={{ padding: "6px 10px", borderRadius: 6, border: "1px solid #D1D5DB", fontSize: 14 }}
          >
            {ACTION_TYPES.map((a) => (
              <option key={a.value} value={a.value}>{a.label}</option>
            ))}
          </select>
        </div>
        <div>
          <label style={{ display: "block", fontSize: 12, color: "#6B7280", marginBottom: 3 }}>Actor</label>
          <input
            type="text"
            value={actorFilter}
            onChange={(e) => setActorFilter(e.target.value)}
            placeholder="username"
            style={{ padding: "6px 10px", borderRadius: 6, border: "1px solid #D1D5DB", fontSize: 14, width: 120 }}
          />
        </div>
        <button
          onClick={handleApply}
          style={{ padding: "6px 14px", borderRadius: 6, border: "1px solid #D1D5DB", backgroundColor: "#fff", fontSize: 14, cursor: "pointer" }}
        >
          Apply
        </button>
        <button
          onClick={() => downloadActivityCSV(fromDate, toDate, actionFilter || undefined, actorFilter || undefined)}
          disabled={!rangeValid}
          style={{
            padding: "6px 14px", borderRadius: 6, border: "1px solid #D1D5DB",
            backgroundColor: rangeValid ? "#fff" : "#F3F4F6",
            color: rangeValid ? "#374151" : "#9CA3AF",
            fontSize: 14, cursor: rangeValid ? "pointer" : "not-allowed",
          }}
        >
          Export CSV
        </button>
      </div>

      {rangeError && (
        <p style={{ color: "#DC2626", fontSize: 13, marginBottom: 12 }}>{rangeError}</p>
      )}

      {/* Entry list */}
      {isLoading && <p style={{ color: "#6B7280", fontSize: 13 }}>Loading…</p>}

      {!isLoading && rangeValid && (data?.entries ?? []).length === 0 && (
        <p style={{ color: "#6B7280", fontSize: 14 }}>No activity in this date range.</p>
      )}

      {(data?.entries ?? []).map((entry) => (
        <div
          key={entry.id}
          style={{
            display: "flex",
            gap: 12,
            padding: "10px 12px",
            borderRadius: 8,
            border: "1px solid #E5E7EB",
            marginBottom: 6,
            backgroundColor: "#fff",
            alignItems: "flex-start",
          }}
        >
          <span style={{ fontSize: 11, color: "#9CA3AF", whiteSpace: "nowrap", paddingTop: 2 }}>
            {new Date(entry.timestamp).toLocaleString()}
          </span>
          <span
            style={{
              padding: "2px 8px", borderRadius: 10,
              backgroundColor: "#EDE9FE", color: "#5B21B6",
              fontSize: 11, fontWeight: 600, whiteSpace: "nowrap", flexShrink: 0,
            }}
          >
            {entry.action}
          </span>
          <div style={{ flex: 1, minWidth: 0 }}>
            <span style={{ fontSize: 13, color: "#111827" }}>{entry.summary}</span>
            <span style={{ fontSize: 12, color: "#6B7280", marginLeft: 8 }}>{entry.design_title}</span>
          </div>
          <span style={{ fontSize: 12, color: "#9CA3AF", whiteSpace: "nowrap" }}>{entry.actor}</span>
        </div>
      ))}

      {/* Pagination */}
      {totalPages > 1 && (
        <div style={{ display: "flex", alignItems: "center", gap: 12, marginTop: 16 }}>
          <button
            onClick={() => setPage(Math.max(1, page - 1))}
            disabled={page <= 1}
            style={{ padding: "4px 12px", borderRadius: 6, border: "1px solid #D1D5DB", backgroundColor: "#fff", fontSize: 13, cursor: page <= 1 ? "not-allowed" : "pointer", color: page <= 1 ? "#9CA3AF" : "#374151" }}
          >
            Prev
          </button>
          <span style={{ fontSize: 13, color: "#6B7280" }}>
            Page {page} of {totalPages}
          </span>
          <button
            onClick={() => setPage(Math.min(totalPages, page + 1))}
            disabled={page >= totalPages}
            style={{ padding: "4px 12px", borderRadius: 6, border: "1px solid #D1D5DB", backgroundColor: "#fff", fontSize: 13, cursor: page >= totalPages ? "not-allowed" : "pointer", color: page >= totalPages ? "#9CA3AF" : "#374151" }}
          >
            Next
          </button>
        </div>
      )}
    </div>
  );
}
