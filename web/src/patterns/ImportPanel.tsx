/** Import a pattern YAML document (paste or upload) as a new draft version (935 US1, US5). */

import React, { useState } from "react";
import { errorDetail, errorIssues, useImportPattern } from "../api/patterns";
import type { PatternIssue } from "../api/patterns";
import IssueList from "./IssueList";

export default function ImportPanel({
  initialYaml = "",
  onImported,
  onCancel,
}: {
  initialYaml?: string;
  onImported: (key: string, version: string) => void;
  onCancel: () => void;
}) {
  const [yaml, setYaml] = useState(initialYaml);
  const [issues, setIssues] = useState<PatternIssue[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const importPattern = useImportPattern();

  const onFile = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (file) setYaml(await file.text());
  };

  const submit = async () => {
    setIssues([]);
    setError(null);
    setNotice(null);
    try {
      const result = await importPattern.mutateAsync(yaml);
      if (result.version) {
        if (result.status === "unchanged") setNotice("This exact version is already in the registry.");
        onImported(result.version.pattern_key, result.version.version);
      }
    } catch (err) {
      const found = errorIssues(err);
      if (found.length) setIssues(found);
      else setError(errorDetail(err));
    }
  };

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
      <p style={{ margin: 0, fontSize: 13, color: "var(--ink-2)" }}>
        Paste or upload one pattern YAML document. It is stored as a <strong>draft</strong>; nothing
        is stored if it has errors.
      </p>
      <input type="file" accept=".yaml,.yml,text/yaml" aria-label="Pattern YAML file" onChange={(e) => void onFile(e)} />
      <textarea
        aria-label="Pattern YAML"
        className="ui-textarea"
        value={yaml}
        onChange={(e) => setYaml(e.target.value)}
        rows={22}
        spellCheck={false}
        style={{ fontFamily: "var(--mono, monospace)", fontSize: 12.5, width: "100%" }}
      />
      {error && <div className="ui-alert crit" role="alert">{error}</div>}
      {notice && <div className="ui-alert info">{notice}</div>}
      <IssueList issues={issues} title="Import rejected" />
      <div style={{ display: "flex", gap: 8 }}>
        <button type="button" className="ui-btn ui-btn-primary ui-btn-sm" disabled={!yaml.trim() || importPattern.isPending} onClick={() => void submit()}>
          {importPattern.isPending ? "Importing…" : "Import"}
        </button>
        <button type="button" className="ui-btn ui-btn-sm" onClick={onCancel}>Cancel</button>
      </div>
    </div>
  );
}
