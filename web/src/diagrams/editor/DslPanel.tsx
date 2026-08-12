import { useEffect, useState } from 'react';
import type { ParseError } from '../core/index.js';
import { UnsupportedElementNotice } from './UnsupportedElementNotice';

export interface DslPanelProps {
  dsl: string;
  parseErrors: ParseError[];
  onApply: (dslText: string) => void;
  /** ADP-914.8 FR-011: disables manual typing/apply while an AI chat
   * request is in flight, so an incoming proposal can never race a manual
   * edit. Absent/false is this component's original, unchanged behavior. */
  disabled?: boolean;
}

/** Editable Mermaid DSL text panel (FR-003): edits here update the canvas via onApply. */
export function DslPanel({ dsl, parseErrors, onApply, disabled = false }: DslPanelProps) {
  const [draft, setDraft] = useState(dsl);

  // Keep the draft in sync when the canvas changes the model (and thus the derived DSL),
  // but don't clobber in-progress typing.
  useEffect(() => {
    setDraft(dsl);
  }, [dsl]);

  return (
    <div className="panel">
      <div className="panel__body panel__body--flush dsl-panel">
        <textarea
          className="dsl-panel__editor"
          data-testid="dsl-panel"
          aria-label="Mermaid DSL for this diagram"
          value={draft}
          onChange={(event) => setDraft(event.target.value)}
          spellCheck={false}
          disabled={disabled}
        />
        <UnsupportedElementNotice errors={parseErrors} />
      </div>
      <div className="panel__footer">
        <button
          type="button"
          className="btn btn--primary btn--compact"
          data-testid="apply-dsl"
          onClick={() => onApply(draft)}
          disabled={disabled}
        >
          Apply
        </button>
      </div>
    </div>
  );
}
