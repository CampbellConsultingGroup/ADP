/** Dry run: evaluate unsaved draft YAML against a scope (936 US6). Nothing is stored. */

import { useState } from "react";
import { errorDetail, errorIssues, useEvaluate } from "../api/patterns";
import type { ConformanceReport, PatternIssue, ScopeType } from "../api/patterns";
import { useDomains } from "../api/business";
import { StatusBadge } from "../ui";
import FindingsTable from "./FindingsTable";
import IssueList from "./IssueList";
import { STATUS_LABELS, STATUS_TONES } from "./labels";

export default function EvaluatePanel({ yaml }: { yaml: string }) {
  const domains = useDomains();
  const evaluate = useEvaluate();
  const [scopeType, setScopeType] = useState<ScopeType>("portfolio");
  const [domain, setDomain] = useState("");
  const [report, setReport] = useState<ConformanceReport | null>(null);
  const [issues, setIssues] = useState<PatternIssue[]>([]);
  const [error, setError] = useState<string | null>(null);

  const run = async () => {
    setReport(null); setIssues([]); setError(null);
    try {
      setReport(await evaluate.mutateAsync({
        yaml,
        scope: { scope_type: scopeType, scope_ref: scopeType === "business_domain" ? domain : null, member_ids: [] },
      }));
    } catch (err) {
      const found = errorIssues(err);
      if (found.length) setIssues(found); else setError(errorDetail(err));
    }
  };

  return (
    <div className="ui-card" style={{ padding: 10, display: "flex", flexDirection: "column", gap: 8 }}>
      <div style={{ display: "flex", gap: 6, alignItems: "center", fontSize: 12.5 }}>
        <span>Evaluate against</span>
        <select aria-label="Evaluate scope" value={scopeType} onChange={(e) => setScopeType(e.target.value as ScopeType)}>
          <option value="portfolio">the whole portfolio</option>
          <option value="business_domain">a business domain</option>
        </select>
        {scopeType === "business_domain" && (
          <select aria-label="Evaluate domain" value={domain} onChange={(e) => setDomain(e.target.value)}>
            <option value="">Choose…</option>
            {(domains.data?.items ?? []).map((d) => <option key={d.id} value={d.id}>{d.name}</option>)}
          </select>
        )}
        <button
          type="button"
          className="ui-btn ui-btn-sm"
          disabled={evaluate.isPending || (scopeType === "business_domain" && !domain)}
          onClick={() => void run()}
        >
          Evaluate
        </button>
      </div>
      {error && <div className="ui-alert crit" role="alert">{error}</div>}
      <IssueList issues={issues} title="Not a valid pattern" />
      {report && (
        <>
          <div><StatusBadge tone={STATUS_TONES[report.status]}>{STATUS_LABELS[report.status]}</StatusBadge> (dry run, without pins)</div>
          <FindingsTable findings={report.findings} />
        </>
      )}
    </div>
  );
}
