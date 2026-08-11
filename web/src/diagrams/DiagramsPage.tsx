// ADP-914.5: top-level page wiring the diagrams list + editor into ADP's
// navigation (App.tsx / AppShell). Neither DiagramListPage nor
// DiagramEditorPage (ADP-SPEC-046) was previously reachable from the running
// app -- this component owns list-vs-editor mode state internally, following
// the same convention as web/src/application/ApplicationPage.tsx, rather than
// introducing a second AppView (diagrams aren't Design-scoped, so there's no
// existing "select a design first" screen to piggyback on the way Canvas does).

import { useState } from "react";
import { DiagramListPage } from "./DiagramListPage";
import { DiagramEditorPage } from "./DiagramEditorPage";
import type { Diagram } from "./api";

type Mode = { kind: "list" } | { kind: "edit"; diagramId?: string };

export function DiagramsPage() {
  const [mode, setMode] = useState<Mode>({ kind: "list" });

  if (mode.kind === "edit") {
    return (
      <div style={{ padding: 16 }}>
        <button type="button" onClick={() => setMode({ kind: "list" })} style={{ marginBottom: 12 }}>
          ← Back to diagrams
        </button>
        <DiagramEditorPage
          diagramId={mode.diagramId}
          onSaved={(diagram: Diagram) => setMode({ kind: "edit", diagramId: diagram.id })}
        />
      </div>
    );
  }

  return (
    <div style={{ padding: 16 }}>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 12 }}>
        <h2 style={{ margin: 0 }}>Diagrams</h2>
        <button type="button" onClick={() => setMode({ kind: "edit" })}>
          + New Diagram
        </button>
      </div>
      <DiagramListPage onOpen={(diagramId) => setMode({ kind: "edit", diagramId })} />
    </div>
  );
}

export default DiagramsPage;
