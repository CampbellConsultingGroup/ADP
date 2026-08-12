import { describe, expect, it, vi, beforeEach } from "vitest";
import { render, screen, waitFor, fireEvent } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { DiagramEditorPage } from "./DiagramEditorPage";
import { useAuth } from "../auth/AuthProvider";
import type { AuthUser } from "../auth/AuthProvider";
import type { DiagramModel } from "./core/index";
import * as api from "./api";
import type { Diagram } from "./api";

vi.mock("./api");
vi.mock("../auth/AuthProvider", () => ({
  useAuth: vi.fn(),
}));

// ADP-914.8: lightweight stubs capturing the props DiagramEditorPage passes
// down, rather than exercising the real ChatButton/ChatPanel (already
// covered by their own tests).
let lastChatPanelProps: Record<string, unknown> | null = null;
vi.mock("../chat/ChatButton", () => ({
  default: ({ onToggle }: { onToggle: () => void }) => (
    <button onClick={onToggle}>Chat</button>
  ),
}));
vi.mock("../chat/ChatPanel", () => ({
  default: (props: Record<string, unknown>) => {
    lastChatPanelProps = props;
    return <div data-testid="chat-panel" />;
  },
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
  lastChatPanelProps = null;
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

  it("shows a persistent save-state indicator that survives after the save completes (FR-003)", async () => {
    mockedApi.createDiagram.mockResolvedValue(SAVED);
    const user = userEvent.setup();

    render(<DiagramEditorPage newDiagramType="flowchart" />);

    // Nothing shown before any save has been attempted.
    expect(screen.queryByTestId("save-state-indicator")).toBeNull();

    await user.click(screen.getByText("Save"));

    // Persistent, not just the Save button's own momentary label -- still present after the
    // mutation resolves and the button itself has reverted from "Saving…" back to "Save".
    const indicator = await screen.findByTestId("save-state-indicator");
    expect(indicator.textContent).toBe("Saved");
    screen.getByText("Save");
  });

  it("shows an error save-state indicator when the save fails, distinct from the Save button", async () => {
    mockedApi.createDiagram.mockRejectedValue(new Error("network down"));
    const user = userEvent.setup();

    render(<DiagramEditorPage newDiagramType="flowchart" />);
    await user.click(screen.getByText("Save"));

    const indicator = await screen.findByTestId("save-state-indicator");
    expect(indicator.textContent).toBe("Error saving");
  });
});

describe("DiagramEditorPage: workspace layout (ADP-SPEC-052, User Story 3)", () => {
  it("renders the palette, canvas, and DSL panel simultaneously, none conditionally unmounted (FR-012)", () => {
    const { container } = render(<DiagramEditorPage newDiagramType="flowchart" />);

    expect(container.querySelector(".diagram-workspace")).toBeTruthy();
    expect(container.querySelector(".diagram-workspace__palette")).toBeTruthy();
    expect(container.querySelector(".diagram-workspace__canvas .canvas-root")).toBeTruthy();
    expect(screen.getByTestId("dsl-panel")).toBeTruthy();
  });

  it("toggles the palette-collapsed state via its disclosure control", async () => {
    const user = userEvent.setup();
    const { container } = render(<DiagramEditorPage newDiagramType="flowchart" />);

    const palette = container.querySelector(".diagram-workspace__palette") as HTMLElement;
    expect(palette.getAttribute("data-collapsed")).toBe("true");

    await user.click(screen.getByTestId("palette-toggle"));
    expect(palette.getAttribute("data-collapsed")).toBe("false");

    await user.click(screen.getByTestId("palette-toggle"));
    expect(palette.getAttribute("data-collapsed")).toBe("true");
  });

  it("shows a clear active/pressed state on the Connect tool while engaged (FR-013)", async () => {
    const user = userEvent.setup();
    render(<DiagramEditorPage newDiagramType="flowchart" />);

    const connectToggle = screen.getByTestId("connect-mode-toggle");
    expect(connectToggle.getAttribute("aria-pressed")).toBe("false");

    await user.click(connectToggle);
    expect(connectToggle.getAttribute("aria-pressed")).toBe("true");
  });

  it("communicates the canvas→DSL live-sync direction distinctly from the DSL→canvas Apply requirement (FR-014)", () => {
    render(<DiagramEditorPage newDiagramType="flowchart" />);

    screen.getByText("Synced from canvas");
    screen.getByText(/Click Apply to send changes to the canvas/);
  });
});

describe("DiagramEditorPage: theme-adaptive canvas surface (ADP-SPEC-052, User Story 2)", () => {
  it("renders the canvas root with the theme-token-driven surface class (FR-006/FR-007)", () => {
    const { container } = render(<DiagramEditorPage newDiagramType="flowchart" />);

    // .canvas-root/.canvas-svg's background comes from diagrams.css's var(--surface-2)/
    // var(--border-strong) rules (contracts/diagram-css-contract.md) -- token-driven, so it
    // resolves per-theme automatically via tokens.css's own light/dark blocks, with no
    // theme-specific class or inline color on the element itself.
    expect(container.querySelector(".canvas-root")).toBeTruthy();
    expect(container.querySelector(".canvas-svg")).toBeTruthy();
  });
});

describe("DiagramEditorPage: ADP-styled chrome (ADP-SPEC-052, User Story 1)", () => {
  it("renders the title field, type selector, and Save action with ADP's styled controls", () => {
    render(<DiagramEditorPage newDiagramType="flowchart" />);

    expect(screen.getByLabelText("Diagram title").className).toContain("ui-input");
    expect(screen.getByLabelText("Diagram type").className).toContain("ui-select");
    expect(screen.getByText("Save").className).toContain("ui-btn");
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
  it("labels only the Enterprise Architect's mapped option as recommended, leaving the other 5 unlabeled and selectable", () => {
    mockRole("enterprise_architect");
    render(<DiagramEditorPage />);
    const select = screen.getByLabelText("Diagram type") as HTMLSelectElement;
    const options = Array.from(select.options);

    // ADP-SPEC-053: "c4" joins the other 5 types (FR-001).
    expect(options).toHaveLength(6);
    const recommendedOptions = options.filter((o) => o.text.includes("(Recommended for your role)"));
    expect(recommendedOptions).toHaveLength(1);
    expect(recommendedOptions[0].value).toBe("architecture");

    // Every option remains present and selectable regardless of the label (FR-005).
    for (const type of ["flowchart", "sequence", "erd", "uml", "architecture", "c4"]) {
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

describe("DiagramEditorPage: seed prop pre-fills a new diagram (ADP-914.7)", () => {
  const SEED_MODEL: DiagramModel = {
    diagramTypeId: "flowchart",
    nodes: [
      { id: "n1", label: "Intake", shape: "rectangle", position: { x: 0, y: 0 } },
      { id: "n2", label: "Review", shape: "rectangle", position: { x: 160, y: 0 } },
    ],
    edges: [{ id: "e1", sourceId: "n1", targetId: "n2" }],
    containers: [],
  };

  it("initializes the title and model from the seed when creating a new diagram", () => {
    render(<DiagramEditorPage seed={{ title: "Quote to Bind", model: SEED_MODEL }} />);

    const titleInput = screen.getByLabelText("Diagram title") as HTMLInputElement;
    expect(titleInput.value).toBe("Quote to Bind");

    const dslPanel = screen.getByTestId("dsl-panel") as HTMLTextAreaElement;
    expect(dslPanel.value).toContain("Intake");
    expect(dslPanel.value).toContain("Review");
  });

  it("an explicit seed takes priority over the persona-aware default (ADP-914.6)", () => {
    // Technical Architect's persona default would be "sequence" -- confirm a
    // seed's own flowchart model wins instead.
    mockRole("technical_architect");
    render(<DiagramEditorPage seed={{ title: "Quote to Bind", model: SEED_MODEL }} />);

    const select = screen.getByLabelText("Diagram type") as HTMLSelectElement;
    expect(select.value).toBe("flowchart");
  });
});

describe("DiagramEditorPage: embedded AI assistant (ADP-914.8, User Story 1)", () => {
  it("passes a getDiagramContext function reflecting the current title/type/DSL", async () => {
    const user = userEvent.setup();
    render(<DiagramEditorPage newDiagramType="flowchart" />);

    await user.click(screen.getByText("Chat"));
    await screen.findByTestId("chat-panel");

    expect(lastChatPanelProps).not.toBeNull();
    const getDiagramContext = lastChatPanelProps!.getDiagramContext as () => string;
    expect(typeof getDiagramContext).toBe("function");

    const context = getDiagramContext();
    expect(context).toContain("Untitled diagram");
    expect(context).toContain("flowchart");
  });
});

describe("DiagramEditorPage: applying a proposed edit (ADP-914.8, User Story 2)", () => {
  async function openChat() {
    const user = userEvent.setup();
    render(<DiagramEditorPage newDiagramType="flowchart" />);
    await user.click(screen.getByText("Chat"));
    await screen.findByTestId("chat-panel");
    return lastChatPanelProps!;
  }

  it("applies an extracted fenced DSL block to the DSL panel", async () => {
    const props = await openChat();
    const onAssistantReply = props.onAssistantReply as (text: string) => void;

    onAssistantReply(
      "Sure, here's the updated diagram:\n```flowchart\nflowchart LR\n  A[Start] --> B[Renamed]\n```",
    );

    const dslPanel = await screen.findByTestId("dsl-panel") as HTMLTextAreaElement;
    await waitFor(() => expect(dslPanel.value).toContain("Renamed"));
  });

  it("leaves the DSL panel unchanged for a plain conversational reply with no fenced block", async () => {
    const props = await openChat();
    const onAssistantReply = props.onAssistantReply as (text: string) => void;
    const dslPanel = screen.getByTestId("dsl-panel") as HTMLTextAreaElement;
    const before = dslPanel.value;

    onAssistantReply("This diagram currently has zero nodes.");

    expect(dslPanel.value).toBe(before);
  });
});

describe("DiagramEditorPage: manual-edit lockout while streaming (ADP-914.8, User Story 2, FR-011)", () => {
  it("disables the DSL panel while onStreamingChange(true), re-enables on false", async () => {
    const user = userEvent.setup();
    render(<DiagramEditorPage newDiagramType="flowchart" />);
    await user.click(screen.getByText("Chat"));
    await screen.findByTestId("chat-panel");
    const onStreamingChange = lastChatPanelProps!.onStreamingChange as (s: boolean) => void;

    const dslPanel = screen.getByTestId("dsl-panel") as HTMLTextAreaElement;
    expect(dslPanel.disabled).toBe(false);

    onStreamingChange(true);
    await waitFor(() => expect(dslPanel.disabled).toBe(true));

    onStreamingChange(false);
    await waitFor(() => expect(dslPanel.disabled).toBe(false));
  });
});

describe("DiagramEditorPage: C4 diagram type (ADP-SPEC-053, User Story 1)", () => {
  it("seeds a new C4 diagram with a valid, empty Context-level starting point (FR-004)", () => {
    render(<DiagramEditorPage newDiagramType="c4" />);
    const dslPanel = screen.getByTestId("dsl-panel") as HTMLTextAreaElement;
    // The serialized empty c4-context model -- just the header line, no elements yet, and no
    // front-matter block (joinFrontMatter omits it when there's nothing to carry).
    expect(dslPanel.value).toBe("C4Context\n");
  });

  it("renders Person/System elements and a relationship authored via the DSL panel (FR-002/FR-003)", async () => {
    const user = userEvent.setup();
    render(<DiagramEditorPage newDiagramType="c4" />);

    const dslPanel = screen.getByTestId("dsl-panel") as HTMLTextAreaElement;
    fireEvent.change(dslPanel, {
      target: {
        value: 'C4Context\nPerson(user, "Customer")\nSystem(sys, "Payments Service")\nRel(user, sys, "Uses")\n',
      },
    });
    await user.click(screen.getByTestId("apply-dsl"));

    const personNode = await screen.findByTestId("node-user");
    const systemNode = screen.getByTestId("node-sys");
    // Label text may wrap across multiple <tspan> lines, so check concatenated textContent
    // rather than a single-node text match.
    expect(personNode.textContent).toContain("Customer");
    // Label wraps across separate <tspan> lines ("Payments" / "Service"), so textContent has no
    // space between them -- check each word rather than the exact phrase.
    expect(systemNode.textContent).toContain("Payments");
    expect(systemNode.textContent).toContain("Service");

    // The Person element renders via the canvas's existing default-shape fallback (a plain
    // <rect>) -- shapes.tsx (vendored, unchanged) has no dedicated 'person' case. This is
    // pre-existing, latent behavior this feature is the first to make reachable, not a defect
    // (svg-renderer.ts's separate export path does have a dedicated case -- see ExportAction.test.tsx).
    expect(personNode.querySelector("rect")).not.toBeNull();
    expect(systemNode.querySelector("rect")).not.toBeNull();
  });

  it("reports a line/content error for malformed C4 text, consistent with every other type (FR-007)", async () => {
    const user = userEvent.setup();
    render(<DiagramEditorPage newDiagramType="c4" />);

    const dslPanel = screen.getByTestId("dsl-panel") as HTMLTextAreaElement;
    fireEvent.change(dslPanel, {
      target: { value: 'C4Context\nPersn(oops, "Typo")\n' },
    });
    await user.click(screen.getByTestId("apply-dsl"));

    const notice = await screen.findByTestId("unsupported-element-notice");
    expect(notice.textContent).toContain("Line");
    expect(notice.textContent).toContain("2");
    expect(notice.textContent).toContain("Persn");
  });
});

describe("DiagramEditorPage: C4 diagram save/reopen (ADP-SPEC-053, User Story 2)", () => {
  const SAVED_C4: Diagram = {
    id: "diag-c4-1",
    title: "Payments Context",
    diagram_type: "c4",
    dsl_source:
      '---\ncanvas:\n  positions:\n    user:\n      x: 40\n      y: 40\n    sys:\n      x: 240\n      y: 40\n  styles: {}\n  edgeStyles: {}\n  containers: {}\n---\nC4Context\nPerson(user, "Customer")\nSystem(sys, "Payments Service")\nRel(user, sys, "Uses")\n',
    created_by: "alice",
    created_at: "2026-08-12T00:00:00Z",
    updated_at: "2026-08-12T00:00:00Z",
  };

  it("reopens a saved C4 diagram with its full content restored (FR-005, SC-003)", async () => {
    mockedApi.getDiagram.mockResolvedValue(SAVED_C4);

    render(<DiagramEditorPage diagramId="diag-c4-1" />);

    await waitFor(() => expect(mockedApi.getDiagram).toHaveBeenCalledWith("diag-c4-1"));

    const titleInput = (await screen.findByLabelText("Diagram title")) as HTMLInputElement;
    expect(titleInput.value).toBe("Payments Context");

    const dslPanel = (await screen.findByTestId("dsl-panel")) as HTMLTextAreaElement;
    await waitFor(() => expect(dslPanel.value).toContain('Person(user, "Customer")'));
    expect(dslPanel.value).toContain('System(sys, "Payments Service")');
    expect(dslPanel.value).toContain('Rel(user, sys, "Uses")');

    // Both elements render on the canvas -- not just present in the reloaded text.
    const personNode = await screen.findByTestId("node-user");
    const systemNode = screen.getByTestId("node-sys");
    expect(personNode.textContent).toContain("Customer");
    expect(systemNode.textContent).toContain("Payments");
  });
});
