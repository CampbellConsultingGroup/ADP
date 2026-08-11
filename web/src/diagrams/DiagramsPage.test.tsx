// ADP-914.5: DiagramsPage wires DiagramListPage <-> DiagramEditorPage into a
// single navigable screen (the same list-owns-mode-state convention as
// web/src/application/ApplicationPage.tsx), since neither sub-page was
// previously reachable from App.tsx / the AppShell nav rail at all.

import { describe, expect, it, vi, beforeEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { DiagramsPage } from "./DiagramsPage";
import * as api from "./api";
import type { DiagramSummary, Diagram } from "./api";

vi.mock("./api");

const mockedApi = vi.mocked(api);

const ITEMS: DiagramSummary[] = [
  { id: "d-1", title: "Claims Flow", diagram_type: "flowchart", updated_at: "2026-08-06T00:00:00Z" },
];

const LOADED: Diagram = {
  id: "d-1",
  title: "Claims Flow",
  diagram_type: "flowchart",
  dsl_source: "flowchart LR\nA[Start] --> B[End]\n",
  created_by: "alice",
  created_at: "2026-08-06T00:00:00Z",
  updated_at: "2026-08-06T00:00:00Z",
};

beforeEach(() => {
  vi.clearAllMocks();
  mockedApi.listDiagrams.mockResolvedValue({ items: ITEMS, total: 1 });
});

describe("DiagramsPage: navigation wiring (ADP-914.5)", () => {
  it("shows the diagram list by default", async () => {
    render(<DiagramsPage />);
    await screen.findByText("Claims Flow");
  });

  it("opens the editor for a new diagram and back returns to the list", async () => {
    const user = userEvent.setup();
    render(<DiagramsPage />);
    await screen.findByText("Claims Flow");

    await user.click(screen.getByText("+ New Diagram"));
    await screen.findByLabelText("Diagram title");
    // Creating a new diagram exposes the type selector (no diagramId yet).
    screen.getByLabelText("Diagram type");

    await user.click(screen.getByText("← Back to diagrams"));
    await screen.findByText("Claims Flow");
    expect(screen.queryByLabelText("Diagram title")).toBeNull();
  });

  it("opens the editor for an existing diagram via the list", async () => {
    mockedApi.getDiagram.mockResolvedValue(LOADED);
    const user = userEvent.setup();
    render(<DiagramsPage />);
    await user.click(await screen.findByText("Claims Flow"));

    await waitFor(() => expect(mockedApi.getDiagram).toHaveBeenCalledWith("d-1"));
    const titleInput = (await screen.findByLabelText("Diagram title")) as HTMLInputElement;
    await waitFor(() => expect(titleInput.value).toBe("Claims Flow"));
    // Editing an existing diagram has no type selector (immutable after creation).
    expect(screen.queryByLabelText("Diagram type")).toBeNull();
  });
});
