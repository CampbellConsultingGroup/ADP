/** Edit a draft version's YAML in place (935 US5): Validate and Preview are dry runs; Save
 * replaces the draft. Save stays disabled while the last validation of the current text found
 * errors. Monospace textarea only — no editor dependency (spec GT-10). */

import { useState } from "react";
import { errorDetail, errorIssues, useRenderPattern, useUpdateDraft, useValidatePattern } from "../api/patterns";
import type { PatternIssue, PatternViewResponse } from "../api/patterns";
import FlowchartView from "./FlowchartView";
import IssueList from "./IssueList";

export default function YamlEditor({ patternKey, version, initialYaml }: { patternKey: string; version: string; initialYaml: string }) {
  const [text, setText] = useState(initialYaml);
  const [issues, setIssues] = useState<PatternIssue[]>([]);
  const [blocked, setBlocked] = useState(false);
  const [notice, setNotice] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [preview, setPreview] = useState<PatternViewResponse | null>(null);
  const validate = useValidatePattern();
  const render = useRenderPattern();
  const save = useUpdateDraft(patternKey, version);

  const reset = () => { setNotice(null); setError(null); };

  const onChange = (value: string) => {
    setText(value);
    setBlocked(false);
    setPreview(null);
  };

  const runValidate = async () => {
    reset();
    try {
      const result = await validate.mutateAsync(text);
      setIssues(result.issues);
      setBlocked(!result.ok);
      if (result.ok) setNotice(result.issues.length ? "Valid, with warnings." : "Valid.");
    } catch (err) {
      setError(errorDetail(err));
    }
  };

  const runPreview = async () => {
    reset();
    try {
      setPreview(await render.mutateAsync(text));
    } catch (err) {
      const found = errorIssues(err);
      if (found.length) { setIssues(found); setBlocked(true); } else setError(errorDetail(err));
    }
  };

  const runSave = async () => {
    reset();
    try {
      const result = await save.mutateAsync(text);
      setIssues(result.issues);
      setNotice("Draft saved.");
    } catch (err) {
      const found = errorIssues(err);
      if (found.length) { setIssues(found); setBlocked(true); } else setError(errorDetail(err));
    }
  };

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
      <textarea
        aria-label="Draft YAML"
        className="ui-textarea"
        rows={24}
        spellCheck={false}
        value={text}
        onChange={(e) => onChange(e.target.value)}
        style={{ fontFamily: "var(--mono, monospace)", fontSize: 12.5, width: "100%" }}
      />
      <div style={{ display: "flex", gap: 8 }}>
        <button type="button" className="ui-btn ui-btn-sm" disabled={validate.isPending} onClick={() => void runValidate()}>Validate</button>
        <button type="button" className="ui-btn ui-btn-sm" disabled={render.isPending} onClick={() => void runPreview()}>Preview</button>
        <button
          type="button"
          className="ui-btn ui-btn-primary ui-btn-sm"
          disabled={blocked || save.isPending || text === initialYaml}
          onClick={() => void runSave()}
        >
          {save.isPending ? "Saving…" : "Save draft"}
        </button>
      </div>
      {notice && <div className="ui-alert info">{notice}</div>}
      {error && <div className="ui-alert crit" role="alert">{error}</div>}
      <IssueList issues={issues} title="Validation" />
      {preview && <FlowchartView flowchart={preview.flowchart} title="Structure preview" />}
    </div>
  );
}
