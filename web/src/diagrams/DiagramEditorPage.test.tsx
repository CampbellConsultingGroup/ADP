import { describe, expect, it, vi, beforeEach } from "vitest";
import { render, screen, waitFor, fireEvent } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { DiagramEditorPage } from "./DiagramEditorPage";
import { useAuth } from "../auth/AuthProvider";
import type { AuthUser } from "../auth/AuthProvider";
import * as api from "./api";
import type { Diagram } from "./api";

vi.mock("./api");
vi.mock("../auth/AuthProvider", () => ({
  useAuth: vi.fn(),
}));

const mockedApi = vi.mocked(api);
const mockedUseAuth = vi.mocked(useAuth);

const SAVED: Diagram = {
  id: "diag-1",
  title: "Claims Intake",
  diagram_type: "flowchart",
  dsl_source: "flowchart LR\nA[Start] --> B[End]\n",
  created_by: "alice",
  created_at: "2026-08-06T00:00:00Z",
  updated_at: "2026-08-06T00:00:00Z",
};

function mockRole(role: string | undefined) {
  const user: AuthUser | null = role
    ? { username: "u", email: "u@example.com", role, roleLabel: role, roleColors: { bg: "", text: "" }, groups: [] }
    : null;
  mockedUseAuth.mockReturnValue({ user, isLoading: false, logout: vi.fn() });
}

beforeEach(() => {
  vi.clearAllMocks();
  // Default: no recognized role -- matches today's pre-feature behavior
  // (fallback to "flowchart", no recommendation badge) unless a test
  // explicitly calls mockRole() with an architect role (ADP-914.6).
  mockRole(undefined);
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

describe("DiagramEditorPage: persona-aware default type (ADP-914.6, User Story 1)", () => {
  it("defaults to 'architecture' for an Enterprise Architect", () => {
    mockRole("enterprise_architect");
    render(<DiagramEditorPage />);
    const select = screen.getByLabelText("Diagram type") as HTMLSelectElement;
    expect(select.value).toBe("architecture");
  });

  it("defaults to 'flowchart' for a Solution Architect", () => {
    mockRole("solution_architect");
    render(<DiagramEditorPage />);
    const select = screen.getByLabelText("Diagram type") as HTMLSelectElement;
    expect(select.value).toBe("flowchart");
  });

  it("defaults to 'sequence' for a Technical Architect", () => {
    mockRole("technical_architect");
    render(<DiagramEditorPage />);
    const select = screen.getByLabelText("Diagram type") as HTMLSelectElement;
    expect(select.value).toBe("sequence");
  });

  it("falls back to 'flowchart' when the role is unrecognized (FR-006)", () => {
    mockRole(undefined);
    render(<DiagramEditorPage />);
    const select = screen.getByLabelText("Diagram type") as HTMLSelectElement;
    expect(select.value).toBe("flowchart");
  });

  it("an explicit newDiagramType prop still wins over the persona default (FR-004)", () => {
    // Technical Architect's default would be "sequence" -- confirm the
    // explicit prop is not overridden by the persona lookup.
    mockRole("technical_architect");
    render(<DiagramEditorPage newDiagramType="uml" />);
    const select = screen.getByLabelText("Diagram type") as HTMLSelectElement;
    expect(select.value).toBe("uml");
  });
});

describe("DiagramEditorPage: 'Recommended for your role' label (ADP-914.6, User Story 2)", () => {
  it("labels only the Enterprise Architect's mapped option as recommended, leaving the other 4 unlabeled and selectable", () => {
    mockRole("enterprise_architect");
    render(<DiagramEditorPage />);
    const select = screen.getByLabelText("Diagram type") as HTMLSelectElement;
    const options = Array.from(select.options);

    expect(options).toHaveLength(5);
    const recommendedOptions = options.filter((o) => o.text.includes("(Recommended for your role)"));
    expect(recommendedOptions).toHaveLength(1);
    expect(recommendedOptions[0].value).toBe("architecture");

    // Every option remains present and selectable regardless of the label (FR-005).
    for (const type of ["flowchart", "sequence", "erd", "uml", "architecture"]) {
      expect(options.some((o) => o.value === type)).toBe(true);
    }
  });

  it("shows no recommendation label when the role is unrecognized (FR-006)", () => {
    mockRole(undefined);
    render(<DiagramEditorPage />);
    const select = screen.getByLabelText("Diagram type") as HTMLSelectElement;
    const options = Array.from(select.options);
    expect(options.some((o) => o.text.includes("(Recommended for your role)"))).toBe(false);
  });
});
