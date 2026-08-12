// ADP-SPEC-052 (research.md Decision 2): mirrors web/src/strategy/
// ThemeList.test.tsx's convention -- mocks web/src/diagrams/api.ts's hooks
// (useDiagrams/useDeleteDiagram) directly rather than wrapping in a
// QueryClientProvider, since DiagramListPage now consumes them as hooks
// instead of the raw listDiagrams()/deleteDiagram() calls this file
// previously mocked.

import { describe, expect, it, vi, beforeEach } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { DiagramListPage } from "./DiagramListPage";
import * as api from "./api";
import type { DiagramSummary } from "./api";

vi.mock("./api");

const mockedApi = vi.mocked(api);

const ITEMS: DiagramSummary[] = [
  { id: "d-1", title: "Claims Flow", diagram_type: "flowchart", updated_at: "2026-08-06T00:00:00Z" },
  { id: "d-2", title: "Order Sequence", diagram_type: "sequence", updated_at: "2026-08-06T01:00:00Z" },
  { id: "d-3", title: "Data Model", diagram_type: "erd", updated_at: "2026-08-06T02:00:00Z" },
];

function mockDiagrams(items: DiagramSummary[]) {
  mockedApi.useDiagrams.mockReturnValue({
    data: { items, total: items.length },
    isLoading: false,
    error: null,
  } as unknown as ReturnType<typeof api.useDiagrams>);
}

beforeEach(() => {
  vi.clearAllMocks();
  mockedApi.useDeleteDiagram.mockReturnValue({
    mutate: vi.fn(),
    isPending: false,
  } as unknown as ReturnType<typeof api.useDeleteDiagram>);
});

describe("DiagramListPage: browse (User Story 3)", () => {
  it("renders items across every diagram type as ADP-styled list rows", () => {
    mockDiagrams(ITEMS);

    const { container } = render(<DiagramListPage onOpen={vi.fn()} />);

    expect(container.querySelector(".ui-list")).toBeTruthy();
    expect(container.querySelectorAll(".ui-list-row")).toHaveLength(3);
    screen.getByText("Claims Flow");
    screen.getByText("Order Sequence");
    screen.getByText("Data Model");
    screen.getByText(/flowchart/);
    screen.getByText(/sequence/);
    screen.getByText(/erd/);
  });

  it("calls onOpen with the diagram id when a title is clicked", async () => {
    mockDiagrams(ITEMS);
    const onOpen = vi.fn();
    const user = userEvent.setup();

    render(<DiagramListPage onOpen={onOpen} />);
    await user.click(screen.getByText("Claims Flow"));

    expect(onOpen).toHaveBeenCalledWith("d-1");
  });

  it("calls onOpen with the diagram id when its Open action is clicked", async () => {
    mockDiagrams(ITEMS);
    const onOpen = vi.fn();
    const user = userEvent.setup();

    render(<DiagramListPage onOpen={onOpen} />);
    const openButtons = screen.getAllByText("Open");
    await user.click(openButtons[0]);

    expect(onOpen).toHaveBeenCalledWith("d-1");
  });

  it("triggers the delete mutation for the clicked row", async () => {
    mockDiagrams(ITEMS);
    const mutate = vi.fn();
    mockedApi.useDeleteDiagram.mockReturnValue({
      mutate,
      isPending: false,
    } as unknown as ReturnType<typeof api.useDeleteDiagram>);
    const user = userEvent.setup();

    render(<DiagramListPage onOpen={vi.fn()} />);
    await user.click(screen.getByLabelText("Delete Claims Flow"));

    expect(mutate).toHaveBeenCalledWith("d-1");
  });

  it("shows ADP's dashed-border empty state with no diagrams", () => {
    mockDiagrams([]);

    const { container } = render(<DiagramListPage onOpen={vi.fn()} />);

    expect(container.querySelector(".ui-empty")).toBeTruthy();
    screen.getByText("No diagrams yet");
  });

  it("shows an error alert when the list fails to load", () => {
    mockedApi.useDiagrams.mockReturnValue({
      data: undefined,
      isLoading: false,
      error: new Error("network down"),
    } as unknown as ReturnType<typeof api.useDiagrams>);

    const { container } = render(<DiagramListPage onOpen={vi.fn()} />);

    expect(container.querySelector(".ui-alert.crit")).toBeTruthy();
    screen.getByText("network down");
  });
});
