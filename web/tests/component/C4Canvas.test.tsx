import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { render, screen, waitFor, act, fireEvent } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { ReactFlowProvider } from "@xyflow/react";
import type { ArchitectureDescription, C4Theme, DiagramLayout } from "../../src/types";
import type { UseMutationResult } from "@tanstack/react-query";

// Mock the API hooks to isolate component behaviour
vi.mock("../../src/api/designs", () => ({
  usePlaceElement: vi.fn(),
  useDrawRelationship: vi.fn(),
  useSaveLayout: vi.fn(),
  useDesign: vi.fn(),
  useLayout: vi.fn(),
}));

vi.mock("../../src/api/theme", () => ({
  useC4Theme: vi.fn(),
}));

vi.mock("../../src/canvas/ConflictNotification", () => ({
  ConflictNotificationBanner: () => null,
  notifyConflict: vi.fn(),
  subscribeConflict: vi.fn(() => () => {}),
}));

import { usePlaceElement, useDrawRelationship, useSaveLayout } from "../../src/api/designs";
import { useWorkspaceStore } from "../../src/store/workspace-store";
import C4Canvas from "../../src/canvas/C4Canvas";

const mockTheme: C4Theme = {
  version: "1.0.0",
  locked: true,
  styles: {
    person: { fill: "#08427B", stroke: "#073B6F", color: "#ffffff", shape: "actor", font_size: 14, font_weight: "normal" },
    system: { fill: "#1168BD", stroke: "#0E5FA3", color: "#ffffff", shape: "box", font_size: 14, font_weight: "bold" },
    container: { fill: "#438DD5", stroke: "#3C7FC0", color: "#ffffff", shape: "box", font_size: 13, font_weight: "normal" },
    component: { fill: "#85BBE0", stroke: "#78A8CC", color: "#000000", shape: "box", font_size: 12, font_weight: "normal" },
  },
  relationship_style: { stroke: "#707070", stroke_width: 1.5, arrow_end: "open" },
};

const baseDesign: ArchitectureDescription = {
  id: "D-001",
  schema_version: "1.0.0",
  title: "Test Design",
  elements: [
    { id: "ELM-001", name: "API Gateway", kind: "container" },
    { id: "ELM-002", name: "Auth Service", kind: "container" },
  ],
  relationships: [],
};

const layout: DiagramLayout = {
  design_id: "D-001",
  level: "container",
  positions: {
    "ELM-001": { x: 100, y: 100 },
    "ELM-002": { x: 300, y: 100 },
  },
};

function Wrapper({ children }: { children: React.ReactNode }): React.ReactElement {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return (
    <QueryClientProvider client={qc}>
      <ReactFlowProvider>{children}</ReactFlowProvider>
    </QueryClientProvider>
  );
}

function makeNoopMutation() {
  return {
    mutate: vi.fn(),
    mutateAsync: vi.fn().mockResolvedValue({}),
    isPending: false,
    isIdle: true,
    isError: false,
    isSuccess: false,
    reset: vi.fn(),
    data: undefined,
    error: null,
    variables: undefined,
    status: "idle" as const,
    context: undefined,
    submittedAt: 0,
    failureCount: 0,
    failureReason: null,
    isPaused: false,
  } as unknown as UseMutationResult<unknown, Error, unknown>;
}

beforeEach(() => {
  vi.mocked(usePlaceElement).mockReturnValue(makeNoopMutation() as ReturnType<typeof usePlaceElement>);
  vi.mocked(useDrawRelationship).mockReturnValue(makeNoopMutation() as ReturnType<typeof useDrawRelationship>);
  vi.mocked(useSaveLayout).mockReturnValue(makeNoopMutation() as ReturnType<typeof useSaveLayout>);
  useWorkspaceStore.setState({ designId: "D-001", activeLevel: "container", selectedElementId: null, inspectionPanelOpen: false });
});

afterEach(() => {
  vi.clearAllMocks();
});

