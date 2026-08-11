import { describe, expect, it, vi, beforeEach } from "vitest";
import { render, screen, waitFor, fireEvent } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { DiagramEditorPage } from "./DiagramEditorPage";
import * as api from "./api";
import type { Diagram } from "./api";

vi.mock("./api");

const mockedApi = vi.mocked(api);

const SAVED: Diagram = {
  id: "diag-1",
  title: "Claims Intake",
  diagram_type: "flowchart",
  dsl_source: "flowchart LR\nA[Start] --> B[End]\n",
  created_by: "alice",
  created_at: "2026-08-06T00:00:00Z",
  updated_at: "2026-08-06T00:00:00Z",
};

beforeEach(() => {
  vi.clearAllMocks();
});

describe("DiagramEditorPage: create -> author -> save (User Story 1)", () => {
  it("saves a new diagram with the authored DSL content", async () => {
    mockedApi.createDiagram.mockResolvedValue(SAVED);
    const onSaved = vi.fn();
    const user = userEvent.setup();

    render(<DiagramEditorPage newDiagramType="flowchart" onSaved={onSaved} />);

    const dslPanel = screen.getByTestId("dsl-panel") as HTMLTextAreaElement;
    fireEvent.change(dslPanel, { target: { value: "flowchart LR\nA[Start] --> B[End]\n" } });
    await user.click(screen.getByTestId("apply-dsl"));

    await user.click(screen.getByText("Save"));

    await waitFor(() => expect(mockedApi.createDiagram).toHaveBeenCalledTimes(1));
    const call = mockedApi.createDiagram.mock.calls[0][0];
    expect(call.diagram_type).toBe("flowchart");
    expect(call.dsl_source).toContain("A[Start]");
    expect(onSaved).toHaveBeenCalledWith(SAVED);
  });
});

describe("DiagramEditorPage: reopen with content intact (User Story 1)", () => {
  it("loads an existing diagram's saved content into the editor", async () => {
    mockedApi.getDiagram.mockResolvedValue(SAVED);

    render(<DiagramEditorPage diagramId="diag-1" />);

    await waitFor(() => expect(mockedApi.getDiagram).toHaveBeenCalledWith("diag-1"));

    const titleInput = (await screen.findByLabelText("Diagram title")) as HTMLInputElement;
    expect(titleInput.value).toBe("Claims Intake");

    const dslPanel = (await screen.findByTestId("dsl-panel")) as HTMLTextAreaElement;
    await waitFor(() => expect(dslPanel.value).toContain("A[Start]"));
  });

  it("saves an edit to an existing diagram via update, not create", async () => {
    mockedApi.getDiagram.mockResolvedValue(SAVED);
    mockedApi.updateDiagram.mockResolvedValue(SAVED);
    const user = userEvent.setup();

    render(<DiagramEditorPage diagramId="diag-1" />);
    await waitFor(() => expect(mockedApi.getDiagram).toHaveBeenCalled());
    await screen.findByLabelText("Diagram title");

    await user.click(screen.getByText("Save"));

    await waitFor(() => expect(mockedApi.updateDiagram).toHaveBeenCalledTimes(1));
    expect(mockedApi.createDiagram).not.toHaveBeenCalled();
    expect(mockedApi.updateDiagram.mock.calls[0][0]).toBe("diag-1");
  });
});
