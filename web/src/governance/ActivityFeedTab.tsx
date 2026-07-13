import React, { useState } from "react";
import { useActivityFeed, downloadActivityCSV } from "../api/governance";
import { Button, StatusBadge } from "../ui";

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
    fromDate, toDate, actionFilter || undefined, actorFilter || undefined, page, rangeValid,
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
          <label className="ui-label">From</label>
          <input type="date" className="ui-input" value={fromDate}
            onChange={(e) => { setFromDate(e.target.value); setRangeError(""); }} />
        </div>
        <div>
          <label className="ui-label">To</label>
          <input type="date" className="ui-input" value={toDate}
            onChange={(e) => { setToDate(e.target.value); setRangeError(""); }} />
        </div>
        <div>
          <label className="ui-label">Action</label>
          <select className="ui-select" value={actionFilter} onChange={(e) => setActionFilter(e.target.value)}>
            {ACTION_TYPES.map((a) => <option key={a.value} value={a.value}>{a.label}</option>)}
          </select>
        </div>
        <div>
          <label className="ui-label">Actor</label>
          <input type="text" className="ui-input" style={{ width: 130 }} value={actorFilter}
            onChange={(e) => setActorFilter(e.target.value)} placeholder="username" />
        </div>
        <Button onClick={handleApply}>Apply</Button>
        <Button icon="doc" disabled={!rangeValid}
          onClick={() => downloadActivityCSV(fromDate, toDate, actionFilter || undefined, actorFilter || undefined)}>
          Export CSV
        </Button>
      </div>

      {rangeError && <p style={{ color: "var(--crit)", fontSize: 13, marginBottom: 12 }}>{rangeError}</p>}

      {isLoading && <p style={{ color: "var(--ink-3)", fontSize: 13 }}>Loading…</p>}
      {!isLoading && rangeValid && (data?.entries ?? []).length === 0 && (
        <p style={{ color: "var(--ink-3)", fontSize: 14 }}>No activity in this date range.</p>
      )}

      {(data?.entries ?? []).map((entry) => (
        <div
          key={entry.id}
          style={{
            display: "flex", gap: 12, padding: "10px 12px", borderRadius: 8,
            border: "1px solid var(--border)", marginBottom: 6, background: "var(--surface)", alignItems: "flex-start",
          }}
        >
          <span style={{ fontSize: 11, color: "var(--ink-3)", whiteSpace: "nowrap", paddingTop: 4, fontFamily: "var(--mono)" }}>
            {new Date(entry.timestamp).toLocaleString()}
          </span>
          <div style={{ flexShrink: 0 }}><StatusBadge tone="info">{entry.action}</StatusBadge></div>
          <div style={{ flex: 1, minWidth: 0 }}>
            <span style={{ fontSize: 13, color: "var(--ink)" }}>{entry.summary}</span>
            <span style={{ fontSize: 12, color: "var(--ink-3)", marginLeft: 8 }}>{entry.design_title}</span>
          </div>
          <span style={{ fontSize: 12, color: "var(--ink-3)", whiteSpace: "nowrap" }}>{entry.actor}</span>
        </div>
      ))}

      {/* Pagination */}
      {totalPages > 1 && (
        <div style={{ display: "flex", alignItems: "center", gap: 12, marginTop: 16 }}>
          <Button size="sm" onClick={() => setPage(Math.max(1, page - 1))} disabled={page <= 1}>Prev</Button>
          <span style={{ fontSize: 13, color: "var(--ink-3)" }}>Page {page} of {totalPages}</span>
          <Button size="sm" onClick={() => setPage(Math.min(totalPages, page + 1))} disabled={page >= totalPages}>Next</Button>
        </div>
      )}
    </div>
  );
}