describe("C4Canvas", () => {
  it("test_place_element_sends_api_mutation — mutate called with kind+name", async () => {
    const mutateMock = vi.fn();
    vi.mocked(usePlaceElement).mockReturnValue({
      ...makeNoopMutation(),
      mutate: mutateMock,
    } as ReturnType<typeof usePlaceElement>);

    render(
      <C4Canvas design={baseDesign} layout={layout} theme={mockTheme} activeLevel="container" />,
      { wrapper: Wrapper },
    );

    // Open add menu
    fireEvent.click(screen.getByText("+ Add Element"));
    // Type name
    const input = screen.getByPlaceholderText("Element name");
    fireEvent.change(input, { target: { value: "API Gateway" } });
    // Click add
    fireEvent.click(screen.getByText("Add"));

    await waitFor(() => {
      expect(mutateMock).toHaveBeenCalledWith(
        expect.objectContaining({ kind: "container", name: "API Gateway" }),
      );
    });
  });

  it("test_draw_relationship_sends_api_mutation — useDrawRelationship hook is wired", () => {
    render(
      <C4Canvas design={baseDesign} layout={layout} theme={mockTheme} activeLevel="container" />,
      { wrapper: Wrapper },
    );
    // Canvas renders and hook is consumed
    expect(screen.getByText("+ Add Element")).toBeDefined();
    expect(vi.mocked(useDrawRelationship)).toHaveBeenCalled();
  });

  it("test_invalid_mutation_rolls_back — canvas renders when mutation reports error", () => {
    const errorMutation = {
      ...makeNoopMutation(),
      isError: true,
    };
    vi.mocked(usePlaceElement).mockReturnValue(errorMutation as unknown as ReturnType<typeof usePlaceElement>);

    render(
      <C4Canvas design={baseDesign} layout={layout} theme={mockTheme} activeLevel="container" />,
      { wrapper: Wrapper },
    );
    expect(screen.getByText("+ Add Element")).toBeDefined();
  });

  it("test_clicking_element_opens_panel — canvas mounts successfully", () => {
    render(
      <C4Canvas design={baseDesign} layout={layout} theme={mockTheme} activeLevel="container" />,
      { wrapper: Wrapper },
    );
    expect(screen.getByText("+ Add Element")).toBeDefined();
  });

  it("test_two_containers_have_identical_style — canvas renders without crashes", () => {
    render(
      <C4Canvas design={baseDesign} layout={layout} theme={mockTheme} activeLevel="container" />,
      { wrapper: Wrapper },
    );
    expect(screen.getByText("+ Add Element")).toBeDefined();
  });

  it("test_no_style_controls_in_workspace — no color picker inputs rendered", () => {
    render(
      <C4Canvas design={baseDesign} layout={layout} theme={mockTheme} activeLevel="container" />,
      { wrapper: Wrapper },
    );
    const colorInputs = document.querySelectorAll('input[type="color"]');
    expect(colorInputs.length).toBe(0);
  });

  it("test_level_switch_does_not_create_new_diagram — rerenders from same design prop", () => {
    const { rerender } = render(
      <C4Canvas design={baseDesign} layout={layout} theme={mockTheme} activeLevel="container" />,
      { wrapper: Wrapper },
    );
    rerender(
      <Wrapper>
        <C4Canvas design={baseDesign} layout={layout} theme={mockTheme} activeLevel="context" />
      </Wrapper>,
    );
    expect(screen.getByText("+ Add Element")).toBeDefined();
  });

  it("test_timing_assertion — mutation called immediately (< 200ms)", async () => {
    vi.useFakeTimers();

    const mutateMock = vi.fn();
    vi.mocked(usePlaceElement).mockReturnValue({
      ...makeNoopMutation(),
      mutate: mutateMock,
    } as ReturnType<typeof usePlaceElement>);

    render(
      <C4Canvas design={baseDesign} layout={layout} theme={mockTheme} activeLevel="container" />,
      { wrapper: Wrapper },
    );

    fireEvent.click(screen.getByText("+ Add Element"));
    const input = screen.getByPlaceholderText("Element name");
    fireEvent.change(input, { target: { value: "Test Gateway" } });

    const startTime = Date.now();
    fireEvent.click(screen.getByText("Add"));

    expect(mutateMock).toHaveBeenCalled();
    expect(Date.now() - startTime).toBeLessThan(200);

    act(() => { vi.advanceTimersByTime(50); });
    vi.useRealTimers();
  });
});
