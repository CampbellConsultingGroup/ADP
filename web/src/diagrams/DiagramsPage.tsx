// ADP-914.5: top-level page wiring the diagrams list + editor into ADP's
// navigation (App.tsx / AppShell). Neither DiagramListPage nor
// DiagramEditorPage (ADP-SPEC-046) was previously reachable from the running
// app -- this component owns list-vs-editor mode state internally, following
// the same convention as web/src/application/ApplicationPage.tsx, rather than
// introducing a second AppView (diagrams aren't Design-scoped, so there's no
// existing "select a design first" screen to piggyback on the way Canvas does).
//
// ADP-SPEC-052: page chrome moved from bare <div style={{...}}> to ADP's
// .ui-page/.ui-toolbar/.ui-h1 convention (mirrors web/src/designs/
// DesignsPage.tsx), and this is diagrams.css's entry point (research.md
// Decision 6 -- imported once, here, not per-component).

import { useEffect, useState } from "react";
import { DiagramListPage } from "./DiagramListPage";
import { DiagramEditorPage } from "./DiagramEditorPage";
import { Button } from "../ui";
import type { DiagramSeed } from "./generators";
import type { Diagram } from "./api";
import "./diagrams.css";

type Mode = { kind: "list" } | { kind: "edit"; diagramId?: string; seed?: DiagramSeed };

export interface DiagramsPageProps {
  /** ADP-914.7: a pending seed from a "Generate Diagram" click elsewhere in
   *  the app (e.g. a value stream or capability page), lifted in App.tsx --
   *  mirrors the existing currentDesignId/onSelectDesign pattern. */
  seed?: DiagramSeed | null;
  /** Called once the seed above has been consumed (opened in the editor), so
   *  the caller can clear its pending state and avoid re-triggering on the
   *  next unrelated render. */
  onSeedConsumed?: () => void;
}

export function DiagramsPage({ seed, onSeedConsumed }: DiagramsPageProps = {}) {
  const [mode, setMode] = useState<Mode>({ kind: "list" });

  useEffect(() => {
    if (!seed) return;
    setMode({ kind: "edit", seed });
    onSeedConsumed?.();
    // onSeedConsumed intentionally omitted -- it's expected to be a fresh
    // closure each render from the caller's state setter; re-running this
    // effect whenever it changes identity (rather than only when `seed`
    // itself changes) would risk consuming the same seed twice.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [seed]);

  if (mode.kind === "edit") {
    return (
      <div className="ui-page">
        <Button variant="ghost" onClick={() => setMode({ kind: "list" })} style={{ marginBottom: 16 }}>
          ← Back to diagrams
        </Button>
        <DiagramEditorPage
          diagramId={mode.diagramId}
          seed={mode.seed}
          onSaved={(diagram: Diagram) => setMode({ kind: "edit", diagramId: diagram.id })}
        />
      </div>
    );
  }

  return (
    <div className="ui-page">
      <div className="ui-toolbar">
        <h1 className="ui-h1">Diagrams</h1>
        <Button variant="primary" icon="plus" onClick={() => setMode({ kind: "edit" })}>
          New Diagram
        </Button>
      </div>
      <DiagramListPage onOpen={(diagramId) => setMode({ kind: "edit", diagramId })} />
    </div>
  );
}

export default DiagramsPage;
